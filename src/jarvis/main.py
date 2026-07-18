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
from jarvis.core.ai_engine import AIEngine

# __name__ here evaluates to "jarvis.main", so every log line from this
# file will show "jarvis.main" as its source — useful once there are
# many files all logging at once.
logger = get_logger(__name__)


def print_banner() -> None:
    """
    Print a simple startup banner to the terminal.

    Even though we now have a graphical window (Phase 2) and real AI
    reasoning (Phase 3), we keep this terminal banner too — it's useful
    confirmation in the console/log that the app is booting, especially
    once we add background behavior like wake-word listening later.
    """
    banner = f"""
    ============================================
      {APP_NAME} — Personal AI Assistant
      Version {APP_VERSION}
      Status: Phase 3 (AI Chat) — Online
    ============================================
    """
    print(banner)


def main() -> None:
    """
    The main function: the single starting point for the whole app.

    Phase 3 responsibilities (building on Phases 1 and 2):
      1. Log that startup began
      2. Print the terminal banner
      3. Create the real AI engine (this is where a missing/invalid API
         key would be caught — see the try/except below)
      4. Create the graphical window, wiring it to the AI engine's
         get_response method instead of the old echo placeholder
      5. Hand control over to the window's event loop
    """
    logger.info("%s v%s starting up...", APP_NAME, APP_VERSION)

    print_banner()

    # Creating the AIEngine can raise RuntimeError if no valid API key is
    # configured (see ai_engine.py). We catch that here specifically so
    # the person running the app gets a clear, friendly terminal message
    # instead of a raw Python traceback.
    try:
        ai_engine = AIEngine()
    except RuntimeError as error:
        logger.error("Failed to start AI engine: %s", error)
        print(f"\n  ERROR: {error}\n")
        return

    logger.info("Launching graphical interface...")
    # ai_engine.get_response is passed directly as the callback — this
    # is the "swap" mentioned in ai_engine.py: the window's code is
    # completely unchanged from Phase 2, it just now points at real AI
    # reasoning instead of an echo function.
    window = MainWindow(on_user_message=ai_engine.get_response)

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
