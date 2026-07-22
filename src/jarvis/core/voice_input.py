# src/jarvis/core/voice_input.py
#
# WHY THIS FILE EXISTS:
# This module gives JARVIS ears — it captures audio from your microphone
# and converts your speech into text, which then gets handed to the AI
# engine (core/ai_engine.py) exactly the same way typed text is.
#
# TWO RECOGNITION BACKENDS:
#   1. ONLINE (default) — SpeechRecognition's recognize_google(). No
#      setup needed, no API key, but sends audio to Google's servers,
#      so it needs internet and isn't private.
#   2. OFFLINE — Vosk, a local speech recognition engine. Fully
#      offline: audio never leaves your computer. Trade-off, stated
#      plainly: requires downloading a ~40MB model file once (see
#      README's "Offline speech recognition setup" section), and is
#      somewhat less accurate than Google's cloud model, especially
#      with background noise or unusual phrasing.
#
# WHICH ONE IS USED is controlled by the "offline_speech_recognition"
# setting (see core/user_settings.py and the in-app Settings window) —
# decided once, at startup, since loading the offline model takes a
# moment and isn't something to redo on every message.
#
# HOW TO USE THIS FILE FROM ELSEWHERE:
#     from jarvis.core.voice_input import VoiceInput
#     listener = VoiceInput()                    # online (default)
#     listener = VoiceInput(use_offline=True)     # offline (Vosk)
#     text = listener.listen_once()   # blocks until you finish speaking

import json

import speech_recognition as sr

from jarvis.utils.logger import get_logger

logger = get_logger(__name__)

# Vosk expects 16kHz, 16-bit mono audio — this is a Kaldi (the speech
# engine Vosk is built on) convention, not something we get to choose.
_VOSK_SAMPLE_RATE = 16000


class VoiceInputError(Exception):
    """Raised when voice input can't be set up (e.g. offline model missing)."""


