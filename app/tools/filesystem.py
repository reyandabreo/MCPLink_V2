import os
import json
import shutil
import tempfile
from pathlib import Path
from pydantic import BaseModel, Field
from app.tools.registry import tool_registry
from app.sandbox.limits import resolve_sandbox_path, check_file_size
from app.config import settings

# ── Helpers ──────────────────────────────────────────────────────────────────

def _ok(message: str, data: dict = None, files_modified: list = None) -> str:
    return json.dumps({
        "status": "success",
        "message": message,
        "data": data or {},
        "files_modified": files_modified or [],
    })

def _err(message: str) -> str:
    return json.dumps({"status": "error", "message": message})


def _content_limit_bytes() -> int:
    return int(settings.MAX_FILE_SIZE_MB * 1024 * 1024)


def _validate_text_content(content: str | None) -> tuple[str | None, str | None]:
    if content is None:
        return "", None
    if not isinstance(content, str):
        return None, f"Content must be a string, got {type(content).__name__}."
    if len(content.encode("utf-8")) > _content_limit_bytes():
        return None, (
            f"Content exceeds max allowed size of {settings.MAX_FILE_SIZE_MB}MB. "
            "Split content into smaller chunks."
        )
    return content, None


def _safe_read_text(path: Path) -> tuple[str | None, str | None]:
    try:
        check_file_size(path)
        return path.read_text(encoding="utf-8"), None
    except UnicodeDecodeError:
        return None, "File is not valid UTF-8 text."
    except Exception as exc:
        return None, f"Failed to read file: {exc}"


def _atomic_write_text(path: Path, content: str) -> tuple[bool, str | None]:
    fd = None
    tmp_path = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=".tmp_", dir=str(path.parent))
        tmp_path = Path(tmp_name)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            fd = None
            f.write(content)
        os.replace(str(tmp_path), str(path))
        tmp_path = None
        return True, None
    except Exception as exc:
        return False, str(exc)
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except Exception:
                pass
        if tmp_path is not None and tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass


def _validate_source_destination(src: Path, dst: Path) -> str | None:
    if src == dst:
        return "Source and destination are the same path."
    if not src.exists():
        return f"Source not found: {src}"
    if src.is_dir():
        return "This tool currently supports files only; source is a directory."
    if dst.exists():
        return "Destination already exists."
    if dst.parent.exists() and not dst.parent.is_dir():
        return "Destination parent exists but is not a directory."
    return None

# ── create_file ───────────────────────────────────────────────────────────────

class CreateFileArgs(BaseModel):
    path: str = Field(..., description="Relative path within the sandbox to create the file")
    content: str = Field(..., description="Content of the file")

@tool_registry.register("create_file", "Creates a new file in the sandbox with given content", CreateFileArgs)
def create_file(args: CreateFileArgs) -> str:
    try:
        path = resolve_sandbox_path(args.path)
        content, err = _validate_text_content(args.content)
        if err:
            return _err(err)
        if path.exists():
            return _err(f"File already exists at {args.path}")
        if path.parent.exists() and not path.parent.is_dir():
            return _err(f"Parent path is not a directory: {path.parent}")
        ok, write_err = _atomic_write_text(path, content)
        if not ok:
            return _err(f"Failed to create file: {write_err}")
        return _ok(f"Created file at {args.path}", files_modified=[args.path])
    except Exception as exc:
        return _err(str(exc))

# ── read_file ─────────────────────────────────────────────────────────────────

class ReadFileArgs(BaseModel):
    path: str = Field(..., description="Relative path of the file to read")

@tool_registry.register("read_file", "Reads the content of a file from the sandbox", ReadFileArgs)
def read_file(args: ReadFileArgs) -> str:
    try:
        path = resolve_sandbox_path(args.path)
        if not path.exists():
            return _err(f"File not found at {args.path}")
        if not path.is_file():
            return _err(f"Path is not a file: {args.path}")
        content, err = _safe_read_text(path)
        if err:
            return _err(err)
        return _ok("File read.", data={"content": content})
    except Exception as exc:
        return _err(str(exc))

# ── edit_file ─────────────────────────────────────────────────────────────────

class EditFileArgs(BaseModel):
    path: str = Field(..., description="Relative path of the file to edit")
    content: str = Field(..., description="New complete content for the file")

@tool_registry.register("edit_file", "Overwrites an existing file with new content", EditFileArgs)
def edit_file(args: EditFileArgs) -> str:
    try:
        path = resolve_sandbox_path(args.path)
        content, err = _validate_text_content(args.content)
        if err:
            return _err(err)
        if not path.exists():
            return _err(f"File not found at {args.path}")
        if not path.is_file():
            return _err(f"Path is not a file: {args.path}")
        ok, write_err = _atomic_write_text(path, content)
        if not ok:
            return _err(f"Failed to edit file: {write_err}")
        return _ok(f"Edited file at {args.path}", files_modified=[args.path])
    except Exception as exc:
        return _err(str(exc))

# ── delete_file ───────────────────────────────────────────────────────────────

class DeleteFileArgs(BaseModel):
    path: str = Field(..., description="Relative path of the file to delete")

