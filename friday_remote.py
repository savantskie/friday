import os
import subprocess
import time
import requests
import smtplib
from email.message import EmailMessage
from flask import Flask, request, jsonify, render_template, Response, stream_with_context
from friday import ask_friday_streaming  # must exist in friday.py
import json
import atexit
from friday import short_term_memory, flush_memory

def handle_remote_shutdown():
    from friday import save_short_term_memory  # ✅ import here so it's callable

    print("[🔻] Remote session shutting down... flushing memory.")
    try:
        flush_memory(clear_after_flush=True)

        # Clear short-term memory and update file
        global short_term_memory
        # short_term_memory already trimmed by flush_memory()
        save_short_term_memory()

        print("[🧹] short_term_memory.txt cleared after remote shutdown.")

    except Exception as e:
        print(f"[ERROR] Failed to flush remote memory: {e}")


# === CONFIGURATION ===
SECRET_KEY = "051407A1007b1982C!"
TO_EMAIL = "savantskie@gmail.com"
FROM_EMAIL = "nmerrill2000@outlook.com"
APP_PASSWORD = "crzetytkgxvsfgwm"
NGROK_PATH = "C:\\ngrok\\ngrok.exe"
FLASK_PORT = 5000
# =====================

# Start ngrok tunnel
print("[...] Starting ngrok tunnel...")
ngrok = subprocess.Popen([NGROK_PATH, "http", str(FLASK_PORT)])
time.sleep(4)

# Get ngrok public URL
try:
    data = requests.get("http://localhost:4040/api/tunnels").json()
    public_url = data['tunnels'][0]['public_url']
    print(f"[✔] ngrok URL: {public_url}")
except Exception as e:
    print(f"[ERROR] Could not retrieve ngrok URL: {e}")
    public_url = None

# Send email
if public_url:
    try:
        msg = EmailMessage()
        msg.set_content(f"Friday is live at: {public_url}")
        msg['Subject'] = "Friday is Online"
        msg['From'] = FROM_EMAIL
        msg['To'] = TO_EMAIL

        with smtplib.SMTP("smtp.office365.com", 587) as smtp:
            smtp.starttls()
            smtp.login(FROM_EMAIL, APP_PASSWORD)
            smtp.send_message(msg)

        print(f"[✔] Email sent to {TO_EMAIL}")

    except Exception as e:
        print(f"[ERROR] Failed to send email: {e}")


# === Flask Server ===
app = Flask(__name__, template_folder="Templates")
atexit.register(handle_remote_shutdown)

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    auth = request.headers.get("Authorization", "")
    if not auth or not auth.startswith("Bearer ") or auth.split(" ")[1] != SECRET_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    message = data.get("message", "").strip()

    if not message:
        return jsonify({"error": "No message provided"}), 400

    try:
        # CORRECT: Don't use list(), just gather from generator
        reply = ""
        for chunk in ask_friday_streaming(message):
            reply += chunk

        return reply.strip(), 200, {'Content-Type': 'text/plain'}

    except Exception as e:
        return f"[ERROR] {e}", 500, {'Content-Type': 'text/plain'}





if __name__ == "__main__":
    print(f"[✔] Flask is running on http://0.0.0.0:{FLASK_PORT}")
    app.run(host="0.0.0.0", port=FLASK_PORT)