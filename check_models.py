import google.generativeai as genai
import os
from dotenv import load_dotenv

# Try to load API key from .env file (if you have one)
load_dotenv()

# Or load from Streamlit secrets (st.secrets) if running in Streamlit
# For this script, we'll try environment variables first
api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

if not api_key:
    print("API Key not found in environment variables.")
    print("Please run:")
    print("set GOOGLE_API_KEY=YOUR_KEY_HERE")
    print("...and then run this script again.")
else:
    try:
        genai.configure(api_key=api_key)

        print("--- Finding models your API key can use ---")

        found_models = False
        for m in genai.list_models():
            # Check if the model supports the 'generateContent' method
            if 'generateContent' in getattr(m, 'supported_generation_methods', []):
                print(f"Found usable model: {m.name}")
                found_models = True

        if not found_models:
            print("No models supporting 'generateContent' were found for your key.")

    except Exception as e:
        print(f"An error occurred: {e}")
