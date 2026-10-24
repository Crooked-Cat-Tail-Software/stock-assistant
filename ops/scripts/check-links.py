"""Check that relative links (and #anchors) in the project's Markdown docs resolve.

    python3 ops/scripts/check-links.py            # exit 1 if any link is broken

External links (http/https/mailto) are not fetched.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILES = ["AGENTS.md", "README.md", "CLAUDE.md", "product-spec.md", *map(str, Path("docs").glob("*.md"))]
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def slug(heading: str) -> str:
    """GitHub's anchor rule: lowercase, drop punctuation, spaces become hyphens."""
    text = re.sub(r"[`*_]", "", heading.strip().lower())
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"\s", "-", text)


def anchors(path: Path) -> set[str]:
    text = re.sub(r"```.*?```", "", path.read_text(), flags=re.S)  # ignore code blocks
    return {slug(m) for m in re.findall(r"^#{1,6}\s+(.+)$", text, flags=re.M)}


def main() -> int:
    broken = []
    for name in FILES:
        source = ROOT / name
        if not source.exists():
            continue
        text = re.sub(r"```.*?```", "", source.read_text(), flags=re.S)
        for target in LINK.findall(text):
            if re.match(r"^(https?:|mailto:)", target):
                continue
            path_part, _, anchor = target.partition("#")
            dest = (source.parent / path_part).resolve() if path_part else source
            if not dest.exists():
                broken.append(f"{name}: {target}  (no such file)")
            elif anchor and dest.suffix == ".md" and anchor not in anchors(dest):
                broken.append(f"{name}: {target}  (no heading #{anchor})")
    for line in broken:
        print(f"✗ {line}")
    print(f"{'✗' if broken else '✓'} {len(broken)} broken link(s) in {len(FILES)} files")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
