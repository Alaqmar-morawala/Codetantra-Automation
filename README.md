# CodeTantra Autopilot

> **Fully automated exam solver for CodeTantra SEA** — Frida bypass + Gemini AI + undetectable typing

<p align="center">
  <img src="https://img.shields.io/badge/platform-Linux-blue?style=flat-square" alt="Linux">
  <img src="https://img.shields.io/badge/python-3.10+-green?style=flat-square" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/AI-Gemini%20API-orange?style=flat-square" alt="Gemini">
  <img src="https://img.shields.io/badge/status-working-brightgreen?style=flat-square" alt="Working">
</p>

## ⚡ What It Does

1. **Launches** the CodeTantra SEA app with Frida (bypasses integrity checks)
2. **Extracts** the question text from the exam page
3. **Solves** it using Google's Gemini AI
4. **Types** the solution using a kernel-level virtual keyboard (`uinput`)
5. **Waits** for you to Submit + click Next
6. **Repeats** for each question (up to 50)

The typing is **undetectable** — `uinput` generates real kernel input events that are indistinguishable from a physical keyboard. No clipboard paste, no injection.

## 🔧 Prerequisites

- **OS:** Linux (tested on Kali, Ubuntu, Debian)
- **Python:** 3.10+
- **Frida:** Runtime framework for dynamic instrumentation
- **uinput:** Linux kernel module for virtual input devices
- **xdotool:** X11 window automation
- **xclip:** Clipboard access
- **espeak-ng:** Voice feedback (optional but recommended)
- **Gemini API Key:** From [Google AI Studio](https://aistudio.google.com/)

## 📦 App Setup

The CodeTantra SEA app binary is **not included** in this repo (too large for GitHub). You need to download and extract it yourself.

### Step 1: Download the `.deb` Package

Get the CodeTantra SEA installer from your institution's portal. The file will be named something like:
```
codetantra-sea_4.3.0_amd64.deb
```

### Step 2: Extract the App

```bash
# From inside the repo directory:
mkdir -p app
dpkg-deb -x /path/to/codetantra-sea_*.deb app/
```

This extracts the Electron app to `app/opt/CodeTantra SEA/`.

### Step 3: Verify

```bash
ls -la "app/opt/CodeTantra SEA/codetantra-sea"
```

You should see the `codetantra-sea` binary (~194 MB). If the binary is at a different path, update the `APP_EXECUTABLE` variable in `src/autopilot.py`.

### Custom App Path

If your app version has a different directory structure, edit the path in `src/autopilot.py`:

```python
# Line ~37 — change this to match your extracted path
APP_EXECUTABLE = os.path.join(REPO_ROOT, "app/opt/CodeTantra SEA/codetantra-sea")
```

## 🚀 Quick Start

### 1. Clone & Setup
```bash
git clone https://github.com/Alaqmar-morawala/Codetantra-Automation.git
cd Codetantra-Automation
chmod +x setup.sh run.sh
./setup.sh
```

### 2. Download & Extract the App
```bash
# Place your .deb file in the repo, then:
mkdir -p app
dpkg-deb -x codetantra-sea_*.deb app/
```

### 3. Set Your API Key
```bash
export GEMINI_API_KEY="your-gemini-api-key-here"
```

### 4. Run
```bash
./run.sh
```

That's it. Log in within 90 seconds, open the first question, and the autopilot takes over.

## 📁 Project Structure

```
codetantra-autopilot/
├── README.md                  # This file
├── setup.sh                   # One-click dependency installer
├── run.sh                     # One-click launcher
├── requirements.txt           # Python dependencies
│
├── src/
│   ├── autopilot.py           # Main automation loop
│   ├── human_typer.py         # uinput virtual keyboard with human timing
│   └── gemini_solver.py       # Gemini API question solver
│
├── patches/
│   └── main_patch.js          # Frida patch (integrity + immortality bypass)
│
├── app/                       # CodeTantra SEA binary (extracted)
│   └── opt/CodeTantra SEA/
│
├── docs/
│   ├── HOW_IT_WORKS.md        # Technical deep-dive
│   ├── DETECTION_EVASION.md   # Anti-detection explained
│   └── TROUBLESHOOTING.md     # Common issues
│
├── config/                    # Electron config (created at runtime)
└── logs/                      # Question/solution logs (created at runtime)
```

## ⚙️ Configuration

Edit the constants at the top of `src/autopilot.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `LOGIN_WAIT` | `90` | Seconds to wait for login |
| `WPM_TARGET` | `40` | Typing speed (words per minute) |
| `ERROR_RATE` | `0.012` | Typo frequency (~1.2%) |
| `MAX_QUESTIONS` | `50` | Max questions to auto-solve |

## 🧠 How It Works

### Frida Bypass
The app has integrity checks that prevent tampering. We use Frida to:
- Patch `InternalVerifyIntegrity` → immediate `RET`
- Patch `exit`/`abort` in libc → `RET` (immortality)

### Question Extraction
- `Ctrl+A` → `Ctrl+C` to copy all visible text
- Text fingerprinting for deduplication (MD5-based)

### Gemini AI Solving
- Sends the raw extracted text (with UI noise) to Gemini
- Auto-detects language from file extensions (`.c`, `.java`, `.py`, etc.)
- Returns clean, compilable solution code

### Human-Like Typing
The `uinput` virtual keyboard types with:
- **Gaussian dwell times** (key hold duration varies naturally)
- **Digraph-aware flight times** (common letter pairs type faster)
- **Burst-pause model** (types in bursts, pauses between)
- **Think breaks** (2-6s pauses every 80-200 chars)
- **Occasional typos** with backspace corrections
- **Line-end pauses** (30% chance of 1-3s pause after newlines)

## ⚠️ Disclaimer

This tool is for **educational and security research purposes only**. Using it to cheat on actual exams violates academic integrity policies and may result in disciplinary action. The authors are not responsible for any misuse.

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
