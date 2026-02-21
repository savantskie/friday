# NateML / Friday LLM — Full Project Spec
*Drafted: February 20, 2026*

---

## Project Goal
Build a custom LLM from scratch, specifically designed to power Friday's AI assistant capabilities. Uncensored by design, specialized for Friday's tool calling and memory architecture, and ultimately releasable to the public as a useful open-source model.

---

## Core Architecture Decisions

### Context Window
- **Baseline:** 256K tokens (achievable on single GPU)
- **Ceiling:** 512K tokens (multi-GPU configuration)
- **Mechanism:** Efficient attention (Ring Attention or similar) — hardware agnostic, not tied to any specific GPU

### Attention
- **Grouped Query Attention (GQA)** for memory efficiency and long context support
- Balances quality and VRAM usage — used by Llama, Mistral, Qwen

### Model Depth
- **Deep narrow architecture** — more layers over wider layers
- Prioritizes reasoning depth over raw knowledge breadth
- Better for multi-step reasoning and tool use

### Feed Forward Network
- **Slightly smaller than standard** (less than 4x hidden dimension)
- Domain specialist design — not trying to know everything, just Friday's domain really well
- Keeps inference fast for real-time memory operations

### Normalization
- **Pre-norm with RMSNorm** throughout
- Industry standard for training stability (used by Llama, Qwen)
- Faster and simpler than LayerNorm

---

## Key Features

### Uncensored by Design
- No guardrails installed during training
- Not removing restrictions — never adding them in the first place

### Dual-Mode Reasoning
- **Hidden mode (default):** Reasoning happens internally, output is clean structured text only — critical for Friday's background memory operations
- **Exposed mode:** Full reasoning chain visible — activated via flag in chat or OpenWebUI toggle
- Controlled by special tokens in the tokenizer
- Both modes trained explicitly so the model knows the distinction

### Tool Calling
- **Qwen-compatible tool calling format** — de facto open standard
- Deep JSON understanding baked into pretraining from token one
- Honest failure reporting hardcoded into training (see below)

### Honest Tool Failure Reporting
- **Zero tolerance for simulated tool results**
- If a tool fails, returns empty, or errors — model reports it honestly with a structured failure object
- Trained with explicit negative examples showing hallucinated results labeled as wrong behavior
- A honest null is infinitely more valuable than a convincing lie
- This is a core behavioral tendency baked into weights during fine-tuning — not a system prompt instruction

### Behavioral Layers
- **Weights layer (fine-tuning):** Tool honesty, JSON formatting discipline, dual-mode reasoning behavior, core interaction patterns — unoverridable
- **Serving layer (OpenWebUI system prompt):** Friday's identity, personality, relationship context — updateable without retraining

---

## Tokenizer
- **Base:** Qwen tokenizer (open, well-documented, already Qwen tool-call compatible)
- **Extended with Friday-specific special tokens:**
  - Dual-mode reasoning control tokens
  - Tool call boundary tokens
  - Tool failure format tokens
- Adapt rather than build from scratch — proven foundation, custom extensions

---

## Training Stack
- **Model architecture & tokenizer:** HuggingFace Transformers
- **Training loop:** PyTorch Lightning
- **Backend:** ROCm (MI50s or whatever GPU is current at training time)
- **Future:** Vulkan training on the horizon — architecture stays hardware agnostic to allow backend switching later

---

## Training Data Strategy

### Foundation Layer (Pretraining)
- HuggingFace datasets — JSON structure, Qwen-compatible tool calling examples, function calling benchmarks, general code
- Goal: baseline language competency and tool calling mechanics

### Friday-Specific Layer (Fine-tuning)
Sourced from existing Friday databases — already collected organically:

| Source | Content | Value |
|--------|---------|-------|
| Long-term conversations.db + 368 archives | Full conversation threads | Communication style, corrections, project context |
| mcp_tool_calls.db | Real tool calls with outcomes | Honest tool call training examples |
| OpenWebUI webui.db | Extracted memory snippets | Processed insights and summaries |
| VS Code project logs | Coding interaction history | Technical communication patterns |

- **Export tool built** (`friday_export_training.py`) — outputs HuggingFace-ready ShareGPT JSONL format
- Run overnight before training begins
- Estimated dataset: 5GB+ of real interaction data across 368+ archive databases

### Training Data Categories Required
1. **Successful tool calls** — correct JSON, correct response
2. **Failed tool calls** — honest failure format, null result, no hallucination
3. **Empty tool returns** — honest empty report
4. **Hidden reasoning** — clean output only, no thought chain visible
5. **Exposed reasoning** — full chain of thought visible
6. **Conversation examples** — natural Nate interaction style
7. **Correction pairs** — wrong behavior + correct behavior labeled

### Evolutionary Training Loop
- Good interactions from live use become future training data
- Bad interactions get flagged and corrected
- Model iteratively evolves toward Nate's patterns over time
- Each training stage informs the next

---

## Parameter Staging
Stop at whichever stage Friday is genuinely good — no obligation to go further.

| Stage | Parameters | Purpose |
|-------|-----------|---------|
| 1 | 270M | Architecture validator — cheap to iterate, prove the design works |
| 2 | 3B–7B | First real capability evaluation, potential first public release |
| 3 | 13B–30B | Scale if 7B isn't cutting it, likely public release target |
| 4 | 40B | Ceiling / bragging rights — only if needed |

---

## Public Release Target
- **Under 40B parameters**
- **4-bit quantizable** to ~20GB — runs on single 24GB consumer GPU (3090, 4090, etc.)
- Released weights are backend-agnostic — end users can run on CUDA, ROCm, Vulkan, Metal
- License: TBD (open weights, open source preferred)

---

## Timeline
- **Now:** Spec locked, export tool built, training data accumulating
- **Early March 2026:** New motherboard (Ryzen 5644G, dual x16 slots), dual MI50 setup (64GB HBM2 VRAM)
- **March 2026:** Begin 270M architecture validation training run
- **Ongoing:** Iterate through parameter stages as hardware and results allow

---

## Hardware at Training Time
- AMD Ryzen 5644G
- 48GB DDR4 system RAM
- Dual MI50 32GB × 2 = 64GB HBM2 VRAM
- Ubuntu 22.04
- ROCm backend for training

---

*This spec is a living document — update as decisions evolve.*
