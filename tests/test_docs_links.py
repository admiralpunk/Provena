"""Tests for the contributor documentation link checker."""

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_docs_links.py"
SPEC = importlib.util.spec_from_file_location("check_docs_links", SCRIPT)
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


def test_valid_links_and_image_paths(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("[parent](../README.md) ![image](picture.png)\n")
    (tmp_path / "README.md").write_text("# Readme\n")
    (docs / "picture.png").write_bytes(b"image")
    assert list(checker.missing_links(tmp_path)) == []


def test_missing_link_reports_source_target_and_failure(tmp_path, capsys):
    (tmp_path / "README.md").write_text("# Readme\n[broken](docs/missing.md)\n")
    assert checker.main(tmp_path) == 1
    assert "README.md:2: missing local target: docs/missing.md" in capsys.readouterr().err


def test_encoded_paths_and_fragments(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "with space.md").write_text("# Page\n")
    (tmp_path / "README.md").write_text(
        "[encoded](docs/with%20space.md#section) [fragment](#readme)\n"
    )
    assert list(checker.missing_links(tmp_path)) == []


def test_remote_and_mail_links_are_skipped(tmp_path):
    (tmp_path / "README.md").write_text(
        "[web](https://example.com/missing) "
        "[old web](http://example.com/missing) "
        "[mail](mailto:hello@example.com)\n"
    )
    assert checker.main(tmp_path) == 0


def test_missing_image_is_reported(tmp_path):
    (tmp_path / "README.md").write_text("![missing](images/nope.png)\n")
    assert list(checker.missing_links(tmp_path)) == [
        (Path("README.md"), 1, "images/nope.png")
    ]
