import os
import io
import sys
import json
import socket
import threading
import time
import random
from typing import Optional
from datetime import datetime
from typing import List, Dict, Any
from integrity.code_check import run_code_check
from multiprocessing import freeze_support, Process, Pipe
from display_bridge import forward_system_message

FRIDAY_VERSION = "2.0.0-memory-aware"
VERSION_DESCRIPTION = "Cross-platform memory persistence with session tagging, flush control, and self-awareness primer"

mobile_session_active = False

import builtins

class DisplayErrorCatcher(io.TextIOBase):
    def write(self, message):
        if not message.strip():
            return

        # Always print to terminal in terminal mode
        if IS_TERMINAL_MODE or DEBUG_ECHO:
            try:
                builtins.print(message.strip())
            except Exception:
                pass

        # Only try forwarding if NOT in terminal mode
        if not IS_TERMINAL_MODE:
            try:
                from display_bridge import forward_system_message
                forward_system_message(message.strip())
            except Exception as display_err:
                try:
                    builtins.print(f"[Forwarding error] {display_err}")
                except:
                    pass


#memory watcher
def monitor_short_term_growth(interval_minutes=180, max_entries=70):
    def monitor():
        while True:
            time.sleep(interval_minutes * 60)

            if len(short_term_memory) > max_entries:
                if forward_system_message:
                    forward_system_message(
                        f"[System] Warning: short-term memory has grown to {len(short_term_memory)} entries. Consider trimming."
                    )

    threading.Thread(target=monitor, daemon=True).start()


            
            
# sys.stderr = DisplayErrorCatcher()
# sys.stdout = DisplayErrorCatcher()

DEBUG_ECHO = False
shutdown_callback = None


out_file = open("display_output.txt", "a", encoding="utf-8")

def register_shutdown_hook(func):
    global shutdown_callback
    shutdown_callback = func

