"""Code Intelligence tools: analyze, format, and generate tests for Python code."""
import ast
import json
import subprocess
from typing import Optional
from pydantic import BaseModel, Field
from app.tools.registry import tool_registry
from app.sandbox.limits import resolve_sandbox_path
from app.config import settings
from app.tools._llm_helper import call_llm


def _ok(message: str, data: dict = None, files_modified: list = None) -> str:
    return json.dumps({
        "status": "success",
        "message": message,
        "data": data or {},
        "files_modified": files_modified or [],
    })


def _err(message: str) -> str:
    return json.dumps({"status": "error", "message": message})


# ── analyze_python_code ───────────────────────────────────────────────────────

class AnalyzePythonCodeArgs(BaseModel):
    file_path: str = Field(..., description="Relative path to the Python file inside the sandbox")


@tool_registry.register(
    "analyze_python_code",
    "Parses a Python file and extracts its functions, classes, and imports using the AST.",
    AnalyzePythonCodeArgs,
)
def analyze_python_code(args: AnalyzePythonCodeArgs) -> str:
    path = resolve_sandbox_path(args.file_path)
    if not path.exists():
        return _err(f"File not found: {args.file_path}")
    if path.suffix != ".py":
        return _err(f"Not a Python file: {args.file_path}")

    try:
        source = path.read_text()
        tree = ast.parse(source)
    except SyntaxError as e:
        return _err(f"Syntax error in {args.file_path}: {e}")

    functions, classes, imports = [], [], []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            functions.append(node.name)
        elif isinstance(node, ast.AsyncFunctionDef):
            functions.append(node.name)
        elif isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append(f"{module}.{alias.name}" if module else alias.name)

    return _ok(
        "Analysis complete.",
        data={
            "functions": functions,
            "classes": classes,
            "imports": sorted(set(imports)),
            "lines": source.count("\n") + 1,
        },
    )


# ── format_code ───────────────────────────────────────────────────────────────

class FormatCodeArgs(BaseModel):
    file_path: str = Field(..., description="Relative path to the Python file to format")


@tool_registry.register(
    "format_code",
    "Format a Python file using the Black formatter (must be installed).",
    FormatCodeArgs,
)
def format_code(args: FormatCodeArgs) -> str:
    path = resolve_sandbox_path(args.file_path)
    if not path.exists():
        return _err(f"File not found: {args.file_path}")
    if path.suffix != ".py":
        return _err(f"Not a Python file: {args.file_path}")

    result = subprocess.run(
        ["black", str(path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        return _err(f"Black formatter failed: {result.stderr.strip()}")
    return _ok(f"Formatted {args.file_path}.", files_modified=[args.file_path])


# ── generate_tests ────────────────────────────────────────────────────────────

class GenerateTestsArgs(BaseModel):
    source_file: str = Field(..., description="Relative path to the Python source file")
    output_file: Optional[str] = Field(None, description="Optional output test file path (defaults to test_<source>.py)")


@tool_registry.register(
    "generate_tests",
    "Generate pytest test cases for a Python file using the configured LLM.",
    GenerateTestsArgs,
)
def generate_tests(args: GenerateTestsArgs) -> str:
    src_path = resolve_sandbox_path(args.source_file)
    if not src_path.exists():
        return _err(f"Source file not found: {args.source_file}")
    if src_path.suffix != ".py":
        return _err(f"Not a Python file: {args.source_file}")

    source_code = src_path.read_text()
    if not source_code.strip():
        return _err("Source file is empty.")

    # Output path
    if args.output_file:
        out_path = resolve_sandbox_path(args.output_file)
    else:
        out_path = src_path.parent / f"test_{src_path.name}"

    try:
        prompt = (
            "You are an expert Python test engineer. "
            "Write comprehensive pytest unit tests for the following Python code.\n"
            "Use only the pytest framework. Include edge cases.\n"
            "Return ONLY the Python test code, no explanations.\n\n"
            f"# Source: {args.source_file}\n\n{source_code}"
        )
        test_code = call_llm(prompt)
        # Strip markdown code fences if present
        if test_code.startswith("```"):
            lines = test_code.splitlines()
            test_code = "\n".join(
                l for l in lines if not l.startswith("```")
            )
    except Exception as e:
        return _err(f"LLM generation failed: {e}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(test_code)
    out_rel = str(out_path.relative_to(resolve_sandbox_path(".")))
    return _ok(
        f"Generated tests saved to {out_rel}.",
        data={"output_file": out_rel},
        files_modified=[out_rel],
    )
