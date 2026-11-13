
import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

from app.llm.huggingface_client import generate_huggingface_answer

load_dotenv()

API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME")

if not API_KEY:
    raise RuntimeError("GOOGLE_GEMINI_API_KEY is not set.")
if not MODEL_NAME:
    raise RuntimeError("MODEL_NAME is not set.")

client = genai.Client(
    api_key=API_KEY,
    http_options=types.HttpOptions(timeout=120000)
)


def _error_text(error):
    return f"{type(error).__name__}: {error}"


def _is_quota_error(error):
    message = str(error).lower()
    return any(term in message for term in (
        "429", "resource_exhausted", "quota exceeded",
        "rate limit", "too many requests"
    ))


def _is_temporary_error(error):
    message = str(error).lower()
    return any(term in message for term in (
        "503", "502", "504", "500", "408", "499",
        "unavailable", "internal server error",
        "service unavailable", "timeout", "timed out",
        "temporarily overloaded", "connection reset"
    ))


def generate_answer(prompt, max_retries=4):
    if not isinstance(prompt, str) or not prompt.strip():
        return "Unable to generate an answer because the prompt is empty."

    max_retries = max(1, int(max_retries))
    gemini_error = None

    # Primary provider: Gemini
    for attempt in range(max_retries):
        try:
            print("\n" + "=" * 50)
            print("LLM PROVIDER: GEMINI")
            print("=" * 50)
            print(f"Model: {MODEL_NAME}")
            print(f"Attempt: {attempt + 1}/{max_retries}")

            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt
            )

            answer = getattr(response, "text", None) if response else None
            if not isinstance(answer, str) or not answer.strip():
                raise RuntimeError("Gemini returned an empty answer.")

            print("GEMINI RESPONSE RECEIVED")
            print(f"Answer length: {len(answer.strip())} characters")
            return answer.strip()

        except Exception as error:
            gemini_error = error
            print("\nGEMINI REQUEST FAILED")
            print(f"Error: {_error_text(error)}")

            if _is_quota_error(error):
                print("Gemini quota/rate limit detected; switching to fallback.")
                break

            if not _is_temporary_error(error):
                print("Non-temporary Gemini error; switching to fallback.")
                break

            if attempt < max_retries - 1:
                wait_time = min(3 * (2 ** attempt), 30)
                print(f"Temporary Gemini error; retrying in {wait_time} seconds.")
                time.sleep(wait_time)
            else:
                print("Gemini retries exhausted.")

    # Secondary provider: Hugging Face
    print("\n" + "=" * 50)
    print("LLM FALLBACK: HUGGING FACE")
    print("=" * 50)

    try:
        answer = generate_huggingface_answer(prompt)

        if isinstance(answer, str) and answer.strip():
            print("HUGGING FACE FALLBACK SUCCESSFUL")
            return answer.strip()

        print("Hugging Face returned an empty answer.")

    except Exception as error:
        hf_message = str(error).lower()
        print("HUGGING FACE FALLBACK FAILED")
        print(f"Error: {_error_text(error)}")

        if "402" in hf_message or "payment required" in hf_message:
            print("Hugging Face credits may be exhausted; check provider billing.")
        elif "429" in hf_message or "rate limit" in hf_message:
            print("Hugging Face rate limit reached.")
        elif "401" in hf_message or "403" in hf_message:
            print("Check Hugging Face credentials and model access.")

    # Keep the existing string-return contract for callers.
    print("\nALL LLM PROVIDERS FAILED")
    print(f"Gemini failure: {_error_text(gemini_error) if gemini_error else 'No answer'}")

    return (
        "Answer generation failed because neither Gemini nor Hugging Face "
        "returned a usable answer. Repository retrieval may have succeeded, "
        "but the LLM providers were unavailable. Check the provider errors "
        "in the backend terminal and try again when a provider is available."
    )


if __name__ == "__main__":
    test_prompt = """
You are an AI software engineering assistant.
Explain what this Java code does:

public static void main(String[] args) {
    SpringApplication.run(RestDemoApplication.class, args);
}
"""
    print(generate_answer(test_prompt))
