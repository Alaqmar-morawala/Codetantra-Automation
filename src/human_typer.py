#!/usr/bin/env python3
"""
CodeTantra SEA — uinput Human Typer v2 (Realistic Coder)
==========================================================
Simulates realistic coding behavior, not just typing:
  - Types code in logical chunks (functions, blocks)
  - Think-pauses between sections (3-15s)
  - Editing sequences (arrow up, delete word, retype)
  - Cursor movements (Home/End, arrows)
  - Variable WPM (fast boilerplate, slow logic)
  - Random corrections and typo-fix sequences

The goal is to be behaviorally indistinguishable from a human coder.
"""

import time
import random
import math
import os
import sys
import re

from evdev import UInput, ecodes as e

# ═══════════════════════════════════════
# Character → Keycode mapping
# ═══════════════════════════════════════

CHAR_MAP = {
    'a': (e.KEY_A, False), 'b': (e.KEY_B, False), 'c': (e.KEY_C, False),
    'd': (e.KEY_D, False), 'e': (e.KEY_E, False), 'f': (e.KEY_F, False),
    'g': (e.KEY_G, False), 'h': (e.KEY_H, False), 'i': (e.KEY_I, False),
    'j': (e.KEY_J, False), 'k': (e.KEY_K, False), 'l': (e.KEY_L, False),
    'm': (e.KEY_M, False), 'n': (e.KEY_N, False), 'o': (e.KEY_O, False),
    'p': (e.KEY_P, False), 'q': (e.KEY_Q, False), 'r': (e.KEY_R, False),
    's': (e.KEY_S, False), 't': (e.KEY_T, False), 'u': (e.KEY_U, False),
    'v': (e.KEY_V, False), 'w': (e.KEY_W, False), 'x': (e.KEY_X, False),
    'y': (e.KEY_Y, False), 'z': (e.KEY_Z, False),
    'A': (e.KEY_A, True), 'B': (e.KEY_B, True), 'C': (e.KEY_C, True),
    'D': (e.KEY_D, True), 'E': (e.KEY_E, True), 'F': (e.KEY_F, True),
    'G': (e.KEY_G, True), 'H': (e.KEY_H, True), 'I': (e.KEY_I, True),
    'J': (e.KEY_J, True), 'K': (e.KEY_K, True), 'L': (e.KEY_L, True),
    'M': (e.KEY_M, True), 'N': (e.KEY_N, True), 'O': (e.KEY_O, True),
    'P': (e.KEY_P, True), 'Q': (e.KEY_Q, True), 'R': (e.KEY_R, True),
    'S': (e.KEY_S, True), 'T': (e.KEY_T, True), 'U': (e.KEY_U, True),
    'V': (e.KEY_V, True), 'W': (e.KEY_W, True), 'X': (e.KEY_X, True),
    'Y': (e.KEY_Y, True), 'Z': (e.KEY_Z, True),
    '1': (e.KEY_1, False), '2': (e.KEY_2, False), '3': (e.KEY_3, False),
    '4': (e.KEY_4, False), '5': (e.KEY_5, False), '6': (e.KEY_6, False),
    '7': (e.KEY_7, False), '8': (e.KEY_8, False), '9': (e.KEY_9, False),
    '0': (e.KEY_0, False),
    '!': (e.KEY_1, True), '@': (e.KEY_2, True), '#': (e.KEY_3, True),
    '$': (e.KEY_4, True), '%': (e.KEY_5, True), '^': (e.KEY_6, True),
    '&': (e.KEY_7, True), '*': (e.KEY_8, True), '(': (e.KEY_9, True),
    ')': (e.KEY_0, True),
    ' ':  (e.KEY_SPACE, False),
    '\t': (e.KEY_TAB, False),
    '\n': (e.KEY_ENTER, False),
    '-':  (e.KEY_MINUS, False),
    '=':  (e.KEY_EQUAL, False),
    '[':  (e.KEY_LEFTBRACE, False),
    ']':  (e.KEY_RIGHTBRACE, False),
    '\\': (e.KEY_BACKSLASH, False),
    ';':  (e.KEY_SEMICOLON, False),
    "'":  (e.KEY_APOSTROPHE, False),
    ',':  (e.KEY_COMMA, False),
    '.':  (e.KEY_DOT, False),
    '/':  (e.KEY_SLASH, False),
    '`':  (e.KEY_GRAVE, False),
    '_':  (e.KEY_MINUS, True),
    '+':  (e.KEY_EQUAL, True),
    '{':  (e.KEY_LEFTBRACE, True),
    '}':  (e.KEY_RIGHTBRACE, True),
    '|':  (e.KEY_BACKSLASH, True),
    ':':  (e.KEY_SEMICOLON, True),
    '"':  (e.KEY_APOSTROPHE, True),
    '<':  (e.KEY_COMMA, True),
    '>':  (e.KEY_DOT, True),
    '?':  (e.KEY_SLASH, True),
    '~':  (e.KEY_GRAVE, True),
}

