import os
import sys
import json
import ollama
import socket
import threading
import time
import random
from datetime import datetime
from integrity.code_check import run_code_check
from multiprocessing import freeze_support, Process, Pipe
from response_worker import process_response

# === GLOBAL STATE ===
freeze_support()
__all__ = ['friday_is_thinking']

base_folder = os.path.dirname(os.path.abspath(__file__))
long_term_memory_file = os.path.join(base_folder, 'memory.txt')

short_term_memory = []
long_term_memory = []
is_processing = False
friday_is_thinking = False
pending_input = None

# === MEMORY ===
def load_long_term_memory():
    if os.path.exists(long_term_memory_file):
        try:
            with open(long_term_memory_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[Memory Load Error] Failed to load memory.txt: {e}")
    return []

def save_long_term_memory(memory_data):
    try:
        with open(long_term_memory_file, 'w', encoding='utf-8') as f:
            json.dump(memory_data, f, indent=2)
    except Exception as e:
        friday_speak(f"Failed to save long-term memory: {e}")

def add_to_memory(role, content):
    short_term_memory.append({"role": role, "content": content})

def save_to_memory(role, content):
    global long_term_memory
    long_term_memory.append({"role": role, "content": content})
    save_long_term_memory(long_term_memory)

# === SPEECH AND LOGGING ===
def friday_speak(message, return_text=False, log_to_memory=False):
    print(f"Friday: {message}")
    if log_to_memory:
        add_to_memory("assistant", message)
        save_to_memory("assistant", message)

    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    try:
        with open("display_output.txt", "a", encoding="utf-8") as out_file:
            out_file.write(f"{timestamp} {message}\n")
    except Exception as e:
        print(f"[Display Output Error] {e}")

    if return_text:
        return message

def log_critical_error(context, exception):
    message = f"[CRITICAL] {context}: {exception}"
    friday_speak(message)
    try:
        with open("error_log.txt", "a", encoding='utf-8') as f:
            timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
            f.write(f"{timestamp} {message}\n")
    except Exception as log_fail:
        print(f"[Logging Error] Failed to write crash: {log_fail}")

# === STARTUP MEMORY INIT ===
def initialize_friday_state():
    global long_term_memory, short_term_memory, is_processing, pending_input, friday_is_thinking
    long_term_memory = load_long_term_memory()
    short_term_memory = []
    is_processing = False
    pending_input = None
    friday_is_thinking = False

initialize_friday_state()  # ✅ This runs even on import

# === FUNCTIONS ===
def get_user_name():
    for msg in long_term_memory:
        if msg["role"] == "user" and "my name is" in msg["content"].lower():
            parts = msg["content"].split()
            try:
                index = parts.index("is")
                return parts[index + 1].strip().strip(".").title()
            except (ValueError, IndexError):
                continue
    return "there"

def get_greeting():
    current_hour = datetime.now().hour
    if 5 <= current_hour <= 11:
        base = "Good morning"
    elif 12 <= current_hour <= 17:
        base = "Good afternoon"
    elif 18 <= current_hour <= 21:
        base = "Good evening"
    else:
        base = "It's late"
    name = get_user_name()
    phrases = [
        f"{base}, {name}. Friday is online and ready.",
        f"{base}, {name}. I'm standing by.",
        f"{base}, {name}. All systems are operational.",
        f"{base}. I'm online, {name}.",
        f"{base}. Ready when you are, {name}."
    ]
    return random.choice(phrases)

def ask_friday(user_input): 
    global short_term_memory, is_processing, pending_input, friday_is_thinking

    if is_processing:
        friday_speak("I'm still replying. I'll respond to that next.")
        pending_input = user_input
        return "Queued your message."

    cmd = user_input.strip().title()

    if cmd == "End Session":
        friday_speak("Are you sure you want to end the session and flush memory? Type 'Confirm End Session' to proceed.")
        return "Awaiting confirmation..."

    elif cmd == "Confirm End Session":
        friday_speak("Session terminated. Flushing memory.")
        try:
            backup_path = os.path.join(base_folder, 'memory', 'memory_backup_before_end_session.json')
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            with open(backup_path, 'w', encoding='utf-8') as backup:
                json.dump(long_term_memory, backup, indent=2)
            save_long_term_memory([])
        except Exception as e:
            friday_speak(f"[Memory Flush Error] {e}")
        short_term_memory.clear()
        friday_speak("Session flushed and core shutting down.")
        os._exit(0)

    elif cmd == "Flush Memory":
        friday_speak("Are you sure you want to flush memory? Type 'Confirm Flush Memory' to proceed.")
        return "Awaiting confirmation..."

    elif cmd == "Confirm Flush Memory":
        friday_speak("Memory flushed but session is still active.")
        try:
            backup_path = os.path.join(base_folder, 'memory', 'memory_backup_before_flush.json')
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            with open(backup_path, 'w', encoding='utf-8') as backup:
                json.dump(long_term_memory, backup, indent=2)
            save_long_term_memory([])
        except Exception as e:
            friday_speak(f"[Memory Flush Error] {e}")
        short_term_memory.clear()
        return "Memory flushed."

    elif cmd == "Restore Memory":
        backup_path = os.path.join(base_folder, 'memory', 'memory_backup_before_flush.json')
        if not os.path.exists(backup_path):
            return "No backup found to restore from."
        try:
            with open(backup_path, 'r', encoding='utf-8') as f:
                restored = json.load(f)
                save_long_term_memory(restored)
                friday_speak("Memory successfully restored from last flush backup.")
                return "Memory restored."
        except Exception as e:
            return f"[Restore Error] Failed to restore memory: {e}"

    is_processing = True

    # Friday assembles the context
    messages = long_term_memory + short_term_memory
    messages.append({"role": "user", "content": user_input})

    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")

    try:
        with open("display_output.txt", "a", encoding="utf-8") as f:
            f.write(f"{timestamp} User: {user_input}\n")
    except Exception as e:
        print(f"[Display Output Error - User] {e}")

    try:
        friday_is_thinking = True
        reply = process_response(messages)
        friday_is_thinking = False


        if reply.startswith("[Error:"):
            return reply

        short_term_memory.append({"role": "user", "content": user_input})
        short_term_memory.append({"role": "assistant", "content": reply})

        try:
            with open("display_output.txt", "a", encoding="utf-8") as f:
                f.write(f"{timestamp} Friday: {reply}\n")
        except Exception as e:
            print(f"[Display Output Error - Assistant] {e}")

        return reply

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"[Error: {e}]"

    finally:
        is_processing = False
        if pending_input:
            next_input = pending_input
            pending_input = None
            friday_speak("Processing your next message now...")
            ask_friday(next_input)



# === FULL STARTUP (ONLY IF RUN DIRECTLY) ===
def initialize_friday():
    friday_speak("Initializing core systems...")

    check_results = run_code_check()
    message = f"I ran a routine integrity scan and found the following:{check_results}"
    friday_speak(message)

    startup_message = (
        "System online. Memory loaded and operational.\n"
        "Running self-integrity check for core systems..."
    )
    friday_speak(startup_message)

    if check_results is None or len(check_results) == 0:
        friday_speak("No differences found.")
    else:
        friday_speak("\n".join(check_results[0]) if check_results[0] else "No differences found.")

    summary = (
        "No changes found."
        if not check_results or not check_results[0]
        else "Differences detected. Summary:\n" +
             "\n".join(
                 line for line in check_results[0]
                 if line.startswith(("+", "-", "@")) and not line.startswith(("+++", "---"))
             )
    )
    friday_speak(summary)
    friday_speak(get_greeting())
    print("Friday core ready for direct integration.")

if __name__ == "__main__":
    initialize_friday()
