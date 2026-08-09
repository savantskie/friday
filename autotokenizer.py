import sys
import re
import subprocess
import requests
from pathlib import Path

BASE_DIR = Path("/media/nate/Friday/Friday")

def get_llama_server_port():
    """Find the port llama-server is actually listening on."""
    try:
        result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if "llama-server" in line and "--port" in line:
                match = re.search(r"--port\s+(\d+)", line)
                if match:
                    return int(match.group(1))
    except Exception:
        pass
    try:
        result = subprocess.run(["ss", "-tlnp"], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if "llama-server" in line or "llama_server" in line:
                match = re.search(r":(\d+)", line)
                if match:
                    return int(match.group(1))
    except Exception:
        pass
    return None


def detect_template(chat_template: str) -> str:
    """
    Detect the template family from the model's Jinja2 template string.
    Returns a short name we can use to pick the right wrapper.
    """
    if not chat_template:
        return "chatml"  # llama-server default fallback

    t = chat_template.lower()

    if "<|im_start|>" in t:
        return "chatml"          # Qwen, Mistral-Nemo, many others
    if "<|start_header_id|>" in t:
        return "llama3"          # Llama 3.x
    if "<start_of_turn>" in t:
        return "gemma"           # Gemma 2/3
    if "<|system|>" in t:
        return "phi"             # Phi-3, Phi-4
    if "<|begin_of_sentence|>" in t or "deepseek" in t:
        return "deepseek"        # DeepSeek v2/v3/R1
    if "[inst]" in t:
        return "llama2"          # Llama 2, Mistral v1-v3
    if "<|user|>" in t:
        return "zephyr"          # Zephyr, some HF models
    if "### instruction" in t or "### system" in t:
        return "alpaca"          # Alpaca-style

    return "chatml"              # safe default


def wrap_content(text: str, role: str, template: str) -> str:
    """
    Wrap text in the correct chat template format for the detected model family.
    """
    if template == "chatml":
        return f"<|im_start|>{role}\n{text}<|im_end|>\n"

    elif template == "llama3":
        return f"<|start_header_id|>{role}<|end_header_id|>\n\n{text}<|eot_id|>"

    elif template == "gemma":
        return f"<start_of_turn>{role}\n{text}<end_of_turn>\n"

    elif template == "phi":
        return f"<|{role}|>\n{text}<|end|>\n"

    elif template == "deepseek":
        if role == "system":
            return f"<|begin_of_sentence|>{text}"
        return f"<|{role}|>{text}<|end_of_sentence|>"

    elif template == "llama2":
        if role == "system":
            return f"<<SYS>>\n{text}\n<</SYS>>\n"
        return f"[INST] {text} [/INST]"

    elif template == "zephyr":
        return f"<|{role}|>\n{text}\n"

    elif template == "alpaca":
        if role == "system":
            return f"### System:\n{text}\n\n"
        return f"### Instruction:\n{text}\n\n### Response:\n"

    else:
        # Unknown — fall back to raw text, still get a useful count
        return text


# --- Main ---

TARGET_FILE = input("Enter filename to tokenize: ").strip()
print("Role options: system, user, assistant (default: system)")
ROLE = input("Role [system]: ").strip().lower() or "system"

matches = [f for f in BASE_DIR.rglob("*") if f.is_file() and f.stem == TARGET_FILE]
if not matches:
    print(f"Error: '{TARGET_FILE}' not found under {BASE_DIR}")
    sys.exit(1)

path = matches[0]
text = path.read_text(encoding="utf-8", errors="ignore")

port = get_llama_server_port()
if not port:
    print("Error: No running llama-server found. Make sure a model is loaded in llama-swap.")
    sys.exit(1)

BASE_URL = f"http://localhost:{port}"

# Step 1: get the model's chat template from /props
try:
    props = requests.get(f"{BASE_URL}/props", timeout=10).json()
    chat_template = props.get("chat_template", "")
    model_name = props.get("default_generation_settings", {}).get("model", "unknown")
except Exception as e:
    print(f"Warning: couldn't fetch /props ({e}), defaulting to ChatML")
    chat_template = ""
    model_name = "unknown"

template_name = detect_template(chat_template)
print(f"\nModel:    {model_name}")
print(f"Template: {template_name} (detected)")

# Step 2: wrap content in the correct format
formatted = wrap_content(text, ROLE, template_name)

# Step 3: tokenize the formatted content
try:
    response = requests.post(
        f"{BASE_URL}/tokenize",
        json={
            "content": formatted,
            "add_special": True,
            "parse_special": True
        },
        timeout=30
    )
    response.raise_for_status()
except requests.exceptions.ConnectionError:
    print(f"Error: Can't reach llama-server on port {port}.")
    sys.exit(1)
except requests.exceptions.RequestException as e:
    print(f"Error: {e}")
    sys.exit(1)

tokens = response.json().get("tokens", [])

print(f"\n{path.name} as [{ROLE}]:")
print(f"  In-context token count:  {len(tokens)}")
print(f"  Recommended --keep:      {len(tokens) + 20}")
