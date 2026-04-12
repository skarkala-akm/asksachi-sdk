"""Shared **CLI** runner: message from args / stdin / prompt, optional progress lines, print reply."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence


def run_text_workflow_cli(
    *,
    description: str,
    runtime: Callable[[str], str],
    progress_labels: Sequence[tuple[str, str]] = (
        ("Step 1/2", "received input"),
        ("Step 2/2", "running workflow…"),
    ),
    prompt_label: str = "Your message (Enter to send): ",
    footer: str | None = None,
    argv: Sequence[str] | None = None,
) -> None:
    """Parse ``-m`` / ``--message``, read user text (``-`` = one stdin line), call ``runtime``, print result.

    ``progress_labels`` are ``(step_title, step_detail)`` pairs printed as ``"{title}: {detail}"``.
    """
    p = argparse.ArgumentParser(description=description)
    p.add_argument(
        "-m",
        "--message",
        default="",
        help="User message (omit to be prompted, or use '-' to read one line from stdin)",
    )
    args = p.parse_args(list(argv) if argv is not None else None)
    msg = args.message
    if msg == "-":
        msg = (sys.stdin.readline() or "").rstrip("\n")
    elif not msg:
        try:
            msg = input(prompt_label).strip()
        except EOFError:
            msg = ""

    for title, detail in progress_labels:
        print(f"{title}: {detail}", flush=True)
    out = runtime(msg)
    print("", flush=True)
    print(out)
    if footer:
        print(footer, flush=True)