# Digraph speed multipliers
FAST_DIGRAPHS = {
    'th': 0.6, 'he': 0.65, 'in': 0.65, 'er': 0.65, 'an': 0.7,
    'nd': 0.7, 'st': 0.7, 'es': 0.7, 're': 0.7, 'on': 0.7,
    'en': 0.7, 'at': 0.75, 'or': 0.75, 'ed': 0.75, 'is': 0.75,
    'it': 0.75, 'al': 0.75, 'ar': 0.75, 'te': 0.75, 'ou': 0.8,
    'ng': 0.7, 'se': 0.8, 'le': 0.8, 'me': 0.8, 'io': 0.8,
    '<<': 0.65, '>>': 0.65, '::': 0.65, '++': 0.7, '//': 0.7,
    'nt': 0.7, 'ri': 0.75, 'co': 0.75, 'ut': 0.75, 'cl': 0.75,
}

SLOW_DIGRAPHS = {
    'qw': 1.4, 'zx': 1.5, 'xz': 1.5, 'qa': 1.3, 'az': 1.3,
    'pl': 1.2, 'mk': 1.2, 'bf': 1.3, 'vg': 1.3, 'yh': 1.2,
}

# Patterns that are "boilerplate" (type faster)
BOILERPLATE_PATTERNS = [
    '#include', 'using namespace', 'import ', 'from ', 'public static',
    'int main', 'void main', 'return 0', 'return;', 'def __init__',
    'System.out', 'printf(', 'scanf(', 'cout <<', 'cin >>',
    'iostream', 'stdio.h', 'stdlib.h', 'string.h', 'math.h',
]


