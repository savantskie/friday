import ollama

def process_response(messages):
    try:
        response = ollama.chat(
            model="llama3",
            messages=messages
        )
        return response['message']['content'].strip()
    except Exception as e:
        return f"[Error: {e}]"
