import os
import sys

# Make the project root importable and give api.py a dummy key so it can be imported
# without a real account. Tests never call a real LLM.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("LLM_PROVIDER", "openai")
os.environ.setdefault("OPENAI_API_KEY", "test-key")
