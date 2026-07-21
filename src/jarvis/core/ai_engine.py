# src/jarvis/core/ai_engine.py
#
# WHY THIS FILE EXISTS:
# This is JARVIS's actual "brain" — the part that takes what you typed,
# sends it to Google's Gemini API for real reasoning, and returns a
# genuine reply.
#
# WHY GEMINI (switched from Anthropic's Claude in this revision): Gemini
# offers a genuinely free tier (no credit card, no payment required) via
# Google AI Studio, which matters a lot while you're still learning and
# testing. The rest of this project's architecture doesn't care which AI
# provider is behind get_response() — the GUI, voice, automation, memory,
# and plugins all stay exactly the same; only this one file changes.
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
# saved to disk) is a separate feature from Phase 6, handled by
# MemoryStore.
#
# TOOL USE (function calling):
# Gemini can DO things, not just talk — opening apps, opening websites,
# searching for files, creating/editing files, managing windows, and
# (only after explicit confirmation) running terminal commands. This
# works via Gemini's "function calling" feature: we describe each tool
# (see core/tools.py) using its provider-agnostic schema, translate that
# into Gemini's expected format below, and when a user's request calls
# for one, Gemini replies with a function-call request instead of plain
# text. We then actually run that action, send the result back to
# Gemini, and Gemini continues — possibly using more tools, or giving a
# final plain-text reply. get_response() loops through this cycle until
# Gemini produces a final text answer.
#
# PERSISTENT MEMORY:
# Every successful exchange (user message + JARVIS's final reply) is
# saved permanently via MemoryStore (core/memory_store.py), so
# conversations survive closing and reopening the app. On startup, the
# most recent messages are preloaded into self._history so a
# conversation feels continuous. Anything older is reachable via the
# "recall_memory" tool, which searches the full permanent history.

import os
from typing import Callable, List, Dict, Optional

from google import genai
from google.genai import types, errors
from dotenv import load_dotenv

from jarvis.config.settings import (
    AI_MODEL,
    AI_MAX_TOKENS,
    AI_SYSTEM_PROMPT,
    MEMORY_PRELOAD_LIMIT,
    MAX_SESSION_HISTORY,
)
from jarvis.core.tools import TOOL_DEFINITIONS, execute_tool
from jarvis.core.memory_store import MemoryStore
from jarvis.utils.logger import get_logger

logger = get_logger(__name__)

# Safety valve: caps how many times, in a single get_response() call,
# Gemini is allowed to chain one tool call into another before we force
# a final answer. Without this, a confused or looping AI response could
# in theory keep calling tools forever on one user message.
_MAX_TOOL_ITERATIONS = 5


def _build_gemini_tools() -> List[types.Tool]:
    """
    Translate our provider-agnostic TOOL_DEFINITIONS (see core/tools.py
    — the same format built-in tools AND plugins use) into the specific
    object shape Gemini's API expects.

    We keep TOOL_DEFINITIONS itself provider-agnostic (using the key
    "input_schema") rather than rewriting it in Gemini's vocabulary, so
    that: (a) the plugin-writing contract documented in
    plugins/__init__.py doesn't need to change if we ever switch AI
    providers again, and (b) this translation step is the ONLY place
    that needs to know Gemini's specific naming ("parameters_json_schema"
    instead of "input_schema").
    """
    function_declarations = [
        types.FunctionDeclaration(
            name=tool_def["name"],
            description=tool_def["description"],
            parameters_json_schema=tool_def["input_schema"],
        )
        for tool_def in TOOL_DEFINITIONS
    ]
    return [types.Tool(function_declarations=function_declarations)]