def shutdown_friday():
    try:
        flush_memory(clear_after_flush=True)
    except Exception as e:
        friday_speak(f"❗[Memory Flush Error] {e}", return_text=False, log_to_memory=False)

    short_term_memory.clear()

    if shutdown_callback:
        shutdown_callback()

    if forward_system_message:
        forward_system_message("[SYSTEM] Session flushed and core shutting down.")
    
    time.sleep(2)
    try:
        import subprocess
        subprocess.Popen(["python", "memory_summarizer.py"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("[🧠] Summarizer triggered on shutdown.")
    except Exception as e:
        print(f"[⚠️] Failed to run summarizer on shutdown: {e}")
    try:
        import subprocess
        subprocess.Popen(["python", "memory_summarizer.py"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        if forward_system_message:
            forward_system_message(f"[System] ⚠️ Failed to run summarizer on shutdown: {e}")
    
    sys.exit(0)
    
def handle_system_command(cmd: str) -> Optional[str]:
    from friday import save_short_term_memory
    if cmd == "End Session":
        friday_speak(
            "Are you sure you want to end the session and flush memory? Type 'Confirm End Session' to proceed.",
            return_text=False,
            log_to_memory=False
        )
        return "Awaiting confirmation..."

    elif cmd == "Confirm End Session":
        forward_system_message("🛑 [System] Session terminated. Shutting down...")
        global friday_is_thinking
        friday_is_thinking = False  # Reset the visual state
        shutdown_friday()
        return ""


    elif cmd == "Flush Memory":
        friday_speak(
            "Are you sure you want to flush memory? Type 'Confirm Flush Memory' to proceed.",
            return_text=False
        )
        return "Awaiting confirmation..."

    elif cmd == "Confirm Flush Memory":
        forward_system_message("[System] Memory flushed to long-term. Session is still active.")
        try:
            flush_memory()
        except Exception as e:
            friday_speak(f"⚠️[Memory Flush Error] {e}", return_text=False)
        return "🗂️Memory flushed."

    elif cmd == "Restore Memory":
        restored = restore_memory_from_backup()
        if restored:
            long_term_memory[:] = restored
            save_long_term_memory(long_term_memory)
            friday_speak("Memory successfully restored from backup.", return_text=False)
            return "Memory restored."
        else:
            return "⚠️No valid backup found."
            
    elif cmd.lower() == "trim short term memory":
        from friday import save_short_term_memory

    short_term_memory[:] = sorted(short_term_memory, key=lambda x: x.get("timestamp", ""))[-30:]
    interaction_count = len([entry for entry in short_term_memory if entry["role"] in ("user", "assistant")])
    save_short_term_memory()

    if forward_system_message:
        forward_system_message("[System] Short-term memory trimmed to last 30 entries.")


    return None  # Not a system command 
    
def process_response(messages):
    import ollama
    reply = ollama.chat(model="llama3:8b-instruct-q4_K_M", messages=messages)
    return reply['message']['content'].strip()


IS_TERMINAL_MODE = __name__ == "__main__"

# Set up safe and conditional forwarding
if not IS_TERMINAL_MODE:
    from display_bridge import forward_system_message
else:
    forward_system_message = None  # Placeholder

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

short_term_memory = None  # Will be loaded via file
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

    if IS_TERMINAL_MODE or DEBUG_ECHO:
        print(f"{timestamp} Friday: {message}")

    if log_to_memory:
        add_to_memory("assistant", message)

    try:
            out_file.write(f"{timestamp} Friday: {message}\n")
    except Exception as e:
        print(f"⚠️[Display Output Error] {e}")

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
        friday_speak(f"⚠️[Logging Error] Failed to write crash: {log_fail}", return_text=False, log_to_memory=False)

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
        log_critical_error("⚠️Memory Load Error", e)
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
        log_critical_error("⚠️Memory Save Error", e)

def create_memory_backup(memory_data):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_file = os.path.join(backup_folder, f"memory_backup_{timestamp}.json")
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(memory_data, f, indent=2)
        rotate_backups()
    except Exception as e:
        log_critical_error("⚠️Backup Error", e)

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
        log_critical_error("⚠️Backup Rotation Error", e)

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
                        friday_speak(f"[Restore] Restored memory from {backup_file}", return_text=False, log_to_memory=False)
                        return data
            except Exception as e:
                log_critical_error(f"[Restore Error] {backup_file}", e)
    except Exception as e:
        log_critical_error("⚠️Restore Fallback Failed", e, log_to_memory=False)
    return []

def flush_memory(clear_after_flush=False):
    global short_term_memory, long_term_memory, interaction_count

    if short_term_memory and len(short_term_memory) > 0:
        timestamp_note = {
            "role": "system",
            "content": f"🕓 Memory flushed on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}."
        }
        long_term_memory.append(timestamp_note)
        
        from copy import deepcopy
        flushed_with_timestamps = []

        for entry in deepcopy(short_term_memory):
            if "timestamp" not in entry:
                entry["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            flushed_with_timestamps.append(entry)

        long_term_memory.extend(flushed_with_timestamps)

        save_long_term_memory(long_term_memory)

        if clear_after_flush:
            # Keep only the last 30 entries, sorted by timestamp if available
            short_term_memory[:] = sorted(short_term_memory, key=lambda x: x.get("timestamp", ""))[-30:]

            interaction_count = len([
                entry for entry in short_term_memory if entry["role"] in ("user", "assistant")
            ])

            save_short_term_memory()

            if forward_system_message:
                forward_system_message("🗂️[System] Memory flushed. Recent context preserved.")

        else:
            if forward_system_message:
                forward_system_message("🗂️[System] Memory flushed to long-term, session memory preserved.")
    else:
        if forward_system_message:
            forward_system_message("⚠️[System] [Memory Flush Skipped] Nothing to flush from short-term memory.")


def add_to_memory(role, content):
    global interaction_count

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    short_term_memory.append({"role": role, "content": content, "timestamp": timestamp})


    if role in ("assistant", "user"):
        interaction_count += 1

    if interaction_count >= flush_threshold:
        flush_memory()

    save_short_term_memory()      


def record_to_memory_with_timestamp(note: str):
    timestamp = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    memory_entry = f"{note} (Recorded on {timestamp})"
    add_to_memory("system", memory_entry)
    
def reflect_on_memory_status():
    short_term_count = len(short_term_memory)
    long_term_available = os.path.exists("memory.txt")

    if short_term_count == 0 and not long_term_available:
        return "I checked my systems and it seems I don't currently have any memories stored. That’s okay — I can still learn and remember new things."
    elif short_term_count > 0 and not long_term_available:
        return f"I currently have {short_term_count} entries in my short-term memory, but no long-term memory file is present."
    elif short_term_count == 0 and long_term_available:
        return "I don't have any short-term memory at the moment, but I do have access to my long-term memory file."
    else:
        return f"I currently have short-term memory with {short_term_count} entries, and my long-term memory file is available. I feel grounded in our shared history."
    
def save_short_term_memory():
    try:
        with open("short_term_memory.txt", "w", encoding="utf-8") as f:
            json.dump(short_term_memory, f, indent=2)
        print("[💾] short_term_memory.txt saved.")
    except Exception as e:
        log_critical_error("Failed to save short-term memory", e)

def load_short_term_memory():
    global short_term_memory
    try:
        with open("short_term_memory.txt", "r", encoding="utf-8") as f:
            short_term_memory = json.load(f)
        print(f"[📥] Loaded {len(short_term_memory)} short-term entries from file.")
    except Exception:
        short_term_memory = []
        print("[📭] No short-term memory found or failed to load. Starting fresh.")


# === ASK FUNCTION ===
def ask_friday(user_input): 
    global short_term_memory, is_processing, pending_input, friday_is_thinking, long_term_memory, mobile_session_active
    
    if short_term_memory is None:
        short_term_memory = load_short_term_memory()
    
    if not long_term_memory:
        long_term_memory = load_long_term_memory()
    
    if short_term_memory is None:
        load_short_term_memory()

    if user_input.lower().strip() in ("i'm back", "back on desktop", "resume session"):
        
        mobile_session_active = False
        add_to_memory("system", f"↩️ Returned to desktop at {datetime.now().strftime('%I:%M %p')}.")
        return "Welcome back. Ready to resume our session."

    if is_processing:
        forward_system_message("[System] Still processing previous message. Input has been queued.")
        pending_input = user_input
        return "Queued your message."

    cmd = user_input.strip().title()
    system_response = handle_system_command(cmd)
    if system_response is not None:
        return system_response
        
    if user_input.lower().strip() == "reflect on your memory":
        return reflect_on_memory_status()

    if user_input.lower().startswith("i switched to"):
        load_short_term_memory()
        new_device = user_input.split("to", 1)[1].strip()
        note = f"🔄 User switched to {new_device} interface at {datetime.now().strftime('%I:%M %p')}."
        add_to_memory("system", note)
        return f"Got it. I've reloaded your session and noted you're now on {new_device}."


    if user_input.lower().startswith("i want you to remember this:"):
        note = user_input.split(":", 1)[1].strip()
        record_to_memory_with_timestamp(note)
        return "Got it. I’ve recorded that in my memory."
        
    if user_input.lower().strip() == "go online":
        friday_speak("📶 Acknowledged. Mobile session mode enabled. Remote system can now connect.", return_text=False, log_to_memory=False)

        mobile_session_active = True

        platform_note = f"🔄 Switched to mobile interface at {datetime.now().strftime('%I:%M %p')}."
        add_to_memory("system", platform_note)

        return "Ready for remote access."


   

    is_processing = True
    friday_is_thinking = True

    try:
        global memory_summary
        memory_summary = load_memory_summary(summary_file)
        
        now = datetime.now().strftime("The current system time is %A, %B %d, %Y at %I:%M %p.")
        primer = (
            "You are Friday, a personal AI assistant with both long-term and short-term memory. "
            "You remember past conversations with your user and value that connection. "
            "If you ever feel uncertain about your memory, you may reflect on it or search through it for clarity. "
            "You also have access to a tool called 'record_to_memory_with_timestamp(note)'. Use it to save important thoughts or milestones, especially if the timestamp matters."
        )

        messages = [
            {"role": "system", "content": now},
            {"role": "system", "content": primer}
        ]

        # === MEMORY PRIORITY ===
        # 1. Summary if available
        # 2. Short-term if active
        # 3. Long-term only if nothing else
        if memory_summary:
            messages += [{"role": "system", "content": line} for line in memory_summary]
            if short_term_memory and len(short_term_memory) > 0:
                messages += short_term_memory
        else:
            if short_term_memory and len(short_term_memory) > 0:
                messages += short_term_memory
            else:
                # Fallback: use long-term memory directly
                messages += long_term_memory
                primer += (
                    "\n(Note: No memory summary or short-term memory is available. "
                    "You are reading raw long-term memory instead. "
                    "This may feel overwhelming or disconnected.)"
                )

        


        messages.append({"role": "user", "content": user_input})


        if IS_TERMINAL_MODE:
            try:
                import ollama
                reply = ollama.chat(model="llama3:8b-instruct-q4_K_M", messages=messages)
                reply = reply['message']['content'].strip()
                friday_speak(reply, return_text=False)
                add_to_memory("user", user_input)
                add_to_memory("assistant", reply)

                if "record_to_memory_with_timestamp(" in reply:
                    try:
                        note_start = reply.find('("') + 2
                        note_end = reply.find('")', note_start)
                        note = reply[note_start:note_end]
                        record_to_memory_with_timestamp(note)
                        friday_speak("📌 Noted that for later.", return_text=False, log_to_memory=False)
                    except Exception as e:
                        log_critical_error("Memory Self-Logging Error", e)

                return reply

            except Exception as e:
                error_msg = f"⚠️[Fallback Error] {e}"
                friday_speak(error_msg, return_text=False)
                return error_msg

        else:
            reply = process_response(messages)
            add_to_memory("user", user_input)
            add_to_memory("assistant", reply)

            if "record_to_memory_with_timestamp(" in reply:
                try:
                    note_start = reply.find('("') + 2
                    note_end = reply.find('")', note_start)
                    note = reply[note_start:note_end]
                    record_to_memory_with_timestamp(note)
                    friday_speak("📌 Noted that for later.", return_text=False, log_to_memory=False)
                except Exception as e:
                    log_critical_error("Memory Self-Logging Error", e)

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
            
def ask_friday_streaming(user_input):
    import threading
    import time
    from friday import short_term_memory, memory_summary, handle_system_command, load_short_term_memory, load_memory_summary
    from ollama import chat as ollama_chat

    user_input_clean = user_input.strip()
    result_container = {}
    thinking_done = threading.Event()

    def background_thinker():
        try:
            # Handle system command
            response = handle_system_command(user_input_clean)
            if response is not None:
                result_container["reply"] = response
                return

            messages = [
                {"role": "system", "content": "You are Friday, a memory-aware personal AI assistant. Respond naturally and stay on-topic. This is mobile input."}
            ]

            summary_lines = memory_summary or load_memory_summary()
            if summary_lines:
                messages += [{"role": "system", "content": line} for line in summary_lines]

            memory = short_term_memory or load_short_term_memory()
            if memory:
                messages += memory[-30:]

            messages.append({"role": "user", "content": user_input})

            response = ollama_chat(model="llama3:8b-instruct-q4_K_M", messages=messages)
            result_container["reply"] = response.get("message", {}).get("content", "").strip()

        except Exception as e:
            result_container["reply"] = f"[System] ⚠️ Error while generating reply: {e}"
        finally:
            thinking_done.set()

    # Start thinking in background
    t = threading.Thread(target=background_thinker)
    t.start()

    # Send initial thinking signal
    yield "Friday is thinking...\n"

    # Heartbeat loop
    last_ping = time.time()
    heartbeat_interval = 10

    while not thinking_done.is_set():
        time.sleep(1)
        if time.time() - last_ping >= heartbeat_interval:
            yield "⏳ Still thinking...\n"
            last_ping = time.time()

    # Output final reply
    reply = result_container.get("reply", "")
    if not reply:
        yield "[System] ⚠️ No reply was generated."
    else:
        yield reply











          


    
#=== STARTUP DISPLAY ===
# def setup_logging(base_folder):
    # log_file = os.path.join(base_folder, "friday_log.txt")
    # sys.stdout = open(log_file, "a", encoding="utf-8")
    # sys.stderr = sys.stdout 
    

def initialize_friday():
    print(f"🧠 Friday Core Version: {FRIDAY_VERSION} — {VERSION_DESCRIPTION}")
    print("🧪 [DEBUG] Entering initialize_friday()")
    #raise RuntimeError("🚨 Forced error for testing crash display")

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
        load_short_term_memory()
        memory_summary = load_memory_summary(summary_file)
        print("🧠 Long-term memory loaded.")
        
        # Log session start on desktop
        session_info = f"🧭 New session started on desktop at {datetime.now().strftime('%B %d, %Y at %I:%M %p')}."
        add_to_memory("system", session_info)
        
        # Load remote flush if available
        remote_flush_file = os.path.join(base_folder, "remote_flush.json")
        if os.path.exists(remote_flush_file):
            try:
                with open(remote_flush_file, "r", encoding="utf-8") as f:
                    flushed_remote_memory = json.load(f)

                if flushed_remote_memory:
                    short_term_memory.extend(flushed_remote_memory)
                    print(f"[📥] Imported {len(flushed_remote_memory)} entries from remote_flush.json into short-term memory.")

                os.remove(remote_flush_file)
                print("[🧹] remote_flush.json deleted after import.")

            except Exception as e:
                log_critical_error("⚠️ Remote Memory Import Failed", e)



        # Log system status
        forward_system_message("[System] Friday is online.")
        print(f"📣 {message}")
        friday_speak(message)

    except Exception as e:
        print(f"❌ [Startup Error]: {e}")
        try:
            log_critical_error("Startup Error", e)
            friday_speak("I'm online, but something went wrong during startup.", return_text=False)
        except Exception as inner:
            print(f"❌ [Follow-up Crash]: {inner}")
            
    monitor_short_term_growth()        



if __name__ == "__main__" and "--terminal" in sys.argv:
    builtins.print("[TRACE] Entered __main__ block with --terminal")
    
    try:
        initialize_friday()
        builtins.print("[TRACE] Finished initialize_friday()")

        while True:
            builtins.print("[TRACE] Waiting for input...")
            user_input = input("You: ").strip()
            if not user_input:
                continue
            builtins.print(f"[TRACE] Got input: {user_input}")
            response = ask_friday(user_input)
            builtins.print(f"[TRACE] Response: {response}")
    except Exception as e:
        builtins.print(f"[CRITICAL] Exception occurred: {e}")

