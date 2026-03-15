#!/usr/bin/env python3
"""
Gemini API Solver for CodeTantra Exam Questions
=================================================
Takes raw extracted text (which may include UI artifacts from Ctrl+A)
and returns clean solution code.

Env:
  GEMINI_API_KEY=your-key-here

Usage:
  python3 scripts/gemini_solver.py --test "Write a Python function to reverse a string"
"""

import os
import sys
import time
import json
import re

try:
    import google.generativeai as genai
except ImportError:
    print("ERROR: google-generativeai not installed.", file=sys.stderr)
    print("  Run: pip install --break-system-packages google-generativeai", file=sys.stderr)
    sys.exit(1)


import difflib
# Resolve paths relative to repo root
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SRC_DIR)
DEFAULT_INDEX_PATH = os.path.join(REPO_ROOT, "data/pdf_index.json")

def clog(msg):
    print(msg, flush=True)

class PdfSolutions:
    """Handles lookup in the indexed PDF solutions."""

    def __init__(self, index_path=None):
        self.index_path = index_path or DEFAULT_INDEX_PATH
        self.index = []
        self.load()

    def load(self):
        if os.path.exists(self.index_path):
            try:
                with open(self.index_path, "r") as f:
                    self.index = json.load(f)
                clog(f"  [PDF] Loaded {len(self.index)} solutions from index.")
            except Exception as e:
                clog(f"  [PDF] ERROR loading index: {e}")
        else:
            clog(f"  [PDF] WARNING: Index file not found at {self.index_path}")

    def find_match(self, problem_text, threshold=0.7):
        """Find the best matching solution in the PDF index."""
        if not self.index:
            return None

        # Clean problem text for matching
        # Remove noisy short words and multiple spaces
        query = re.sub(r'\s+', ' ', problem_text.lower().strip())
            
        clog(f"  [PDF] Searching index for: {query[:50]}...")
        
        # 1. Filename Exact Match (High Confidence)
        # Search for any 'filename' from the index that appears in the raw text
        for item in self.index:
            fname = item.get("filename", "")
            if fname and fname.lower() in query:
                clog(f"  [PDF] Found filename match: {fname}")
                return item["code"]
            
            # Also try basename
            basename = os.path.basename(fname)
            if basename and basename.lower() in query:
                clog(f"  [PDF] Found basename match: {basename}")
                return item["code"]

        # 2. Fuzzy Title Match
        best_match = None
        highest_ratio = 0.0
        
        # We search both title and filename for fuzzy matching
        for item in self.index:
            title = item.get("title", "")
            fname = item.get("filename", "")
            
            # Combine for better matching
            search_space = f"{title} {fname}"
            
            ratio = difflib.SequenceMatcher(None, query.lower(), search_space.lower()).ratio()
            if ratio > highest_ratio:
                highest_ratio = ratio
                best_match = item
                
        if highest_ratio > 0.6: # Relaxed threshold but logged
            clog(f"  [PDF] Fuzzy match found: '{best_match.get('title')}' (ratio: {highest_ratio:.2f})")
            return best_match["code"]
            
        clog("  [PDF] No close match found.")
        return None


