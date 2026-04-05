from __future__ import annotations

import argparse
import subprocess
from collections import OrderedDict
from pathlib import Path

SECTION_TITLES = OrderedDict(
    [
        ("feat", "Features"),
        ("fix", "Fixes"),
        ("refactor", "Refactors"),
        ("perf", "Performance"),
        ("docs", "Documentation"),
        ("test", "Tests"),
        ("build", "Build"),
        ("ci", "CI"),
        ("chore", "Chores"),
        ("other", "Other Changes"),
    ]
)


def _run_git_log(base_ref: str, head_ref: str) -> list[str]:
    result = subprocess.run(
        ["git", "log", "--format=%s", f"{base_ref}..{head_ref}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _normalize_commit_message(message: str) -> tuple[str, str]:
    if ":" not in message:
        return "other", message

    prefix, summary = message.split(":", 1)
    prefix = prefix.strip().casefold()
    summary = summary.strip()
    if not summary:
        return "other", message

    if "(" in prefix:
        prefix = prefix.split("(", 1)[0]
    if prefix.endswith("!"):
        prefix = prefix[:-1]

    if prefix in SECTION_TITLES:
        return prefix, summary
    return "other", message


def build_changelog(base_ref: str, head_ref: str) -> str:
    commits = _run_git_log(base_ref, head_ref)
    grouped: dict[str, list[str]] = {key: [] for key in SECTION_TITLES}

    for commit in commits:
        category, summary = _normalize_commit_message(commit)
        grouped[category].append(summary)

    lines = ["# Changelog", "", "## Unreleased", ""]

    if not commits:
        lines.append("- No unreleased changes recorded.")
        return "\n".join(lines) + "\n"

    for key, title in SECTION_TITLES.items():
        entries = grouped[key]
        if not entries:
            continue
        lines.append(f"### {title}")
        for entry in entries:
            lines.append(f"- {entry}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate CHANGELOG.md from git history.")
    parser.add_argument("--base", required=True, help="Base git ref")
    parser.add_argument("--head", required=True, help="Head git ref")
    parser.add_argument("--output", required=True, help="Output changelog path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = Path(args.output)
    output_path.write_text(build_changelog(args.base, args.head), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
