# src/jarvis/core/wake_word.py
#
# WHY THIS FILE EXISTS:
# This module lets JARVIS listen passively in the background for its
# own name. When it hears "Jarvis," it triggers a callback so the rest
# of the app can react (e.g. open the window, start actively listening
# for a command, play a sound, etc).
#
# HOW THIS WORKS (read this before editing):
# There is no dedicated wake-word engine here (see the Phase 4 design
# notes for why — real wake-word engines like Picovoice Porcupine need
# a separate account/API key). Instead, this repeatedly captures short
# chunks of audio via VoiceInput and checks whether the transcribed text
# contains "jarvis." This is simpler to set up but less efficient and
# slightly slower to react than a dedicated wake-word engine — a
# reasonable trade-off for this phase, and swappable later.
#
# THREADING NOTE (important if you're new to this):
# Listening for audio blocks (pauses) whatever code calls it. If we did
# that on the SAME thread as the GUI, the whole window would freeze
# while waiting for you to say "Jarvis." So this class runs the
# listening loop on a SEPARATE background thread, leaving the GUI free
# to stay responsive the whole time.

import threading
from typing import Callable, Optional

from jarvis.core.voice_input import VoiceInput
from jarvis.utils.logger import get_logger

logger = get_logger(__name__)


class WakeWordListener:
    """
    Runs a background thread that listens for the wake word and calls
    a callback function when it's detected.
    """

    def __init__(
        self,
        on_wake: Callable[[], None],
        voice_input: Optional[VoiceInput] = None,
        wake_word: str = "jarvis",
    ):
        """
        Args:
            on_wake: A function with no arguments, called every time the
                wake word is detected. Kept intentionally simple (no
                arguments) — what happens after waking up (e.g. actively
                listening for a command) is decided by whoever provides
                this callback, not by this class.
            voice_input: An existing VoiceInput instance to reuse (saves
                re-initializing the microphone). If not given, a new one
                is created.
            wake_word: The word/phrase to listen for. Lowercased at
                comparison time, so case doesn't matter.
        """
        self._on_wake = on_wake
        self._voice_input = voice_input or VoiceInput()
        self._wake_word = wake_word.lower()

        # threading.Event is a simple thread-safe on/off flag. The
        # background loop checks this every cycle and stops cleanly when
        # it's set, rather than being forcibly killed mid-operation.
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """
        Start listening for the wake word on a background thread.
        Safe to call once; calling it again while already running has
        no effect (logged as a warning) rather than starting a duplicate
        listener.
        """
        if self._thread is not None and self._thread.is_alive():
            logger.warning("WakeWordListener.start() called but already running.")
            return

        self._stop_event.clear()

        # daemon=True means this background thread will not prevent the
        # whole application from exiting — if the user closes the main
        # window, we don't want this thread to keep the process alive.
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

        logger.info("Wake word listener started (listening for '%s').", self._wake_word)

    def stop(self) -> None:
        """
        Signal the background thread to stop after its current listening
        cycle finishes, and wait briefly for it to actually exit.
        """
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        logger.info("Wake word listener stopped.")

    def _listen_loop(self) -> None:
        """
        The actual background loop: repeatedly listen for short phrases
        and check each one for the wake word. Runs until stop() is called.
        """
        while not self._stop_event.is_set():
            # A short phrase_time_limit keeps each listening cycle brief,
            # so the loop checks self._stop_event frequently and can
            # exit promptly when asked to stop, rather than being stuck
            # inside one long listen() call.
            text = self._voice_input.listen_once(timeout=3.0, phrase_time_limit=4.0)

            if text and self._wake_word in text.lower():
                logger.info("Wake word detected in: '%s'", text)
                self._on_wake()