class GeminiSolver:
    """Sends exam questions to Gemini and gets solution code back."""

    SYSTEM_PROMPT = """You are a competitive programming expert. You will receive raw text extracted from an exam page which may contain UI elements, navigation text, and other artifacts mixed in with the actual programming question.

Your task:
1. Extract the actual programming question from the noisy text
2. FIRST, determine if this is a Multiple Choice Question (MCQ). If you see options like A), B), C), D) or radio button markers, reply STRICTLY and EXCLUSIVELY with the text:
IS_MCQ
3. If it is NOT an MCQ, identify the programming language required and write a COMPLETE, WORKING solution.

CRITICAL RULES FOR CODING SOLUTIONS:
- Output ONLY the solution code, no explanations, no markdown fences
- Do NOT include ANY comments in the code (no //, no #, no /* */, no docstrings)
- The code must be complete and runnable as-is
- Handle all edge cases mentioned in the problem
- Follow the exact input/output format specified in the problem
- If sample test cases are provided, make sure your solution passes them
- IMPORTANT: The editor already contains fixed, read-only boilerplate (like the class declaration `public class Main { ... }` or `import` statements). Do NOT output the outer class wrappers or imports again! Output ONLY the inner functions, inner logic, or `main` block contents that need to be typed inside the existing boilerplate.
- For C, C++, Java: do NOT add extra spaces or indentation at the start of lines unless inside a block (if/for/while/function body)
- Keep the code minimal and clean - no blank lines between statements unless necessary"""

    def __init__(self, api_key=None, model="gemini-2.0-flash", index_path="data/pdf_index.json"):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "No Gemini API key. Set GEMINI_API_KEY env var or pass api_key parameter."
            )
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(model)
        self.pdf = PdfSolutions(index_path)

    def solve(self, raw_text, language_hint=None, max_retries=3):
        """
        Send question text to Gemini and get solution code.

        Args:
            raw_text: Raw text from Ctrl+A extraction (may contain UI noise)
            language_hint: Optional language hint (e.g., "python", "cpp")
            max_retries: Number of retry attempts on failure

        Returns:
            str: Clean solution code, or None on failure
        """
        # Phase 1: Try PDF lookup first
        pdf_code = self.pdf.find_match(raw_text)
        if pdf_code:
            return self.clean_code(pdf_code, language_hint)

        # Phase 2: Fallback to Gemini
        print("  [Gemini] Falling back to AI generation...", flush=True)
        prompt = self.SYSTEM_PROMPT + "\n\n"
        if language_hint:
            prompt += f"Language: {language_hint}\n\n"
        prompt += f"--- RAW EXTRACTED TEXT ---\n{raw_text}\n--- END ---\n\n"
        prompt += "Write the complete solution code now:"

        for attempt in range(max_retries):
            try:
                response = self.model.generate_content(prompt)
                code = response.text.strip()

                # Strip markdown fences if Gemini adds them
                code = self._strip_fences(code)

                if code and len(code) > 10:
                    return self.clean_code(code, language_hint)

            except Exception as ex:
                err = str(ex)
                if attempt < max_retries - 1:
                    wait = 2 ** attempt  # exponential backoff
                    print(f"  Gemini attempt {attempt+1} failed: {err[:80]}. Retrying in {wait}s...",
                          flush=True)
                    time.sleep(wait)
                else:
                    print(f"  Gemini FAILED after {max_retries} attempts: {err[:120]}", flush=True)

        return None

    def _strip_fences(self, text):
        """Remove markdown code fences if present."""
        # Match ```python ... ``` or ```cpp ... ``` etc.
        m = re.match(r'^```\w*\n(.*?)```$', text, re.DOTALL)
        if m:
            return m.group(1).strip()
        # Sometimes just ``` without language
        m = re.match(r'^```\n(.*?)```$', text, re.DOTALL)
        if m:
            return m.group(1).strip()
        return text

    def clean_code(self, code, language=None):
        """Post-process code: only strip markdown fences. Keep everything else as-is (v5 behavior)."""
        lines = code.split('\n')
        cleaned = []

        for line in lines:
            line = line.rstrip()
            cleaned.append(line)

        # Remove trailing empty lines
        while cleaned and not cleaned[-1]:
            cleaned.pop()

        return '\n'.join(cleaned)

    def _strip_auto_braces(self, code):
        """Remove matched closing braces that Monaco editor auto-inserts.

        When you type { in Monaco, it automatically inserts }.
        Since our code already contains }, typing it would create duplicates.
        This removes the matched } so Monaco's auto-insertion handles them.

        Uses a counter for correct nesting: { increments, } decrements+skips.
        Unmatched } (counter=0) are kept as-is.
        """
        result = []
        pending = 0  # count of } that Monaco will auto-insert

        for ch in code:
            if ch == '{':
                pending += 1
                result.append(ch)
            elif ch == '}' and pending > 0:
                pending -= 1
                # Skip — Monaco already inserted this
            else:
                result.append(ch)

        return ''.join(result)

    def detect_language(self, raw_text):
        """Guess the programming language from the extracted text."""
        text_lower = raw_text.lower()

        # Check for file extensions in tab names
        # IMPORTANT: check .java/.class BEFORE .c (because .class contains .c)
        if '.py' in text_lower:
            return 'python'
        if '.java' in text_lower or '.class' in text_lower:
            return 'java'
        if '.cpp' in text_lower or '.cc' in text_lower:
            return 'cpp'
        if '.js' in text_lower:
            return 'javascript'

        # Check for language keywords
        if 'import ' in raw_text and 'def ' in raw_text:
            return 'python'
        if 'public static void main' in raw_text or 'System.out' in raw_text:
            return 'java'
        if '#include' in raw_text and ('cout' in raw_text or 'cin' in raw_text):
            return 'cpp'
        if '#include' in raw_text:
            return 'c'
        if 'scanf' in raw_text or 'printf' in raw_text:
            return 'c'

        # Check for .c LAST to avoid .class/.css/.csv false matches
        import re
        if re.search(r'\b\w+\.c\b', text_lower):
            return 'c'

        return 'python'  # Default


# ═══════════════════════════════════════
# CLI test mode
# ═══════════════════════════════════════
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Test Gemini solver")
    parser.add_argument("--test", type=str, help="Question to solve")
    parser.add_argument("--file", type=str, help="File containing question text")
    parser.add_argument("--lang", type=str, default=None, help="Language hint")
    args = parser.parse_args()

    text = None
    if args.test:
        text = args.test
    elif args.file:
        with open(args.file) as f:
            text = f.read()
    else:
        print("Provide --test 'question' or --file path", file=sys.stderr)
        sys.exit(1)

    print(f"Question ({len(text)} chars): {text[:100]}...", flush=True)

    try:
        solver = GeminiSolver()
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    lang = args.lang or solver.detect_language(text)
    print(f"Detected language: {lang}", flush=True)
    print("Solving...", flush=True)

    code = solver.solve(text, language_hint=lang)
    if code:
        print(f"\n{'='*50}")
        print("SOLUTION:")
        print(f"{'='*50}")
        print(code)
        print(f"{'='*50}")
        print(f"✓ {len(code)} chars, {code.count(chr(10))+1} lines")
    else:
        print("✗ Failed to get solution", file=sys.stderr)
        sys.exit(1)
