#!/usr/bin/env python3
"""
CodeTantra SEA — Exam Autopilot
================================
Fully automated exam solver:
  1. Spawns the app via Frida (bypasses integrity checks)
  2. Waits for you to log in (90 seconds)
  3. Extracts each question via Ctrl+A/Ctrl+C
  4. Sends to Gemini API for solving
  5. Types solution using uinput virtual keyboard (undetectable)
  6. Waits for you to Submit + click Next
  7. Repeats for up to 50 questions

Usage:
  export GEMINI_API_KEY="your-key"
  sudo sysctl -w kernel.yama.ptrace_scope=0
  python3 -u src/autopilot.py
"""

import frida
import time
import os
import sys
import subprocess
import threading
import signal
import random
import traceback
import hashlib

# Resolve paths relative to repo root
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

from human_typer import HumanTyper
from gemini_solver import GeminiSolver

# ═══════════════════════════════════════
# Configuration
# ═══════════════════════════════════════
APP_EXECUTABLE = os.path.join(REPO_ROOT, "app/opt/CodeTantra SEA/codetantra-sea")
MAIN_PATCH = os.path.join(REPO_ROOT, "patches/main_patch.js")
LOG_DIR = os.path.join(REPO_ROOT, "logs")
CONFIG_DIR = os.path.join(REPO_ROOT, "config")

LOGIN_WAIT = 90       # Seconds to wait for login
WPM_TARGET = 40       # Typing speed (35-45 WPM effective range)
ERROR_RATE = 0.012    # Typo frequency (~1.2%)
MAX_QUESTIONS = 50    # Max questions to solve

main_pid = None
device = None
running = True


# ═══════════════════════════════════════
# Voice + Logging
# ═══════════════════════════════════════
def speak(text):
    """Voice announcements via espeak."""
    for cmd in [
        ["espeak-ng", "-s", "160", "-a", "200", text],
        ["espeak", "-s", "160", text],
    ]:
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except FileNotFoundError:
            continue
    print(f"\a💬 {text}", flush=True)


def beep(n=1):
    for _ in range(n):
        print("\a", end="", flush=True)
        time.sleep(0.15)


