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

    def find_match(self, problem_text, threshold=0.75):
        """Find the best matching solution in the PDF index.
        
        V7.1 Features:
        - Multi-candidate ranking for duplicate titles.
        - Filename tie-breaking using keywords in problem text.
        - Higher threshold (0.75) for fuzzy matching.
        """
        if not self.index:
            return None

        query = re.sub(r'\s+', ' ', problem_text.lower().strip())
        clog(f"  [PDF] Searching index for identifiers in text ({len(query)} chars)...")
        
        # 1. High Confidence ID/Filename Segment Match
        candidates = []
        for item in self.index:
            fname = item.get("filename", "")
            if not fname: continue
            
            basename = os.path.basename(fname).lower()
            stem = os.path.splitext(basename)[0]
            
            # Exact presence checks
            match_type = None
            if basename in query: 
                match_type = "basename"
            elif stem in query and (len(stem) >= 6 or any(c.isdigit() for c in stem)): 
                # Avoid greedy matching on common stems like 'data', 'app', 'main'
                match_type = "stem"
            else:
                # Numeric ID extraction and check
                nums = re.findall(r'\d+', stem)
                for n in nums:
                    # Skip common small numbers and greedy matches
                    if len(n) >= 4 and f" {n}" in f" {query}": 
                        match_type = f"numeric_id({n})"
                        break
            
            if match_type:
                candidates.append((item, 1.0, match_type))

        if candidates:
            # If we have matches here, we check for ambiguity.
            # Stage 1: Absolute Certainty Check
            safe_id_candidates = []
            ambiguous_id_candidates = []
            
            for item, score, m_type in candidates:
                if m_type == "basename":
                    basename = os.path.basename(item.get("filename", "")).lower()
                    if len(basename) > 8 and any(c.isdigit() for c in basename):
                        safe_id_candidates.append((item, score, m_type))
                    else:
                        ambiguous_id_candidates.append((item, score, m_type))
                else:
                    safe_id_candidates.append((item, score, m_type)) # Stems > 6 or numeric IDs are already filtered for safety
            
            if len(safe_id_candidates) == 1:
                # Absolute certainty achieved
                best = safe_id_candidates[0]
                clog(f"  [PDF] Stage 1 Absolute Certainty: {best[0].get('filename')} via {best[2]}")
                return best[0]["code"], best[0].get("lang", "unknown")
            elif len(safe_id_candidates) > 1:
                clog("  [PDF] Stage 2 Ambiguity: Multiple safe IDs found. Reverting to context tie-break.")
                # We will let it fall through to fuzzy/context check below
            elif ambiguous_id_candidates:
                clog(f"  [PDF] Stage 2 Ambiguity: Common basenames found ({len(ambiguous_id_candidates)}). Proceeding to context check.")

        # 2. Title Substring & Token Match
        fuzzy_candidates = []
        for item in self.index:
            title = item.get("title", "").lower()
            if not title: continue
            
            # 2a. Exact Substring Match
            if title in query:
                fuzzy_candidates.append((item, 1.0))
                continue
                
            # 2b. Token Overlap Match (Handles OCR noise and extra words)
            title_words = set(re.findall(r'\w+', title))
            query_words = set(re.findall(r'\w+', query))
            
            if not title_words: continue
            
            # Ignore common stop words from the title for scoring
            stopwords = {'a', 'an', 'the', 'in', 'on', 'at', 'to', 'for', 'of', 'and', 'or', 'with', 'is', 'are', 'write', 'program', 'function'}
            sig_title_words = title_words - stopwords
            
            if not sig_title_words:
                sig_title_words = title_words # Fallback if only stopwords
                
            overlap = len(sig_title_words.intersection(query_words))
            ratio = overlap / len(sig_title_words)
            
            # Require at least 90% of significant title words to be present for robustness
            if ratio >= 0.9:
                fuzzy_candidates.append((item, ratio))

        # Merge any ID-based candidates into fuzzy pool for Stage 3 validation
        if candidates and not fuzzy_candidates:
             # Default to 0.5 score to force tie-breaking
             fuzzy_candidates.extend([(item, 0.5) for item, _, _ in candidates])
        elif candidates:
             # Boost fuzzy score if they were also an ID candidate
             id_filenames = {item.get("filename", "") for item, _, _ in candidates}
             for i in range(len(fuzzy_candidates)):
                 if fuzzy_candidates[i][0].get("filename", "") in id_filenames:
                     fuzzy_candidates[i] = (fuzzy_candidates[i][0], fuzzy_candidates[i][1] + 0.5)

        if not fuzzy_candidates:
            clog("  [PDF] Failure: No candidates met the strict requirements. Falling back to Gemini.")
            return None

        # Sort by ratio descending
        fuzzy_candidates.sort(key=lambda x: x[1], reverse=True)
        
        top_score = fuzzy_candidates[0][1]
        best_candidate = fuzzy_candidates[0][0]

        # Stage 3: The Ambiguity Trap and Tie-Breaking
        # Check if the next best candidate is too close (within 15%)
        ambiguous_tier = [c for c in fuzzy_candidates if top_score - c[1] < 0.15]
        
        if len(ambiguous_tier) > 1:
            clog(f"  [PDF] Stage 3 Ambiguity Trap: {len(ambiguous_tier)} candidates within 15% margin. Evaluating Active Tab...")
            
            # Tie-breaker 1: Active Tab Detection (rfind)
            # In CodeTantra, if multiple files share a title, the problem text often
            # prints the name of the currently active tab just before the code editor.
            # We search backwards to find which candidate's basename appears last (highest index).
            
            last_indices = {}
            for item, score in ambiguous_tier:
                fname = item.get("filename", "")
                basename = os.path.basename(fname).lower()
                
                # Find the right-most occurrence of the basename as a distinct token
                # Using regex to ensure we don't match 'app.py' inside 'test_app.py'
                matches = list(re.finditer(rf'(?<![a-zA-Z0-9_-]){re.escape(basename)}(?![a-zA-Z0-9_-])', query))
                if matches:
                    last_indices[item.get("filename", "")] = matches[-1].start()
                else:
                    last_indices[item.get("filename", "")] = -1
            
            best_filename = max(last_indices, key=last_indices.get)
            best_index = last_indices[best_filename]
            
            if best_index != -1:
                # Find the item corresponding to the winning filename
                winner = next(item for item, score in ambiguous_tier if item.get("filename", "") == best_filename)
                clog(f"  [PDF] Stage 3 Resolution: Active Tab Detected. Winning candidate: '{best_filename}' (Index: {best_index})")
                return winner["code"], winner.get("lang", "unknown")
            
            # Tie-breaker 2: Code context (variable/function names)
            # Find words in problem text that exist in candidate code
            query_identifiers = set(re.findall(r'[a-zA-Z_]\w{3,}', query))
            for item, score in ambiguous_tier:
                code_text = item.get("code", "").lower()
                # Check for explicit function or class names being asked for
                if "def " in query and "def " in code_text: return item["code"], item.get("lang", "unknown")
                if "class " in query and "class " in code_text: return item["code"], item.get("lang", "unknown")
            
            # If tie-breakers fail, it is UNSAFE to proceed.
            clog("  [PDF] CRITICAL: Ambiguity unresolved. Tie-breakers failed. SAFE ABORT to Gemini.")
            return None

        # Absolute winner found
        clog(f"  [PDF] Resolution: Clear winner found '{best_candidate.get('filename')}' (score: {top_score:.2f}). SAFE.")
        return best_candidate["code"], best_candidate.get("lang", "unknown")


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
        match = self.pdf.find_match(raw_text)
        if match:
            pdf_code, pdf_lang = match
            # Use detected lang if hint is missing
            lang = language_hint or pdf_lang
            return self.clean_code(pdf_code, lang)

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
        """Post-process code: strip markdown fences and ALL leading whitespace from lines.
        
        This prevents 'double-indentation' in editors that auto-indent on newline.
        """
        if not code:
            return ""

        # Remove markdown fences first
        code = self._strip_fences(code)
        
        lines = code.split('\n')
        cleaned_lines = []

        for line in lines:
            # strip() to remove the 'initial spaces' that cause double-indentation
            cleaned_line = line.strip()
            if cleaned_line or cleaned_lines:
                cleaned_lines.append(cleaned_line)

        # Remove trailing empty lines
        while cleaned_lines and not cleaned_lines[-1]:
            cleaned_lines.pop()

        return '\n'.join(cleaned_lines)

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
