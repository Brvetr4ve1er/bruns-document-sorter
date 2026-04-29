import os
import sys

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.extraction.llm_client import LLMClient
from core.extraction.prompt_registry import register_prompt

def test_phase1():
    print("Testing LLMClient and Core schemas...")
    
    # Register a dummy prompt
    register_prompt(
        module="test_module",
        doc_type="TEST_DOC",
        version="1.0",
        template='Extract the main topic as JSON, like {{"topic": "..."}} from this text: {text}'
    )
    
    # Use a dummy ollama url if not available, but since we are just testing if it compiles/imports
    # we can try hitting the local ollama
    client = LLMClient(ollama_url="http://localhost:11434/api/generate", model="llama3.2")
    
    try:
        res = client.extract("The quick brown fox jumps over the lazy dog.", module="test_module", doc_type="TEST_DOC")
        print(f"Extraction successful: {res.data}")
    except Exception as e:
        if "Connection" in str(e):
            print("Ollama not running, but imports and compilation succeeded.")
        else:
            print(f"Error during extraction: {e}")

if __name__ == "__main__":
    test_phase1()
