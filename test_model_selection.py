"""
Test script to verify dynamic model selection functionality
"""
import streamlit as st
import sys
import os

# Mock streamlit functions for testing
class MockStreamlit:
    def __init__(self):
        self.secrets = {
            'GOOGLE_API_KEY': 'AIzaSyALAs6t-hrB3oskizuVyqexfHwjzVQvoxs'
        }
    
    def cache_data(self, ttl=None):
        def decorator(func):
            return func
        return decorator
    
    def cache_resource(self, func):
        return func
    
    def success(self, msg): print(f"✅ {msg}")
    def info(self, msg): print(f"ℹ️ {msg}")
    def warning(self, msg): print(f"⚠️ {msg}")
    def error(self, msg): print(f"❌ {msg}")
    def write(self, msg): print(msg)

# Replace streamlit module temporarily
original_st = sys.modules.get('streamlit')
sys.modules['streamlit'] = MockStreamlit()

# Now we can import utils
import google.generativeai as genai
from utils import get_available_gemini_models, get_default_model_fallback, get_gemini_model

print("="*60)
print("Testing Dynamic Model Selection System")
print("="*60)

# Test 1: Get available models
print("\n1️⃣ Testing get_available_gemini_models()...")
available = get_available_gemini_models()
if available:
    print(f"   Found {len(available)} models:")
    for model in available[:5]:  # Show first 5
        print(f"   - {model}")
    if len(available) > 5:
        print(f"   ... and {len(available) - 5} more")
else:
    print("   ⚠️ No models found (this is okay, will use fallback)")

# Test 2: Get fallback list
print("\n2️⃣ Testing get_default_model_fallback()...")
fallback = get_default_model_fallback()
print(f"   Fallback list has {len(fallback)} models:")
for model in fallback[:3]:
    print(f"   - {model}")

# Test 3: Test model with valid preference
print("\n3️⃣ Testing get_gemini_model() with valid preference...")
if available:
    test_model = available[0]
    print(f"   Trying to load: {test_model}")
    model = get_gemini_model(_preferred_model=test_model)
    if model:
        print("   ✅ Model loaded successfully!")
    else:
        print("   ❌ Failed to load model")
else:
    print("   Skipping (no models available)")

# Test 4: Test model with invalid preference (fallback logic)
print("\n4️⃣ Testing get_gemini_model() with invalid preference (fallback)...")
model = get_gemini_model(_preferred_model='models/invalid-model-name')
if model:
    print("   ✅ Fallback logic worked!")
else:
    print("   ❌ Fallback logic failed")

# Test 5: Test model with no preference (auto-select)
print("\n5️⃣ Testing get_gemini_model() with no preference (auto)...")
model = get_gemini_model()
if model:
    print("   ✅ Auto-selection worked!")
    
    # Try generating content
    try:
        response = model.generate_content("Say 'test passed' in one word")
        print(f"   ✅ Model response: {response.text}")
    except Exception as e:
        print(f"   ⚠️ Model loaded but generation failed: {e}")
else:
    print("   ❌ Auto-selection failed")

print("\n" + "="*60)
print("🎉 All tests completed!")
print("="*60)

# Restore original streamlit module
if original_st:
    sys.modules['streamlit'] = original_st
