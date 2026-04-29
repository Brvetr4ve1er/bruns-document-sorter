import os
from huey import SqliteHuey

base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
db_path = os.environ.get("BRUNS_DATA_DIR", os.path.join(base_dir, "data"))
os.makedirs(db_path, exist_ok=True)

queue_db = os.path.join(db_path, "queue.db")

# Initialize the queue
task_queue = SqliteHuey('bruns_tasks', filename=queue_db, immediate=False)

@task_queue.task()
def process_file_background(file_path: str, module: str, doc_type: str = "UNKNOWN"):
    """
    Background worker task to process a file using the PipelineProcessor.
    This runs asynchronously so the UI is never blocked.
    """
    from .router import route_file
    
    try:
        job = route_file(file_path, module, doc_type)
        return {
            "status": job.status,
            "error": job.error_message
        }
    except Exception as e:
        return {
            "status": "FAILED",
            "error": str(e)
        }
