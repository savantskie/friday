import ollama
import time

def query(messages):
    # Optional: Limit history to reduce token load
    trimmed_messages = messages[-50:]  # Keep the last 8 exchanges max

    start_time = time.time()

    response = ollama.chat(
        model="llama3",
        messages=trimmed_messages,
        options={
            "num_predict": 200,   # Limit max tokens in response
            "temperature": 0.7    # Optional: adjust creativity vs speed
        },
        stream=False  # Can flip to True later for real-time word streaming
    )

    end_time = time.time()
    print(f"[Response Worker] LLM response time: {end_time - start_time:.2f}s")

    return response["message"]["content"]
    
def process_response(messages):
    return query(messages)