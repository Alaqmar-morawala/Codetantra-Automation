#!/usr/bin/env python3
import os
import sys
import json
import re
import time
import google.generativeai as genai

# Config
OCR_DIR = "/tmp/raw_ocr"
OUTPUT_INDEX = "data/pdf_index.json"
MODEL_NAME = "models/gemini-flash-latest"  # Verified working model
BATCH_SIZE = 20

def init_gemini():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY env var not set.")
        sys.exit(1)
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(MODEL_NAME)

def clean_ocr_batch(model, texts_with_pages, retries=5):
    combined_text = ""
    for page, text in texts_with_pages:
        combined_text += f"\n--- PAGE {page} ---\n{text}\n"

    prompt = f"""You are an expert programmer and the following is raw Tesseract OCR output from a lab manual.
Your goal is to correct any OCR typos and extract (Problem Description, Source Code) pairs into a clean JSON list.

Rules:
1. Extract 'title' (a short summary or title of the problem).
2. Extract 'code' (the actual cleaned source code, fixing OCR typos like 'print1n' -> 'println').
3. For EVERY item, include the exact 'page' number it was found on.
4. Return a JSON LIST: [{{"title": "...", "code": "...", "lang": "...", "page": X}}]
5. If no code/problem is on a page, SKIP it.
6. Do NOT summarize or explain. RAW code only in the JSON.
7. Return ONLY the JSON block.

RAW OCR INPUT:
{combined_text}
"""

    for attempt in range(retries):
        try:
            response = model.generate_content(prompt)
            text = response.text.strip()
            text = re.sub(r'^```json\s*', '', text)
            text = re.sub(r'\s*```$', '', text)
            if text.startswith("```"):
                text = text[3:-3].strip()
            
            return json.loads(text)
        except Exception as e:
            err_msg = str(e)
            print(f"    ✗ Attempt {attempt+1} failed: {err_msg[:100]}", flush=True)
            if "429" in err_msg:
                match = re.search(r'seconds: (\d+)', err_msg)
                wait = int(match.group(1)) + 5 if match else 60
                print(f"    ⏳ Rate limited. Waiting {wait}s...", flush=True)
                time.sleep(wait)
            elif attempt < retries - 1:
                time.sleep(10)
    return []

def main():
    if not os.path.exists(OCR_DIR):
        print(f"ERROR: {OCR_DIR} not found.")
        return

    model = init_gemini()
    
    # Sort files numerically
    all_files = os.listdir(OCR_DIR)
    files = []
    for f in all_files:
        if f.endswith(".txt"):
            m = re.search(r'(\d+)', f)
            if m:
                files.append((int(m.group(1)), f))
    files.sort()

    full_index = []
    print(f"Processing {len(files)} OCR files in batches of {BATCH_SIZE}...")

    for i in range(0, len(files), BATCH_SIZE):
        batch = files[i : i + BATCH_SIZE]
        texts_with_pages = []
        for page_num, filename in batch:
            with open(os.path.join(OCR_DIR, filename), "r") as f:
                texts_with_pages.append((page_num, f.read()))
        
        print(f"  Cleaning pages {[p[0] for p in batch]}...")
        results = clean_ocr_batch(model, texts_with_pages)
        if results:
            full_index.extend(results)
            print(f"    ✓ Found {len(results)} items")
            
            # Incremental save
            os.makedirs(os.path.dirname(OUTPUT_INDEX), exist_ok=True)
            with open(OUTPUT_INDEX, "w") as f:
                json.dump(full_index, f, indent=2)
        
        # Delay to avoid 429
        time.sleep(10)
    
    print(f"\n✓ DONE! Saved {len(full_index)} items to {OUTPUT_INDEX}")

if __name__ == "__main__":
    main()
