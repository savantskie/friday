import os
import json
import ollama
import socket
import threading
import time
from datetime import datetime
from integrity.code_check import run_code_check  # Make sure this matches the actual function name

base_folder = os.path.dirname(os.path.abspath(__file__))
long_term_memory_file = os.path.join(base_folder, 'memory.txt')
short_term_memory = []

# Add this check before the crashing line (line 74)
if check_results is None or len(check_results) == 0:
    friday_speak("No differences found.")
else:
    friday_speak("\n".join(check_results[0]) if check_results[0] else "No differences found.")

def load_long_term_memory():
    if os.path.exists(long_term_memory_file):
        try:
            with open(long_term_memory_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            friday_speak(f"Failed to load long-term memory: {e}")
    return []
    
def add_to_memory(role, content):
    short_term_memory.append({"role": role, "content": content})

def save_to_memory(role, content):
    long_term_memory.append({"role": role, "content": content})
    save_long_term_memory(long_term_memory)
    
def friday_speak(message):
    print(f"Friday: {message}")  # Console/debug print
    add_to_memory("assistant", message)
    save_to_memory("assistant", message)

    # ✅ Define timestamp before writing
    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    try:
        with open("display_output.txt", "a", encoding="utf-8") as out_file:
            out_file.write(f"{timestamp} {message}\n")
    except Exception as e:
        print(f"[Display Output Error] {e}")

       
def save_long_term_memory(memory_data):
    try:
        with open(long_term_memory_file, 'w', encoding='utf-8') as f:
            json.dump(memory_data, f, indent=2)
    except Exception as e:
        friday_speak("Failed to save long-term memory:", e)

# ✅ Initialize global memory right here:
long_term_memory = load_long_term_memory()

# --- STARTUP LOGIC ---
friday_speak("Initializing core systems...")
add_to_memory("assistant", "Initializing core systems...")

# Run integrity check
from integrity.code_check import run_code_check
check_results = run_code_check()
message = f"I ran a routine integrity scan and found the following:{check_results}"
friday_speak(message)
save_to_memory("assistant", message)

startup_message = (
    "System online. Memory loaded and operational.\n"
    "Running self-integrity check for core systems..."
)
friday_speak(startup_message)
add_to_memory("assistant", startup_message)

# Fixed line 78
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


add_to_memory("user", "Thanks for checking your code. Let me know if anything ever seems off.")

def schedule_integrity_checks():
    def loop_checks():
        while True:
            try:
                diffs, _ = run_code_check()
                if not diffs:
                    message = "I ran a routine integrity scan. All systems are stable — no changes were found."
                else:
                    summary_lines = [line for line in diffs if line.startswith(("+", "-", "@")) and not line.startswith(("+++", "---"))]
                    summary_snippet = "\n".join(summary_lines[:10])
                    message = f"I ran a routine integrity scan and found the following:\n{summary_snippet}\n(Changes trimmed for brevity)"
                friday_speak(message)
            except Exception as e:
                friday_speak(f"[ERROR] Integrity check failed: {e}")
            time.sleep(3 * 60 * 60)
    t = threading.Thread(target=loop_checks, daemon=True)
    t.start()

def reorganize_memory(short_term, long_term):
    for msg in short_term:
        if msg["role"] == "assistant" and len(msg["content"].split()) >= 10:
            long_term.append(msg)
        elif msg["role"] == "user":
            long_term.append(msg)
    return long_term



def ask_friday(user_input):
    global short_term_memory
    messages = long_term_memory + short_term_memory
    messages.append({"role": "user", "content": user_input})

    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")

    # Echo user input to display
    try:
        with open("display_output.txt", "a", encoding="utf-8") as f:
            f.write(f"{timestamp} User: {user_input}\n")
    except Exception as e:
        print(f"[Display Output Error - User] {e}")

    try:
        response = ollama.chat(model="llama3", messages=messages)
        reply = response["message"]["content"]
        short_term_memory.append({"role": "user", "content": user_input})
        short_term_memory.append({"role": "assistant", "content": reply})

        # Echo Friday's response to display
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

def get_greeting():
    return "Friday is online."
    
# Start periodic code integrity checks
schedule_integrity_checks()

if __name__ == "__main__":
    HOST = '127.0.0.1'
    PORT = 5050
    print("Socket server initializing...")  # Console-only log

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((HOST, PORT))
            s.listen()
            print(f"Listening on {HOST}:{PORT}")  # Still silent to display
            while True:
                try:
                    conn, addr = s.accept()
                except OSError as e:
                    print(f"Socket accept failed — {e}")
                    break
                with conn:
                    # Now it's safe to speak — the display is connected
                    friday_speak("Display connection established.")
                    run_code_check()
# You can summarize or skip entirely if already done at the top
                    greeting = get_greeting()
                    if greeting:
                        friday_speak(greeting)

                    while True:
                        data = conn.recv(1024)
                        if not data:
                            break
                        user_input = data.decode("utf-8").strip().lower()
                        if user_input == "end session":
                            friday_speak("Ending session. Goodbye.")
                            conn.sendall(b"Session ended.")
                            break
                        response = ask_friday(user_input)
                        conn.sendall(response.encode("utf-8"))
    except Exception as e:
        friday_speak(f"Socket server error: {e}")
