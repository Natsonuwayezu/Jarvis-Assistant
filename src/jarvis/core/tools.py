# src/jarvis/core/tools.py
#
# WHY THIS FILE EXISTS:
# This file bridges the AI engine (ai_engine.py) and the automation
# actions (automation/*.py). It has two jobs:
#
#   1. TOOL_DEFINITIONS describes each automation action to Claude, in
#      the exact schema format Claude's API expects for "tool use"
#      (function calling). This is how Claude knows these actions
#      exist and what arguments each one needs.
#
#   2. execute_tool() is the dispatcher: when Claude decides to use one
#      of these tools, this function actually calls the real
#      automation code and returns a plain-text result, which gets fed
#      back to Claude so it can describe the outcome conversationally.
#
# WHY TOOL USE INSTEAD OF KEYWORD-MATCHING THE USER'S TEXT: asking
# Claude to decide "does this message need an action, and which one?"
# is far more robust than pattern-matching phrases like "open" or
# "search" ourselves — Claude already understands natural language
# variation ("could you pull up my browser and check the weather"
# should still trigger open_website, without us hand-coding every
# possible phrasing).

from typing import Callable, Optional

from jarvis.core.automation.app_launcher import open_application, AppLaunchError
from jarvis.core.automation.web_opener import open_website
from jarvis.core.automation.file_search import search_files
from jarvis.core.automation.file_manager import create_file, edit_file, FileOperationError
from jarvis.core.automation.command_executor import execute_command, CommandNotConfirmedError
from jarvis.core.memory_store import MemoryStore
from jarvis.utils.logger import get_logger

logger = get_logger(__name__)

# --- Tool schemas, in the format the Anthropic API requires ---
# Each "input_schema" follows standard JSON Schema — Claude uses these
# to know exactly what arguments to provide and validates its own
# output against them before calling us.
TOOL_DEFINITIONS = [
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


def execute_tool(
    tool_name: str,
    tool_input: dict,
    confirm_command: Optional[Callable[[str], bool]] = None,
    memory_store: Optional[MemoryStore] = None,
) -> str:
    """
    Actually perform the automation action Claude asked for, and return
    a plain-text result describing what happened (success or failure).

    Args:
        tool_name: Which tool Claude wants to use (must match a name in
            TOOL_DEFINITIONS above).
        tool_input: The arguments Claude provided, already validated by
            Claude against that tool's input_schema.
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
        Claude as the tool's output. Errors are caught and turned into
        descriptive strings (not raised) so a failed action becomes
        part of the conversation Claude can react to, rather than
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

        elif tool_name == "recall_memory":
            if memory_store is None:
                return "Memory search is unavailable right now."

            matches = memory_store.search_messages(tool_input["query"])
            if not matches:
                return f"Nothing found in past conversations matching '{tool_input['query']}'."

            # Format each match with its timestamp so Claude can tell
            # the user roughly when something was said, e.g. "you
            # mentioned that on July 3rd."
            lines = [f"[{m['timestamp']}] {m['role']}: {m['content']}" for m in matches]
            return "Found these past messages:\n" + "\n".join(lines)

        else:
            # Should never happen unless TOOL_DEFINITIONS and this
            # dispatcher fall out of sync with each other.
            logger.error("Unknown tool requested: %s", tool_name)
            return f"Unknown tool '{tool_name}' — this is a bug in JARVIS, not your request."

    except (AppLaunchError, FileOperationError, CommandNotConfirmedError) as error:
        # These are our own, expected, descriptive errors (e.g. "app
        # not found", "file already exists") — safe to hand straight
        # back to Claude as the tool result so it can explain plainly.
        logger.warning("Tool '%s' failed: %s", tool_name, error)
        return f"Action failed: {error}"
