# src/jarvis/core/ai_engine.py
#
# WHY THIS FILE EXISTS:
# This is JARVIS's actual "brain" — the part that takes what you typed,
# sends it to Anthropic's Claude API for real reasoning, and returns a
# genuine reply (instead of the Phase 2 placeholder that just echoed
# your message back).
#
# HOW THIS FITS THE PROJECT'S DESIGN:
# The GUI (ui/main_window.py) doesn't know anything about the AI or the
# API — it only calls whatever function it was given. In main.py, we'll
# now hand it AIEngine.get_response instead of the old echo function.
# The GUI code itself does not change at all.
#
# MEMORY NOTE (important — don't confuse this with Phase 6):
# self._history below is IN-SESSION memory only. It lives in your
# computer's RAM while the app is running, and is lost the moment you
# close JARVIS. Persistent memory (remembering things across restarts,
# saved to disk) is a separate feature we build in Phase 6.

# src/jarvis/core/ai_engine.py
#
# WHY THIS FILE EXISTS:
# This is JARVIS's actual "brain" — the part that takes what you typed,
# sends it to Anthropic's Claude API for real reasoning, and returns a
# genuine reply.
#
# HOW THIS FITS THE PROJECT'S DESIGN:
# The GUI (ui/main_window.py) doesn't know anything about the AI or the
# API — it only calls whatever function it was given. The GUI code
# itself does not change as this file grows more capable.
#
# MEMORY NOTE (important — don't confuse this with Phase 6):
# self._history below is IN-SESSION memory only. It lives in your
# computer's RAM while the app is running, and is lost the moment you
# close JARVIS. Persistent memory (remembering things across restarts,
# saved to disk) is a separate feature we build in Phase 6.
#
# PHASE 5 ADDITION — TOOL USE (function calling):
# Claude can now DO things, not just talk — opening apps, opening
# websites, searching for files, creating/editing files, and (only
# after explicit confirmation) running terminal commands. This works
# via Claude's "tool use" feature: we tell Claude what tools exist
# (see core/tools.py), and when a user's request calls for one, Claude
# replies with a request to use a specific tool instead of plain text.
# We then actually run that action, send the result back to Claude,
# and Claude continues — possibly using more tools, or giving a final
# plain-text reply. get_response() below loops through this cycle
# until Claude produces a final text answer.

import os
from typing import Callable, List, Dict, Optional

import anthropic
from dotenv import load_dotenv

from jarvis.config.settings import AI_MODEL, AI_MAX_TOKENS, AI_SYSTEM_PROMPT
from jarvis.core.tools import TOOL_DEFINITIONS, execute_tool
from jarvis.utils.logger import get_logger

logger = get_logger(__name__)

# Safety valve: caps how many times, in a single get_response() call,
# Claude is allowed to chain one tool call into another before we force
# a final answer. Without this, a confused or looping AI response could
# in theory keep calling tools forever on one user message.
_MAX_TOOL_ITERATIONS = 5


