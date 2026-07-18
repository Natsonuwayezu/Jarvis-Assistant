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

# __name__ here evaluates to "jarvis.main", so every log line from this
# file will show "jarvis.main" as its source — useful once there are
# many files all logging at once.
logger = get_logger(__name__)


def print_banner() -> None:
    """
    Print a simple startup banner to the terminal.

    This exists purely as visual, human-friendly confirmation that the
    app started correctly — separate from the logger, which is more for
    a technical/permanent record.
    """
    banner = f"""
    ============================================
      {APP_NAME} — Personal AI Assistant
      Version {APP_VERSION}
      Status: Phase 1 (Foundation) — Online
    ============================================
    """
    print(banner)


def main() -> None:
    """
    The main function: the single starting point for the whole app.

    Phase 1 responsibilities (and ONLY these — later phases add more):
      1. Log that startup began (for the permanent record in logs/jarvis.log)
      2. Print the banner (for the human watching the terminal)
      3. Log that startup finished successfully
    """
    logger.info("%s v%s starting up...", APP_NAME, APP_VERSION)

    print_banner()

    logger.info("Startup complete. Foundation is working correctly.")


# This check means "only run main() if this file was run directly"
# (e.g. `python src/jarvis/main.py`), NOT if this file gets imported by
# another file. This is a standard Python convention you'll see in almost
# every real project.
if __name__ == "__main__":
    main()
