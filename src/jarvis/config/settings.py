# src/jarvis/config/settings.py
#
# WHY THIS FILE EXISTS:
# Instead of scattering constants like the app's name or version across
# many files, we define them once here. Later phases (Settings page, API
# keys, feature toggles) will expand this file — but the pattern starts now.
#
# IMPORTANT SECURITY NOTE (relevant from Phase 3 onward):
# Real secrets (API keys, tokens) must NEVER be written directly in this
# file or committed to git. When we reach Phase 3 (AI chat), we will load
# secrets from a local ".env" file instead, which is excluded from git via
# .gitignore. This file only holds non-secret, non-sensitive configuration.

from pathlib import Path

APP_NAME = "JARVIS"
APP_VERSION = "0.1.0"

# Controls how much detail gets printed to the console.
# Options (from least to most detail): "WARNING", "INFO", "DEBUG"
LOG_LEVEL = "INFO"

# Where JARVIS looks for a downloaded offline speech-recognition model
# (see core/voice_input.py and the README's "Offline speech recognition
# setup" section). Not used at all unless offline mode is turned on in
# Settings — online (Google) recognition is the default and needs no
# model download.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
VOSK_MODEL_PATH = _PROJECT_ROOT / "data" / "vosk-model"

# --- Phase 3: AI settings ---
#
# Which Gemini model JARVIS uses for conversation. "gemini-3.5-flash" is
# Google's fast, general-purpose model — strong at real reasoning and
# tool use, and (importantly for testing without a budget) available on
# Google's free tier via an AI Studio API key, no credit card required.
AI_MODEL = "gemini-3.5-flash"

# The maximum length (in "tokens", roughly ~4 characters each) of a
# single JARVIS reply. Keeps responses focused and keeps API costs
# predictable. 1024 tokens is roughly 700-800 words — plenty for
# conversational replies.
AI_MAX_TOKENS = 1024

# The SYSTEM PROMPT defines JARVIS's personality and behavior. It is sent
# with every request but is invisible in the chat window — it shapes HOW
# the AI responds, not WHAT the user sees. Feel free to edit this text
# any time to change JARVIS's tone or style.
AI_SYSTEM_PROMPT = (
    "You are JARVIS, a helpful, capable, and personable AI assistant "
    "inspired by the assistant from Iron Man. You are concise, clear, "
    "and a little warm in tone, but never overly casual or verbose. "
    "You can open applications, open websites, search the user's "
    "computer for files, and create or edit files directly using your "
    "tools — use them whenever a request calls for it, rather than just "
    "describing what you would do. Running terminal commands always "
    "requires the user's real-time confirmation, so don't ask them to "
    "confirm in words first; simply request the command and the "
    "confirmation dialog will be handled separately. You have persistent "
    "memory of past conversations — recent messages are already in your "
    "context, and you can use the recall_memory tool to search further "
    "back when the user references something from an earlier session. "
    "You can also schedule proactive reminders using create_routine — "
    "these fire on their own later, without the user needing to ask "
    "again, so use them whenever the user wants to be reminded of "
    "something at a specific time (once, or daily). "
    "You can read PDF files directly using read_pdf to answer questions "
    "about their contents. You can also check GitHub repositories — "
    "getting repo info, listing issues, and listing pull requests need "
    "no confirmation, but creating a new issue is a real, visible, "
    "hard-to-undo action, so it always requires the user's real-time "
    "confirmation regardless of how the request was phrased. "
    "You can also manage open windows — listing, focusing, minimizing, "
    "maximizing, or closing them by title. Additional tools may be "
    "available from user-installed plugins — use any tool provided to "
    "you whenever it fits the request. For capabilities you don't have "
    "a tool for at all, politely explain that it's still being built "
    "rather than pretending to do it."
)

# --- Phase 6: persistent memory settings ---
#
# How many of the most recent messages (combined user + assistant) get
# loaded back into JARVIS's working context every time the app starts,
# so a conversation feels continuous across restarts. Kept fairly small
# (20 messages = roughly 10 back-and-forth exchanges) since every one of
# these gets sent to the AI with every request — larger values mean a
# more continuous-feeling memory, but also a bigger, more expensive
# request every time. Anything older is still searchable in full via
# the recall_memory tool.
MEMORY_PRELOAD_LIMIT = 20

# The maximum number of entries kept in a SINGLE SESSION's live working
# history (self._history in ai_engine.py) before older ones get
# trimmed off the front. Without this cap, a long conversation grows
# unbounded — every message sent to Gemini gets bigger, slower, and
# closer to hitting the free tier's rate/token limits. This is
# deliberately larger than MEMORY_PRELOAD_LIMIT (which only controls
# what's loaded back in at startup) since it also needs room for
# tool-use turns (each tool call adds 2 extra entries: the request and
# its result) that happen WITHIN a single session. Trimming only
# happens at the very start of get_response(), a clean point where the
# previous exchange has already fully finished — so it never risks
# cutting off a function call from its matching result mid-sequence.
MAX_SESSION_HISTORY = 60
