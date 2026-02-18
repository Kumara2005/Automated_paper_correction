"""
Simple test script to verify Gemini API connection and model access
"""
import google.generativeai as genai
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Get API key
api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ API Key not found in .env file")
    exit(1)

print("✅ API Key loaded successfully")

try:
    # Configure Gemini
    genai.configure(api_key=api_key)
    print("✅ Gemini API configured")
    
    # Test with the model we're using in the app
    model = genai.GenerativeModel('models/gemini-2.5-flash')
    print(f"✅ Model 'models/gemini-2.5-flash' loaded successfully")
    
    # Simple test query
    response = model.generate_content("Say hello in one word")
    print(f"✅ Model successfully generated response: {response.text}")
    
    print("\n🎉 Everything is working correctly!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    exit(1)
