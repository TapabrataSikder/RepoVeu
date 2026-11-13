# app/llm/huggingface_client.py
import os
from dotenv import load_dotenv
from huggingface_hub import InferenceClient

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")
HF_MODEL_NAME = os.getenv("HF_MODEL_NAME")

if not HF_TOKEN:
    raise RuntimeError("HF_TOKEN is not set.")

if not HF_MODEL_NAME:
    raise RuntimeError("HF_MODEL_NAME is not set.")

client = InferenceClient(api_key=HF_TOKEN)

def generate_huggingface_answer(prompt):
    """
    Generate an answer using Hugging Face Inference Providers.
    This function is intended to be used as the secondary
    LLM when Gemini is unavailable or its quota is exhausted.
    """
    if not prompt or not prompt.strip():
        return "Unable to generate an answer because the prompt is empty."

    try:
        print()
        print("=" * 50)
        print("SENDING REQUEST TO HUGGING FACE")
        print("=" * 50)
        print(f"Model: {HF_MODEL_NAME}")

        response = client.chat.completions.create(
            model=HF_MODEL_NAME,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=2048,
        )

        if response is None:
            raise RuntimeError("Hugging Face returned no response object.")

        if not response.choices:
            raise RuntimeError("Hugging Face returned no choices.")

        answer = response.choices[0].message.content

        if answer is None or not answer.strip():
            raise RuntimeError("Hugging Face returned an empty answer.")

        print()
        print("=" * 50)
        print("HUGGING FACE RESPONSE RECEIVED")
        print("=" * 50)
        print(f"Answer length: {len(answer.strip())} characters")

        return answer.strip()

    except Exception as error:
        error_type = type(error).__name__
        error_text = str(error)

        print()
        print("=" * 50)
        print("HUGGING FACE REQUEST FAILED")
        print("=" * 50)
        print(f"Error type: {error_type}")
        print(f"Error: {error_text}")

        return None

if __name__ == "__main__":
    test_prompt = """
You are an AI software engineering assistant.

Explain what the following Java code does:

public static void main(String[] args) {
    SpringApplication.run(RestDemoApplication.class, args);
}
"""

    print("=" * 50)
    print("HUGGING FACE LLM TEST")
    print("=" * 50)

    answer = generate_huggingface_answer(test_prompt)

    print()
    print("=" * 50)
    print("ANSWER")
    print("=" * 50)
    print()
    print(answer)