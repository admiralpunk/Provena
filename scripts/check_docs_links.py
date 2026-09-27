"""Check repository-relative links in contributor-facing Markdown files."""

from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
DOCS = ("README.md", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md", "SECURITY.md")
LINK = re.compile(r"""!?\[[^\]\n]*\]\((<[^>\n]+>|[^\s)\n]+)(?:\s+(?:"[^"]*"|'[^']*'))?\)""")


def markdown_files(root: Path):
    for name in DOCS:
        path = root / name
        if path.is_file():
            yield path
    yield from sorted((root / "docs").rglob("*.md"))


def missing_links(root: Path):
    """Yield (source, line number, target) for missing local files."""
    root = root.resolve()
    for source in markdown_files(root):
        for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
            for match in LINK.finditer(line):
                target = match.group(1).removeprefix("<").removesuffix(">")
                parsed = urlsplit(target)
                if parsed.scheme.lower() in {"http", "https", "mailto"} or not parsed.path:
                    continue
                path = unquote(parsed.path)
                resolved = ((root if path.startswith("/") else source.parent) / path.lstrip("/")).resolve()
                if not resolved.is_relative_to(root) or not resolved.exists():
                    yield source.relative_to(root), line_number, target


def main(root: Path = ROOT) -> int:
    failures = list(missing_links(root))
    for source, line_number, target in failures:
        print(f"{source}:{line_number}: missing local target: {target}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
