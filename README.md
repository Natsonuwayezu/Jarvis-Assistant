# JARVIS — Personal AI Assistant

A production-quality personal AI assistant, built in Python, inspired by
Iron Man's JARVIS. This project is being built incrementally, one phase
at a time.

## Current Status: Phase 2 — Graphical Interface

Phase 1 proved the project skeleton works: folder structure, virtual
environment, logging, and a runnable entry point.

Phase 2 adds a real desktop window (built with CustomTkinter): a chat
history area, a text input box, and a Send button. Typing a message and
pressing Send/Enter currently gets you an ECHO reply — there's no real
AI thinking yet. That's Phase 3. The point of Phase 2 is to prove the
window itself works end-to-end before we plug in real intelligence.

## Project Structure

```
Jarvis-Assistant/
├── src/
│   └── jarvis/
│       ├── main.py          # Entry point — run this file to start the app
│       ├── config/
│       │   └── settings.py  # App-wide constants and configuration
│       ├── core/             # (Phase 3+) AI reasoning, conversation engine
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

   You should see a startup banner printed in the terminal, a new
   `logs/jarvis.log` file appear in the project folder, AND (new in
   Phase 2) a dark-themed JARVIS window should open. Type a message and
   press Enter or click Send — you'll get an echo reply for now (real AI
   arrives in Phase 3).

## Development Roadmap

| Phase | Focus |
|-------|-------|
| 1 | Architecture, folder structure, first working app |
| 2 | Graphical desktop interface *(current)* |
| 3 | AI chat |
| 4 | Voice input/output + wake word |
| 5 | Automation (open apps, websites, files) |
| 6 | Memory (conversation history) |
| 7 | Plugins/modules |
| 8 | Advanced automation (Windows control, terminal commands) |
