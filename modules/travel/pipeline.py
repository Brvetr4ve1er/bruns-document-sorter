from core.pipeline.router import route_file
from .prompts import init_prompts
from .mrz_parser import parse_mrz

def process_travel_file(file_path: str, doc_type: str = "UNKNOWN"):
    init_prompts()
    
    # Try MRZ first
    mrz_data = parse_mrz(file_path)
    if mrz_data:
        # If we got MRZ, we could skip LLM or augment it.
        # For Phase 4, we'll return the MRZ data wrapped in a mock job
        from core.pipeline.job import Job, JobStatus
        job = Job(type="MRZ_EXTRACTION", input_data={"file_path": file_path, "module": "travel"})
        job.complete({
            "source": "mrz",
            "extracted_data": mrz_data
        })
        return job
        
    # Fallback to LLM pipeline
    return route_file(file_path, module="travel", doc_type=doc_type)