class HumanTyper:
    """Kernel-level virtual keyboard with realistic CODING behavior."""

    def __init__(self, wpm_target=50, error_rate=0.015):
        self.wpm_target = wpm_target
        self.error_rate = error_rate

        chars_per_sec = (wpm_target * 5) / 60
        self.base_interval_ms = 1000 / chars_per_sec

        self.dwell_mean = 82
        self.dwell_std = 28
        self.flight_mean = self.base_interval_ms - self.dwell_mean
        self.flight_std = self.flight_mean * 0.40

        # Burst model
        self.burst_length_mean = 6
        self.burst_length_std = 3
        self.pause_mean_ms = 350
        self.pause_std_ms = 180

        # Create virtual keyboard
        all_keys = set()
        for keycode, _ in CHAR_MAP.values():
            all_keys.add(keycode)
        all_keys.add(e.KEY_LEFTSHIFT)
        all_keys.add(e.KEY_BACKSPACE)
        all_keys.add(e.KEY_UP)
        all_keys.add(e.KEY_DOWN)
        all_keys.add(e.KEY_LEFT)
        all_keys.add(e.KEY_RIGHT)
        all_keys.add(e.KEY_HOME)
        all_keys.add(e.KEY_END)
        all_keys.add(e.KEY_DELETE)
        all_keys.add(e.KEY_LEFTCTRL)
        all_keys.add(e.KEY_ESC)

        cap = {e.EV_KEY: list(all_keys)}
        self.ui = UInput(cap, name='AT-Translated-Set-2-keyboard', bustype=e.BUS_USB,
                         vendor=0x0461, product=0x4d81)
        time.sleep(0.5)

        self.prev_char = None
        self.chars_in_burst = 0
        self.next_burst_len = self._next_burst_length()
        self.total_chars_typed = 0

    def _next_burst_length(self):
        return max(2, int(random.gauss(self.burst_length_mean, self.burst_length_std)))

    def _dwell_time(self):
        t = random.gauss(self.dwell_mean, self.dwell_std)
        return max(25, min(220, t)) / 1000

    def _flight_time(self, prev_char, next_char, speed_mult=1.0):
        base = random.gauss(self.flight_mean, self.flight_std)

        if prev_char and next_char:
            pair = (prev_char + next_char).lower()
            if pair in FAST_DIGRAPHS:
                base *= FAST_DIGRAPHS[pair]
            elif pair in SLOW_DIGRAPHS:
                base *= SLOW_DIGRAPHS[pair]

        if prev_char in '.!?\n':
            base *= random.uniform(1.8, 3.5)
        elif prev_char in ',;:':
            base *= random.uniform(1.2, 1.8)
        elif prev_char == ' ':
            base *= random.uniform(0.85, 1.15)

        base *= speed_mult
        return max(15, base) / 1000

    def _should_error(self):
        return random.random() < self.error_rate

    def _nearby_key(self, keycode):
        neighbors = {
            e.KEY_A: [e.KEY_S, e.KEY_Q, e.KEY_W, e.KEY_Z],
            e.KEY_S: [e.KEY_A, e.KEY_D, e.KEY_W, e.KEY_E, e.KEY_X],
            e.KEY_D: [e.KEY_S, e.KEY_F, e.KEY_E, e.KEY_R, e.KEY_C],
            e.KEY_F: [e.KEY_D, e.KEY_G, e.KEY_R, e.KEY_T, e.KEY_V],
            e.KEY_G: [e.KEY_F, e.KEY_H, e.KEY_T, e.KEY_Y, e.KEY_B],
            e.KEY_H: [e.KEY_G, e.KEY_J, e.KEY_Y, e.KEY_U, e.KEY_N],
            e.KEY_J: [e.KEY_H, e.KEY_K, e.KEY_U, e.KEY_I, e.KEY_M],
            e.KEY_K: [e.KEY_J, e.KEY_L, e.KEY_I, e.KEY_O],
            e.KEY_L: [e.KEY_K, e.KEY_SEMICOLON, e.KEY_O, e.KEY_P],
            e.KEY_Q: [e.KEY_W, e.KEY_A],
            e.KEY_W: [e.KEY_Q, e.KEY_E, e.KEY_A, e.KEY_S],
            e.KEY_E: [e.KEY_W, e.KEY_R, e.KEY_S, e.KEY_D],
            e.KEY_R: [e.KEY_E, e.KEY_T, e.KEY_D, e.KEY_F],
            e.KEY_T: [e.KEY_R, e.KEY_Y, e.KEY_F, e.KEY_G],
            e.KEY_Y: [e.KEY_T, e.KEY_U, e.KEY_G, e.KEY_H],
            e.KEY_U: [e.KEY_Y, e.KEY_I, e.KEY_H, e.KEY_J],
            e.KEY_I: [e.KEY_U, e.KEY_O, e.KEY_J, e.KEY_K],
            e.KEY_O: [e.KEY_I, e.KEY_P, e.KEY_K, e.KEY_L],
            e.KEY_P: [e.KEY_O, e.KEY_LEFTBRACE, e.KEY_L],
        }
        if keycode in neighbors:
            return random.choice(neighbors[keycode])
        return keycode

    def _press_key(self, keycode, need_shift=False):
        dwell = self._dwell_time()
        if need_shift:
            self.ui.write(e.EV_KEY, e.KEY_LEFTSHIFT, 1)
            self.ui.syn()
            time.sleep(random.uniform(0.02, 0.06))
        self.ui.write(e.EV_KEY, keycode, 1)
        self.ui.syn()
        time.sleep(dwell)
        self.ui.write(e.EV_KEY, keycode, 0)
        self.ui.syn()
        if need_shift:
            time.sleep(random.uniform(0.01, 0.04))
            self.ui.write(e.EV_KEY, e.KEY_LEFTSHIFT, 0)
            self.ui.syn()

    def _press_nav_key(self, keycode, with_ctrl=False):
        """Press a navigation key (arrows, Home, End, etc.)."""
        if with_ctrl:
            self.ui.write(e.EV_KEY, e.KEY_LEFTCTRL, 1)
            self.ui.syn()
            time.sleep(random.uniform(0.02, 0.05))
        dwell = random.uniform(0.04, 0.10)
        self.ui.write(e.EV_KEY, keycode, 1)
        self.ui.syn()
        time.sleep(dwell)
        self.ui.write(e.EV_KEY, keycode, 0)
        self.ui.syn()
        if with_ctrl:
            time.sleep(random.uniform(0.01, 0.03))
            self.ui.write(e.EV_KEY, e.KEY_LEFTCTRL, 0)
            self.ui.syn()
        time.sleep(random.uniform(0.05, 0.15))

    def _backspace(self):
        time.sleep(random.uniform(0.12, 0.35))
        self._press_key(e.KEY_BACKSPACE)
        time.sleep(random.uniform(0.06, 0.12))

    def _backspace_word(self):
        """Delete a word using Ctrl+Backspace."""
        time.sleep(random.uniform(0.2, 0.5))
        self.ui.write(e.EV_KEY, e.KEY_LEFTCTRL, 1)
        self.ui.syn()
        time.sleep(random.uniform(0.02, 0.05))
        self._press_key(e.KEY_BACKSPACE)
        time.sleep(random.uniform(0.01, 0.03))
        self.ui.write(e.EV_KEY, e.KEY_LEFTCTRL, 0)
        self.ui.syn()
        time.sleep(random.uniform(0.1, 0.25))

    # ═══════════════════════════════════════
    # Editing simulation behaviors
    # ═══════════════════════════════════════

    def clear_editor_safe(self):
        """Safely moves cursor to the end of the file, bypassing read-only boilerplates."""
        time.sleep(random.uniform(0.3, 0.8))
        # Ctrl + End to jump to absolute bottom
        self._press_nav_key(e.KEY_END, with_ctrl=True)
        time.sleep(random.uniform(0.2, 0.4))
        # Extra safety: spam down arrow 5 times just in case
        for _ in range(5):
            self._press_nav_key(e.KEY_DOWN)
            time.sleep(0.05)
        # Hit enter twice to start fresh lines
        self._press_key(e.KEY_ENTER)
        time.sleep(0.1)
        self._press_key(e.KEY_ENTER)
        time.sleep(0.2)

    def _do_cursor_review(self):
        """Simulate reviewing previous lines (arrow up, look, arrow down back)."""
        ups = random.randint(1, 4)
        for _ in range(ups):
            self._press_nav_key(e.KEY_UP)
            time.sleep(random.uniform(0.08, 0.20))
        time.sleep(random.uniform(0.5, 2.0))
        for _ in range(ups):
            self._press_nav_key(e.KEY_DOWN)
            time.sleep(random.uniform(0.08, 0.20))
        # CRITICAL: Return to absolute end of all text with Ctrl+End
        self._press_nav_key(e.KEY_END, with_ctrl=True)

    def _do_line_edit(self):
        """Simulate scanning the current line (go to start, scan, go back to end)."""
        self._press_nav_key(e.KEY_HOME)
        time.sleep(random.uniform(0.3, 0.8))
        rights = random.randint(2, 10)
        for _ in range(rights):
            self._press_nav_key(e.KEY_RIGHT)
            time.sleep(random.uniform(0.04, 0.10))
        time.sleep(random.uniform(0.2, 0.6))
        # CRITICAL: Return to absolute end of all text with Ctrl+End
        self._press_nav_key(e.KEY_END, with_ctrl=True)

    def _think_pause(self, context=""):
        """Natural thinking pause — varies by what just happened."""
        if "newblock" in context:
            pause = random.uniform(1.5, 5.0)
        elif "midblock" in context:
            pause = random.uniform(0.5, 2.0)
        elif "aftererror" in context:
            pause = random.uniform(0.3, 1.0)
        else:
            pause = random.uniform(0.8, 3.0)
        time.sleep(pause)

    # ═══════════════════════════════════════
    # Code chunking
    # ═══════════════════════════════════════

    def _split_into_chunks(self, code):
        """Split code into logical chunks for typing.
        
        Chunks are groups of 1-5 lines that form logical units:
        - Function signatures
        - Single statements
        - Block openings/closings
        - #include groups
        """
        lines = code.split('\n')
        chunks = []
        current_chunk = []

        for line in lines:
            current_chunk.append(line)
            stripped = line.strip()

            is_boundary = (
                stripped == '' or
                stripped.endswith('{') or
                stripped == '}' or
                stripped.endswith(';') and len(current_chunk) >= 2 or
                stripped.startswith('#include') or
                stripped.startswith('import ') or
                stripped.startswith('def ') or
                stripped.startswith('class ') or
                stripped.startswith('for ') or
                stripped.startswith('while ') or
                stripped.startswith('if ') or
                stripped.startswith('return') or
                len(current_chunk) >= random.randint(3, 6)
            )

            if is_boundary and current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = []

        if current_chunk:
            chunks.append('\n'.join(current_chunk))

        return chunks

    def _is_boilerplate(self, text):
        """Check if text is boilerplate (type faster)."""
        for pattern in BOILERPLATE_PATTERNS:
            if pattern in text:
                return True
        return False

    def _get_speed_mult(self, chunk_text):
        """Get speed multiplier for a chunk.
        
        < 1.0 = faster, > 1.0 = slower
        """
        if self._is_boilerplate(chunk_text):
            return random.uniform(0.6, 0.8)  # Fast for boilerplate
        if any(kw in chunk_text for kw in ['for ', 'while ', 'if ', 'else']):
            return random.uniform(1.0, 1.4)  # Slower for logic
        if any(kw in chunk_text for kw in ['return', '}']):
            return random.uniform(0.8, 1.0)  # Medium for endings
        return random.uniform(0.85, 1.15)  # Normal

    # ═══════════════════════════════════════
    # Main typing methods
    # ═══════════════════════════════════════

    def type_char(self, char, speed_mult=1.0):
        """Type a single character with human behavior."""
        if char not in CHAR_MAP:
            return

        keycode, need_shift = CHAR_MAP[char]

        if self.prev_char is not None:
            flight = self._flight_time(self.prev_char, char, speed_mult)
            time.sleep(flight)

        self.chars_in_burst += 1
        if self.chars_in_burst >= self.next_burst_len and char == ' ':
            pause = max(0.08, random.gauss(self.pause_mean_ms, self.pause_std_ms) / 1000)
            time.sleep(pause)
            self.chars_in_burst = 0
            self.next_burst_len = self._next_burst_length()

        if self._should_error() and char.isalpha():
            wrong_key = self._nearby_key(keycode)
            if wrong_key != keycode:
                self._press_key(wrong_key, need_shift)
                self._backspace()
                time.sleep(random.uniform(0.05, 0.15))

        self._press_key(keycode, need_shift)
        self.prev_char = char
        self.total_chars_typed += 1

    def type_text(self, text, callback=None):
        """Type text with random human-like think breaks."""
        total = len(text)
        start_time = time.time()
        next_break = random.randint(80, 200)  # chars until next think break

        for i, char in enumerate(text):
            self.type_char(char)

            # Random think break every 80-200 chars
            if i >= next_break:
                pause = random.uniform(2.0, 6.0)
                time.sleep(pause)
                next_break = i + random.randint(80, 200)

            # Short pause after newlines (30% chance — reading back)
            elif char == '\n' and random.random() < 0.30:
                time.sleep(random.uniform(1.0, 3.0))

            if callback and (i + 1) % 50 == 0:
                callback(i + 1, total)

        elapsed = time.time() - start_time
        return (len(text) / 5) / (elapsed / 60) if elapsed > 0 else 0

    def type_code_realistically(self, code, callback=None):
        """Type code with realistic coding behavior.
        
        Simulates actual coding: chunks, variable speed, think-pauses,
        and safe read-only cursor movements (no edits that could corrupt code).
        """
        chunks = self._split_into_chunks(code)
        total_chars = len(code)
        chars_typed = 0
        start_time = time.time()

        for chunk_idx, chunk in enumerate(chunks):
            if chunk_idx > 0:
                if chunk_idx % random.randint(2, 4) == 0:
                    self._think_pause("newblock")
                else:
                    self._think_pause("midblock")

            speed_mult = self._get_speed_mult(chunk)

            for i, char in enumerate(chunk):
                self.type_char(char, speed_mult)
                chars_typed += 1
                if callback and chars_typed % 80 == 0:
                    callback(chars_typed, total_chars)

            # Add newline between chunks
            if chunk_idx < len(chunks) - 1 and not chunk.endswith('\n'):
                self.type_char('\n', speed_mult)
                chars_typed += 1

            # Safe read-only behaviors every few chunks (NO code modifications)
            if chunk_idx > 0 and chunk_idx % random.randint(3, 5) == 0:
                behavior = random.choice([
                    'cursor_review',
                    'line_edit',
                    'none',
                    'none',
                ])
                if behavior == 'cursor_review':
                    self._do_cursor_review()
                elif behavior == 'line_edit':
                    self._do_line_edit()

        # Final callback
        if callback:
            callback(total_chars, total_chars)

        elapsed = time.time() - start_time
        actual_wpm = (total_chars / 5) / (elapsed / 60) if elapsed > 0 else 0
        return actual_wpm

    def close(self):
        """Clean up the virtual device."""
        self.ui.close()


