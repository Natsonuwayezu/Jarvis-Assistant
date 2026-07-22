# src/jarvis/ui/settings_window.py
#
# WHY THIS FILE EXISTS:
# This is the in-app Settings window — lets you adjust JARVIS's
# personality (system prompt) and voice speed/volume WITHOUT ever
# opening a source file. It's a separate CTkToplevel window (a
# secondary window, not the main app window), opened from a button in
# MainWindow's status bar.
#
# DESIGN DECISION (same separation-of-concerns pattern as MainWindow):
# this window doesn't know HOW to apply a new personality or voice
# setting to the running AI engine or speech engine — it only knows
# how to read/write UserSettings (core/user_settings.py) and then call
# an `on_applied` callback, telling main.py "something changed, go
# apply it." main.py is the only place that knows AIEngine and
# VoiceOutput exist at all.

from typing import Callable

import customtkinter as ctk

from jarvis.core.user_settings import UserSettings
from jarvis.utils.logger import get_logger

logger = get_logger(__name__)


class SettingsWindow(ctk.CTkToplevel):
    """
    A secondary window for adjusting JARVIS's personality and voice
    speed/volume. Changes are saved to disk (via UserSettings) and
    applied to the currently-running app immediately on Save.
    """

    def __init__(self, user_settings: UserSettings, on_applied: Callable[[], None]):
        """
        Args:
            user_settings: The shared UserSettings instance to read
                current values from and write new ones to.
            on_applied: Called (with no arguments) after settings are
                saved, so main.py can push the new values into the
                running AIEngine and VoiceOutput. This window doesn't
                call those directly — it doesn't know they exist.
        """
        super().__init__()

        self._user_settings = user_settings
        self._on_applied = on_applied

        self.title("JARVIS Settings")
        self.geometry("520x600")
        self.minsize(420, 480)

        # Being a CTkToplevel (a secondary window), this makes it
        # appear "on top of" the main window and grabs input focus,
        # which is the standard, expected behavior for a settings
        # dialog — you shouldn't be able to interact with the main
        # chat window while this is open, to avoid confusing overlaps.
        self.transient()
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_personality_section()
        self._build_voice_section()
        self._build_buttons()

        logger.info("SettingsWindow opened.")

    def _build_personality_section(self) -> None:
        """
        A multi-line text box for editing JARVIS's personality/system
        prompt, pre-filled with the current effective value (custom
        override if set, otherwise the built-in default).
        """
        label = ctk.CTkLabel(
            self,
            text="Personality (system prompt)",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        )
        label.grid(row=0, column=0, padx=20, pady=(20, 5), sticky="ew")

        # Deliberately imported here (not at module load time) to avoid
        # a circular import: config/settings.py doesn't need to know
        # about this UI file, but this file needs the built-in default
        # text to show when no custom override is set.
        from jarvis.config.settings import AI_SYSTEM_PROMPT

        current_value = self._user_settings.get_effective_personality(AI_SYSTEM_PROMPT)

        self.personality_box = ctk.CTkTextbox(self, wrap="word", font=ctk.CTkFont(size=13))
        self.personality_box.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="nsew")
        self.personality_box.insert("1.0", current_value)

    def _build_voice_section(self) -> None:
        """
        Sliders for voice speed and volume, each with a live-updating
        label showing the current value as you drag.
        """
        voice_frame = ctk.CTkFrame(self, fg_color="transparent")
        voice_frame.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        voice_frame.grid_columnconfigure(0, weight=1)

        # --- Voice speed ---
        self.rate_label = ctk.CTkLabel(
            voice_frame, text=f"Voice Speed: {self._user_settings.get('voice_rate')} wpm", anchor="w"
        )
        self.rate_label.grid(row=0, column=0, sticky="ew")

        self.rate_slider = ctk.CTkSlider(
            voice_frame, from_=100, to=300, number_of_steps=40, command=self._on_rate_changed
        )
        self.rate_slider.set(self._user_settings.get("voice_rate"))
        self.rate_slider.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        # --- Voice volume ---
        self.volume_label = ctk.CTkLabel(
            voice_frame,
            text=f"Voice Volume: {int(self._user_settings.get('voice_volume') * 100)}%",
            anchor="w",
        )
        self.volume_label.grid(row=2, column=0, sticky="ew")

        self.volume_slider = ctk.CTkSlider(
            voice_frame, from_=0.0, to=1.0, number_of_steps=20, command=self._on_volume_changed
        )
        self.volume_slider.set(self._user_settings.get("voice_volume"))
        self.volume_slider.grid(row=3, column=0, sticky="ew")

        # --- Offline speech recognition ---
        self.offline_speech_switch = ctk.CTkSwitch(
            voice_frame,
            text="Offline speech recognition (local Vosk model, no internet)",
        )
        if self._user_settings.get("offline_speech_recognition"):
            self.offline_speech_switch.select()
        self.offline_speech_switch.grid(row=4, column=0, sticky="ew", pady=(15, 0))

        offline_note = ctk.CTkLabel(
            voice_frame,
            text=(
                "Requires a downloaded model (see README) — "
                "restart JARVIS after changing this for it to take effect."
            ),
            font=ctk.CTkFont(size=11),
            text_color="gray60",
            anchor="w",
            justify="left",
            wraplength=440,
        )
        offline_note.grid(row=5, column=0, sticky="ew", pady=(2, 0))

    def _build_buttons(self) -> None:
        """Save / Reset to Defaults / Cancel buttons along the bottom."""
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=3, column=0, padx=20, pady=20, sticky="ew")
        button_frame.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkButton(button_frame, text="Reset to Defaults", command=self._handle_reset).grid(
            row=0, column=0, padx=5, sticky="ew"
        )
        ctk.CTkButton(button_frame, text="Cancel", command=self.destroy).grid(
            row=0, column=1, padx=5, sticky="ew"
        )
        ctk.CTkButton(button_frame, text="Save", command=self._handle_save).grid(
            row=0, column=2, padx=5, sticky="ew"
        )

    def _on_rate_changed(self, value: float) -> None:
        """Live-update the speed label as the slider is dragged (not yet saved)."""
        self.rate_label.configure(text=f"Voice Speed: {int(value)} wpm")

    def _on_volume_changed(self, value: float) -> None:
        """Live-update the volume label as the slider is dragged (not yet saved)."""
        self.volume_label.configure(text=f"Voice Volume: {int(value * 100)}%")

    def _handle_save(self) -> None:
        """
        Read the current field values, save them via UserSettings, and
        tell main.py to apply them to the running app.
        """
        personality_text = self.personality_box.get("1.0", "end").strip()

        # An empty box means "use the built-in default" — we store None
        # rather than an empty string, matching how UserSettings and
        # AIEngine.set_system_prompt() both interpret "no override."
        self._user_settings.set("personality", personality_text or None)
        self._user_settings.set("voice_rate", int(self.rate_slider.get()))
        self._user_settings.set("voice_volume", round(self.volume_slider.get(), 2))
        self._user_settings.set(
            "offline_speech_recognition", bool(self.offline_speech_switch.get())
        )
        self._user_settings.save()

        logger.info("Settings saved from SettingsWindow.")

        self._on_applied()
        self.destroy()

    def _handle_reset(self) -> None:
        """
        Reset every setting to its built-in default, save that, refresh
        the displayed fields to match, and apply it to the running app
        immediately (consistent with Save — Reset is not a no-op preview).
        """
        from jarvis.config.settings import AI_SYSTEM_PROMPT

        self._user_settings.reset_to_defaults()
        self._user_settings.save()

        self.personality_box.delete("1.0", "end")
        self.personality_box.insert("1.0", AI_SYSTEM_PROMPT)

        self.rate_slider.set(self._user_settings.get("voice_rate"))
        self._on_rate_changed(self._user_settings.get("voice_rate"))

        self.volume_slider.set(self._user_settings.get("voice_volume"))
        self._on_volume_changed(self._user_settings.get("voice_volume"))

        self.offline_speech_switch.deselect()

        logger.info("Settings reset to defaults from SettingsWindow.")

        self._on_applied()
