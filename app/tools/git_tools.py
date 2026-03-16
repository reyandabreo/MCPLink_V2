"""Git tools: init, commit, and status operations inside the sandbox."""
import json
import subprocess
from pydantic import BaseModel, Field
from app.tools.registry import tool_registry
from app.sandbox.limits import resolve_sandbox_path
from app.config import settings


def _ok(message: str, data: dict = None, files_modified: list = None) -> str:
    return json.dumps({
        "status": "success",
        "message": message,
        "data": data or {},
        "files_modified": files_modified or [],
    })


def _err(message: str) -> str:
    return json.dumps({"status": "error", "message": message})


def _git(args_list: list, cwd: str, timeout: int = 30) -> tuple[int, str, str]:
    """Run a git command, return (returncode, stdout, stderr)."""
    result = subprocess.run(
        ["git"] + args_list,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=cwd,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


# ── init_git_repo ─────────────────────────────────────────────────────────────

class InitGitRepoArgs(BaseModel):
    path: str = Field(..., description="Relative path to the project directory inside the sandbox")


@tool_registry.register(
    "init_git_repo",
    "Initialize a Git repository inside a sandbox project directory.",
    InitGitRepoArgs,
)
def init_git_repo(args: InitGitRepoArgs) -> str:
    path = resolve_sandbox_path(args.path)
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)

    rc, out, err = _git(["init"], cwd=str(path))
    if rc != 0:
        return _err(f"git init failed: {err}")

    # Create a sensible .gitignore if one doesn't exist
    gitignore = path / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(
            "__pycache__/\n*.pyc\n*.pyo\n.env\n.venv/\n*.egg-info/\ndist/\nbuild/\n"
        )

    return _ok(
        f"Initialized Git repo at {args.path}.",
        data={"output": out},
        files_modified=[str(args.path / ".gitignore")],
    )


# ── git_commit ────────────────────────────────────────────────────────────────

class GitCommitArgs(BaseModel):
    message: str = Field(..., description="Commit message")
    path: str = Field(default=".", description="Repo directory inside the sandbox (default: workspace root)")


@tool_registry.register(
    "git_commit",
    "Stage all changes and create a Git commit inside the sandbox.",
    GitCommitArgs,
)
def git_commit(args: GitCommitArgs) -> str:
    path = resolve_sandbox_path(args.path)
    if not path.exists():
        return _err(f"Path not found: {args.path}")

    # git add .
    rc, _, err = _git(["add", "."], cwd=str(path))
    if rc != 0:
        return _err(f"git add failed: {err}")

    # git commit
    rc, out, err = _git(
        ["commit", "-m", args.message, "--allow-empty-message"],
        cwd=str(path),
    )
    if rc != 0:
        # "nothing to commit" is not really an error
        if "nothing to commit" in out or "nothing to commit" in err:
            return _ok("Nothing to commit — working tree clean.", data={"output": out})
        return _err(f"git commit failed: {err or out}")

    return _ok(f"Committed: {args.message}", data={"output": out})


# ── git_status ────────────────────────────────────────────────────────────────

class GitStatusArgs(BaseModel):
    path: str = Field(..., description="Repo directory inside the sandbox")


@tool_registry.register(
    "git_status",
    "Show the Git working-tree status of a sandbox repository.",
    GitStatusArgs,
)
def git_status(args: GitStatusArgs) -> str:
    path = resolve_sandbox_path(args.path)
    if not path.exists():
        return _err(f"Path not found: {args.path}")

    rc, out, err = _git(["status", "--porcelain"], cwd=str(path))
    if rc != 0:
        return _err(f"git status failed: {err}")

    changed, untracked, staged = [], [], []
    for line in out.splitlines():
        if len(line) < 3:
            continue
        xy = line[:2]
        fname = line[3:]
        if xy[0] in "MADRC":
            staged.append(fname)
        if xy[1] in "MD":
            changed.append(fname)
        if xy == "??":
            untracked.append(fname)

    summary = "clean" if not out else f"{len(staged)} staged, {len(changed)} unstaged, {len(untracked)} untracked"
    return _ok(
        f"Status: {summary}",
        data={
            "staged": staged,
            "unstaged": changed,
            "untracked": untracked,
            "raw": out,
        },
    )
