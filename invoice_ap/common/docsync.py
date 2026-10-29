"""Keep generated tables inside hand-written markdown in sync with the code that produces them.

A generated block is delimited by
    <!-- BEGIN GENERATED: <name> (python -m invoice_ap docs) -->
    <!-- END GENERATED: <name> -->
`python -m invoice_ap docs` rewrites the blocks; tests fail when a block is stale.
"""
from __future__ import annotations

from pathlib import Path


def _markers(name: str) -> tuple[str, str]:
    return (f"<!-- BEGIN GENERATED: {name} (python -m invoice_ap docs) -->",
            f"<!-- END GENERATED: {name} -->")


def replace_block(text: str, name: str, content: str) -> str:
    begin, end = _markers(name)
    start = text.find(begin)
    stop = text.find(end)
    if start < 0 or stop < start:
        raise KeyError(f"generated block {name!r} not found")
    return text[: start + len(begin)] + "\n" + content.rstrip("\n") + "\n" + text[stop:]


def block_in_sync(path: Path, name: str, content: str) -> bool:
    text = path.read_text(encoding="utf-8")
    return replace_block(text, name, content) == text


def write_block(path: Path, name: str, content: str) -> bool:
    """Rewrite the block; return True when the file changed."""
    text = path.read_text(encoding="utf-8")
    new = replace_block(text, name, content)
    if new != text:
        path.write_text(new, encoding="utf-8", newline="\n")
        return True
    return False
