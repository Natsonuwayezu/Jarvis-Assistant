# src/jarvis/core/voice_output.py
#
# WHY THIS FILE EXISTS:
# This module gives JARVIS a voice — it converts text (JARVIS's replies)
# into spoken audio through your computer's speakers.
#
# WHY pyttsx3: it works FULLY OFFLINE. Unlike the AI chat in Phase 3
# (which needs internet to reach the AI), speaking a reply out loud
# needs no internet connection at all — pyttsx3 uses your operating
# system's own built-in speech engine (SAPI5 on Windows, NSSpeechSynthesizer
# on macOS, espeak on Linux).
#
# HOW TO USE THIS FILE FROM ELSEWHERE:
#     from jarvis.core.voice_output import VoiceOutput
#     voice = VoiceOutput()
#     voice.speak("Hello, I am online.")

import pyttsx3

from jarvis.utils.logger import get_logger

logger = get_logger(__name__)


class VoiceOutput:
    """
    Wraps pyttsx3 to speak text out loud through the computer's speakers.
    """

    def __init__(self, rate: int = 175, volume: float = 1.0):
        """
        Set up the text-to-speech engine.

        Args:
            rate: Speaking speed in words per minute. pyttsx3's default
                is around 200, which can sound rushed — 175 is a calmer,
                more natural pace for a conversational assistant.
            volume: Speech volume from 0.0 (silent) to 1.0 (full volume).
        """
        # pyttsx3.init() connects to whichever speech engine your
        # operating system provides. This can occasionally fail on a
        # machine with no audio drivers configured, so we let any error
        # here be visible in the log rather than silently swallowing it.
        self._engine = pyttsx3.init()
        self._engine.setProperty("rate", rate)
        self._engine.setProperty("volume", volume)

        logger.info("VoiceOutput initialized (rate=%d, volume=%.1f).", rate, volume)

    def speak(self, text: str) -> None:
        """
        Speak the given text out loud.

        NOTE ON BLOCKING: this call blocks (pauses) execution until the
        speech finishes playing. For Phase 4, that's the correct, simple
        behavior — JARVIS shouldn't try to listen for a new command while
        still mid-sentence. If we want JARVIS to be interruptible in a
        later phase, that would need to run this on a separate thread.

        Args:
            text: The text to speak aloud.
        """
        if not text:
            # Nothing to say — skip silently rather than making the
            # engine "speak" an empty string.
            return

        logger.debug("Speaking (%d chars): %s", len(text), text)

        self._engine.say(text)
        self._engine.runAndWait()  # Blocks here until speech playback completes.

    def save_to_file(self, text: str, filepath: str) -> None:
        """
        Render speech to an audio file instead of playing it live.

        This exists mainly as a way to TEST that the speech engine is
        producing real audio without needing speakers connected — useful
        for automated testing/verification. Not used in normal operation.

        Args:
            text: The text to convert to speech.
            filepath: Where to save the resulting audio file (e.g. .wav).
        """
        self._engine.save_to_file(text, filepath)
        self._engine.runAndWait()
        logger.debug("Saved speech audio to %s", filepath)
