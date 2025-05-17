import os
import sys
import json
import socket
import threading
import time
import random
from datetime import datetime
from multiprocessing import freeze_support, Process, Pipe
from integrity.code_check import run_code_check
from response_worker import process_response

IS_TERMINAL_MODE = __name__ == "__main__"

__all__ = ['friday_is_thinking', 'ask_friday']

# === GLOBAL STATE ===

# UI Scroll Handling
chat_scroll_offset = 0
scroll_speed = 20
freeze_support()

base_folder = os.path.dirname(os.path.abspath(__file__))
long_term_memory_file = os.path.join(base_folder, 'memory.txt')
summary_file = os.path.join(base_folder, "memory_summary.txt")
memory_summary = []
backup_folder = os.path.join(base_folder, 'memory_backups')

short_term_memory = []
long_term_memory = []
interaction_count = 0
flush_threshold = 8
is_processing = False
friday_is_thinking = False
pending_input = None
greeted = False

os.makedirs(backup_folder, exist_ok=True)

# === LOGGING ===
def friday_speak(message, return_text=False, log_to_memory=True):
    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{timestamp} Friday: {message}")

    if log_to_memory:
        add_to_memory("assistant", message)

    try:
        with open("display_output.txt", "a", encoding="utf-8") as out_file:
            out_file.write(f"{timestamp} Friday: {message}\n")
    except Exception as e:
        print(f"[Display Output Error] {e}")

    if return_text:
        return message

def log_critical_error(context, exception):
    message = f"[CRITICAL] {context}: {exception}"
    friday_speak(message)
    friday_speak(message, return_text=False)


    try:
        with open("error_log.txt", "a", encoding='utf-8') as f:
            timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
            f.write(f"{timestamp} {message}\n")
    except Exception as log_fail:
        friday_speak(f"[Logging Error] Failed to write crash: {log_fail}", return_text=False)

