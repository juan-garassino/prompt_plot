"""Brief loader — machine-readable access to the studio guideline files.

Parses the front-matter-less markdown convention used by ``studio/<domain>/*.md``
(e.g. ``studio/nets/cnn.md``)::

    # CNN — FROM PIXELS TO MEANING
    **Essence:** hierarchical feature extraction — ... **Status:** built as
    `bauhaus_locality` (3D engine).

    ## The idea (the true thing)
    ...
    ## Pen-plotter visual (our engine)
    ...

Section bodies are kept as raw markdown — the LLM consumes them, so structural
fidelity beats parsing depth. ``README.md`` files are treated as domain indexes
and skipped.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# studio/ lives at the repo root, two levels up from this file's package
_DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "studio"

# normalized section keys -> heading prefixes we recognise (lowercased)
_SECTION_KEYS = {
    "idea": ("the idea",),
    "visual": ("pen-plotter visual", "the pen-plotter visual"),
    "palette": ("palette",),
    "annotations": ("annotations",),
    "reference": ("reference prompt",),
    "build": ("build notes",),
}


@dataclass
class Brief:
    slug: str  # file stem, e.g. "cnn"
    domain: str  # parent dir, e.g. "nets"
    title: str  # "CNN"
    tagline: str  # "FROM PIXELS TO MEANING"
    essence: str
    status: str
    sections: Dict[str, str] = field(default_factory=dict)  # normalized key -> raw md
    extra_sections: Dict[str, str] = field(default_factory=dict)  # unrecognised headings
    path: Optional[Path] = None

    @property
    def built(self) -> bool:
        return "built" in self.status.lower()

    def to_context(self) -> str:
        """Render the brief back to a compact markdown block for LLM prompts."""
        parts = [f"# {self.title} — {self.tagline}", f"**Essence:** {self.essence}", f"**Status:** {self.status}"]
        for key, body in {**self.sections, **self.extra_sections}.items():
            parts.append(f"## {key}\n{body.strip()}")
        return "\n\n".join(parts)


def _normalize_heading(heading: str) -> Optional[str]:
    h = heading.strip().lower()
    for key, prefixes in _SECTION_KEYS.items():
        if any(h.startswith(p) for p in prefixes):
            return key
    return None


def parse_brief(path: Path, domain: Optional[str] = None) -> Brief:
    text = path.read_text(encoding="utf-8")

    m = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
    h1 = m.group(1).strip() if m else path.stem
    if "—" in h1:
        title, tagline = (part.strip() for part in h1.split("—", 1))
    else:
        title, tagline = h1, ""

    em = re.search(r"\*\*Essence:\*\*\s*(.*?)\s*\*\*Status:\*\*", text, flags=re.DOTALL)
    essence = re.sub(r"\s+", " ", em.group(1)).strip() if em else ""
    sm = re.search(r"\*\*Status:\*\*\s*(.*?)(?:\n\s*\n|\n##)", text, flags=re.DOTALL)
    status = re.sub(r"\s+", " ", sm.group(1)).strip() if sm else ""

    sections: Dict[str, str] = {}
    extra: Dict[str, str] = {}
    for hm in re.finditer(r"^##\s+(.+?)\s*$\n(.*?)(?=^##\s|\Z)", text, flags=re.MULTILINE | re.DOTALL):
        heading, body = hm.group(1), hm.group(2)
        key = _normalize_heading(heading)
        if key is not None:
            sections[key] = body.strip()
        else:
            extra[heading.strip()] = body.strip()

    return Brief(
        slug=path.stem,
        domain=domain or path.parent.name,
        title=title,
        tagline=tagline,
        essence=essence,
        status=status,
        sections=sections,
        extra_sections=extra,
        path=path,
    )


def load_briefs(root: Optional[Path] = None, domain: Optional[str] = None) -> List[Brief]:
    """Load every brief under ``studio/`` (or one domain subdir). Skips READMEs
    and non-brief dirs (project dossiers without the H1+Essence shape parse to
    briefs with an empty essence and are kept — callers can filter)."""
    base = Path(root) if root is not None else _DEFAULT_ROOT
    if domain is not None:
        dirs = [base / domain]
    else:
        dirs = sorted(d for d in base.iterdir() if d.is_dir()) if base.is_dir() else []
    briefs: List[Brief] = []
    for d in dirs:
        for f in sorted(d.glob("*.md")):
            if f.name.lower() == "readme.md":
                continue
            try:
                briefs.append(parse_brief(f, domain=d.name))
            except Exception:
                logger.exception("failed to parse brief %s", f)
    return briefs


def list_briefs(root: Optional[Path] = None, domain: Optional[str] = None) -> List[Dict[str, str]]:
    """Compact listing for CLI/agent: slug, domain, title, tagline, status."""
    return [
        {"slug": b.slug, "domain": b.domain, "title": b.title, "tagline": b.tagline, "status": b.status}
        for b in load_briefs(root, domain)
    ]


def get_brief(slug: str, root: Optional[Path] = None, domain: Optional[str] = None) -> Brief:
    for b in load_briefs(root, domain):
        if b.slug == slug:
            return b
    available = ", ".join(x.slug for x in load_briefs(root, domain))
    raise KeyError(f"Unknown brief {slug!r}. Available: {available}")