def clog(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ═══════════════════════════════════════
# Window helpers
# ═══════════════════════════════════════
def find_ct_window():
    """Find the CodeTantra window. Returns window ID or None."""
    for _ in range(3):
        try:
            r = subprocess.run(
                ["xdotool", "search", "--name", "CodeTantra"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0 and r.stdout.strip():
                wins = [w.strip() for w in r.stdout.strip().split("\n") if w.strip()]
                if wins:
                    return wins[-1]
        except Exception:
            pass
        time.sleep(1)
    return None


def get_window_size(wid):
    """Get window width and height."""
    try:
        r = subprocess.run(["xdotool", "getwindowgeometry", wid],
                          capture_output=True, text=True, timeout=3)
        for line in r.stdout.split("\n"):
            if "Geometry" in line:
                g = line.split(":")[1].strip()
                w, h = map(int, g.split("x"))
                return w, h
    except Exception:
        pass
    return 1920, 1080


def activate_window(wid):
    """Bring window to front and focus it."""
    subprocess.run(["xdotool", "windowactivate", "--sync", wid],
                  timeout=5, capture_output=True)
    time.sleep(0.3)


# ═══════════════════════════════════════
# Click helpers
# ═══════════════════════════════════════
def click_at(wid, x_pct, y_pct, description=""):
    """Click at %-based position within the window."""
    w, h = get_window_size(wid)
    x = int(w * x_pct)
    y = int(h * y_pct)
    clog(f"  click: {description} ({x},{y}) in {w}x{h}")

    subprocess.run(["xdotool", "mousemove", "--window", wid, str(x), str(y)],
                  timeout=3, capture_output=True)
    time.sleep(0.15)
    subprocess.run(["xdotool", "click", "--window", wid, "1"],
                  timeout=3, capture_output=True)
    time.sleep(0.5)


def click_editor(wid):
    """Click inside the code editor area."""
    click_at(wid, 0.70, 0.45, "Editor")


# ═══════════════════════════════════════
# Text extraction
# ═══════════════════════════════════════
def extract_text(wid, retries=2):
    """Extract text from the active page via Ctrl+A → Ctrl+C."""
    for attempt in range(retries + 1):
        try:
            activate_window(wid)
            time.sleep(0.3)

            if attempt > 0:
                click_at(wid, 0.25, 0.40, "QuestionPanel")
                time.sleep(0.4)

            subprocess.run(["xdotool", "key", "ctrl+a"], timeout=2, capture_output=True)
            time.sleep(0.3)
            subprocess.run(["xdotool", "key", "ctrl+c"], timeout=2, capture_output=True)
            time.sleep(0.4)

            clip = subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
                capture_output=True, text=True, timeout=3,
            )
            subprocess.run(["xdotool", "key", "Escape"], timeout=2, capture_output=True)

            text = clip.stdout if clip.returncode == 0 else ""
            if text and len(text) > 30:
                return text

            clog(f"  extract attempt {attempt+1}: {len(text)} chars")
            time.sleep(2)
        except Exception as ex:
            clog(f"  extract error: {ex}")
            time.sleep(1)
    return ""


# ═══════════════════════════════════════
# Editor operations
# ═══════════════════════════════════════
def clear_editor(wid):
    """Clear the code editor content."""
    click_editor(wid)
    time.sleep(0.3)
    subprocess.run(["xdotool", "key", "--window", wid, "ctrl+a"], timeout=3, capture_output=True)
    time.sleep(0.2)
    subprocess.run(["xdotool", "key", "--window", wid, "Delete"], timeout=3, capture_output=True)
    time.sleep(0.3)


def type_solution(wid, code):
    """Type solution into the editor using human-like timing."""
    click_editor(wid)
    time.sleep(0.3)
    clear_editor(wid)
    time.sleep(0.5)

    typer = HumanTyper(wpm_target=WPM_TARGET, error_rate=ERROR_RATE)

    def progress(typed, total):
        pct = typed / total * 100
        clog(f"  [{pct:.0f}%] {typed}/{total}")

    actual_wpm = typer.type_text(code, callback=progress)
    typer.close()
    return actual_wpm


# ═══════════════════════════════════════
# Question fingerprint (for deduplication)
# ═══════════════════════════════════════
def text_fingerprint(text):
    """Create a fingerprint of question text to detect duplicates."""
    clean = text.lower().strip()
    for noise in ["search course", "type to search", "minimum 3 characters",
                   "#type your code here", "sample test cases"]:
        clean = clean.replace(noise, "")
    return hashlib.md5(clean.encode()).hexdigest()[:16]


# ═══════════════════════════════════════
# Main autopilot loop
# ═══════════════════════════════════════
def autopilot():
    global running

    speak("App launched. 90 seconds to log in and open the first question.")
    clog(f"AUTOPILOT: {LOGIN_WAIT}s countdown.")

    # Countdown
    for elapsed in range(LOGIN_WAIT):
        if not running:
            return
        remaining = LOGIN_WAIT - elapsed
        if remaining == 60:
            speak("60 seconds.")
        elif remaining == 30:
            speak("30 seconds. Open a question.")
        elif remaining == 10:
            speak("10 seconds.")
            beep(1)
        elif 1 <= remaining <= 5:
            speak(str(remaining))
        time.sleep(1)

    if not running:
        return

    # Init Gemini
    speak("Starting Gemini.")
    try:
        solver = GeminiSolver()
        clog("✓ Gemini ready")
    except Exception as ex:
        speak("Gemini failed. Check A P I key.")
        clog(f"Gemini error: {ex}")
        return

    # ══════════════════════════════════════
    # QUESTION LOOP
    # ══════════════════════════════════════
    seen_fingerprints = set()
    question_num = 0
    consecutive_failures = 0
    solved_count = 0

    while running and question_num < MAX_QUESTIONS:
        question_num += 1
        clog(f"\n{'='*50}")
        clog(f"QUESTION {question_num} (solved: {solved_count})")
        clog(f"{'='*50}")
        speak(f"Question {question_num}.")

        try:
            # Find window
            wid = find_ct_window()
            if not wid:
                speak("No window.")
                consecutive_failures += 1
                if consecutive_failures >= 5:
                    speak("Too many failures. Stopping.")
                    break
                time.sleep(5)
                continue

            # Extract
            speak("Extracting.")
            clog("  [1/3] Extracting...")
            time.sleep(2)

            text = extract_text(wid)
            if not text or len(text) < 30:
                speak("Extraction failed. Click next. Auto-continuing in 8 seconds.")
                clog(f"  ✗ Got {len(text)} chars")
                consecutive_failures += 1
                if consecutive_failures >= 5:
                    speak("Too many failures. Stopping.")
                    break
                clog("  ⏳ Waiting 8s for you to click Next...")
                time.sleep(8)
                continue

            # Dedup check
            fp = text_fingerprint(text)
            clog(f"  Fingerprint: {fp}")
            if fp in seen_fingerprints:
                speak("Same question. Click next. Auto-continuing in 8 seconds.")
                clog(f"  ⚠ DUPLICATE — skipping")
                clog("  ⏳ Waiting 8s for you to click Next...")
                time.sleep(8)
                continue
            seen_fingerprints.add(fp)

            # Save raw text
            ts = time.strftime("%Y%m%d_%H%M%S")
            qpath = os.path.join(LOG_DIR, f"q{question_num:02d}_{ts}.txt")
            with open(qpath, "w") as f:
                f.write(text)
            clog(f"  ✓ {len(text)} chars → {qpath}")

            # Solve with Gemini
            speak("Solving with Gemini.")
            clog("  [2/3] Gemini...")

            lang = solver.detect_language(text)
            clog(f"  Language: {lang}")

            code = solver.solve(text, language_hint=lang)
            if not code:
                speak("Gemini failed. Click next. Auto-continuing in 8 seconds.")
                clog("  ✗ No solution")
                consecutive_failures += 1
                clog("  ⏳ Waiting 8s for you to click Next...")
                time.sleep(8)
                continue

            # Save solution
            spath = os.path.join(LOG_DIR, f"s{question_num:02d}_{ts}.txt")
            with open(spath, "w") as f:
                f.write(code)
            clog(f"  ✓ {len(code)} chars, {code.count(chr(10))+1} lines")
            clog(f"  Code: {code[:80].replace(chr(10), ' ')}")

            # Type it
            speak("Typing now. Do not touch anything.")
            clog(f"  [3/3] Typing {len(code)} chars...")

            wid = find_ct_window()
            if not wid:
                speak("Window lost.")
                continue

            activate_window(wid)
            actual_wpm = type_solution(wid, code)
            clog(f"  ✓ {actual_wpm:.0f} WPM")

            # Done — user handles Submit + Next
            consecutive_failures = 0
            solved_count += 1
            clog(f"  ✅ Question {question_num} DONE! ({solved_count} solved)")
            speak("Done! Submit and open next question. Auto-continuing in 30 seconds.")
            beep(2)
            clog("  ⏳ Waiting 30s for you to Submit + Next...")
            time.sleep(30)

        except Exception as ex:
            clog(f"  ✗ ERROR: {ex}")
            clog(traceback.format_exc())
            speak("Error. Click next. Auto-continuing in 8 seconds.")
            consecutive_failures += 1

            if consecutive_failures >= 5:
                speak("Too many failures. Stopping.")
                break

            clog("  ⏳ Waiting 8s for you to click Next...")
            time.sleep(8)

    speak(f"Autopilot done. Solved {solved_count} of {question_num} questions.")
    clog(f"DONE: {solved_count}/{question_num}")
    beep(3)


# ═══════════════════════════════════════
# Frida message handler
# ═══════════════════════════════════════
def on_frida_msg(message, data):
    if message["type"] == "send":
        p = message["payload"]
        txt = p.get("data", str(p)) if isinstance(p, dict) else str(p)
        clog(f"  FRIDA: {txt[:120]}")
    elif message["type"] == "error":
        clog(f"  FRIDA ERROR: {message.get('description','')[:120]}")


# ═══════════════════════════════════════
# Cleanup
# ═══════════════════════════════════════
def cleanup(signum=None, frame=None):
    global running
    running = False
    try:
        if main_pid:
            device.kill(main_pid)
    except Exception:
        pass
    subprocess.run(["pkill", "-9", "-f", "codetantra-sea"], stderr=subprocess.DEVNULL)
    clog("Cleaned up.")
    sys.exit(0)


signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)


# ═══════════════════════════════════════
# Entry point
# ═══════════════════════════════════════
if __name__ == "__main__":
    print("""
╔═══════════════════════════════════════════════════════╗
║     CodeTantra SEA — Exam Autopilot                   ║
║                                                       ║
║  ✓ Frida spawn + integrity/immortality patches        ║
║  ✓ Extract → Gemini AI → Human-like typing            ║
║  ✓ Voice guidance (espeak)                            ║
║  ✓ YOU click Submit & Next (30s auto-continue)        ║
║  ✓ uinput virtual keyboard (kernel-level, trusted)    ║
╚═══════════════════════════════════════════════════════╝
""", flush=True)

    # ── Pre-flight checks ──
    if not os.path.exists("/dev/uinput"):
        clog("Loading uinput module...")
        subprocess.run(["sudo", "-n", "modprobe", "uinput"], capture_output=True)
        time.sleep(0.5)
    if not os.path.exists("/dev/uinput"):
        print("ERROR: /dev/uinput missing. Run: sudo modprobe uinput", file=sys.stderr)
        sys.exit(1)

    if not os.access("/dev/uinput", os.W_OK):
        clog("Setting /dev/uinput permissions...")
        subprocess.run(["sudo", "-n", "chmod", "666", "/dev/uinput"], capture_output=True)
        time.sleep(0.3)
    if not os.access("/dev/uinput", os.W_OK):
        print("ERROR: /dev/uinput not writable. Run: sudo chmod 666 /dev/uinput", file=sys.stderr)
        sys.exit(1)

    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY not set → export GEMINI_API_KEY='your-key'", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(APP_EXECUTABLE):
        print(f"ERROR: App not found at {APP_EXECUTABLE}", file=sys.stderr)
        print("  Run setup.sh first to extract the app binary.", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(MAIN_PATCH):
        print(f"ERROR: Frida patch not found at {MAIN_PATCH}", file=sys.stderr)
        sys.exit(1)

    clog("✓ Pre-flight OK")
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(CONFIG_DIR, exist_ok=True)
    subprocess.run(["pkill", "-9", "-f", "codetantra-sea"], stderr=subprocess.DEVNULL)
    time.sleep(1)

    # ── Frida spawn ──
    device = frida.get_local_device()
    clog(f"Frida: {device.name}")

    home = os.path.expanduser("~")
    env = {
        "DISPLAY": os.environ.get("DISPLAY", ":0.0"),
        "HOME": home,
        "USER": os.environ.get("USER", "kali"),
        "LOGNAME": os.environ.get("LOGNAME", "kali"),
        "XDG_CONFIG_HOME": CONFIG_DIR,
        "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"),
        "DBUS_SESSION_BUS_ADDRESS": os.environ.get(
            "DBUS_SESSION_BUS_ADDRESS", f"unix:path=/run/user/{os.getuid()}/bus"
        ),
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "XAUTHORITY": os.environ.get("XAUTHORITY", f"{home}/.Xauthority"),
        "SHELL": "/bin/bash",
    }

    clog("[1/3] Spawning app...")
    try:
        main_pid = device.spawn([APP_EXECUTABLE, "--no-sandbox"], env=env)
    except Exception as ex:
        clog(f"FATAL: {ex}")
        sys.exit(1)
    clog(f"      PID: {main_pid}")

    clog("[2/3] Applying patches...")
    session = device.attach(main_pid)
    with open(MAIN_PATCH) as f:
        script = session.create_script(f.read())
    script.on("message", on_frida_msg)
    script.load()
    clog("      ✓ Patched")
    time.sleep(0.5)

    clog("[3/3] Resuming app...")
    threading.Thread(target=autopilot, daemon=True).start()
    device.resume(main_pid)
    clog("      ✓ Running!")
    clog("=" * 60)
    clog(f"🔑 LOG IN NOW — {LOGIN_WAIT}s to open first question")
    clog("   Autopilot handles everything after that.")
    clog("=" * 60)

    try:
        while running:
            try:
                os.kill(main_pid, 0)
            except OSError:
                clog("App terminated.")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    cleanup()
