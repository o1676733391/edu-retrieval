import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
api_key = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=api_key)

models_to_test = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash-lite",
    "gemini-3.5-flash",
    "gemini-flash-latest",
]

for model_name in models_to_test:
    print(f"\n--- Testing {model_name} ---")
    model = genai.GenerativeModel(model_name)
    try:
        response = model.generate_content("Say hello in one word")
        print(f"Success! Response: {response.text.strip()}")
    except Exception as e:
        print(f"Failed: {e}")
