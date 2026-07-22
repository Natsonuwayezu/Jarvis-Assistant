# src/jarvis/core/user_settings.py
#
# WHY THIS FILE EXISTS:
# config/settings.py holds DEVELOPER-facing constants — the kind of
# thing you'd edit in code and commit to git. This file is different:
# it holds USER-facing preferences (JARVIS's personality, voice speed,
# voice volume) that you adjust through the in-app Settings window,
# without ever touching a source file. It's saved to a small JSON file
# in data/ — the same folder as your memory database, and likewise
# gitignored, since it's personal configuration, not source code.
#
# WHY A SEPARATE FILE FROM settings.py: settings.py's AI_SYSTEM_PROMPT
# is the DEFAULT personality JARVIS ships with. This file holds your
# OVERRIDE of it (or None, meaning "use the default"). Keeping them
# separate means updating JARVIS's code never overwrites something you
# personally customized.

import json
from pathlib import Path

from jarvis.utils.logger import get_logger

logger = get_logger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_SETTINGS_PATH = _PROJECT_ROOT / "data" / "user_settings.json"

# The only settings this file manages. Adding a new adjustable setting
# means adding it here AND actually wiring it into the Settings window
# and main.py — no unused/half-wired fields.
_DEFAULTS = {
    "personality": None,  # None means "use AI_SYSTEM_PROMPT from settings.py"
    "voice_rate": 175,  # Words per minute — matches VoiceOutput's own default
    "voice_volume": 1.0,  # 0.0 (silent) to 1.0 (full volume)
    "offline_speech_recognition": False,  # True = local Vosk model, no internet needed
}


class UserSettings:
    """
    Loads, holds, and saves the user's personal JARVIS preferences.
    """

    def __init__(self, settings_path: Path = None):
        """
        Args:
            settings_path: Where the settings JSON file lives. Defaults
                to data/user_settings.json in the project root.
        """
        self._path = settings_path or _DEFAULT_SETTINGS_PATH
        self._values = dict(_DEFAULTS)
        self._load()

    def _load(self) -> None:
        """
        Load saved settings from disk, if the file exists. If it's
        missing (first run) or corrupted somehow, we fall back to
        defaults rather than crashing the whole app over a settings file.
        """
        if not self._path.exists():
            return

        try:
            with open(self._path, "r", encoding="utf-8") as file:
                saved_values = json.load(file)
            # Only accept keys we actually recognize — protects against
            # a manually-edited or corrupted file introducing garbage
            # keys that nothing in the app expects.
            for key, value in saved_values.items():
                if key in _DEFAULTS:
                    self._values[key] = value
            logger.info("Loaded user settings from %s", self._path)
        except (json.JSONDecodeError, OSError) as error:
            logger.warning(
                "Could not load user settings (%s) — using defaults instead.", error
            )

    def save(self) -> None:
        """Write the current settings to disk, creating data/ if needed."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as file:
            json.dump(self._values, file, indent=2)
        logger.info("Saved user settings to %s", self._path)

    def get(self, key: str):
        """Get a setting's current value (falls back to its default if unset)."""
        return self._values.get(key, _DEFAULTS.get(key))

    def set(self, key: str, value) -> None:
        """
        Set a setting's value (in memory only — call save() to persist it).

        Raises:
            KeyError: if key isn't a recognized setting, to catch typos
                early rather than silently storing an ignored value.
        """
        if key not in _DEFAULTS:
            raise KeyError(f"Unknown setting: '{key}'")
        self._values[key] = value

    def reset_to_defaults(self) -> None:
        """Reset every setting back to its built-in default (in memory only)."""
        self._values = dict(_DEFAULTS)
        logger.info("User settings reset to defaults.")

    def get_effective_personality(self, fallback: str) -> str:
        """
        Convenience helper: returns the user's custom personality text
        if they've set one, otherwise the given fallback (normally
        AI_SYSTEM_PROMPT from config/settings.py).
        """
        custom = self.get("personality")
        return custom if custom else fallback
