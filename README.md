# JARVIS — Personal AI Assistant

A production-quality personal AI assistant, built in Python, inspired by
Iron Man's JARVIS. This project is being built incrementally, one phase
at a time.

## Current Status: Phase 3 — AI Chat

Phase 1 proved the project skeleton works. Phase 2 added a real desktop
window. Phase 3 replaces the echo placeholder with REAL AI reasoning,
powered by Anthropic's Claude API. JARVIS can now hold an actual
conversation (with in-session memory of what you've said so far in the
current run — persistent cross-session memory is Phase 6).

**Before running Phase 3, you need your own Anthropic API key:**
1. Get one at https://console.anthropic.com/ (Settings → API Keys)
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
│       │   └── ai_engine.py  # Talks to Claude API, manages conversation memory
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

   You should see a startup banner in the terminal, a `logs/jarvis.log`
   file appear, and the JARVIS window open. Type a real message and
   press Enter — JARVIS will now think and respond using Claude, not an
   echo. If you see an error about a missing API key, double-check step
   above about creating your `.env` file.

## Development Roadmap

| Phase | Focus |
|-------|-------|
| 1 | Architecture, folder structure, first working app |
| 2 | Graphical desktop interface |
| 3 | AI chat *(current)* |
| 4 | Voice input/output + wake word |
| 5 | Automation (open apps, websites, files) |
| 6 | Memory (conversation history) |
| 7 | Plugins/modules |
| 8 | Advanced automation (Windows control, terminal commands) |
