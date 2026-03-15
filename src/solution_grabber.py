#!/usr/bin/env python3
import os
import json
import time
import subprocess
import argparse
import sys

def get_clipboard():
    """Returns the current content of the clipboard using xclip."""
    try:
        return subprocess.check_output(['xclip', '-selection', 'clipboard', '-o']).decode('utf-8')
    except subprocess.CalledProcessError:
        return ""
    except Exception as e:
        print(f"Error reading clipboard: {e}")
        return ""

def speak(text):
    """Speaks text using espeak-ng if available."""
    try:
        subprocess.Popen(['espeak-ng', text], stderr=subprocess.DEVNULL)
    except:
        pass

def main():
    parser = argparse.ArgumentParser(description="Grab solution from clipboard after 30s and update index.")
    parser.add_argument("--index", default="data/pdf_index.json", help="Path to pdf_index.json")
    args = parser.parse_args()

    # Find project root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    index_path = os.path.join(project_root, args.index)

    if not os.path.exists(index_path):
        print(f"Error: Index file not found at {index_path}")
        sys.exit(1)

    print("\n" + "="*50)
    print("       🚀 SOLUTION GRABBER v1.0 🚀")
    print("="*50)
    print("\n1. Go to CodeTantra editor.")
    print("2. Select and Copy (Ctrl+C) the solution code.")
    print(f"3. I will grab the clipboard in 30 seconds.")
    print("\n" + "-"*50)

    speak("Solution grabber started. You have 30 seconds to copy the code.")

    # Countdown
    for i in range(30, 0, -1):
        sys.stdout.write(f"\r⏳ Automating in {i:2d} seconds... ")
        sys.stdout.flush()
        time.sleep(1)

    print("\n\n💥 TRIGGERING EXTRACTION...")
    
    # Automate the Copy via xdotool
    try:
        # Find window
        r = subprocess.run(["xdotool", "search", "--name", "CodeTantra"], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            wid = r.stdout.strip().split("\n")[-1]
            # Get geometry
            g_out = subprocess.check_output(["xdotool", "getwindowgeometry", wid]).decode('utf-8')
            width, height = 1920, 1080
            for line in g_out.split('\n'):
                if "Geometry" in line:
                    geom = line.split(":")[1].strip()
                    width, height = map(int, geom.split("x"))
            
            # Target Editor: 70% width, 45% height
            target_x = int(width * 0.70)
            target_y = int(height * 0.45)

            # Activate and focus
            subprocess.run(["xdotool", "windowactivate", "--sync", wid])
            time.sleep(0.5)
            # Click Editor area
            subprocess.run(["xdotool", "mousemove", "--window", wid, str(target_x), str(target_y), "click", "1"])
            time.sleep(0.3)
            # Select All and Copy
            subprocess.run(["xdotool", "key", "ctrl+a", "ctrl+c"])
            time.sleep(0.5)
            print(f"✅ Clicked at ({target_x}, {target_y}) and sent Ctrl+A, Ctrl+C.")
        else:
            print("⚠️ Warning: CodeTantra window not found. Please copy manually NOW!")
            time.sleep(2)
    except Exception as e:
        print(f"⚠️ xdotool error: {e}. Falling back to manual clipboard.")

    code = get_clipboard().strip()

    if not code:
        print("❌ FAILED: Clipboard is empty!")
        speak("Failed. Clipboard is empty.")
        sys.exit(1)

    print(f"✅ Captured {len(code)} characters.")
    print("-" * 50)
    print(code[:200] + "..." if len(code) > 200 else code)
    print("-" * 50)

    # Prompt user for metadata
    speak("Code captured. Please enter details in the terminal.")
    
    filename = input("\n📝 Enter Filename or ID (e.g. MySolution.java or q11488): ").strip()
    if not filename:
        print("❌ Cancelled: No filename provided.")
        sys.exit(1)

    title = input("💡 Enter Title (Brief description, optional): ").strip() or filename
    lang = input("🌐 Enter Language (java/python/cpp/c): ").strip().lower()
    if not lang:
        if filename.endswith(".java"): lang = "java"
        elif filename.endswith(".py"): lang = "python"
        elif filename.endswith(".cpp"): lang = "cpp"
        elif filename.endswith(".c"): lang = "c"
        else: lang = "java" # Default

    # Load and update index
    try:
        with open(index_path, "r") as f:
            index = json.load(f)
        
        # Check if already exists (update instead of append)
        existing = next((item for item in index if item["filename"].lower() == filename.lower()), None)
        if existing:
            print(f"🔄 Updating existing entry for {filename}...")
            existing["code"] = code
            existing["title"] = title
            existing["lang"] = lang
        else:
            print(f"➕ Adding new entry for {filename}...")
            index.append({
                "title": title,
                "filename": filename,
                "lang": lang,
                "code": code
            })

        with open(index_path, "w") as f:
            json.dump(index, f, indent=2)

        print("\n✅ SUCCESS: pdf_index.json updated!")
        speak("Solution saved successfully.")

        # Optional: Git Push
        do_push = input("\n🚀 Push to GitHub now? (y/n): ").strip().lower()
        if do_push == 'y':
            print("📤 Pushing to repository...")
            subprocess.run(["git", "add", "data/pdf_index.json"])
            subprocess.run(["git", "commit", "-m", f"Manual add: {filename} via grabber"])
            subprocess.run(["git", "push"])
            print("🏁 Push complete!")
            speak("Changes pushed to cloud.")

    except Exception as e:
        print(f"❌ ERROR: {e}")
        speak("An error occurred while saving.")

if __name__ == "__main__":
    main()
