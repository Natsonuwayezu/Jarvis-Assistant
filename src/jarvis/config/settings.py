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

APP_NAME = "JARVIS"
APP_VERSION = "0.1.0"

# Controls how much detail gets printed to the console.
# Options (from least to most detail): "WARNING", "INFO", "DEBUG"
LOG_LEVEL = "INFO"

# --- Phase 3: AI settings ---
#
# Which Claude model JARVIS uses for conversation. "claude-sonnet-5" is a
# strong, balanced choice for a personal assistant — capable enough for
# real reasoning, without the higher cost of Anthropic's top-tier models.
AI_MODEL = "claude-sonnet-5"

# The maximum length (in "tokens", roughly ~4 characters each) of a
# single JARVIS reply. Keeps responses focused and keeps API costs
# predictable. 1024 tokens is roughly 700-800 words — plenty for
# conversational replies.
AI_MAX_TOKENS = 1024

# The SYSTEM PROMPT defines JARVIS's personality and behavior. It is sent
# with every request but is invisible in the chat window — it shapes HOW
# Claude responds, not WHAT the user sees. Feel free to edit this text
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
    "Additional tools may be available from user-installed plugins — "
    "use any tool provided to you whenever it fits the request. For "
    "capabilities you don't have a tool for at all, politely explain "
    "that it's still being built rather than pretending to do it."
)

# --- Phase 6: persistent memory settings ---
#
# How many of the most recent messages (combined user + assistant) get
# loaded back into JARVIS's working context every time the app starts,
# so a conversation feels continuous across restarts. Kept fairly small
# (20 messages = roughly 10 back-and-forth exchanges) since every one of
# these gets sent to Claude with every request — larger values mean a
# more continuous-feeling memory, but also a bigger, more expensive
# request every time. Anything older is still searchable in full via
# the recall_memory tool.
MEMORY_PRELOAD_LIMIT = 20