class AIEngine:
    """
    Manages the conversation with Claude: sending messages, keeping track
    of conversation history for context, executing tool/action requests,
    and handling errors gracefully.
    """

    def __init__(self, confirm_command: Optional[Callable[[str], bool]] = None):
        """
        Set up the connection to the Claude API.

        Args:
            confirm_command: A function that takes a proposed shell
                command (string) and returns True/False based on real
                user confirmation — normally wired up in main.py to a
                GUI Yes/No dialog. If not provided, JARVIS will simply
                never be able to run terminal commands (every request
                to do so is treated as declined) — a safe default.

        Raises:
            RuntimeError: if no API key can be found. We raise a clear,
            specific error here (rather than letting a cryptic library
            error bubble up) so that whoever runs this knows exactly
            what to fix.
        """
        # load_dotenv() reads the .env file (if it exists) in the project
        # root and loads its contents into the environment variables for
        # this running program. This is how ANTHROPIC_API_KEY ends up
        # available to os.environ.get() below, without ever being
        # written directly in this source file.
        load_dotenv()

        api_key = os.environ.get("ANTHROPIC_API_KEY")

        if not api_key or api_key == "your-api-key-goes-here":
            # This is a deliberately loud, specific error. A vague
            # "authentication failed" from deep inside the API library
            # would be confusing for someone new to this; this message
            # tells them exactly what file to create and what to put in it.
            raise RuntimeError(
                "No Anthropic API key found. Copy '.env.example' to '.env' "
                "in the project root and put your real API key in it. "
                "Get a key at https://console.anthropic.com/"
            )

        self._client = anthropic.Anthropic(api_key=api_key)
        self._confirm_command = confirm_command

        # Conversation history as a list of {"role": ..., "content": ...}
        # dictionaries — this is the exact format the Claude API expects,
        # and sending the full history with each request is what allows
        # Claude to "remember" earlier parts of THIS session's conversation.
        self._history: List[Dict] = []

        logger.info("AIEngine initialized with model '%s'.", AI_MODEL)

    def get_response(self, user_message: str) -> str:
        """
        Send the user's message to Claude and return JARVIS's final
        reply as plain text. Along the way, this may involve one or
        more rounds of Claude requesting to use a tool (open an app,
        run a command, etc.) — those rounds happen transparently
        inside this method; the caller only ever sees the final text.

        Args:
            user_message: The raw text the user typed or spoke.

        Returns:
            JARVIS's reply as a plain string. If something goes wrong
            (network issue, API error), returns a friendly error message
            instead of raising an exception — so the GUI never crashes
            because of an API problem.
        """
        # Add the user's new message to history BEFORE sending, so it's
        # included as part of the context Claude sees.
        self._history.append({"role": "user", "content": user_message})

        for _ in range(_MAX_TOOL_ITERATIONS):
            try:
                response = self._client.messages.create(
                    model=AI_MODEL,
                    max_tokens=AI_MAX_TOKENS,
                    system=AI_SYSTEM_PROMPT,
                    messages=self._history,
                    tools=TOOL_DEFINITIONS,
                )

            except anthropic.AuthenticationError:
                # Wrong or revoked API key specifically — distinct from other
                # errors so the user gets a targeted, actionable message.
                logger.error("Anthropic authentication failed — check your API key in .env")
                self._history.pop()  # Remove the unanswered user turn.
                return (
                    "I can't authenticate with the AI service. Please check that "
                    "your API key in the .env file is correct."
                )

            except anthropic.APIError as error:
                # Catches broader API/network issues (rate limits, server
                # errors, connectivity problems) without crashing the app.
                logger.error("Anthropic API error: %s", error)
                self._history.pop()
                return (
                    "I'm having trouble reaching the AI service right now. "
                    "Please check your internet connection and try again."
                )

            # Record Claude's response turn (whether it's a tool request
            # or a final answer) in history so it has context for
            # whatever happens next in this loop, or in future messages.
            self._history.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                # Claude gave a normal, final answer — no tool needed
                # (or no more tools needed after earlier ones this turn).
                reply_text = "".join(
                    block.text for block in response.content if block.type == "text"
                )
                logger.debug("AI response generated (%d chars).", len(reply_text))
                return reply_text

            # --- Claude wants to use one or more tools ---
            # response.content may contain a mix of text and tool_use
            # blocks; we run every tool_use block found and collect a
            # matching tool_result for each, since Claude expects a
            # result for every tool call it made before it will continue.
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                result_text = execute_tool(
                    tool_name=block.name,
                    tool_input=block.input,
                    confirm_command=self._confirm_command,
                )

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_text,
                    }
                )

            # Tool results are sent back as a "user" turn — this is the
            # format the Claude API requires for continuing a
            # conversation after tool use. The loop then goes around
            # again, giving Claude the results so it can respond.
            self._history.append({"role": "user", "content": tool_results})

        # Safety valve triggered: Claude kept requesting tools beyond our
        # limit. Rather than looping forever, we stop and say so plainly.
        logger.warning("Tool iteration limit (%d) reached for one message.", _MAX_TOOL_ITERATIONS)
        return (
            "I attempted several actions for that request but couldn't reach a final "
            "answer — could you try rephrasing or breaking it into smaller steps?"
        )
