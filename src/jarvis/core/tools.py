# src/jarvis/core/tools.py
#
# WHY THIS FILE EXISTS:
# This file bridges the AI engine (ai_engine.py) and the automation
# actions (automation/*.py), AND (as of Phase 7) any plugins loaded
# from plugins/. It has two jobs:
#
#   1. TOOL_DEFINITIONS describes each available tool to the AI, in
#      the exact schema format the AI's API expects for "tool use"
#      (function calling). This is how the AI knows these actions
#      exist and what arguments each one needs. It's built by combining
#      the built-in tools defined directly in this file with whatever
#      plugins were successfully loaded from plugins/ at startup.
#
#   2. execute_tool() is the dispatcher: when the AI decides to use one
#      of these tools, this function actually calls the real
#      automation code (or a plugin's handle() function) and returns a
#      plain-text result, which gets fed back to the AI so it can
#      describe the outcome conversationally.
#
# WHY TOOL USE INSTEAD OF KEYWORD-MATCHING THE USER'S TEXT: asking
# the AI to decide "does this message need an action, and which one?"
# is far more robust than pattern-matching phrases like "open" or
# "search" ourselves — the AI already understands natural language
# variation ("could you pull up my browser and check the weather"
# should still trigger open_website, without us hand-coding every
# possible phrasing).

from typing import Callable, Optional

from jarvis.core.automation.app_launcher import open_application, AppLaunchError
from jarvis.core.automation.web_opener import open_website
from jarvis.core.automation.file_search import search_files
from jarvis.core.automation.file_manager import create_file, edit_file, FileOperationError
from jarvis.core.automation.command_executor import execute_command, CommandNotConfirmedError
from jarvis.core.automation.window_manager import (
    list_open_windows,
    focus_window,
    minimize_window,
    maximize_window,
    close_window,
    WindowNotFoundError,
    WindowControlUnsupportedError,
)
from jarvis.core.memory_store import MemoryStore
from jarvis.core.plugin_loader import discover_plugins
from jarvis.utils.logger import get_logger

logger = get_logger(__name__)

# PHASE 7: discover plugins ONCE, when this module is first imported
# (i.e. once per app run, at startup) — not on every single message,
# which would mean re-scanning and re-importing every plugin file for
# every user message. _LOADED_PLUGINS maps tool name -> LoadedPlugin,
# and is used both to extend TOOL_DEFINITIONS below and to dispatch
# plugin tool calls in execute_tool().
_LOADED_PLUGINS = discover_plugins()

