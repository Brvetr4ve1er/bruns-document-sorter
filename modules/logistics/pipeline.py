from core.pipeline.router import route_file
from .prompts import init_prompts

def process_logistics_file(file_path: str):
    init_prompts()
    return route_file(file_path, module="logistics", doc_type="UNKNOWN")
