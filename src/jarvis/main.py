# src/jarvis/main.py
#
# THIS IS THE ENTRY POINT OF THE ENTIRE APPLICATION.
# No matter how big JARVIS gets, you will always start it by running this
# file. It loads settings, sets up logging, creates the AI engine and
# voice/wake-word features, wires up the command-confirmation dialog
# (Phase 5), then launches the graphical window and hands control over to it.

from tkinter import messagebox

from jarvis.config.settings import APP_NAME, APP_VERSION
from jarvis.utils.logger import get_logger
from jarvis.ui.main_window import MainWindow
from jarvis.core.ai_engine import AIEngine
from jarvis.core.voice_input import VoiceInput
from jarvis.core.voice_output import VoiceOutput
from jarvis.core.wake_word import WakeWordListener

# __name__ here evaluates to "jarvis.main", so every log line from this
# file will show "jarvis.main" as its source — useful once there are
# many files all logging at once.
logger = get_logger(__name__)


def print_banner() -> None:
    """
    Print a simple startup banner to the terminal.

    Even though we now have a graphical window, real AI reasoning, and
    voice features, we keep this terminal banner too — it's useful
    confirmation in the console/log that the app is booting.
    """
    banner = f"""
    ============================================
      {APP_NAME} — Personal AI Assistant
      Version {APP_VERSION}
      Status: Phase 6 (Persistent Memory) — Online
    ============================================
    """
    print(banner)


def _init_voice_input() -> "VoiceInput | None":
    """
    Try to set up microphone access. Returns None (instead of raising)
    if no microphone is available, so the app can still run in
    text-only mode rather than crashing on machines without a mic.
    """
    try:
        voice_input = VoiceInput()
        # Sample the room's background noise once at startup so the
        # microphone's sensitivity is calibrated correctly from the
        # very first use, rather than using a generic guessed default.
        voice_input.calibrate_for_ambient_noise()
        return voice_input
    except OSError as error:
        # sr.Microphone() raises OSError when no input device is found.
        logger.warning("Voice input unavailable (no microphone found?): %s", error)
        return None


def _init_voice_output() -> "VoiceOutput | None":
    """
    Try to set up text-to-speech. Returns None (instead of raising) if
    the system's speech engine can't be reached, so the app can still
    run in text-only mode.
    """
    try:
        return VoiceOutput()
    except Exception as error:  # pyttsx3 can raise various backend-specific errors
        logger.warning("Voice output unavailable: %s", error)
        return None


def main() -> None:
    """
    The main function: the single starting point for the whole app.

    Phase 5 responsibilities (building on Phases 1-4):
      1. Log startup, print the banner
      2. Define confirm_command — a real Yes/No dialog box — and pass
         it into the AIEngine so terminal commands can only ever run
         after genuine, real-time user approval
      3. Set up voice input/output (unchanged from Phase 4)
      4. Wire up wake-word support (unchanged from Phase 4)
      5. Launch the window, hand control to its event loop, and clean
         up the wake-word thread on exit
    """
    logger.info("%s v%s starting up...", APP_NAME, APP_VERSION)

    print_banner()

    def confirm_command(command: str) -> bool:
        """
        Shows a real, blocking Yes/No dialog box asking the user to
        approve a specific terminal command before it's allowed to run.

        THIS IS THE ENTIRE SAFETY GATE for JARVIS's most dangerous
        capability (see core/automation/command_executor.py and
        core/tools.py) — it is the ONLY place in the whole project
        that decides a command is allowed to actually execute.

        THREADING NOTE: this function is only ever called from deep
        inside ai_engine.get_response(), which itself is only ever
        called from MainWindow's _process_message — and that method
        only ever runs on the MAIN thread (see the threading notes in
        main_window.py). So it's always safe to show a Tkinter dialog
        here directly, without needing the queue-based pattern used
        for background threads elsewhere in this project.

        `window` is referenced here even though it's defined further
        down in this same function — that's fine in Python, since this
        function only actually RUNS later, once window already exists
        (the same pattern used for on_wake below).
        """
        return messagebox.askyesno(
            title="JARVIS wants to run a command",
            message=(
                "JARVIS wants to run this command on your computer:\n\n"
                f"    {command}\n\n"
                "Allow it?"
            ),
            parent=window,
        )

    # Creating the AIEngine can raise RuntimeError if no valid API key is
    # configured (see ai_engine.py). We catch that here specifically so
    # the person running the app gets a clear, friendly terminal message
    # instead of a raw Python traceback.
    try:
        ai_engine = AIEngine(confirm_command=confirm_command)
    except RuntimeError as error:
        logger.error("Failed to start AI engine: %s", error)
        print(f"\n  ERROR: {error}\n")
        return

    voice_input = _init_voice_input()
    voice_output = _init_voice_output()

    # A single mutable container (dict) to hold the currently-running
    # WakeWordListener, if any. Using a dict (rather than a plain
    # variable) lets the nested functions below modify it — a plain
    # local variable can't be reassigned from within a nested function
    # without extra syntax, but mutating a dict's contents works fine.
    wake_word_state = {"listener": None}

    def on_wake() -> None:
        """
        Called (from the wake-word listener's OWN background thread)
        whenever "Jarvis" is heard. Triggers the same mic-capture flow
        as clicking the mic button — trigger_mic_listen() is safe to
        call from any thread.
        """
        logger.info("Wake word triggered — starting mic capture.")
        window.trigger_mic_listen()

    def on_toggle_wake_word(enabled: bool) -> None:
        """
        Called when the user flips the 'Wake word' switch in the GUI.
        Starts or stops the background WakeWordListener accordingly.
        """
        if enabled:
            if voice_input is None:
                logger.warning("Cannot enable wake word: no microphone available.")
                return
            listener = WakeWordListener(on_wake=on_wake, voice_input=voice_input)
            listener.start()
            wake_word_state["listener"] = listener
        else:
            listener = wake_word_state["listener"]
            if listener is not None:
                listener.stop()
                wake_word_state["listener"] = None

    logger.info("Launching graphical interface...")

    # Voice features degrade gracefully: if voice_input/voice_output are
    # None (unavailable), we pass None for the matching callback, and
    # MainWindow hides that specific control (mic button / speak toggle
    # / wake-word toggle) rather than showing something broken.
    window = MainWindow(
        on_user_message=ai_engine.get_response,
        on_voice_capture=voice_input.listen_once if voice_input else None,
        on_speak=voice_output.speak if voice_output else None,
        on_toggle_wake_word=on_toggle_wake_word if voice_input else None,
    )

    # mainloop() is Tkinter's event loop — it listens for clicks, key
    # presses, and window events, and keeps the window alive and
    # responsive. Execution stays inside this call until the window
    # is closed, at which point the function returns and the app exits.
    window.mainloop()

    # Clean up the background wake-word thread (if it was left running)
    # so the process can exit fully instead of hanging on a stray thread.
    listener = wake_word_state["listener"]
    if listener is not None:
        listener.stop()

    # PHASE 6: close the persistent memory database cleanly so it isn't
    # left in a partially-flushed state between runs.
    ai_engine.close()

    logger.info("JARVIS window closed. Shutting down.")


# This check means "only run main() if this file was run directly"
# (e.g. `python src/jarvis/main.py`), NOT if this file gets imported by
# another file. This is a standard Python convention you'll see in almost
# every real project.
if __name__ == "__main__":
    main()
