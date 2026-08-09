#!/usr/bin/env python3
import gguf

reader = gguf.GGUFReader("/media/nate/Friday/lmstudio models/HauhauCS/Qwen3.5-35B-A3B-Uncensored-HauhauCS-Aggressive/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf", "r+")

for field in reader.fields.values():
    if field.name == "qwen35moe.context_length":
        field.parts[-1][0] = 266144
        print(f"Patched: {field.name} -> 266144")
        break

print("Done.")
