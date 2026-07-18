# src/jarvis/config/__init__.py
#
# Marks "config" as a sub-package so we can do:
#     from jarvis.config.settings import APP_NAME
#
# This folder will eventually hold: API keys (loaded safely from a .env file,
# NEVER hardcoded), user preferences, and feature toggles (e.g. "voice enabled").
