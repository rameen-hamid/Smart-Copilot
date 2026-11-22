import subprocess
from pathlib import Path
from typing import Any

import pytest

from smart_copilot import check


def test_script_path_points_at_scripts_check_py() -> None:
    assert check.SCRIPT.name == "check.py"
    assert check.SCRIPT.parent.name == "scripts"
    assert check.SCRIPT.is_file()


def test_missing_tool_is_recorded_and_other_checks_still_run(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    ran: list[str] = []
    envs: list[dict[str, str]] = []

    def fake_which(name: str) -> str | None:
        return None if name == "gitleaks" else f"/fake/{name}"

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        ran.append(Path(cmd[0]).name)
        envs.append(kwargs["env"])
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr("shutil.which", fake_which)
    monkeypatch.setattr("subprocess.run", fake_run)

    assert check.main() == 1
    assert ran == ["ruff", "semgrep"]
    assert all(e["SEMGREP_SEND_METRICS"] == "off" for e in envs)
    assert all(e["DO_NOT_TRACK"] == "1" for e in envs)
    out = capsys.readouterr().out
    assert "NOT RUN (tool missing): gitleaks" in out
    assert "--metrics=off --disable-version-check" in out


def test_all_tools_pass_returns_zero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("shutil.which", lambda name: f"/fake/{name}")
    monkeypatch.setattr(
        "subprocess.run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0)
    )

    assert check.main() == 0
    assert "All checks passed." in capsys.readouterr().out


def test_failing_tool_is_reported(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("shutil.which", lambda name: f"/fake/{name}")
    monkeypatch.setattr(
        "subprocess.run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1 if "ruff" in cmd[0] else 0),
    )

    assert check.main() == 1
    assert "FAILED: ruff" in capsys.readouterr().out