# ═══════════════════════════════════════
# CLI test mode
# ═══════════════════════════════════════
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Human-like code typing via uinput")
    parser.add_argument("--test", type=str, help="Text to type")
    parser.add_argument("--file", type=str, help="File to type")
    parser.add_argument("--wpm", type=int, default=50, help="Target WPM (default 50)")
    parser.add_argument("--errors", type=float, default=0.015, help="Error rate (default 0.015)")
    parser.add_argument("--delay", type=int, default=3, help="Seconds before typing starts")
    parser.add_argument("--realistic", action="store_true", help="Use realistic code typing mode")
    args = parser.parse_args()

    text = None
    if args.test:
        text = args.test
    elif args.file:
        with open(args.file) as f:
            text = f.read()
    else:
        print("Provide --test 'text' or --file path", file=sys.stderr)
        sys.exit(1)

    mode = "realistic" if args.realistic else "linear"
    print(f"Mode: {mode} | {len(text)} chars | ~{args.wpm} WPM | {args.errors*100:.1f}% errors")
    print(f"Starting in {args.delay}s... Focus the target window!")

    for i in range(args.delay, 0, -1):
        print(f"  {i}...", flush=True)
        time.sleep(1)

    typer = HumanTyper(wpm_target=args.wpm, error_rate=args.errors)

    def progress(typed, total):
        pct = typed / total * 100
        print(f"  [{pct:.0f}%] {typed}/{total}", flush=True)

    print("Typing!", flush=True)
    if args.realistic:
        actual_wpm = typer.type_code_realistically(text, callback=progress)
    else:
        actual_wpm = typer.type_text(text, callback=progress)
    typer.close()
    print(f"\n✓ Done! {actual_wpm:.0f} WPM")
