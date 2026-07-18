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

import os
from typing import List, Dict

import anthropic
from dotenv import load_dotenv

from jarvis.config.settings import AI_MODEL, AI_MAX_TOKENS, AI_SYSTEM_PROMPT
from jarvis.utils.logger import get_logger

logger = get_logger(__name__)


class AIEngine:
    """
    Manages the conversation with Claude: sending messages, keeping track
    of conversation history for context, and handling errors gracefully.
    """

    def __init__(self):
        """
        Set up the connection to the Claude API.

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

        # Conversation history as a list of {"role": ..., "content": ...}
        # dictionaries — this is the exact format the Claude API expects,
        # and sending the full history with each request is what allows
        # Claude to "remember" earlier parts of THIS session's conversation.
        self._history: List[Dict[str, str]] = []

        logger.info("AIEngine initialized with model '%s'.", AI_MODEL)

    def get_response(self, user_message: str) -> str:
        """
        Send the user's message to Claude (along with prior conversation
        history for context) and return Claude's reply as plain text.

        Args:
            user_message: The raw text the user typed into the GUI.

        Returns:
            JARVIS's reply as a plain string. If something goes wrong
            (network issue, API error), returns a friendly error message
            instead of raising an exception — so the GUI never crashes
            because of an API problem.
        """
        # Add the user's new message to history BEFORE sending, so it's
        # included as part of the context Claude sees.
        self._history.append({"role": "user", "content": user_message})

        try:
            response = self._client.messages.create(
                model=AI_MODEL,
                max_tokens=AI_MAX_TOKENS,
                system=AI_SYSTEM_PROMPT,
                messages=self._history,
            )

            # response.content is a list of content blocks (Claude can, in
            # general, return multiple blocks — e.g. text plus tool calls).
            # For plain conversation we only expect a single text block,
            # so we take the first one.
            reply_text = response.content[0].text

        except anthropic.AuthenticationError:
            # Wrong or revoked API key specifically — distinct from other
            # errors so the user gets a targeted, actionable message.
            logger.error("Anthropic authentication failed — check your API key in .env")
            reply_text = (
                "I can't authenticate with the AI service. Please check that "
                "your API key in the .env file is correct."
            )
            # Remove the user message we added above — since we never got a
            # real reply, we don't want a half-finished exchange polluting
            # future context sent to the API.
            self._history.pop()
            return reply_text

        except anthropic.APIError as error:
            # Catches broader API/network issues (rate limits, server
            # errors, connectivity problems) without crashing the app.
            logger.error("Anthropic API error: %s", error)
            reply_text = (
                "I'm having trouble reaching the AI service right now. "
                "Please check your internet connection and try again."
            )
            self._history.pop()
            return reply_text

        # Only add Claude's reply to history once we know it succeeded.
        self._history.append({"role": "assistant", "content": reply_text})

        logger.debug("AI response generated (%d chars).", len(reply_text))

        return reply_text
