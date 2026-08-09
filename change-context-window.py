import gguf

reader = gguf.GGUFReader("/media/nate/Friday/lmstudio models/HauhauCS/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf", "r+")

for field in reader.fields.values():
    if field.name == "llama.context_length":
        field.parts[-1][0] = 1010000
        print(f"Patched: {field.name} -> 1,010,000")
        break

print("Done.")
