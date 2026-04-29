import os
import sys

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.pipeline.router import route_file
from core.extraction.prompt_registry import register_prompt

def test_phase2():
    print("Testing pipeline router...")
    
    register_prompt(
        module="logistics",
        doc_type="TEST_DOC",
        version="1.0",
        template='Extract the document_type as "TEST_DOC" and anything else into JSON from this text: {text}'
    )
    
    os.makedirs("tests", exist_ok=True)
    dummy_path = "tests/dummy.txt"
    with open(dummy_path, "w", encoding="utf-8") as f:
        f.write("This is a dummy logistics document.")
        
    job = route_file(dummy_path, module="logistics", doc_type="TEST_DOC")
    
    print(f"Job status: {job.status}")
    print("Job logs:")
    for log in job.logs:
        print(f"  {log}")
        
    if job.error_message:
        print(f"Error: {job.error_message}")
        
    if job.result_data:
        print(f"Result: {job.result_data}")

if __name__ == "__main__":
    test_phase2()
