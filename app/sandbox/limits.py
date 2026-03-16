import os
from pathlib import Path
from typing import Union
from app.config import settings
from app.core.exceptions import PolicyViolationError

def resolve_sandbox_path(requested_path: Union[str, Path]) -> Path:
    """
    Resolve and validate that a requested path is strictly within the sandbox directory.
    Uses path normalization to prevent directory traversal attacks (../).
    """
    sandbox_base = Path(settings.SANDBOX_DIR).resolve()
    
    # Check if path is absolute, if so, we need to handle it carefully
    # We will assume requested_path is meant to be relative to sandbox_base if it's not starting with sandbox_base
    requested_path_obj = Path(requested_path)
    
    if requested_path_obj.is_absolute():
        try:
            target_path = requested_path_obj.resolve()
        except Exception:
            raise PolicyViolationError(f"Invalid path format: {requested_path}")
    else:
        target_path = (sandbox_base / requested_path).resolve()
    
    # Check if target is inside the sandbox base
    if sandbox_base not in target_path.parents and target_path != sandbox_base:
        raise PolicyViolationError(f"Path traversal detected or path outside sandbox bounds: {requested_path}")
        
    return target_path

def check_file_size(file_path: Union[str, Path]):
    """
    Validate that a file does not exceed the maximum allowed size.
    """
    path = resolve_sandbox_path(file_path)
    if not path.exists():
        return
        
    size_bytes = path.stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    
    if size_mb > settings.MAX_FILE_SIZE_MB:
        raise PolicyViolationError(f"File {path.name} exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB}MB ({size_mb:.2f}MB).")
