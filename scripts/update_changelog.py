from __future__ import annotations

import argparse
import subprocess
import sys
from collections import OrderedDict
from collections.abc import Sequence
from datetime import date
from pathlib import Path

CHANGELOG_TITLE = "# Changelog"
UNRELEASED_TITLE = "Unreleased"
NO_UNRELEASED_CHANGES = "- No unreleased changes recorded."

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


def _build_unreleased_body_from_commits(commits: Sequence[str]) -> str:
    grouped: dict[str, list[str]] = {key: [] for key in SECTION_TITLES}

    for commit in commits:
        category, summary = _normalize_commit_message(commit)
        grouped[category].append(summary)

    if not commits:
        return NO_UNRELEASED_CHANGES

    lines: list[str] = []
    for key, title in SECTION_TITLES.items():
        entries = grouped[key]
        if not entries:
            continue
        lines.append(f"### {title}")
        for entry in entries:
            lines.append(f"- {entry}")
        lines.append("")

    return "\n".join(lines).rstrip()


def build_unreleased_body(base_ref: str, head_ref: str) -> str:
    return _build_unreleased_body_from_commits(_run_git_log(base_ref, head_ref))


def _load_changelog_sections(content: str) -> tuple[str, list[tuple[str, str]]]:
    normalized = content.replace("\r\n", "\n")
    lines = normalized.split("\n")
    header_lines: list[str] = []
    sections: list[tuple[str, str]] = []
    current_title: str | None = None
    current_lines: list[str] = []

    for line in lines:
        if line.startswith("## "):
            if current_title is not None:
                sections.append((current_title, "\n".join(current_lines).strip()))
            current_title = line[3:].strip()
            current_lines = []
            continue

        if current_title is None:
            header_lines.append(line)
        else:
            current_lines.append(line)

    if current_title is None:
        return (("\n".join(header_lines).strip() or CHANGELOG_TITLE), [])

    sections.append((current_title, "\n".join(current_lines).strip()))
    return (("\n".join(header_lines).strip() or CHANGELOG_TITLE), sections)


def _render_changelog(header: str, sections: Sequence[tuple[str, str]]) -> str:
    lines = [header.strip() or CHANGELOG_TITLE, ""]
    for index, (title, body) in enumerate(sections):
        lines.append(f"## {title}")
        lines.append("")
        section_body = body.strip() or NO_UNRELEASED_CHANGES
        lines.extend(section_body.splitlines())
        if index != len(sections) - 1:
            lines.append("")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def update_unreleased_changelog(
    existing_content: str,
    base_ref: str,
    head_ref: str,
) -> str:
    header, sections = _load_changelog_sections(existing_content)
    unreleased_body = build_unreleased_body(base_ref, head_ref)
    updated_sections: list[tuple[str, str]] = [(UNRELEASED_TITLE, unreleased_body)]

    for title, body in sections:
        if title == UNRELEASED_TITLE:
            continue
        updated_sections.append((title, body))

    return _render_changelog(header, updated_sections)


def finalize_release_changelog(
    existing_content: str,
    version: str,
    release_date: str,
) -> str:
    header, sections = _load_changelog_sections(existing_content)
    unreleased_body = NO_UNRELEASED_CHANGES
    remaining_sections: list[tuple[str, str]] = []
    release_title = f"v{version} - {release_date}"

    for title, body in sections:
        if title == UNRELEASED_TITLE:
            unreleased_body = body.strip() or NO_UNRELEASED_CHANGES
            continue
        if title == release_title:
            continue
        remaining_sections.append((title, body))

    finalized_sections = [
        (UNRELEASED_TITLE, NO_UNRELEASED_CHANGES),
        (release_title, unreleased_body),
        *remaining_sections,
    ]
    return _render_changelog(header, finalized_sections)


def extract_release_notes(existing_content: str, version: str) -> str:
    _, sections = _load_changelog_sections(existing_content)
    prefix = f"v{version} - "
    for title, body in sections:
        if title == f"v{version}" or title.startswith(prefix):
            return body.strip() or NO_UNRELEASED_CHANGES
    raise ValueError(f"Release notes for version {version} were not found.")


def _read_text(path: Path) -> str:
    if not path.exists():
        return f"{CHANGELOG_TITLE}\n"
    return path.read_text(encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Maintain CHANGELOG.md from git history."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    update_parser = subparsers.add_parser(
        "update", help="Regenerate the Unreleased section from git history."
    )
    update_parser.add_argument("--base", required=True, help="Base git ref")
    update_parser.add_argument("--head", required=True, help="Head git ref")
    update_parser.add_argument("--output", required=True, help="Output changelog path")

    finalize_parser = subparsers.add_parser(
        "finalize",
        help="Promote the current Unreleased section into a versioned release section.",
    )
    finalize_parser.add_argument("--version", required=True, help="Release version")
    finalize_parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Release date in YYYY-MM-DD format",
    )
    finalize_parser.add_argument("--path", required=True, help="Changelog path")

    release_notes_parser = subparsers.add_parser(
        "release-notes",
        help="Extract release notes for a specific version from CHANGELOG.md.",
    )
    release_notes_parser.add_argument(
        "--version", required=True, help="Release version"
    )
    release_notes_parser.add_argument("--path", required=True, help="Changelog path")
    release_notes_parser.add_argument(
        "--output", required=True, help="Output file path"
    )

    return parser


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = _build_parser()
    argv_list = list(argv) if argv is not None else sys.argv[1:]

    if argv_list and argv_list[0] not in {
        "update",
        "finalize",
        "release-notes",
    }:
        argv_list = ["update", *argv_list]

    return parser.parse_args(argv_list)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    if args.command == "update":
        output_path = Path(args.output)
        current_content = _read_text(output_path)
        updated = update_unreleased_changelog(current_content, args.base, args.head)
        _write_text(output_path, updated)
        return 0

    if args.command == "finalize":
        changelog_path = Path(args.path)
        current_content = _read_text(changelog_path)
        updated = finalize_release_changelog(current_content, args.version, args.date)
        _write_text(changelog_path, updated)
        return 0

    if args.command == "release-notes":
        changelog_path = Path(args.path)
        notes = extract_release_notes(_read_text(changelog_path), args.version)
        _write_text(Path(args.output), notes.rstrip() + "\n")
        return 0

    raise AssertionError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
