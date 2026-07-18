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
    "You are currently running as an early-stage personal desktop "
    "assistant, so if asked to perform actions you cannot yet do "
    "(such as controlling the computer, opening applications, or "
    "browsing the web), politely explain that capability is still "
    "being built, rather than pretending to do it."
)
