# Detection Evasion

## Threat Model

CodeTantra SEA uses multiple layers of detection:

| Layer | What It Checks | Our Bypass |
|-------|---------------|------------|
| **Client: Integrity** | ASAR hash validation | Frida patches `InternalVerifyIntegrity` → `RET` |
| **Client: Exit** | Server-commanded termination | Frida patches `exit`/`abort` → `RET` |
| **Server: Keystroke** | Typing pattern analysis | Human-like timing model (uinput) |
| **Server: Speed** | Suspicious WPM | 35-45 WPM with natural variation |
| **Server: Account** | Flagged accounts | Use fresh, unflagged accounts |

## Key Design Decisions

### uinput Over Alternatives

| Method | Detectable? | Why |
|--------|-------------|-----|
| Clipboard paste (`Ctrl+V`) | ✅ Trivial | No keyDown events, instant appear |
| JavaScript injection | ✅ Easy | `isTrusted=false` on all events |
| xdotool key simulation | ⚠️ Possible | X11 synthetic events may differ |
| **uinput virtual keyboard** | ❌ Undetectable | Real kernel events, `isTrusted=true` |

### Typing Speed: 40 WPM

- A typical student types 30-50 WPM for code
- Our effective range (35-45) with Gaussian variation looks natural
- Too fast (60+ WPM) triggers speed heuristics
- Too slow (<25 WPM) looks suspicious for simple boilerplate

### Think Breaks

Real humans don't type continuously:
- Pause to read the next line of code they're writing
- Stop to think about logic
- Rest between logical blocks

We simulate this with:
- **2-6 second pauses** every 80-200 characters
- **1-3 second pauses** after ~30% of newlines

### Code Formatting

We do NOT strip indentation, comments, or braces. The code is typed **exactly as Gemini generates it**, which looks natural because:
- Properly indented C/Java code is expected
- Comments show "thinking process"
- Blank lines between functions are normal

### Error Rate

A 1.2% typo rate with backspace corrections makes the typing pattern more realistic. Real humans make ~2-5% errors; we stay on the low end to avoid breaking the code.

## What Can Still Get You Caught

1. **Account flagging**: If a previous session was detected, the server may flag the account permanently. Always use fresh accounts.
2. **Session timing**: If you solve 50 questions in 30 minutes, that's suspicious regardless of typing patterns. Take breaks.
3. **Code similarity**: If Gemini generates solutions identical to other students using the same tool, that's a plagiarism flag. This is outside our control.
4. **Camera monitoring**: If the exam has camera proctoring, the automation is visible on screen. Use a VM with the host screen showing something innocuous.
