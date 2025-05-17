# memory_summarizer.py

def is_relevant_line(line):
    line = line.strip()
    if not line:
        return False
    # Filter out obvious system logs or low-value data
    ignore_phrases = [
        "Checking backup file",
        "Restored from backup",
        "Performing memory flush",
        "status check", 
        "heartbeat:", 
        "debug", 
        "LLM:", 
        "loading file"
    ]
    for phrase in ignore_phrases:
        if phrase.lower() in line.lower():
            return False
    return True


def read_memory_file(path="memory.txt"):
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    return [line.strip() for line in lines if is_relevant_line(line)]


def main():
    relevant_lines = read_memory_file()

    print(f"\n[DEBUG] Found {len(relevant_lines)} relevant lines.")

    if relevant_lines:
        with open("filtered_memory.txt", "w", encoding="utf-8") as f:
            for line in relevant_lines:
                f.write(line + "\n")
        print("[DEBUG] Saved filtered_memory.txt")
    else:
        print("[DEBUG] No lines matched relevance criteria.")

    summary_lines = summarize_lines(relevant_lines)

    with open("memory_summary.txt", "w", encoding="utf-8") as f:
        for line in summary_lines:
            f.write(line + "\n")

    print(f"\nSummarized {len(relevant_lines)} relevant memory lines.")
    print("Saved summary to 'memory_summary.txt'")

from collections import defaultdict

def categorize_line(line):
    # You can expand this with more categories
    categories = {
        "preferences": ["likes", "dislikes", "prefers", "favorite", "enjoys"],
        "identity": ["friday is", "i am", "you are", "we are"],
        "commands": ["remember", "note", "log this", "add to memory"],
        "events": ["today", "this morning", "earlier", "just now", "last night"],
        "relationships": ["you and i", "our bond", "our connection", "i trust", "you trust"],
    }

    for category, keywords in categories.items():
        if any(word in line.lower() for word in keywords):
            return category
    return "misc"


def summarize_lines(lines):
    categorized = defaultdict(list)

    for line in lines:
        category = categorize_line(line)
        categorized[category].append(line)

    summary_lines = []

    for category, items in categorized.items():
        if not items:
            continue
        summary_lines.append(f"\n[{category.upper()}] — {len(items)} lines")
        for line in items[:3]:  # Only show 3 examples per category for now
            summary_lines.append(f"  - {line}")
        if len(items) > 3:
            summary_lines.append(f"  ... ({len(items)-3} more in this category)")

    return summary_lines

if __name__ == "__main__":
    main()