# --- Tool schemas, in a provider-agnostic format ---
# Each "input_schema" follows standard JSON Schema — the AI uses these
# to know exactly what arguments to provide and validates its own
# output against them before calling us.
# These are the tools JARVIS ships with out of the box (Phases 5-6).
_BUILTIN_TOOL_DEFINITIONS = [
    {
        "name": "open_application",
        "description": (
            "Open a desktop application on the user's computer by name, "
            "e.g. 'notepad', 'calculator', 'spotify'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": "The name of the application to open.",
                }
            },
            "required": ["app_name"],
        },
    },
    {
        "name": "open_website",
        "description": (
            "Open a website in the user's default browser, OR perform a web "
            "search if given a plain-language query instead of a URL."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "destination": {
                    "type": "string",
                    "description": (
                        "A URL/domain (e.g. 'github.com') or a search query "
                        "(e.g. 'weather in Kigali')."
                    ),
                }
            },
            "required": ["destination"],
        },
    },
    {
        "name": "search_files",
        "description": "Search the user's computer for files whose name matches a query.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Text to search for within file names.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "create_file",
        "description": "Create a new file on the user's computer with the given text content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filepath": {
                    "type": "string",
                    "description": "Path where the file should be created.",
                },
                "content": {
                    "type": "string",
                    "description": "Text content to write into the new file.",
                },
            },
            "required": ["filepath", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": "Edit an existing file by appending to it or overwriting its content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filepath": {
                    "type": "string",
                    "description": "Path to the existing file to edit.",
                },
                "content": {
                    "type": "string",
                    "description": "Text content to write.",
                },
                "mode": {
                    "type": "string",
                    "enum": ["append", "overwrite"],
                    "description": "Whether to append to or overwrite the file.",
                },
            },
            "required": ["filepath", "content", "mode"],
        },
    },
    {
        "name": "execute_command",
        "description": (
            "Run a terminal/shell command on the user's computer. This is "
            "POWERFUL and POTENTIALLY DANGEROUS — it always requires the "
            "user's explicit real-time confirmation before running, no "
            "matter how the request was phrased. Use only when the user is "
            "clearly asking for a command to be run."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The exact shell command to run.",
                }
            },
            "required": ["command"],
        },
    },
    {
        "name": "list_open_windows",
        "description": "List the titles of all currently open windows on the user's desktop.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "focus_window",
        "description": "Bring an already-open window to the front and give it focus, by (partial) title.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Text to match against open window titles.",
                }
            },
            "required": ["title"],
        },
    },
    {
        "name": "minimize_window",
        "description": "Minimize an open window, by (partial) title.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Text to match against open window titles.",
                }
            },
            "required": ["title"],
        },
    },
    {
        "name": "maximize_window",
        "description": "Maximize an open window, by (partial) title.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Text to match against open window titles.",
                }
            },
            "required": ["title"],
        },
    },
    {
        "name": "close_window",
        "description": "Close an open window, by (partial) title.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Text to match against open window titles.",
                }
            },
            "required": ["title"],
        },
    },
    {
        "name": "create_routine",
        "description": (
            "Schedule a proactive reminder JARVIS will bring up on its own, "
            "without the user asking again — e.g. 'remind me to drink water "
            "every day at 3pm' or 'remind me about the dentist tomorrow at 9am'. "
            "If you need to compute a relative time (like 'tomorrow' or 'in 2 "
            "hours'), call get_current_datetime first to learn the current date/time."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "What to remind the user of, e.g. 'drink water'.",
                },
                "next_run": {
                    "type": "string",
                    "description": (
                        "ISO 8601 datetime for when this should first fire, "
                        "e.g. '2026-07-20T15:00:00'."
                    ),
                },
                "recurrence": {
                    "type": "string",
                    "enum": ["once", "daily"],
                    "description": "'once' fires a single time; 'daily' repeats every day at the same time.",
                },
            },
            "required": ["description", "next_run", "recurrence"],
        },
    },
    {
        "name": "list_routines",
        "description": "List every reminder/routine currently scheduled.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "cancel_routine",
        "description": "Cancel a previously scheduled reminder/routine by its ID (from list_routines).",
        "input_schema": {
            "type": "object",
            "properties": {
                "routine_id": {
                    "type": "integer",
                    "description": "The routine's ID, as shown by list_routines.",
                }
            },
            "required": ["routine_id"],
        },
    },
    {
        "name": "recall_memory",
        "description": (
            "Search the FULL history of past conversations with the user, "
            "beyond what's currently visible in this conversation. Use this "
            "when the user references something from an earlier session "
            "(e.g. 'what did I tell you about X before', 'did we discuss Y "
            "last week') that isn't already in the current context."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Text to search for in past conversation history.",
                }
            },
            "required": ["query"],
        },
    },
]

# PHASE 7: the FINAL list of tools sent to the AI — every built-in tool
# above, PLUS one entry per successfully loaded plugin. This is what
# ai_engine.py actually imports and uses; it never needs to know
# whether any given tool is built-in or came from a plugin file.
TOOL_DEFINITIONS = _BUILTIN_TOOL_DEFINITIONS + [
    plugin.tool_definition for plugin in _LOADED_PLUGINS.values()
]


