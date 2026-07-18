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