@tool_registry.register("delete_file", "Deletes a file from the sandbox", DeleteFileArgs)
def delete_file(args: DeleteFileArgs) -> str:
    try:
        path = resolve_sandbox_path(args.path)
        if not path.exists():
            return _err(f"File not found at {args.path}")
        if not path.is_file():
            return _err(f"Path is not a file: {args.path}")
        path.unlink()
        return _ok(f"Deleted file at {args.path}", files_modified=[args.path])
    except Exception as exc:
        return _err(str(exc))

# ── create_directory ──────────────────────────────────────────────────────────

class CreateDirectoryArgs(BaseModel):
    path: str = Field(..., description="Relative path of the directory to create")

@tool_registry.register("create_directory", "Creates a directory in the sandbox", CreateDirectoryArgs)
def create_directory(args: CreateDirectoryArgs) -> str:
    try:
        path = resolve_sandbox_path(args.path)
        if path.exists() and not path.is_dir():
            return _err(f"Path exists and is not a directory: {args.path}")
        path.mkdir(parents=True, exist_ok=True)
        return _ok(f"Created directory at {args.path}")
    except Exception as exc:
        return _err(str(exc))

# ── list_directory ────────────────────────────────────────────────────────────

class ListDirectoryArgs(BaseModel):
    path: str = Field(..., description="Relative directory path inside the sandbox workspace")
    include_hidden: bool = Field(False, description="Include hidden files/directories when true")

@tool_registry.register("list_directory", "Lists files and sub-directories inside a sandbox directory.", ListDirectoryArgs)
def list_directory(args: ListDirectoryArgs) -> str:
    try:
        path = resolve_sandbox_path(args.path)
        if not path.exists():
            return _err(f"Path not found: {args.path}")
        if not path.is_dir():
            return _err(f"Not a directory: {args.path}")

        files, directories = [], []
        file_details, directory_details = [], []
        for entry in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if not args.include_hidden and entry.name.startswith("."):
                continue
            item = {
                "name": entry.name,
                "size": entry.stat().st_size if entry.is_file() else None,
                "modified": entry.stat().st_mtime,
            }
            if entry.is_dir():
                directories.append(entry.name)
                directory_details.append(item)
            else:
                files.append(entry.name)
                file_details.append(item)

        return _ok(
            "Directory listed.",
            data={
                "files": files,
                "directories": directories,
                "file_details": file_details,
                "directory_details": directory_details,
                "counts": {"files": len(files), "directories": len(directories)},
            },
        )
    except Exception as exc:
        return _err(str(exc))

# ── move_file ─────────────────────────────────────────────────────────────────

class MoveFileArgs(BaseModel):
    source: str = Field(..., description="Source file path inside the sandbox")
    destination: str = Field(..., description="Destination path inside the sandbox")

@tool_registry.register("move_file", "Move or rename a file inside the sandbox.", MoveFileArgs)
def move_file(args: MoveFileArgs) -> str:
    try:
        src = resolve_sandbox_path(args.source)
        dst = resolve_sandbox_path(args.destination)
        validation_error = _validate_source_destination(src, dst)
        if validation_error:
            return _err(validation_error)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return _ok(f"Moved {args.source} -> {args.destination}", files_modified=[args.source, args.destination])
    except Exception as exc:
        return _err(str(exc))

# ── copy_file ─────────────────────────────────────────────────────────────────

class CopyFileArgs(BaseModel):
    source: str = Field(..., description="Source file path inside the sandbox")
    destination: str = Field(..., description="Destination path inside the sandbox")

@tool_registry.register("copy_file", "Duplicate a file inside the sandbox.", CopyFileArgs)
def copy_file(args: CopyFileArgs) -> str:
    try:
        src = resolve_sandbox_path(args.source)
        dst = resolve_sandbox_path(args.destination)
        validation_error = _validate_source_destination(src, dst)
        if validation_error:
            return _err(validation_error)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dst))
        check_file_size(dst)
        return _ok(f"Copied {args.source} -> {args.destination}", files_modified=[args.destination])
    except Exception as exc:
        return _err(str(exc))


# ── append_file ───────────────────────────────────────────────────────────────

class AppendFileArgs(BaseModel):
    path: str = Field(..., description="Relative path of the file to append to")
    content: str = Field(..., description="Content to append")


@tool_registry.register("append_file", "Appends content to an existing text file in the sandbox", AppendFileArgs)
def append_file(args: AppendFileArgs) -> str:
    try:
        path = resolve_sandbox_path(args.path)
        append_content, err = _validate_text_content(args.content)
        if err:
            return _err(err)
        if not path.exists():
            return _err(f"File not found at {args.path}")
        if not path.is_file():
            return _err(f"Path is not a file: {args.path}")

        existing, read_err = _safe_read_text(path)
        if read_err:
            return _err(read_err)

        combined = (existing or "") + append_content
        if len(combined.encode("utf-8")) > _content_limit_bytes():
            return _err(f"Resulting file would exceed max size of {settings.MAX_FILE_SIZE_MB}MB")

        ok, write_err = _atomic_write_text(path, combined)
        if not ok:
            return _err(f"Failed to append file: {write_err}")
        return _ok(f"Appended content to {args.path}", files_modified=[args.path])
    except Exception as exc:
        return _err(str(exc))
