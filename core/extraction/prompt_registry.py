_REGISTRY = {}

def register_prompt(module: str, doc_type: str, version: str, template: str):
    """Register a prompt template for a specific module and document type."""
    _REGISTRY[(module, doc_type)] = {"version": version, "template": template}

def get_prompt(module: str, doc_type: str) -> tuple[str, str]:
    """Return (version, template). Falls back to UNKNOWN if doc_type not found."""
    key = (module, doc_type)
    if key not in _REGISTRY:
        key = (module, "UNKNOWN")
    
    if key not in _REGISTRY:
        raise ValueError(f"No prompt registered for module '{module}' and doc_type '{doc_type}'")
        
    entry = _REGISTRY[key]
    return entry["version"], entry["template"]
