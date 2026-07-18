# src/jarvis/main.py
#
# THIS IS THE ENTRY POINT OF THE ENTIRE APPLICATION.
# No matter how big JARVIS gets, you will always start it by running this
# file. Right now (Phase 1) it just proves the project skeleton works:
# it loads settings, sets up logging, and prints a startup banner.
#
# In later phases, this file will grow to launch the graphical window
# (Phase 2), start the AI conversation loop (Phase 3), and begin listening
# for the wake word (Phase 4) — but the file itself stays small; it will
# mostly just call functions defined in core/, ui/, etc.

from jarvis.config.settings import APP_NAME, APP_VERSION
from jarvis.utils.logger import get_logger
from jarvis.ui.main_window import MainWindow

# __name__ here evaluates to "jarvis.main", so every log line from this
# file will show "jarvis.main" as its source — useful once there are
# many files all logging at once.
logger = get_logger(__name__)


def print_banner() -> None:
    """
    Print a simple startup banner to the terminal.

    Even though we now have a graphical window (Phase 2), we keep this
    terminal banner too — it's useful confirmation in the console/log
    that the app is booting, especially once we add background behavior
    like wake-word listening in later phases where the terminal is still
    the place you'll watch for status/errors.
    """
    banner = f"""
    ============================================
      {APP_NAME} — Personal AI Assistant
      Version {APP_VERSION}
      Status: Phase 2 (Graphical Interface) — Online
    ============================================
    """
    print(banner)


def handle_message(message: str) -> str:
    """
    Temporary Phase 2 "brain" — just echoes the user's message back.

    WHY THIS EXISTS: Phase 2 is only about proving the GUI works
    end-to-end (typing, sending, displaying replies). We deliberately do
    NOT add real AI reasoning yet — that's Phase 3. This function is a
    stand-in that will be REPLACED (not extended) when we build the real
    AI reasoning engine in core/. The MainWindow doesn't know or care
    that this is a placeholder — that's the point of the callback design.

    Args:
        message: The raw text the user typed.

    Returns:
        JARVIS's reply as plain text.
    """
    logger.debug("Echo handler processing message: %s", message)
    return f'You said: "{message}" (real AI reasoning arrives in Phase 3)'


def main() -> None:
    """
    The main function: the single starting point for the whole app.

    Phase 2 responsibilities (building on Phase 1):
      1. Log that startup began
      2. Print the terminal banner
      3. Create the graphical window, wiring it to our placeholder
         message handler
      4. Hand control over to the window's event loop (mainloop) —
         this call blocks and keeps the window open/responsive until
         the user closes it
    """
    logger.info("%s v%s starting up...", APP_NAME, APP_VERSION)

    print_banner()

    logger.info("Launching graphical interface...")
    window = MainWindow(on_user_message=handle_message)

    # mainloop() is Tkinter's event loop — it listens for clicks, key
    # presses, and window events, and keeps the window alive and
    # responsive. Execution stays inside this call until the window
    # is closed, at which point the function returns and the app exits.
    window.mainloop()

    logger.info("JARVIS window closed. Shutting down.")


# This check means "only run main() if this file was run directly"
# (e.g. `python src/jarvis/main.py`), NOT if this file gets imported by
# another file. This is a standard Python convention you'll see in almost
# every real project.
if __name__ == "__main__":
    main()
