# JARVIS — Personal AI Assistant

A production-quality personal AI assistant, built in Python, inspired by
Iron Man's JARVIS. This project is being built incrementally, one phase
at a time.

## Current Status: Phase 4 — Voice Input, Voice Output & Wake Word

Phases 1-3 built the foundation, the window, and real AI chat. Phase 4
adds:
- **Voice output** — JARVIS can speak its replies out loud (fully
  offline, via your OS's built-in speech engine)
- **Voice input** — click the 🎤 button to speak a command instead of
  typing (requires internet — uses Google's free speech-to-text)
- **Wake word** — toggle "Wake word" on, then just say "Jarvis" and
  your next sentence to trigger a response hands-free

**Known trade-off:** voice input is NOT offline (voice output is).
Making voice input fully offline is possible in a later phase by
swapping in a different speech-recognition engine — this file
(`core/voice_input.py`) is the only place that would need to change.

### Platform-specific setup for voice features

**PyAudio (microphone access)** can be the trickiest part to install:
- **Windows:** `pip install pyaudio` usually works directly.
- **macOS:** install PortAudio first: `brew install portaudio`, then
  `pip install pyaudio`.
- **Linux:** install PortAudio's dev headers first:
  `sudo apt install portaudio19-dev`, then `pip install pyaudio`.

**Text-to-speech (pyttsx3) on Linux specifically:** requires
`espeak-ng` (NOT the older `espeak` package — they use different voice
naming and pyttsx3 will crash on plain `espeak`). Install it with:
`sudo apt install espeak-ng`. Windows and macOS use their built-in
speech engines and need no extra install.

If voice input or output can't be set up on your machine (no
microphone/speakers, or a missing dependency), JARVIS will still run —
it just runs in text-only mode and logs a warning explaining why.

### API key setup (still required, from Phase 3)
1. Get a key at https://console.anthropic.com/ (Settings → API Keys)
2. Copy `.env.example` to a new file named `.env` in the project root
3. Paste your real key into `.env`, replacing the placeholder text
4. `.env` is already excluded from git (see `.gitignore`) — it will
   never be accidentally pushed to GitHub

## Project Structure

```
Jarvis-Assistant/
├── src/
│   └── jarvis/
│       ├── main.py          # Entry point — run this file to start the app
│       ├── config/
│       │   └── settings.py  # App-wide constants and configuration
│       ├── core/
│       │   ├── ai_engine.py    # Talks to Claude API, manages conversation memory
│       │   ├── voice_input.py  # Microphone capture + speech-to-text
│       │   ├── voice_output.py # Text-to-speech (offline)
│       │   └── wake_word.py    # Background "Jarvis" wake-word listener
│       ├── ui/
│       │   └── main_window.py # The desktop window (chat display, input box)
│       └── utils/
│           └── logger.py     # Shared logging setup
├── tests/                     # Automated tests
├── docs/                      # Project documentation
├── requirements.txt           # External Python packages this project needs
├── .gitignore                 # Files git should never track
└── README.md                  # This file
```

## How to Run Phase 1

These steps assume Python 3.10+ is installed on your machine.

1. **Open a terminal in the project folder** (the folder containing this
   README).

2. **Create a virtual environment** (an isolated space for this project's
   Python packages, separate from the rest of your system):

   ```
   python -m venv venv
   ```

3. **Activate the virtual environment:**

   - Windows: `venv\Scripts\activate`
   - macOS/Linux: `source venv/bin/activate`

   Your terminal prompt should now show `(venv)` at the start of the line.

4. **Install dependencies** (Phase 1 has none yet, but this is the command
   you'll use from here on as we add packages):

   ```
   pip install -r requirements.txt
   ```

5. **Run the app:**

   ```
   python -m src.jarvis.main
   ```

   You should see a startup banner, the JARVIS window open, and (new in
   Phase 4) a "Speak replies" toggle and a 🎤 mic button. Try:
   - Typing a message as before
   - Clicking 🎤 and speaking a command instead
   - Turning on "Speak replies" so JARVIS talks back
   - Turning on "Wake word" and saying "Jarvis, [your question]"

## Development Roadmap

| Phase | Focus |
|-------|-------|
| 1 | Architecture, folder structure, first working app |
| 2 | Graphical desktop interface |
| 3 | AI chat |
| 4 | Voice input/output + wake word *(current)* |
| 4 | Voice input/output + wake word |
| 5 | Automation (open apps, websites, files) |
| 6 | Memory (conversation history) |
| 7 | Plugins/modules |
| 8 | Advanced automation (Windows control, terminal commands) |
