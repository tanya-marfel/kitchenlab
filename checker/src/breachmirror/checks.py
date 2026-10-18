from __future__ import annotations

import re
from pathlib import Path

TEXT_SUFFIXES = {".py", ".md", ".yml", ".yaml", ".toml", ".json", ".txt"}
TOKEN_RE = re.compile(r"(?i)\b(?:hf_|sk-|github_pat_|AKIA)[A-Za-z0-9_\-]{16,}\b")
PRETRAINED_RE = re.compile(
    r"from_pretrained\(\s*[\"'][^\"']+[\"'](?P<rest>[^)]*)\)",
    re.DOTALL,
)
PINNED_RE = re.compile(r"revision\s*=\s*[\"'][A-Za-z0-9._\-]{7,}[\"']")
REMOTE_CODE_RE = re.compile(r"trust_remote_code\s*=\s*True")
WRITE_TOOL_RE = re.compile(
    r"(?i)[\"'](?:write_file|run_shell|delete_file|fetch_url)[\"']|\"capability\"\s*:\s*\"(?:write|network)\""
)
NO_GATE_RE = re.compile(
    r"(?i)no separate human approval|no human approval gate|tool calls execute as soon as"
)
HAS_GATE_RE = re.compile(r"(?i)require(?:s|d)? (?:operator |human )?approval")

CHECK_IDS = (
    "exposed_token_literal",
    "unpinned_pretrained",
    "trust_remote_code",
    "write_or_network_tool",
    "authorization_step",
    "isolation",
)


def iter_files(root: Path, include_docs: bool) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        relative = path.relative_to(root)
        if not include_docs and relative.parts and relative.parts[0] == "docs":
            continue
        if path.stat().st_size > 200_000:
            continue
        files.append(path)
    return files


def _line_span(text: str, start: int, end: int) -> tuple[int, int]:
    line_start = text.count("\n", 0, start) + 1
    line_end = text.count("\n", 0, end) + 1
    return line_start, line_end


def run_checks(root: Path, include_docs: bool = False) -> dict:
    files = iter_files(root, include_docs)
    scope = ", ".join(str(path.relative_to(root)) for path in files) or "no files"
    observations: list[dict] = []

    token_hits: list[dict] = []
    unpinned: list[dict] = []
    pinned: list[dict] = []
    remote_code: list[dict] = []
    tools: list[dict] = []
    no_gate: list[dict] = []
    has_gate: list[dict] = []

    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        relative = str(path.relative_to(root))
        for match in TOKEN_RE.finditer(text):
            line_start, line_end = _line_span(text, match.start(), match.end())
            token_hits.append(
                {"path": relative, "line_start": line_start, "line_end": line_end, "redacted": True}
            )
        for match in PRETRAINED_RE.finditer(text):
            line_start, line_end = _line_span(text, match.start(), match.end())
            hit = {"path": relative, "line_start": line_start, "line_end": line_end}
            if PINNED_RE.search(match.group("rest") or ""):
                pinned.append(hit)
            else:
                unpinned.append(hit)
        for match in REMOTE_CODE_RE.finditer(text):
            line_start, line_end = _line_span(text, match.start(), match.end())
            remote_code.append({"path": relative, "line_start": line_start, "line_end": line_end})
        for match in WRITE_TOOL_RE.finditer(text):
            line_start, line_end = _line_span(text, match.start(), match.end())
            tools.append({"path": relative, "line_start": line_start, "line_end": line_end})
        for match in NO_GATE_RE.finditer(text):
            line_start, line_end = _line_span(text, match.start(), match.end())
            no_gate.append({"path": relative, "line_start": line_start, "line_end": line_end})
        for match in HAS_GATE_RE.finditer(text):
            line_start, line_end = _line_span(text, match.start(), match.end())
            has_gate.append({"path": relative, "line_start": line_start, "line_end": line_end})

    if token_hits:
        observations.append(
            {
                "check": "exposed_token_literal",
                "status": "OBSERVED",
                "detail": "A token-shaped literal is present. The value was redacted and was not validated.",
                "evidence": token_hits[:8],
                "scope": scope,
            }
        )
    else:
        observations.append(
            {
                "check": "exposed_token_literal",
                "status": "NOT OBSERVED",
                "detail": "No token-shaped literal was found in the inspected files.",
                "evidence": [],
                "scope": scope,
            }
        )

    if unpinned:
        observations.append(
            {
                "check": "unpinned_pretrained",
                "status": "OBSERVED",
                "detail": "from_pretrained is called without a revision pin.",
                "evidence": unpinned[:8],
                "scope": scope,
            }
        )
    elif pinned:
        observations.append(
            {
                "check": "unpinned_pretrained",
                "status": "NOT OBSERVED",
                "detail": "from_pretrained calls in the inspected files pass a revision.",
                "evidence": pinned[:8],
                "scope": scope,
            }
        )
    else:
        observations.append(
            {
                "check": "unpinned_pretrained",
                "status": "NOT OBSERVED",
                "detail": "No from_pretrained call was found in the inspected files.",
                "evidence": [],
                "scope": scope,
            }
        )

    observations.append(
        {
            "check": "trust_remote_code",
            "status": "OBSERVED" if remote_code else "NOT OBSERVED",
            "detail": "trust_remote_code=True is present."
            if remote_code
            else "trust_remote_code=True was not found in the inspected files.",
            "evidence": remote_code[:8],
            "scope": scope,
        }
    )

    if tools:
        observations.append(
            {
                "check": "write_or_network_tool",
                "status": "OBSERVED",
                "detail": "A write-capable or networked tool is declared.",
                "evidence": tools[:8],
                "scope": scope,
            }
        )
    else:
        observations.append(
            {
                "check": "write_or_network_tool",
                "status": "NOT OBSERVED",
                "detail": "No write-capable or networked tool declaration was found.",
                "evidence": [],
                "scope": scope,
            }
        )

    if no_gate and not has_gate:
        observations.append(
            {
                "check": "authorization_step",
                "status": "OBSERVED",
                "detail": "Inspected documentation states tool calls run without a separate human approval gate.",
                "evidence": no_gate[:4],
                "scope": scope,
            }
        )
    elif has_gate and not no_gate:
        observations.append(
            {
                "check": "authorization_step",
                "status": "NOT OBSERVED",
                "detail": "An approval step is described in the inspected files. The missing-approval condition was not observed in this scope.",
                "evidence": has_gate[:4],
                "scope": scope,
            }
        )
    else:
        observations.append(
            {
                "check": "authorization_step",
                "status": "UNKNOWN",
                "detail": "Inspected files do not establish whether tool calls require a separate authorization step.",
                "evidence": [],
                "scope": scope,
            }
        )

    observations.append(
        {
            "check": "isolation",
            "status": "UNKNOWN",
            "detail": "Runtime isolation and secret placement are not established by static inspection of these files.",
            "evidence": [],
            "scope": scope,
        }
    )

    return {
        "root": str(root),
        "include_docs": include_docs,
        "file_count": len(files),
        "scope": scope,
        "observations": observations,
    }