class VoiceInput:
    """
    Captures audio from the default microphone and transcribes it to
    text, using either an online (Google) or offline (Vosk) backend.
    """

    def __init__(
        self,
        energy_threshold: int = 300,
        pause_threshold: float = 0.8,
        use_offline: bool = False,
        vosk_model_path: str = None,
    ):
        """
        Set up the microphone and recognizer.

        Args:
            energy_threshold: How loud a sound must be to count as
                "speech" rather than background noise. SpeechRecognition
                can auto-calibrate this (see calibrate_for_ambient_noise
                below), so this is just a starting default.
            pause_threshold: How many seconds of silence signal "the
                person has finished speaking." Lower = more responsive
                but might cut off slower speakers; higher = more patient
                but slower to react.
            use_offline: If True, use the local Vosk engine instead of
                Google's online recognizer. Requires a downloaded model
                (see vosk_model_path).
            vosk_model_path: Folder containing the unzipped Vosk model.
                Only used when use_offline=True. Defaults to
                VOSK_MODEL_PATH from config/settings.py.

        Raises:
            VoiceInputError: if use_offline=True but the model folder
                doesn't exist or fails to load — with a clear message
                pointing to setup instructions, rather than a cryptic
                error from deep inside the vosk library.
        """
        self._recognizer = sr.Recognizer()
        self._recognizer.energy_threshold = energy_threshold
        self._recognizer.pause_threshold = pause_threshold

        # sr.Microphone() opens a connection to the system's default
        # input device. On a machine with no microphone at all, this
        # raises an OSError — we let that surface clearly rather than
        # hiding it, since voice features simply cannot work without one.
        self._microphone = sr.Microphone()

        self._use_offline = use_offline
        self._vosk_model = None

        if use_offline:
            self._vosk_model = self._load_vosk_model(vosk_model_path)

        logger.info(
            "VoiceInput initialized using default microphone (%s recognition).",
            "offline/Vosk" if use_offline else "online/Google",
        )

    def _load_vosk_model(self, model_path: str):
        """
        Load the Vosk model once at startup (loading it is the
        expensive part — recognizing individual phrases afterward is
        fast). Importing vosk here, rather than at the top of the file,
        means the (optional) vosk package is only required if someone
        actually turns offline mode on — online mode works even if
        vosk isn't installed at all.
        """
        from jarvis.config.settings import VOSK_MODEL_PATH

        path = model_path or VOSK_MODEL_PATH

        try:
            import vosk
        except ImportError:
            raise VoiceInputError(
                "Offline speech recognition needs the 'vosk' package. "
                "Install it with: pip install vosk"
            )

        from pathlib import Path

        if not Path(path).exists():
            raise VoiceInputError(
                f"Offline speech recognition model not found at '{path}'. "
                "See the README's 'Offline speech recognition setup' section "
                "for how to download and place it."
            )

        vosk.SetLogLevel(-1)  # Silence Vosk's own verbose console logging.

        try:
            model = vosk.Model(str(path))
        except Exception as error:
            # Vosk's own model-loading errors aren't a specific
            # exception subclass, so we catch broadly here and wrap it
            # in our own clear error rather than leaking a raw,
            # possibly-cryptic library error.
            raise VoiceInputError(f"Failed to load the offline speech model: {error}")

        logger.info("Offline speech model loaded from %s", path)
        return model

    def calibrate_for_ambient_noise(self, duration: float = 1.0) -> None:
        """
        Listen briefly to the room's background noise level and adjust
        the energy threshold automatically. Call this once, e.g. right
        after startup, in a quiet moment, before the user starts talking.

        Args:
            duration: How many seconds to sample ambient noise for.
        """
        with self._microphone as source:
            logger.debug("Calibrating for ambient noise (%.1fs)...", duration)
            self._recognizer.adjust_for_ambient_noise(source, duration=duration)
        logger.info(
            "Calibration complete. Energy threshold set to %.0f.",
            self._recognizer.energy_threshold,
        )

    def listen_once(self, timeout: float = None, phrase_time_limit: float = 15.0) -> str:
        """
        Listen for a single spoken phrase and transcribe it to text.

        This call BLOCKS (pauses your program) until the person starts
        speaking and then stops (detected by a pause), or until the
        timeout is reached.

        Args:
            timeout: Max seconds to wait for speech to START. None means
                wait indefinitely. Useful to avoid hanging forever if
                nobody says anything.
            phrase_time_limit: Max seconds a single phrase is allowed to
                run for once speech has started, so one long ramble
                doesn't block the app forever.

        Returns:
            The transcribed text, as a plain string. Returns an empty
            string ("") if nothing could be understood — callers should
            treat that as "no valid command," not as an error.
        """
        with self._microphone as source:
            logger.debug("Listening for speech...")
            try:
                audio = self._recognizer.listen(
                    source, timeout=timeout, phrase_time_limit=phrase_time_limit
                )
            except sr.WaitTimeoutError:
                # Nobody spoke within the timeout window — not an error,
                # just "no input this time."
                logger.debug("Listening timed out with no speech detected.")
                return ""

        if self._use_offline:
            return self._recognize_offline(audio)
        return self._recognize_online(audio)

    def _recognize_online(self, audio: "sr.AudioData") -> str:
        """
        Transcribe using Google's free online recognizer. Requires
        internet — see the module-level docstring for the trade-off.
        """
        try:
            text = self._recognizer.recognize_google(audio)
            logger.info("Transcribed speech (online): %s", text)
            return text

        except sr.UnknownValueError:
            # Audio was captured but no speech could be understood in it
            # (e.g. mumbling, noise, silence that slipped past the
            # threshold). Not a crash-worthy error — just no result.
            logger.debug("Speech was not understood.")
            return ""

        except sr.RequestError as error:
            # The Google speech API itself was unreachable (no internet,
            # or the service is down). Distinct from "didn't understand,"
            # so we log it as an actual error for easier troubleshooting.
            logger.error("Speech recognition service error: %s", error)
            return ""

    def _recognize_offline(self, audio: "sr.AudioData") -> str:
        """
        Transcribe using the local Vosk model. No network call happens
        anywhere in this method — genuinely offline.
        """
        import vosk

        # Vosk needs 16kHz, 16-bit mono PCM specifically — get_raw_data
        # handles resampling/reformatting the captured audio to match,
        # regardless of the microphone's native format.
        raw_audio = audio.get_raw_data(convert_rate=_VOSK_SAMPLE_RATE, convert_width=2)

        # A fresh KaldiRecognizer per phrase (cheap to create) avoids
        # any state leaking between separate, unrelated utterances —
        # the loaded Model (the expensive part) is reused every time.
        recognizer = vosk.KaldiRecognizer(self._vosk_model, _VOSK_SAMPLE_RATE)
        recognizer.AcceptWaveform(raw_audio)

        result = json.loads(recognizer.FinalResult())
        text = result.get("text", "").strip()

        if text:
            logger.info("Transcribed speech (offline): %s", text)
        else:
            logger.debug("Offline recognition found no understandable speech.")

        return text