def execute_tool(
    tool_name: str,
    tool_input: dict,
    confirm_command: Optional[Callable[[str], bool]] = None,
    memory_store: Optional[MemoryStore] = None,
) -> str:
    """
    Actually perform the automation action the AI asked for, and return
    a plain-text result describing what happened (success or failure).

    Args:
        tool_name: Which tool the AI wants to use (must match a name in
            TOOL_DEFINITIONS above).
        tool_input: The arguments the AI provided, already validated by
            the AI against that tool's input_schema.
        confirm_command: Only used for the "execute_command" tool. A
            function that takes the proposed command string and
            returns True/False based on real user confirmation (e.g. a
            Yes/No dialog). If not provided, execute_command requests
            are always treated as NOT confirmed — a safe default.
        memory_store: Only used for the "recall_memory" tool. The
            AIEngine's MemoryStore instance, used to search past
            conversation history. If not provided, recall_memory
            requests report that memory search is unavailable.

    Returns:
        A plain-text description of the result, to be sent back to
        the AI as the tool's output. Errors are caught and turned into
        descriptive strings (not raised) so a failed action becomes
        part of the conversation the AI can react to, rather than
        crashing the whole request.
    """
    logger.info("Executing tool '%s' with input: %s", tool_name, tool_input)

    try:
        if tool_name == "open_application":
            return open_application(tool_input["app_name"])

        elif tool_name == "open_website":
            return open_website(tool_input["destination"])

        elif tool_name == "search_files":
            matches = search_files(tool_input["query"])
            if not matches:
                return f"No files matching '{tool_input['query']}' were found."
            return "Found these files:\n" + "\n".join(matches)

        elif tool_name == "create_file":
            return create_file(tool_input["filepath"], tool_input.get("content", ""))

        elif tool_name == "edit_file":
            return edit_file(
                tool_input["filepath"], tool_input["content"], tool_input.get("mode", "append")
            )

        elif tool_name == "execute_command":
            command = tool_input["command"]

            # This is THE safety gate for the entire project's most
            # dangerous capability. confirm_command is only ever True
            # here if a real human clicked "Yes" on a real dialog box
            # asking about THIS EXACT command — see main.py for where
            # that dialog actually gets shown.
            is_confirmed = confirm_command(command) if confirm_command else False

            if not is_confirmed:
                logger.info("User declined (or no confirmation available) for: %s", command)
                return "The user did not approve running that command, so it was not run."

            return execute_command(command, confirmed=True)

        elif tool_name == "list_open_windows":
            return list_open_windows()

        elif tool_name == "focus_window":
            return focus_window(tool_input["title"])

        elif tool_name == "minimize_window":
            return minimize_window(tool_input["title"])

        elif tool_name == "maximize_window":
            return maximize_window(tool_input["title"])

        elif tool_name == "close_window":
            return close_window(tool_input["title"])

        elif tool_name == "create_routine":
            if memory_store is None:
                return "Routines are unavailable right now."
            routine_id = memory_store.create_routine(
                description=tool_input["description"],
                next_run=tool_input["next_run"],
                recurrence=tool_input["recurrence"],
            )
            return (
                f"Scheduled routine #{routine_id}: I'll {tool_input['description']} "
                f"at {tool_input['next_run']} ({tool_input['recurrence']})."
            )

        elif tool_name == "list_routines":
            if memory_store is None:
                return "Routines are unavailable right now."
            routines = memory_store.list_routines()
            if not routines:
                return "No routines are currently scheduled."
            lines = [
                f"#{r['id']}: {r['description']} at {r['next_run']} ({r['recurrence']})"
                for r in routines
            ]
            return "Scheduled routines:\n" + "\n".join(lines)

        elif tool_name == "cancel_routine":
            if memory_store is None:
                return "Routines are unavailable right now."
            cancelled = memory_store.cancel_routine(tool_input["routine_id"])
            if cancelled:
                return f"Cancelled routine #{tool_input['routine_id']}."
            return f"No routine with ID {tool_input['routine_id']} was found."

        elif tool_name == "recall_memory":
            if memory_store is None:
                return "Memory search is unavailable right now."

            matches = memory_store.search_messages(tool_input["query"])
            if not matches:
                return f"Nothing found in past conversations matching '{tool_input['query']}'."

            # Format each match with its timestamp so the AI can tell
            # the user roughly when something was said, e.g. "you
            # mentioned that on July 3rd."
            lines = [f"[{m['timestamp']}] {m['role']}: {m['content']}" for m in matches]
            return "Found these past messages:\n" + "\n".join(lines)

        elif tool_name in _LOADED_PLUGINS:
            # PHASE 7: this tool wasn't one of the built-ins above, but
            # matches a successfully loaded plugin. Call its handle()
            # function directly. Plugin code is wrapped in its own
            # try/except here (separate from the built-in error
            # handling below) since a plugin can raise ANY kind of
            # exception — we can't know in advance what a
            # user-written plugin might do wrong, so we must catch
            # broadly here specifically, to keep one bad plugin call
            # from crashing the whole conversation.
            try:
                return _LOADED_PLUGINS[tool_name].handler(tool_input)
            except Exception as error:
                logger.error("Plugin '%s' raised an error: %s", tool_name, error)
                return f"The '{tool_name}' plugin encountered an error: {error}"

        else:
            # Should never happen unless TOOL_DEFINITIONS and this
            # dispatcher fall out of sync with each other.
            logger.error("Unknown tool requested: %s", tool_name)
            return f"Unknown tool '{tool_name}' — this is a bug in JARVIS, not your request."

    except (
        AppLaunchError,
        FileOperationError,
        CommandNotConfirmedError,
        WindowNotFoundError,
        WindowControlUnsupportedError,
    ) as error:
        # These are our own, expected, descriptive errors (e.g. "app
        # not found", "file already exists") — safe to hand straight
        # back to the AI as the tool result so it can explain plainly.
        logger.warning("Tool '%s' failed: %s", tool_name, error)
        return f"Action failed: {error}"
