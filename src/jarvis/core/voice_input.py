# src/jarvis/core/voice_input.py
#
# WHY THIS FILE EXISTS:
# This module gives JARVIS ears — it captures audio from your microphone
# and converts your speech into text, which then gets handed to the AI
# engine (core/ai_engine.py) exactly the same way typed text is.
#
# WHY SpeechRecognition + Google's free recognizer: it requires NO API
# key to get started, which keeps Phase 4 simple. The trade-off (stated
# plainly, not hidden): recognize_google() sends audio to Google's
# servers over the internet, so this specific piece is NOT offline,
# unlike voice_output.py. An offline alternative (e.g. the Vosk engine)
# can be swapped in later using the same class interface below, without
# changing any other file — this class is the ONLY place that would
# need to change.
#
# HOW TO USE THIS FILE FROM ELSEWHERE:
#     from jarvis.core.voice_input import VoiceInput
#     listener = VoiceInput()
#     text = listener.listen_once()   # blocks until you finish speaking

import speech_recognition as sr

from jarvis.utils.logger import get_logger

logger = get_logger(__name__)


class VoiceInput:
    """
    Captures audio from the default microphone and transcribes it to text.
    """

    def __init__(self, energy_threshold: int = 300, pause_threshold: float = 0.8):
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
        """
        self._recognizer = sr.Recognizer()
        self._recognizer.energy_threshold = energy_threshold
        self._recognizer.pause_threshold = pause_threshold

        # sr.Microphone() opens a connection to the system's default
        # input device. On a machine with no microphone at all, this
        # raises an OSError — we let that surface clearly rather than
        # hiding it, since voice features simply cannot work without one.
        self._microphone = sr.Microphone()

        logger.info("VoiceInput initialized using default microphone.")

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

        try:
            # recognize_google() sends the captured audio to Google's
            # free speech-to-text service and returns the transcribed
            # text. This step requires an internet connection.
            text = self._recognizer.recognize_google(audio)
            logger.info("Transcribed speech: %s", text)
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
