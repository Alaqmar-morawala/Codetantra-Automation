# How It Works

## Architecture Overview

```
┌─────────────────────────────────────────────────┐
│                   autopilot.py                   │
│                                                  │
│  ┌──────────┐  ┌──────────────┐  ┌───────────┐  │
│  │  Frida   │→ │ Gemini API   │→ │  uinput   │  │
│  │  Spawn   │  │  Solver      │  │  Typer    │  │
│  └──────────┘  └──────────────┘  └───────────┘  │
│       ↓              ↓                ↓          │
│  Launch app    Solve question    Type solution   │
│  + patch it    (AI-powered)     (human-like)     │
└─────────────────────────────────────────────────┘
```

## Phase 1: App Launch + Patching

### Frida Spawn
The autopilot uses Frida to spawn the CodeTantra SEA Electron app in suspended state:

```python
main_pid = device.spawn([APP_EXECUTABLE, "--no-sandbox"], env=env)
```

Before resuming, it loads `main_patch.js` which performs two critical patches:

### Integrity Bypass
CodeTantra uses Electron's `InternalVerifyIntegrity` function to validate its ASAR archive hasn't been tampered with. We patch this function to `RET` immediately:

```javascript
const addr = mainModule.base.add(ptr("0x307e570"));
Memory.protect(addr, 8, 'rwx');
addr.writeU8(0xc3);  // x86 RET instruction
```

### Immortality Patch
The app can terminate itself via `exit()`, `_exit()`, `abort()`, or `_Exit()`. We patch all four in libc to `RET`:

```javascript
const targets = ['exit', '_exit', 'abort', '_Exit'];
for (const fname of targets) {
    const addr = Module.findExportByName(libcName, fname);
    addr.writeU8(0xc3);
}
```

This prevents the server from killing the app.

## Phase 2: Text Extraction

Once the user has logged in and opened a question, the autopilot extracts text:

1. Focus the CodeTantra window (`xdotool windowactivate`)
2. Select all text (`Ctrl+A`)
3. Copy to clipboard (`Ctrl+C`)
4. Read clipboard (`xclip -selection clipboard -o`)
5. Fingerprint the text (MD5 hash) to detect duplicate questions

## Phase 3: AI Solving

The extracted text (which includes UI noise from the page) is sent to Google's Gemini API:

- **Language detection**: Checks file extensions (`.c`, `.java`, `.py`) and keywords (`#include`, `scanf`, `System.out`)
- **Prompt engineering**: System prompt instructs Gemini to extract the question from noisy text and produce clean, compilable code
- **Retry logic**: Exponential backoff on API failures

## Phase 4: Human-Like Typing

The solution is typed character-by-character using a `uinput` virtual keyboard device:

### Why uinput?
- Creates a real `/dev/input/eventN` device in the Linux kernel
- Events are indistinguishable from a physical keyboard
- Shows as `AT-Translated-Set-2-keyboard` (standard laptop keyboard)
- All events have `isTrusted=true` in the browser
- No clipboard, no paste, no JavaScript injection

### Timing Model
- **Dwell time**: How long a key is held (Gaussian, mean=82ms, std=28ms)
- **Flight time**: Gap between keystrokes (based on target WPM)
- **Digraph awareness**: Common pairs like `th`, `he`, `in` type faster
- **Burst-pause**: Types 4-9 chars, then pauses 170-530ms
- **Think breaks**: Every 80-200 chars, pauses 2-6s
- **Line-end pauses**: 30% chance of 1-3s pause after newlines
- **Typo injection**: ~1.2% error rate with backspace correction

## Phase 5: Wait + Repeat

After typing completes:
1. Voice announces "Done! Submit and open next question"
2. Waits 30 seconds for user to click Submit, then Next
3. Auto-continues to extract the next question
4. Deduplicates via text fingerprinting (skips already-seen questions)
