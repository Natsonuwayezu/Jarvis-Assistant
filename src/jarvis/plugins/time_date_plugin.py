# src/jarvis/plugins/time_date_plugin.py
#
# EXAMPLE PLUGIN — read this file as a template for writing your own.
#
# This plugin adds one new tool: get_current_datetime. It lets JARVIS
# answer questions like "what time is it?" or "what's today's date?"
# accurately, since the AI itself has no built-in awareness of the
# actual current date/time on your machine.

from datetime import datetime

# --- Required part 1: TOOL_DEFINITION ---
# This dict is merged into the full list of tools sent to the AI,
# exactly alongside the built-in tools from Phase 5.
TOOL_DEFINITION = {
    "name": "get_current_datetime",
    "description": (
        "Get the current date and time on the user's computer. Use this "
        "whenever the user asks what time or date it is, or needs the "
        "current date/time for a calculation."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},  # No arguments needed for this simple tool.
        "required": [],
    },
}


# --- Required part 2: handle() ---
def handle(tool_input: dict) -> str:
    """
    Return the current date and time as a plain-text string.

    Args:
        tool_input: Unused here (this tool takes no arguments), but the
            loader always calls handle() with a dict, so every plugin's
            handle() function must accept one, even if it's ignored.

    Returns:
        A human-readable current date/time string.
    """
    now = datetime.now()
    # Example output: "Saturday, July 18, 2026 at 03:45 PM"
    return now.strftime("%A, %B %d, %Y at %I:%M %p")
