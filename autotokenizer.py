import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

from pathlib import Path
from transformers import AutoTokenizer
import warnings
warnings.filterwarnings("ignore")

BASE_DIR = Path("/media/nate/Friday/Friday")

# Prompt user for filename
TARGET_FILE = input("Enter filename to tokenize: ").strip()

# Search for any file starting with TARGET_FILE
matches = [f for f in BASE_DIR.rglob("*") if f.is_file() and f.stem == TARGET_FILE]

if not matches:
    print(f"Error: '{TARGET_FILE}' not found under {BASE_DIR}")
    exit(1)

path = matches[0]
text = path.read_text(encoding="utf-8", errors="ignore")

# Use GLM-4.7-Flash tokenizer
tokenizer = AutoTokenizer.from_pretrained(
    "Qwen/Qwen2.5-7B-Instruct",
    use_fast=True
)

tokens = tokenizer.encode(text, add_special_tokens=False)

print(f"{path.name}: {len(tokens)} tokens")
