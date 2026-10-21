from __future__ import annotations

from pathlib import Path


def test_ci_workflow_structure_and_steps() -> None:
    workflow_path = Path(".github") / "workflows" / "ci.yml"
    assert workflow_path.is_file(), "CI workflow file .github/workflows/ci.yml must exist"

    content = workflow_path.read_text(encoding="utf-8")
    assert "name: DualDesk CI" in content
    assert "windows-latest" in content
    assert "ruff check src tests" in content
    assert "pytest tests/" in content
    assert "QT_QPA_PLATFORM: offscreen" in content
    assert "scripts/configure_firewall.ps1 -DryRun" in content
    assert "scripts/build_driver.ps1 -DryRun" in content
    assert "packaging/build_package.ps1 -DryRun" in content
    assert "Secret and certificate hygiene scan" in content
