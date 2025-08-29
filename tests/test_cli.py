import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from protoswift.cli import (
    load_user_config,
    render_content,
    create_structure,
    DEFAULT_SCAFFOLD,
    main,  # call CLI entry directly so our patch target is correct
)


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def config_file(temp_dir: Path) -> Path:
    config = {
        "folders": ["src", "tests"],
        "files": [
            {"name": "README.md", "content": "# {project_name}"},
            {"name": "src/__init__.py", "content": ""},
        ],
    }
    p = temp_dir / "config.json"
    p.write_text(json.dumps(config), encoding="utf-8")
    return p


def test_load_user_config_json(config_file: Path):
    config = load_user_config(str(config_file))
    assert config["folders"] == ["src", "tests"]
    assert isinstance(config["files"], list)


def test_load_user_config_nonexistent():
    with pytest.raises(FileNotFoundError):
        load_user_config("nonexistent.json")


def test_render_content():
    template = "# {project_name}\n## {distribution_name}"
    result = render_content(template, "My Project", "my_project")
    assert result == "# My Project\n## my_project"


def test_create_structure(temp_dir: Path):
    project_name = "test_project"
    dist = "test_project"
    create_structure(
        root=temp_dir,
        project_name=project_name,
        distribution_name=dist,
        folders=DEFAULT_SCAFFOLD["folders"],
        files=DEFAULT_SCAFFOLD["files"],
        overwrite=True,
        dry_run=False,
    )
    for folder in DEFAULT_SCAFFOLD["folders"]:
        assert (temp_dir / folder).is_dir()
    for file_info in DEFAULT_SCAFFOLD["files"]:
        fp = temp_dir / file_info["name"]
        assert fp.is_file()
        expected = render_content(file_info["content"], project_name, dist)
        assert fp.read_text(encoding="utf-8") == expected


def test_create_structure_dry_run(temp_dir: Path):
    create_structure(
        root=temp_dir,
        project_name="test",
        distribution_name="test",
        folders=["src"],
        files=[{"name": "test.txt", "content": "test"}],
        dry_run=True,
    )
    assert not (temp_dir / "src").exists()
    assert not (temp_dir / "test.txt").exists()


def test_create_structure_no_overwrite(temp_dir: Path):
    f = temp_dir / "test.txt"
    f.write_text("original", encoding="utf-8")
    create_structure(
        root=temp_dir,
        project_name="test",
        distribution_name="test",
        folders=[],
        files=[{"name": "test.txt", "content": "new content"}],
        overwrite=False,
    )
    assert f.read_text(encoding="utf-8") == "original"


# ---------------- Conda tests ----------------

def test_conda_option_invokes_conda(temp_dir: Path):
    """--conda should invoke `conda create -y -n <env> python=<ver>`."""
    proj = temp_dir / "withconda"
    args = [str(proj), "--conda", "--python-version", "3.10", "--env-name", "condax"]

    # Patch the EXACT location used in the code
    with patch("protoswift.cli.subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(args=["conda"], returncode=0)
        rc = main(args)
        assert rc == 0
        mock_run.assert_called()
        called = mock_run.call_args[0][0]
        assert called[0] == "conda"
        assert called[1] == "create"
        assert "-y" in called
        # ensure env name and python version are present
        assert "-n" in called and "condax" in called
        assert "python=3.10" in called


def test_conda_missing_binary_is_handled(temp_dir: Path):
    """If conda isn't on PATH, we should handle FileNotFoundError gracefully."""
    proj = temp_dir / "naconda"
    args = [str(proj), "--conda"]

    with patch("protoswift.cli.subprocess.run", side_effect=FileNotFoundError):
        rc = main(args)
        # main still returns 0; we just log the error to stderr
        assert rc == 0
