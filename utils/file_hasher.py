import hashlib
import os


def compute_file_hash(file_path: str, algorithm: str = "sha256") -> str:
    """Compute SHA256 hash of a file."""
    hasher = hashlib.sha256() if algorithm == "sha256" else hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        raise IOError(f"Cannot hash file {file_path}: {e}")


def hash_filename(filename: str) -> str:
    """Quick hash of filename only."""
    return hashlib.md5(filename.encode()).hexdigest()
