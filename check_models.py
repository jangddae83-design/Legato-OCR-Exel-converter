import google.generativeai as genai
import os
import streamlit as st

# Load secrets directly
try:
    secret_key = st.secrets.get("GEMINI_API_KEY")
    if not secret_key and "general" in st.secrets:
        secret_key = st.secrets["general"].get("GEMINI_API_KEY")
except Exception:
    secret_key = None

# Fallback to manual check if running outside streamlit
if not secret_key:
    # Try reading from .streamlit/secrets.toml manually
    try:
        with open(".streamlit/secrets.toml", "r") as f:
            for line in f:
                if "GEMINI_API_KEY" in line:
                    secret_key = line.split("=")[1].strip().strip('"')
                    break
    except:
        pass

if not secret_key:
    print("Error: Could not find GEMINI_API_KEY in secrets.")
    exit(1)

genai.configure(api_key=secret_key)

print(f"Checking models for key: {secret_key[:5]}...{secret_key[-3:]}")
print("-" * 30)

try:
    models = list(genai.list_models())
    supported_models = []
    
    for m in models:
        # We only care about models that support generateContent
        if 'generateContent' in m.supported_generation_methods:
            supported_models.append(m.name)
            print(f"- {m.name} (Ver: {m.version})")
            
    if not supported_models:
        print("No models found that support generateContent.")
except Exception as e:
    print(f"Error listing models: {e}")
