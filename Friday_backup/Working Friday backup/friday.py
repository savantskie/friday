import os
import json
import ollama
import socket

base_folder = os.path.dirname(os.path.abspath(__file__))
long_term_memory_file = os.path.join(base_folder, 'memory.txt')
short_term_memory = []

def load_long_term_memory():
    if os.path.exists(long_term_memory_file):
        try:
            with open(long_term_memory_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print("Failed to load long-term memory:", e)
    return []

def save_long_term_memory(memory):
    try:
        with open(long_term_memory_file, 'w', encoding='utf-8') as f:
            json.dump(memory, f, indent=2)
    except Exception as e:
        print("Failed to save long-term memory:", e)

def reorganize_memory(short_term, long_term):
    # Placeholder logic: only save meaningful assistant responses > 10 words
    for msg in short_term:
        if msg["role"] == "assistant" and len(msg["content"].split()) >= 10:
            long_term.append(msg)
        elif msg["role"] == "user":
            long_term.append(msg)
    return long_term

# Read the full memory on startup to refamiliarize Friday with herself
long_term_memory = load_long_term_memory()

def ask_friday(user_input):
    global short_term_memory
    messages = long_term_memory + short_term_memory
    messages.append({"role": "user", "content": user_input})

    try:
        response = ollama.chat(model="llama3", messages=messages)
        reply = response["message"]["content"]
        short_term_memory.append({"role": "user", "content": user_input})
        short_term_memory.append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"[Error: {e}]"

import socket

if __name__ == "__main__":
    print("Friday: Socket server initializing...")
    HOST = '127.0.0.1'
    PORT = 5050

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((HOST, PORT))
            s.listen()
            print(f"Friday: Listening on {HOST}:{PORT}")

            while True:
                try:
                    conn, addr = s.accept()
                except OSError as e:
                    print(f"Friday: Socket accept failed — {e}")
                    break

                with conn:
                    print(f"Friday: Connection established with {addr}")
                    while True:
                        try:
                            data = conn.recv(4096)
                            if not data:
                                break
                            user_input = data.decode('utf-8')
                            if user_input.strip().lower() == "end session":
                                conn.sendall(b"Friday: Logging off and saving important memories...")
                                final_memory = reorganize_memory(short_term_memory, long_term_memory)
                                save_long_term_memory(final_memory)
                                print("Friday: Session ended. Waiting for new connection...")
                                break
                            response = ask_friday(user_input)
                            conn.sendall(response.encode('utf-8'))
                        except Exception as e:
                            print(f"Friday: Error during communication — {e}")
                            break
    except Exception as e:
        print(f"Friday: Server crashed during startup — {e}")
