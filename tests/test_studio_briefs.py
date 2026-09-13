"""Studio briefs loader: parses the real studio/nets/*.md guideline files."""

from pathlib import Path

import pytest

from promptplot.studio.briefs import get_brief, list_briefs, load_briefs, parse_brief

NETS = Path(__file__).resolve().parents[1] / "studio" / "nets"


def test_loads_all_nets_briefs():
    briefs = load_briefs(domain="nets")
    slugs = {b.slug for b in briefs}
    for expected in [
        "cnn", "lstm", "mlp", "transformer", "gan", "diffusion", "vae", "gnn",
        "moe", "ssm-mamba", "flow-matching", "vit", "dino", "rl-actor-critic",
    ]:
        assert expected in slugs
    assert "README" not in slugs and "readme" not in slugs


def test_briefs_have_title_essence_status():
    for b in load_briefs(domain="nets"):
        assert b.title, f"{b.slug}: empty title"
        assert b.essence, f"{b.slug}: empty essence"
        assert b.status, f"{b.slug}: empty status"
        assert b.domain == "nets"


def test_cnn_brief_fields():
    b = get_brief("cnn", domain="nets")
    assert b.title == "CNN"
    assert "PIXELS" in b.tagline.upper()
    assert "feature" in b.essence.lower()
    assert b.built
    assert "visual" in b.sections and "palette" in b.sections


def test_to_build_brief_has_reference_prompt():
    b = get_brief("gan", domain="nets")
    assert not b.built
    assert "reference" in b.sections
    assert "build" in b.sections


def test_to_context_roundtrip_mentions_sections():
    b = get_brief("transformer", domain="nets")
    ctx = b.to_context()
    assert b.title in ctx and "**Essence:**" in ctx and "##" in ctx


def test_list_briefs_compact():
    rows = list_briefs(domain="nets")
    assert all(set(r) == {"slug", "domain", "title", "tagline", "status"} for r in rows)
    assert len(rows) >= 14


def test_unknown_brief_raises():
    with pytest.raises(KeyError):
        get_brief("nonexistent-net", domain="nets")


def test_malformed_brief_degrades_gracefully(tmp_path):
    f = tmp_path / "weird.md"
    f.write_text("just some text\nno headings at all\n")
    b = parse_brief(f)
    assert b.slug == "weird"
    assert b.essence == "" and b.sections == {}
