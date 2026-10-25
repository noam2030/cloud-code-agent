import pathlib
import subprocess

from app import config

ROOT = pathlib.Path(config.WORKSPACE)
MAX_FILE_BYTES = 20_000
COAUTHOR = "Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>"
PR_FOOTER = "🤖 Generated with [Claude Code](https://claude.com/claude-code)"


def _run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"{' '.join(cmd[:2])} failed: {result.stderr.strip()}")
    return result.stdout


def snapshot(max_chars: int = 60_000) -> str:
    """Concatenate tracked text files so the agents can see the repository."""
    parts, total = [], 0
    for path in _run(["git", "ls-files"]).splitlines():
        file = ROOT / path
        if not file.is_file() or file.stat().st_size > MAX_FILE_BYTES:
            continue
        block = f"### {path}\n{file.read_text(errors='ignore')}\n"
        total += len(block)
        if total > max_chars:
            parts.append("...(truncated)")
            break
        parts.append(block)
    return "\n".join(parts)


def _safe_path(path: str) -> pathlib.PurePosixPath:
    p = pathlib.PurePosixPath(path)
    if p.is_absolute() or ".." in p.parts or ".git" in p.parts:
        raise ValueError(f"unsafe path: {path}")
    return p


def commit_and_pr(branch: str, proposal: dict, message: str) -> str:
    """Apply approved changes on a side branch, push, and open a pull request."""
    _run(["git", "checkout", "main"])
    _run(["git", "pull", "--ff-only"])
    _run(["git", "checkout", "-B", branch])
    for change in proposal["files"]:
        target = ROOT / _safe_path(change["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(change["content"])
    _run(["git", "add", "-A"])
    _run(["git", "commit", "-m", f"{proposal['summary']}\n\n{COAUTHOR}"])
    _run(["git", "push", "-u", "origin", branch])
    body = f"Requested via cloud-code-agent:\n\n> {message}\n\n{PR_FOOTER}"
    return _run(
        ["gh", "pr", "create", "--base", "main", "--head", branch,
         "--title", proposal["summary"][:70], "--body", body]
    ).strip()
