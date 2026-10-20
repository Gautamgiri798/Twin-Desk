from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_required_docs_exist() -> None:
    required = [
        "README.md",
        "AGENTS.md",
        "docs/prd.md",
        "docs/design.md",
        "docs/architecture.md",
        "docs/database.md",
        "docs/api.md",
        "docs/agents.md",
        "docs/project-implementation.md",
        "docs/setup.md",
        "docs/feature-development.md",
        "docs/authentication-security.md",
        "docs/mcp-communication.md",
        "docs/integrations.md",
        "docs/testing-qa.md",
        "docs/debugging.md",
    ]
    for item in required:
        assert (ROOT / item).is_file(), item


def test_readme_discloses_scaffold_status() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "not a working virtual-display product" in readme
