#!/usr/bin/env python3
import gguf

reader = gguf.GGUFReader("/media/nate/Friday/lmstudio models/HauhauCS/Qwen3.5-35B-A3B-Uncensored-HauhauCS-Aggressive/Qwen3.5-35B-A3B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf")

for field in reader.fields.values():
    print(field.name)
