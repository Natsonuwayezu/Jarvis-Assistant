# src/jarvis/core/automation/app_launcher.py
#
# WHY THIS FILE EXISTS:
# Opens desktop applications by name (e.g. "notepad", "calculator",
# "chrome"). Windows, macOS, and Linux each launch applications
# completely differently, so this file's whole job is to hide that
# difference behind one simple function: open_application(name).
#
# LIMITATION TO BE HONEST ABOUT: this works best for applications
# already registered with the operating system (installed normally,
# appearing in the Start Menu / Applications folder / app launcher).
# It won't find an app by a name that doesn't match how the OS knows it
# (e.g. asking for "Word" when the OS only recognizes "winword").

import platform
import subprocess

from jarvis.utils.logger import get_logger

logger = get_logger(__name__)


class AppLaunchError(Exception):
    """Raised when an application could not be found or started."""


def open_application(app_name: str) -> str:
    """
    Attempt to open a desktop application by name.

    Args:
        app_name: The application's name as you'd normally refer to it,
            e.g. "notepad", "calculator", "chrome", "spotify".

    Returns:
        A short human-readable confirmation message (e.g. "Opened
        notepad."), suitable for JARVIS to say back to the user.

    Raises:
        AppLaunchError: if the application could not be found/started.
            The caller (ai_engine.py) catches this and reports it back
            to Claude as a tool result, so the AI can explain the
            failure conversationally instead of the app crashing.
    """
    system = platform.system()  # "Windows", "Darwin" (macOS), or "Linux"
    app_name_clean = app_name.strip()

    logger.info("Attempting to open application '%s' on %s.", app_name_clean, system)

    try:
        if system == "Windows":
            # `start` is a Windows command-shell built-in for launching
            # registered applications by name. The empty "" after start
            # is a required placeholder for the window title argument.
            subprocess.Popen(
                ["cmd", "/c", "start", "", app_name_clean], shell=False
            )

        elif system == "Darwin":  # macOS
            # `open -a` launches an application by its macOS app name,
            # e.g. `open -a "Calculator"`.
            result = subprocess.run(
                ["open", "-a", app_name_clean], capture_output=True, text=True
            )
            if result.returncode != 0:
                raise AppLaunchError(
                    f"macOS could not find an application named '{app_name_clean}'."
                )

        elif system == "Linux":
            # There's no single universal launcher command on Linux, so
            # we try running the app name directly as a command (this
            # works for many common apps, e.g. "firefox", "gedit").
            subprocess.Popen([app_name_clean.lower()])

        else:
            raise AppLaunchError(f"Unsupported operating system: {system}")

    except FileNotFoundError:
        # Raised when subprocess can't find the given command/app at all.
        logger.warning("Application '%s' not found.", app_name_clean)
        raise AppLaunchError(
            f"I couldn't find an application called '{app_name_clean}' on this computer."
        )

    logger.info("Successfully launched '%s'.", app_name_clean)
    return f"Opened {app_name_clean}."
