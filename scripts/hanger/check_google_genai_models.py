import os
from dotenv import load_dotenv
import google.generativeai as genai

# Load local environment configuration
load_dotenv()

# Extract configuration targets from .env
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Paste your actual key here
genai.configure(api_key=GEMINI_API_KEY)

print("🔍 Scanning for available Gemini models...\n")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(m.name)