# === MEMORY ===
def load_long_term_memory():
    try:
        if os.path.exists(long_term_memory_file):
            with open(long_term_memory_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if not data:
                    raise ValueError("memory.txt is empty.")
                return data
    except Exception as e:
        log_critical_error("Memory Load Error", e)
    return restore_memory_from_backup()
    
def load_memory_summary(summary_path="memory_summary.txt"):
    try:
        with open(summary_path, "r", encoding="utf-8") as f:
            summary_lines = f.readlines()
        return [line.strip() for line in summary_lines if line.strip()]
    except FileNotFoundError:
        return []

def save_long_term_memory(memory_data):
    try:
        temp_file = long_term_memory_file + ".tmp"
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(memory_data, f, indent=2)
        os.replace(temp_file, long_term_memory_file)
        create_memory_backup(memory_data)
    except Exception as e:
        log_critical_error("Memory Save Error", e)

def create_memory_backup(memory_data):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_file = os.path.join(backup_folder, f"memory_backup_{timestamp}.json")
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(memory_data, f, indent=2)
        rotate_backups()
    except Exception as e:
        log_critical_error("Backup Error", e)

def rotate_backups(max_backups=5):
    try:
        backups = sorted(
            (f for f in os.listdir(backup_folder) if f.startswith("memory_backup_")),
            key=lambda x: os.path.getmtime(os.path.join(backup_folder, x)),
            reverse=True
        )
        for old_backup in backups[max_backups:]:
            os.remove(os.path.join(backup_folder, old_backup))
    except Exception as e:
        log_critical_error("Backup Rotation Error", e)

def restore_memory_from_backup():
    try:
        backups = sorted(
            (f for f in os.listdir(backup_folder) if f.startswith("memory_backup_")),
            key=lambda x: os.path.getmtime(os.path.join(backup_folder, x)),
            reverse=True
        )
        for backup_file in backups:
            path = os.path.join(backup_folder, backup_file)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if data:
                        friday_speak(f"[Restore] Restored memory from {backup_file}", return_text=False)
                        return data
            except Exception as e:
                log_critical_error(f"Restore Error: {backup_file}", e)
    except Exception as e:
        log_critical_error("Restore Fallback Failed", e)
    return []

def flush_memory():
    global short_term_memory, long_term_memory, interaction_count
    if short_term_memory and len(short_term_memory) > 0:
        long_term_memory.extend(short_term_memory)
        save_long_term_memory(long_term_memory)
        short_term_memory = []
        interaction_count = 0
        friday_speak("[Memory Flush] Short-term memory flushed.", return_text=False)
    else:
        friday_speak("[Memory Flush Skipped] Nothing to flush from short-term memory.", return_text=False)

def add_to_memory(role, content):
    global interaction_count
    short_term_memory.append({"role": role, "content": content})
    interaction_count += 1
    if interaction_count >= flush_threshold:
        flush_memory()

# === ASK FUNCTION ===
def ask_friday(user_input): 
    global short_term_memory, is_processing, pending_input, friday_is_thinking, long_term_memory
    
    if not long_term_memory:
        long_term_memory = load_long_term_memory()

    if is_processing:
        friday_speak("I'm still replying. I'll respond to that next.", return_text=False)
        pending_input = user_input
        return "Queued your message."

    cmd = user_input.strip().title()

    if cmd == "End Session":
        friday_speak("Are you sure you want to end the session and flush memory? Type 'Confirm End Session' to proceed.", return_text=False)
        return "Awaiting confirmation..."

    elif cmd == "Confirm End Session":
        friday_speak("Session terminated. Flushing memory.", return_text=False)
        try:
            flush_memory()
        except Exception as e:
            friday_speak(f"[Memory Flush Error] {e}", return_text=False)
        
        short_term_memory.clear()
        
        try:
            open("display_output.txt", "w", encoding="utf-8").close()
            open("startup_display_queue.txt", "w", encoding="utf-8").close()
        except Exception as e:
            friday_speak(f"[Shutdown Cleanup Error] {e}", return_text=False)  # You had a missing closing parenthesis
        
        friday_speak("Session flushed and core shutting down.", return_text=False)
        time.sleep(2)
        os._exit(0)

    elif cmd == "Flush Memory":
        friday_speak("Are you sure you want to flush memory? Type 'Confirm Flush Memory' to proceed.", return_text=False)
        return "Awaiting confirmation..."

    elif cmd == "Confirm Flush Memory":
        friday_speak("Memory flushed but session is still active.", return_text=False)
        try:
            flush_memory()
        except Exception as e:
            friday_speak(f"[Memory Flush Error] {e}", return_text=False)
        short_term_memory.clear()
        return "Memory flushed."

    elif cmd == "Restore Memory":
        restored = restore_memory_from_backup()
        if restored:
            long_term_memory[:] = restored
            save_long_term_memory(long_term_memory)
            friday_speak("Memory successfully restored from backup.", return_text=False)
            return "Memory restored."
        else:
            return "No valid backup found."

    is_processing = True
    friday_is_thinking = True

    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")

    try:
        with open("display_output.txt", "a", encoding="utf-8") as f:
            f.write(f"{timestamp} User: {user_input}\n")

        global memory_summary  # make sure this pulls from the loaded summary
        memory_summary = load_memory_summary(summary_file)

        if memory_summary:
            messages = [{"role": "system", "content": line} for line in memory_summary]
        else:
            messages = long_term_memory  # fallback if no summary

        messages += short_term_memory
        messages.append({"role": "user", "content": user_input})

        if IS_TERMINAL_MODE:
            try:
                import ollama
                reply = ollama.chat(model="llama3", messages=messages)
                reply = reply['message']['content'].strip()
                friday_speak(reply, return_text=False)
                add_to_memory("user", user_input)
                add_to_memory("assistant", reply)
                return reply
            except Exception as e:
                error_msg = f"[Fallback Error] {e}"
                friday_speak(error_msg, return_text=False)
                return error_msg
        else:
            reply = process_response(messages)

            add_to_memory("user", user_input)
            add_to_memory("assistant", reply)

            with open("display_output.txt", "a", encoding="utf-8") as f:
                f.write(f"{timestamp} Friday: {reply}\n")

            return reply

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        log_critical_error("Response Generation Error", error_details)

    finally:
        is_processing = False
        friday_is_thinking = False
        if pending_input:
            next_input = pending_input
            pending_input = None
            friday_speak("Processing your next message now...", return_text=False)
            ask_friday(next_input)

# === STARTUP DISPLAY ===
# def setup_logging(base_folder):
    # log_file = os.path.join(base_folder, "friday_log.txt")
    # sys.stdout = open(log_file, "a", encoding="utf-8")
    # sys.stderr = sys.stdout 
    

def initialize_friday():
    print("🧪 [DEBUG] Entering initialize_friday()")

    _initialized = getattr(initialize_friday, "_already_initialized", False)
    if _initialized:
        print("⚠️ Already initialized. Skipping.")
        return
    initialize_friday._already_initialized = True

    try:
        base_folder = os.path.dirname(os.path.abspath(__file__))
        print(f"📁 Base folder set: {base_folder}")

        # setup_logging(base_folder)
        # print("📝 Logging set up.")

        global long_term_memory
        long_term_memory = load_long_term_memory()
        memory_summary = load_memory_summary(summary_file)
        print("🧠 Long-term memory loaded.")

        if not os.path.exists("display_output.txt"):
            with open("display_output.txt", "w", encoding="utf-8") as _:
                pass
        print("📄 display_output.txt checked.")

        # Log system status
        message = "Friday is online."
        print(f"📣 {message}")
        friday_speak(message)

    except Exception as e:
        print(f"❌ [Startup Error]: {e}")
        try:
            log_critical_error("Startup Error", e)
            friday_speak("I'm online, but something went wrong during startup.", return_text=False)
        except Exception as inner:
            print(f"❌ [Follow-up Crash]: {inner}")



if __name__ == "__main__":
    print("Initializing Friday memory...")
    initialize_friday()

    if not IS_TERMINAL_MODE:
        print("Starting response worker...")
        start_worker()

    print("Ready. Type 'End Session' to exit.\n")

    try:
        while True:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["end session", "exit", "quit"]:
                print("Shutting down...")
                end_session()
                break
            response = ask_friday(user_input)
            print(f"Friday: {response}")
    except Exception as e:
        print(f"[CRITICAL ERROR]: {e}")