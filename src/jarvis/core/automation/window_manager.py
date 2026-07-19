# src/jarvis/core/automation/window_manager.py
#
# WHY THIS FILE EXISTS:
# Phase 5 could OPEN applications. This file goes further: it can see
# what windows are currently open, and bring one to the front, minimize
# it, maximize it, or close it — e.g. "minimize notepad", "what's open
# right now?", "close the calculator."
#
# HONEST PLATFORM LIMITATION (please read before relying on this):
# Window management is one of the least standardized things across
# operating systems. Using the "pygetwindow" library:
#   - Windows: fully supported.
#   - Linux: supported IF the desktop is running an EWMH-compliant
#     window manager (most common ones — GNOME, KDE, XFCE, etc. — are).
#     A bare/minimal Linux setup with no window manager at all won't
#     work, since there's no window manager to ask.
#   - macOS: pygetwindow has very limited support here — macOS
#     restricts this kind of control much more tightly than Windows or
#     Linux do. Some operations may raise NotImplementedError.
# This file catches that unsupported case and reports it honestly
# rather than pretending the action succeeded.
#
# WHY NOT GATE THIS BEHIND A CONFIRMATION DIALOG (like execute_command
# in Phase 5): closing a window can't touch files, run arbitrary code,
# or affect anything outside that one application's UI — it's a much
# narrower, more reversible action than a shell command. Your original
# project spec only required confirmation specifically for terminal
# commands, so this stays ungated, consistent with that.
#
# CRITICAL DISCOVERY MADE WHILE TESTING THIS FILE: pygetwindow doesn't
# just have "limited" support on unsupported platforms — on Linux
# specifically, the library raises NotImplementedError the moment
# you *import* it, not just when you call a function. Since every
# automation module gets imported by tools.py at startup, an
# unguarded `import pygetwindow` here would have crashed JARVIS
# entirely on Linux, not just made window control unavailable. The
# try/except below catches that at import time so the REST of JARVIS
# keeps working normally, and only window-control features specifically
# report themselves as unavailable.

try:
    import pygetwindow as gw

    _WINDOW_CONTROL_AVAILABLE = True
except (ImportError, NotImplementedError):
    gw = None
    _WINDOW_CONTROL_AVAILABLE = False

from jarvis.utils.logger import get_logger

logger = get_logger(__name__)

if not _WINDOW_CONTROL_AVAILABLE:
    logger.warning(
        "Window control (pygetwindow) is not available on this operating system/"
        "desktop setup. Window management requests will be reported as unsupported."
    )


class WindowNotFoundError(Exception):
    """Raised when no open window matches the requested title."""


class WindowControlUnsupportedError(Exception):
    """
    Raised when the current operating system / desktop environment
    doesn't support a given window operation (see the platform
    limitations described above).
    """


def _require_available() -> None:
    """
    Raise a clear, specific error immediately if window control isn't
    available on this platform, rather than letting an unrelated
    AttributeError (from calling methods on gw, which is None) leak
    through and confuse whoever's debugging it.
    """
    if not _WINDOW_CONTROL_AVAILABLE:
        raise WindowControlUnsupportedError(
            "Window control isn't supported on this operating system/desktop setup."
        )


def list_open_windows() -> str:
    """
    List the titles of all currently open, visible windows.

    Returns:
        A human-readable, newline-separated list of window titles, or a
        message saying none were found.
    """
    _require_available()

    try:
        titles = [title for title in gw.getAllTitles() if title.strip()]
    except NotImplementedError:
        raise WindowControlUnsupportedError(
            "Listing windows isn't supported on this operating system/desktop setup."
        )

    if not titles:
        return "No open windows were found."

    logger.info("Found %d open window(s).", len(titles))
    return "Open windows:\n" + "\n".join(f"- {title}" for title in titles)


def _find_window(title_substring: str):
    """
    Internal helper: find the first open window whose title contains
    the given text (case-insensitive).

    Args:
        title_substring: Text to search for within window titles.

    Returns:
        The matching pygetwindow Window object.

    Raises:
        WindowNotFoundError: if no open window matches.
    """
    _require_available()

    query = title_substring.strip().lower()

    try:
        all_titles = gw.getAllTitles()
    except NotImplementedError:
        raise WindowControlUnsupportedError(
            "Window control isn't supported on this operating system/desktop setup."
        )

    for title in all_titles:
        if query in title.lower():
            # getWindowsWithTitle needs the EXACT title string as found,
            # not our partial query — that's why we search all_titles
            # first, then re-look-up the matching window object by its
            # real, full title.
            matches = gw.getWindowsWithTitle(title)
            if matches:
                return matches[0]

    raise WindowNotFoundError(f"No open window found matching '{title_substring}'.")


def focus_window(title_substring: str) -> str:
    """Bring the matching window to the front and give it focus."""
    window = _find_window(title_substring)
    window.activate()
    logger.info("Focused window: %s", window.title)
    return f"Brought '{window.title}' to the front."


def minimize_window(title_substring: str) -> str:
    """Minimize the matching window."""
    window = _find_window(title_substring)
    window.minimize()
    logger.info("Minimized window: %s", window.title)
    return f"Minimized '{window.title}'."


def maximize_window(title_substring: str) -> str:
    """Maximize the matching window."""
    window = _find_window(title_substring)
    window.maximize()
    logger.info("Maximized window: %s", window.title)
    return f"Maximized '{window.title}'."


def close_window(title_substring: str) -> str:
    """Close the matching window."""
    window = _find_window(title_substring)
    title = window.title  # Save before closing, since the object may become invalid after.
    window.close()
    logger.info("Closed window: %s", title)
    return f"Closed '{title}'."
