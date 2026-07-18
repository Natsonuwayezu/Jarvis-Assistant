# src/jarvis/utils/logger.py
#
# WHY THIS FILE EXISTS:
# As JARVIS grows (voice, automation, terminal commands), you will need a
# record of exactly what happened and when — especially if something goes
# wrong while running unattended (e.g. listening for a wake word in the
# background). print() statements disappear once the terminal closes.
# A LOGGER writes timestamped messages to both the screen and a log file,
# so you always have a history to look back at.
#
# HOW TO USE THIS FILE FROM ANYWHERE ELSE IN THE PROJECT:
#     from jarvis.utils.logger import get_logger
#     logger = get_logger(__name__)
#     logger.info("Something happened")
#     logger.error("Something went wrong")

import logging
import os
from pathlib import Path

# Figure out where this file lives, then walk up to the project root.
# __file__ = .../Jarvis-Assistant/src/jarvis/utils/logger.py
# .parents[3] = .../Jarvis-Assistant  (three folders up from this file)
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# All logs go into a top-level "logs" folder, kept separate from source code
# so it's easy to .gitignore (log files should never be committed to git;
# they are machine-specific and can grow large).
LOGS_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOGS_DIR / "jarvis.log"


def get_logger(name: str) -> logging.Logger:
    """
    Create (or reuse) a logger for a given module.

    Args:
        name: Usually you pass __name__ here, which Python automatically
              fills in with the calling file's module path (e.g.
              "jarvis.main"). This makes every log line show exactly
              which file it came from.

    Returns:
        A configured logging.Logger instance that writes to both the
        console (what you see when you run the app) and a log file
        (a permanent record on disk).
    """
    # Make sure the logs folder exists before we try to write into it.
    # exist_ok=True means "don't error if it's already there."
    os.makedirs(LOGS_DIR, exist_ok=True)

    logger = logging.getLogger(name)

    # Without this check, importing this function multiple times (which
    # happens naturally as the app grows) would attach duplicate handlers,
    # causing every log line to be printed multiple times.
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)  # Capture everything; handlers below filter it.

    # Format: timestamp | log level | module name | the actual message
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler: shows INFO and above (skips noisy DEBUG messages)
    # so the terminal stays readable while you're using the app.
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # File handler: captures EVERYTHING, including DEBUG messages, so the
    # full history is available on disk if you need to dig into a bug later.
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
