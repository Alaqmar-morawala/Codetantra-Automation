# Troubleshooting

## Common Issues

### `/dev/uinput` not found
```
ERROR: /dev/uinput missing
```
**Fix:**
```bash
sudo modprobe uinput
sudo chmod 666 /dev/uinput
```

### Frida fails to spawn
```
FATAL: need Gadget to attach on jailed Linux
```
**Fix:**
```bash
sudo sysctl -w kernel.yama.ptrace_scope=0
```

### Gemini API errors
```
Gemini FAILED after 3 attempts
```
**Possible causes:**
- API key not set: `export GEMINI_API_KEY="your-key"`
- Rate limited: wait a few seconds, the script auto-retries
- Invalid key: get a new one from [Google AI Studio](https://aistudio.google.com/)

### App terminates immediately
**Cause:** Account may be server-side flagged from previous detection.
**Fix:** Use a fresh, unflagged account. Clear the config directory:
```bash
rm -rf config/
mkdir config/
```

### Wrong language detected (C instead of Java)
**Cause:** `.class` file extension was matching `.c` check (fixed in latest version).
**Fix:** Pull the latest code. The `detect_language` function now correctly prioritizes `.java`/`.class` before `.c`.

### Typing goes to wrong window
**Cause:** xdotool couldn't find the CodeTantra window.
**Fix:** Make sure the CodeTantra window title contains "CodeTantra". The app must be visible (not minimized).

### Screen goes blank during typing
**Fix:** Disable screen blanking before running:
```bash
xset s off -dpms
```
The `run.sh` script does this automatically.

### VMware: Can I switch to host while typing?
**Yes.** The uinput keyboard is a kernel device inside the VM. It continues typing even when the VMware window is not focused on the host. Just don't:
- Pause/suspend the VM
- Minimize VMware to system tray (may reduce CPU)

### Voice is too loud/quiet
Edit the espeak volume in `src/autopilot.py`:
```python
["espeak-ng", "-s", "160", "-a", "200", text]
#                         └ speed  └ amplitude (0-200)
```

### Monaco editor doubles closing braces
When you type `{`, the Monaco editor auto-inserts `}`. If the generated code also contains `}`, you'll get `}}`. **Check the code before submitting** and delete extra braces manually.
