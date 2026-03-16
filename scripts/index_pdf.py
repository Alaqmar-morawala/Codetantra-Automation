#!/usr/bin/env python3
import os
import sys
import json
import time
import re
import PIL.Image
import google.generativeai as genai

# Config
IMG_DIR = "data/pdf_pages"
OUTPUT_INDEX = "data/pdf_index.json"
MODEL_NAME = "models/gemini-flash-latest" 
BATCH_SIZE = 5

def init_gemini():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY env var not set.")
        sys.exit(1)
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(MODEL_NAME)

def extract_from_batch(model, img_paths, page_nums, retries=5):
    print(f"  Processing pages {page_nums}...", flush=True)
    imgs = [PIL.Image.open(p) for p in img_paths]
    
    # Construct labels for each image so Gemini can associate code with page numbers
    labeled_imgs = []
    for i, img in enumerate(imgs):
        labeled_imgs.append(f"PAGE {page_nums[i]}:")
        labeled_imgs.append(img)

    prompt = """These are screenshots from a CodeTantra lab manual.
Extract all (Problem Description, EXACT Source Code) pairs from these images.

Rules:
1. Extract the 'title' (short problem summary) and 'code' (RAW source code).
2. For EACH item, specify the 'page' number it was found on.
3. Return as a JSON LIST of objects: [{"title": "...", "code": "...", "lang": "...", "page": X}]
4. IMPORTANT: 'code' must be the RAW source code. Do NOT summarize.
5. If an image has no code, do NOT include it in the list.
6. Output ONLY the JSON block. No markdown. No explanations."""

    for attempt in range(retries):
        try:
            response = model.generate_content([prompt] + labeled_imgs)
            text = response.text.strip()
            
            # Clean JSON
            text = re.sub(r'^```json\s*', '', text)
            text = re.sub(r'\s*```$', '', text)
            if text.startswith("```"):
                text = text[3:-3].strip()
            
            return json.loads(text)
        except Exception as e:
            err_msg = str(e)
            print(f"    ✗ Attempt {attempt+1} failed: {err_msg[:100]}", flush=True)
            if "429" in err_msg or "quota" in err_msg.lower():
                match = re.search(r'seconds: (\d+)', err_msg)
                wait = int(match.group(1)) + 5 if match else 45
                print(f"    ⏳ Rate limited. Waiting {wait}s...", flush=True)
                time.sleep(wait)
            elif attempt < retries - 1:
                time.sleep(10)
    return []

def main():
    if not os.path.exists(IMG_DIR):
        print(f"ERROR: {IMG_DIR} not found.")
        return

    model = init_gemini()
    
    files = [f for f in os.listdir(IMG_DIR) if f.endswith(".jpg")]
    files.sort(key=lambda x: int(re.search(r'(\d+)', x).group(1)))

    full_index = []
    if os.path.exists(OUTPUT_INDEX):
        try:
            with open(OUTPUT_INDEX, "r") as f:
                full_index = json.load(f)
            print(f"  Loaded existing index with {len(full_index)} items.")
        except:
            pass

    done_pages = {item.get('page') for item in full_index}
    
    all_pages = []
    for i, f in enumerate(files):
        p_num = i + 1
        if p_num not in done_pages:
            all_pages.append((p_num, os.path.join(IMG_DIR, f)))

    print(f"Total pages to process: {len(all_pages)}")

    for i in range(0, len(all_pages), BATCH_SIZE):
        batch = all_pages[i : i + BATCH_SIZE]
        p_nums = [item[0] for item in batch]
        p_paths = [item[1] for item in batch]
        
        results = extract_from_batch(model, p_paths, p_nums)
        if results:
            full_index.extend(results)
            print(f"    ✓ Found {len(results)} items in batch.")
            
            with open(OUTPUT_INDEX, "w") as f:
                json.dump(full_index, f, indent=2)
        
        # Delay between batches
        time.sleep(10)

    print(f"\n✓ DONE! Total items: {len(full_index)}")

if __name__ == "__main__":
    main()
