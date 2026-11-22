"""Unit tests for kb.py: load_kb_documents and get_kb_path."""

from __future__ import annotations

from pathlib import Path

import pytest

from smart_copilot.kb import get_kb_path, load_kb_documents

# ---------------------------------------------------------------------------
# Task 2.2 – load_kb_documents
# ---------------------------------------------------------------------------


def test_missing_directory_returns_empty_list(tmp_path: Path) -> None:
    # Requirement 1.2: missing dir → [] without error
    missing = tmp_path / "no_such_dir"
    assert load_kb_documents(missing) == []


def test_empty_directory_returns_empty_list(tmp_path: Path) -> None:
    # Requirement 1.3: empty dir → []
    empty = tmp_path / "empty"
    empty.mkdir()
    assert load_kb_documents(empty) == []


def test_loads_txt_files_with_correct_title_and_content(kb_path: Path) -> None:
    # Requirement 1.1: title = stem, content = text
    (kb_path / "billing.txt").write_text("hello world")
    result = load_kb_documents(kb_path)
    assert len(result) == 1
    assert result[0]["title"] == "billing"
    assert result[0]["content"] == "hello world"


def test_strips_whitespace_from_content(kb_path: Path) -> None:
    # Requirement 1.1: content is stripped
    (kb_path / "doc.txt").write_text("  hello  \n\n")
    result = load_kb_documents(kb_path)
    assert result[0]["content"] == "hello"


def test_ignores_non_txt_files(kb_path: Path) -> None:
    # Requirement 1.5: non-.txt files ignored
    (kb_path / "readme.md").write_text("markdown")
    (kb_path / "data.json").write_text('{"key": "val"}')
    assert load_kb_documents(kb_path) == []


def test_mixed_txt_and_non_txt_returns_only_txt(kb_path: Path) -> None:
    # Requirement 1.5: mixed directory → only .txt files returned
    (kb_path / "a.txt").write_text("content a")
    (kb_path / "b.md").write_text("markdown b")
    result = load_kb_documents(kb_path)
    assert len(result) == 1
    assert result[0]["title"] == "a"


def test_multiple_txt_files_returned_sorted(kb_path: Path) -> None:
    # Multiple files returned, sorted by filename
    (kb_path / "z_last.txt").write_text("last")
    (kb_path / "a_first.txt").write_text("first")
    result = load_kb_documents(kb_path)
    assert len(result) == 2
    assert result[0]["title"] == "a_first"
    assert result[1]["title"] == "z_last"


def test_ignores_subdirectories(kb_path: Path) -> None:
    # Directories inside KB path should be silently skipped
    (kb_path / "subdir").mkdir()
    (kb_path / "doc.txt").write_text("real doc")
    result = load_kb_documents(kb_path)
    assert len(result) == 1
    assert result[0]["title"] == "doc"


# ---------------------------------------------------------------------------
# Task 2.2 – get_kb_path
# ---------------------------------------------------------------------------


def test_kb_path_reads_from_env_var(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Requirement 1.4: reads KB_PATH env var
    monkeypatch.setenv("KB_PATH", str(tmp_path))
    assert get_kb_path() == tmp_path


def test_kb_path_defaults_to_data_kb(monkeypatch: pytest.MonkeyPatch) -> None:
    # Requirement 1.4: defaults to data/kb/
    monkeypatch.delenv("KB_PATH", raising=False)
    assert get_kb_path() == Path("data/kb/")