class AIEngine:
    """
    Manages the conversation with Gemini: sending messages, keeping
    track of conversation history for context, executing tool/action
    requests, and handling errors gracefully.
    """

    def __init__(
        self,
        confirm_command: Optional[Callable[[str], bool]] = None,
        memory_store: Optional[MemoryStore] = None,
        confirm_action: Optional[Callable[[str], bool]] = None,
        system_prompt: Optional[str] = None,
    ):
        """
        Set up the connection to the Gemini API.

        Args:
            confirm_command: A function that takes a proposed shell
                command (string) and returns True/False based on real
                user confirmation — normally wired up in main.py to a
                GUI Yes/No dialog. If not provided, JARVIS will simply
                never be able to run terminal commands (every request
                to do so is treated as declined) — a safe default.
            confirm_action: A function that takes a plain-text
                description of some other real, external, hard-to-undo
                action (currently just creating a GitHub issue) and
                returns True/False based on real user confirmation. If
                not provided, those actions are always treated as
                declined — a safe default.
            system_prompt: A custom personality/system prompt to use
                instead of the built-in AI_SYSTEM_PROMPT default (see
                config/settings.py). Normally comes from the user's
                Settings window (core/user_settings.py). If not
                provided (or empty), the built-in default is used.
            memory_store: An existing MemoryStore instance to use,
                instead of creating a new one. This exists so main.py
                can share ONE MemoryStore between AIEngine (for
                conversation history) and RoutineScheduler (for
                proactive reminders) — both need to read/write the same
                underlying database. If not provided, a new MemoryStore
                is created internally, exactly as in earlier versions
                of this class.

        Raises:
            RuntimeError: if no API key can be found. We raise a clear,
            specific error here (rather than letting a cryptic library
            error bubble up) so that whoever runs this knows exactly
            what to fix.
        """
        # load_dotenv() reads the .env file (if it exists) in the project
        # root and loads its contents into the environment variables for
        # this running program. This is how GEMINI_API_KEY ends up
        # available to os.environ.get() below, without ever being
        # written directly in this source file.
        load_dotenv()

        api_key = os.environ.get("GEMINI_API_KEY")

        if not api_key or api_key == "your-api-key-goes-here":
            # This is a deliberately loud, specific error. A vague
            # "authentication failed" from deep inside the API library
            # would be confusing for someone new to this; this message
            # tells them exactly what file to create and what to put in it.
            raise RuntimeError(
                "No Gemini API key found. Copy '.env.example' to '.env' "
                "in the project root and put your real API key in it. "
                "Get a FREE key at https://aistudio.google.com/apikey"
            )

        self._client = genai.Client(api_key=api_key)
        self._confirm_command = confirm_command
        self._confirm_action = confirm_action
        self._tools = _build_gemini_tools()
        self._system_prompt = system_prompt or AI_SYSTEM_PROMPT

        # Open (or create) the permanent memory database, and preload
        # the most recent exchanges into working history so a
        # conversation feels continuous across app restarts, instead of
        # JARVIS acting like it's never spoken to you before.
        #
        # MemoryStore stores role as "user"/"assistant" (provider-
        # agnostic — see memory_store.py), but Gemini's API expects
        # "user"/"model" for the two conversation roles, and expects
        # each turn's text wrapped in a "parts" list. This translation
        # happens here, at the boundary, rather than inside MemoryStore
        # itself, so MemoryStore stays reusable if we switch providers
        # again later.
        self._memory = memory_store or MemoryStore()
        # If a MemoryStore was handed to us (shared with RoutineScheduler
        # in main.py), we don't own its lifecycle — main.py is
        # responsible for closing it. We only close it ourselves in
        # close() below if WE were the ones who created it.
        self._owns_memory = memory_store is None
        raw_history = self._memory.get_recent_messages(limit=MEMORY_PRELOAD_LIMIT)
        self._history: List[Dict] = [
            {
                "role": "user" if message["role"] == "user" else "model",
                "parts": [{"text": message["content"]}],
            }
            for message in raw_history
        ]

        if self._history:
            logger.info(
                "Preloaded %d message(s) from persistent memory.", len(self._history)
            )

        logger.info("AIEngine initialized with model '%s'.", AI_MODEL)

    def get_response(self, user_message: str) -> str:
        """
        Send the user's message to Gemini and return JARVIS's final
        reply as plain text. Along the way, this may involve one or
        more rounds of Gemini requesting to use a tool (open an app,
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
        # Trim the working history BEFORE adding anything new for this
        # call. This is the one safe point to do it: the previous
        # get_response() call has already fully completed (no
        # in-progress function-call sequence hanging mid-way), so
        # dropping old entries from the front here can never split a
        # function call from its matching result.
        if len(self._history) > MAX_SESSION_HISTORY:
            overflow = len(self._history) - MAX_SESSION_HISTORY
            del self._history[:overflow]
            logger.debug("Trimmed %d old entries from session history.", overflow)

        # Add the user's new message to history BEFORE sending, so it's
        # included as part of the context Gemini sees.
        self._history.append({"role": "user", "parts": [{"text": user_message}]})

        config = types.GenerateContentConfig(
            system_instruction=self._system_prompt,
            max_output_tokens=AI_MAX_TOKENS,
            tools=self._tools,
            # We disable Gemini's own automatic function calling because
            # we need to run our OWN logic in between (the confirmation
            # dialog for execute_command, memory_store access for
            # recall_memory) rather than letting the SDK call our
            # Python functions directly and invisibly.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

        for _ in range(_MAX_TOOL_ITERATIONS):
            try:
                response = self._client.models.generate_content(
                    model=AI_MODEL,
                    contents=self._history,
                    config=config,
                )

            except errors.ClientError as error:
                # 4xx errors — most commonly a bad/missing API key (401)
                # or a request the API rejected (400). We treat these as
                # a single "check your key" message since that's by far
                # the most common cause for someone setting this up.
                logger.error("Gemini client error: %s", error)
                self._history.pop()  # Remove the unanswered user turn.
                return (
                    "I couldn't authenticate or complete that request with the AI "
                    "service. Please check that your API key in the .env file is "
                    "correct and hasn't hit its free-tier rate limit."
                )

            except errors.APIError as error:
                # Catches broader API/server/network issues without
                # crashing the app.
                logger.error("Gemini API error: %s", error)
                self._history.pop()
                return (
                    "I'm having trouble reaching the AI service right now. "
                    "Please check your internet connection and try again."
                )

            function_calls = response.function_calls

            if not function_calls:
                # Gemini gave a normal, final answer — no tool needed
                # (or no more tools needed after earlier ones this turn).
                reply_text = response.text or ""
                logger.debug("AI response generated (%d chars).", len(reply_text))

                # Record Gemini's final turn in history so it has
                # context for future messages in this same session.
                self._history.append({"role": "model", "parts": [{"text": reply_text}]})

                # Only NOW, once we know the exchange truly succeeded,
                # do we save it permanently. We deliberately save the
                # plain user_message and reply_text — not the
                # function-call plumbing that may have happened along
                # the way — since that's implementation detail, not
                # something a person means by "remember this."
                self._memory.save_message("user", user_message)
                self._memory.save_message("assistant", reply_text)

                return reply_text

            # --- Gemini wants to use one or more tools ---
            # response.candidates[0].content is the exact Content object
            # representing Gemini's turn (including the function-call
            # parts) — appending it directly (rather than reconstructing
            # it by hand) keeps everything Gemini expects intact for the
            # next request in this loop.
            self._history.append(response.candidates[0].content)

            # Run every requested tool call and collect a matching
            # function_response part for each, since Gemini expects a
            # result for every tool call it made before it will continue.
            response_parts = []
            for function_call in function_calls:
                result_text = execute_tool(
                    tool_name=function_call.name,
                    tool_input=dict(function_call.args or {}),
                    confirm_command=self._confirm_command,
                    memory_store=self._memory,
                    confirm_action=self._confirm_action,
                )

                response_parts.append(
                    types.Part.from_function_response(
                        name=function_call.name,
                        response={"result": result_text},
                    )
                )

            # Function results are sent back as a "user" turn — this is
            # the format the Gemini API requires for continuing a
            # conversation after tool use. The loop then goes around
            # again, giving Gemini the results so it can respond.
            self._history.append(types.Content(role="user", parts=response_parts))

        # Safety valve triggered: Gemini kept requesting tools beyond our
        # limit. Rather than looping forever, we stop and say so plainly.
        logger.warning("Tool iteration limit (%d) reached for one message.", _MAX_TOOL_ITERATIONS)
        return (
            "I attempted several actions for that request but couldn't reach a final "
            "answer — could you try rephrasing or breaking it into smaller steps?"
        )

    def set_system_prompt(self, new_prompt: str) -> None:
        """
        Update JARVIS's personality/system prompt while the app keeps
        running (used by the Settings window — see ui/settings_window.py).
        Takes effect on the NEXT message; a conversation already in
        progress isn't retroactively changed.

        Args:
            new_prompt: The new system prompt text. If empty/None, the
                built-in default (AI_SYSTEM_PROMPT) is restored instead.
        """
        self._system_prompt = new_prompt or AI_SYSTEM_PROMPT
        logger.info("System prompt updated (%d chars).", len(self._system_prompt))

    def close(self) -> None:
        """
        Close the underlying memory database cleanly — but ONLY if
        this AIEngine created it itself. If a shared MemoryStore was
        passed in (see __init__), main.py owns closing it, since
        RoutineScheduler may still be using the same instance.
        """
        if self._owns_memory:
            self._memory.close()
