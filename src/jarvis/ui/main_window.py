# src/jarvis/ui/main_window.py
#
# WHY THIS FILE EXISTS:
# This is the visual "face" of JARVIS — the window you actually see and
# click on. It uses CustomTkinter, a library that adds a modern look
# (rounded corners, dark mode, clean fonts) on top of Python's built-in
# Tkinter GUI toolkit.
#
# IMPORTANT DESIGN DECISION — read this before touching this file later:
# This window does NOT know how to think, reason, or respond intelligently.
# It only knows how to:
#   1. Display messages in the chat area
#   2. Notice when you type something and press Send / Enter
#   3. Hand your message off to a "callback" function (given to it from
#      outside — see on_user_message below)
#
# This keeps the UI decoupled from the "brain" (added in core/ during
# Phase 3). When we add real AI reasoning, we won't touch this file at
# all — we'll just pass in a smarter callback function from main.py.

import customtkinter as ctk
from typing import Callable

from jarvis.utils.logger import get_logger

logger = get_logger(__name__)

# Appearance settings applied once, globally, before any window is created.
# "dark" mode and a blue accent color give the modern look we want.
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class MainWindow(ctk.CTk):
    """
    The main JARVIS application window.

    This class represents the entire visible app: title bar, scrollable
    chat history, a text input box, and a Send button.
    """

    def __init__(self, on_user_message: Callable[[str], str]):
        """
        Args:
            on_user_message: A function that takes the user's typed message
                (a string) and returns JARVIS's reply (a string). This
                window does not care HOW the reply is generated — in
                Phase 2 it will be a simple echo function; in Phase 3
                it becomes the real AI. This is the "callback" pattern
                mentioned above.
        """
        super().__init__()

        # Store the callback so button clicks / Enter key presses can use it.
        self._on_user_message = on_user_message

        # --- Window setup ---
        self.title("JARVIS — Personal AI Assistant")
        self.geometry("700x600")
        self.minsize(500, 400)

        # Make the chat area expand to fill the window when resized.
        # (Row 0 = chat history, should grow; Row 1 = input bar, fixed height.)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_chat_area()
        self._build_input_bar()

        logger.info("MainWindow initialized.")

    def _build_chat_area(self) -> None:
        """
        Create the scrollable text box that displays the conversation
        history. It is READ-ONLY from the user's perspective — they can't
        type directly into it, only we (the code) write into it.
        """
        self.chat_display = ctk.CTkTextbox(
            self,
            wrap="word",          # Wrap long lines at word boundaries, not mid-word
            state="disabled",     # Starts locked so the user can't type into it directly
            font=ctk.CTkFont(size=14),
            corner_radius=10,
        )
        self.chat_display.grid(row=0, column=0, padx=15, pady=(15, 5), sticky="nsew")

        # Greet the user immediately so the window doesn't look empty/broken.
        self._append_message("JARVIS", "Systems online. How can I help you?")

    def _build_input_bar(self) -> None:
        """
        Create the bottom row: a text entry box and a Send button,
        side by side, docked to the bottom of the window.
        """
        input_frame = ctk.CTkFrame(self, fg_color="transparent")
        input_frame.grid(row=1, column=0, padx=15, pady=(5, 15), sticky="ew")

        # The input box should stretch to fill available space;
        # the Send button stays a fixed width.
        input_frame.grid_columnconfigure(0, weight=1)

        self.input_box = ctk.CTkEntry(
            input_frame,
            placeholder_text="Type a message to JARVIS...",
            font=ctk.CTkFont(size=14),
            height=40,
        )
        self.input_box.grid(row=0, column=0, padx=(0, 10), sticky="ew")

        # Pressing Enter while focused on the input box also sends the message,
        # so the user isn't forced to click the button every time.
        self.input_box.bind("<Return>", lambda event: self._handle_send())

        self.send_button = ctk.CTkButton(
            input_frame,
            text="Send",
            width=80,
            height=40,
            command=self._handle_send,
        )
        self.send_button.grid(row=0, column=1)

    def _handle_send(self) -> None:
        """
        Called when the user clicks Send or presses Enter.

        Steps:
          1. Read the text from the input box.
          2. Ignore it if it's empty (no point sending nothing).
          3. Display the user's message in the chat area.
          4. Clear the input box for the next message.
          5. Call the callback to get JARVIS's reply, and display that too.
        """
        message = self.input_box.get().strip()

        if not message:
            return  # Nothing typed — do nothing, rather than sending a blank message.

        self._append_message("You", message)
        self.input_box.delete(0, "end")

        logger.info("User message received: %s", message)

        # This is where Phase 2's simple echo (or Phase 3's real AI) gets called.
        # The window doesn't know or care which one it is.
        reply = self._on_user_message(message)

        self._append_message("JARVIS", reply)

    def _append_message(self, sender: str, message: str) -> None:
        """
        Add a new line to the chat display.

        The textbox is normally "disabled" (read-only) so the user can't
        type into it directly. We briefly re-enable it, insert the new
        text, then disable it again — this is the standard Tkinter pattern
        for a read-only-but-programmatically-updatable text widget.
        """
        self.chat_display.configure(state="normal")
        self.chat_display.insert("end", f"{sender}: {message}\n\n")
        self.chat_display.configure(state="disabled")

        # Auto-scroll to the bottom so the newest message is always visible.
        self.chat_display.see("end")
