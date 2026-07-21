# src/jarvis/main.py
#
# THIS IS THE ENTRY POINT OF THE ENTIRE APPLICATION.
# No matter how big JARVIS gets, you will always start it by running this
# file. It loads settings, sets up logging, creates a shared memory store,
# the AI engine, voice/wake-word features, and the proactive routine
# scheduler, wires up the command-confirmation dialog, then launches the
# graphical window and hands control over to it.

from tkinter import messagebox

from jarvis.config.settings import APP_NAME, APP_VERSION
from jarvis.utils.logger import get_logger
from jarvis.ui.main_window import MainWindow
from jarvis.core.ai_engine import AIEngine
from jarvis.core.memory_store import MemoryStore
from jarvis.core.routine_scheduler import RoutineScheduler
from jarvis.core.user_settings import UserSettings
from jarvis.core.voice_input import VoiceInput
from jarvis.core.voice_output import VoiceOutput
from jarvis.core.wake_word import WakeWordListener
from jarvis.ui.settings_window import SettingsWindow

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
      Status: All 8 phases + proactive routines — Online
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


def _init_voice_output(user_settings: UserSettings) -> "VoiceOutput | None":
    """
    Try to set up text-to-speech, using the user's saved voice
    speed/volume preferences (see core/user_settings.py). Returns None
    (instead of raising) if the system's speech engine can't be
    reached, so the app can still run in text-only mode.
    """
    try:
        return VoiceOutput(
            rate=user_settings.get("voice_rate"), volume=user_settings.get("voice_volume")
        )
    except Exception as error:  # pyttsx3 can raise various backend-specific errors
        logger.warning("Voice output unavailable: %s", error)
        return None


def main() -> None:
    """
    The main function: the single starting point for the whole app.

    Responsibilities:
      1. Log startup, print the banner
      2. Create ONE shared MemoryStore — used by both the AI engine
         (conversation history) and the routine scheduler (proactive
         reminders), since both need to read/write the same database
      3. Load UserSettings (personality/voice preferences) and use them
         for the AI engine's initial personality and voice output's
         initial speed/volume
      4. Define confirm_command and confirm_action — real Yes/No dialog
         boxes — and pass them into the AIEngine so terminal commands
         and other risky actions can only ever run after genuine,
         real-time user approval
      5. Set up voice input/output
      6. Wire up wake-word support
      7. Wire up the proactive routine scheduler
      8. Wire up the Settings window, including applying changes live
         to the already-running AI engine and voice output
      9. Launch the window, hand control to its event loop, and clean
         up all background threads + the shared memory store on exit
    """
    logger.info("%s v%s starting up...", APP_NAME, APP_VERSION)

    print_banner()

    # Created once, here, and shared: AIEngine uses it for conversation
    # history and the recall_memory tool; RoutineScheduler uses it for
    # proactive reminders. See memory_store.py's threading note — every
    # method on this object is safe to call from either the main thread
    # or the scheduler's background thread.
    shared_memory = MemoryStore()

    # Loads any saved personality/voice preferences from data/user_settings.json
    # (or built-in defaults, on first run). See core/user_settings.py.
    user_settings = UserSettings()

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
        (the same pattern used for on_wake and on_routine_due below).
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

    def confirm_action(description: str) -> bool:
        """
        Shows a real, blocking Yes/No dialog box asking the user to
        approve some other real, external, hard-to-undo action —
        currently just creating a GitHub issue (see core/tools.py and
        core/automation/github_client.py). Same safety role as
        confirm_command above, just for a different category of
        risky-but-not-a-shell-command action.
        """
        return messagebox.askyesno(
            title="JARVIS wants to take an action",
            message=f"JARVIS wants to:\n\n    {description}\n\nAllow it?",
            parent=window,
        )

    # Creating the AIEngine can raise RuntimeError if no valid API key is
    # configured (see ai_engine.py). We catch that here specifically so
    # the person running the app gets a clear, friendly terminal message
    # instead of a raw Python traceback.
    try:
        ai_engine = AIEngine(
            confirm_command=confirm_command,
            memory_store=shared_memory,
            confirm_action=confirm_action,
            system_prompt=user_settings.get("personality"),
        )
    except RuntimeError as error:
        logger.error("Failed to start AI engine: %s", error)
        print(f"\n  ERROR: {error}\n")
        shared_memory.close()
        return

    voice_input = _init_voice_input()
    voice_output = _init_voice_output(user_settings)

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

    def on_routine_due(description: str) -> None:
        """
        Called (from the routine scheduler's OWN background thread)
        whenever a scheduled reminder becomes due. Just forwards it to
        the window — notify_routine() is safe to call from any thread,
        following the exact same pattern as trigger_mic_listen above.
        """
        logger.info("Routine due — notifying window: %s", description)
        window.notify_routine(description)

    def apply_settings() -> None:
        """
        Called after the user saves (or resets) settings in the
        Settings window. Pushes the new values into the ALREADY
        RUNNING AIEngine and VoiceOutput — this is what makes changes
        take effect immediately, instead of only on next restart.
        """
        ai_engine.set_system_prompt(user_settings.get("personality"))
        if voice_output is not None:
            voice_output.set_rate(user_settings.get("voice_rate"))
            voice_output.set_volume(user_settings.get("voice_volume"))
        logger.info("Settings applied to the running app.")

    def on_open_settings() -> None:
        """
        Called when the user clicks the "⚙ Settings" button. Opens the
        Settings window, wiring it to the shared UserSettings instance
        and the apply_settings() function above.
        """
        SettingsWindow(user_settings=user_settings, on_applied=apply_settings)

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
        on_open_settings=on_open_settings,
    )

    # The routine scheduler runs independently of voice/wake-word
    # features — reminders are text (and optionally spoken), not tied
    # to any particular input method, so it's always started.
    routine_scheduler = RoutineScheduler(memory_store=shared_memory, on_routine_due=on_routine_due)
    routine_scheduler.start()

    # mainloop() is Tkinter's event loop — it listens for clicks, key
    # presses, and window events, and keeps the window alive and
    # responsive. Execution stays inside this call until the window
    # is closed, at which point the function returns and the app exits.
    window.mainloop()

    # Clean up every background thread and the shared memory store so
    # the process can exit fully instead of hanging on stray threads or
    # leaving the database in a partially-flushed state.
    routine_scheduler.stop()

    listener = wake_word_state["listener"]
    if listener is not None:
        listener.stop()

    ai_engine.close()  # No-op here since memory_store was injected — see ai_engine.py
    shared_memory.close()  # main.py owns the shared instance, so it closes it

    logger.info("JARVIS window closed. Shutting down.")


# This check means "only run main() if this file was run directly"
# (e.g. `python src/jarvis/main.py`), NOT if this file gets imported by
# another file. This is a standard Python convention you'll see in almost
# every real project.
if __name__ == "__main__":
    main()
