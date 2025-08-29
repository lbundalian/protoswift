# src/protoswift/cli.py
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn

try:
    import yaml  # type: ignore
except Exception:
    yaml = None

console = Console()

DEFAULT_SCAFFOLD: Dict[str, Any] = {
    "folders": ["app", "context", "models", "services"],
    "files": [
        {"name": "README.md", "content": "# {project_name}\n\nGenerated with ProtoSwift 🕊️\n"},
        {"name": ".gitignore", "content": "__pycache__/\n*.py[cod]\n.venv/\n.env\n"},
        {"name": ".env.example", "content": "ENV=dev\n"},
        {"name": "requirements.txt", "content": "# add dependencies here\n"},
        {"name": "app/__init__.py", "content": ""},
        {
            "name": "app/__main__.py",
            "content": "def main():\n    print('Hello from app!')\n\nif __name__ == '__main__':\n    main()\n",
        },
    ],
}





def _read_yaml(path: Path) -> Dict[str, Any]:
    if yaml is None:
        raise RuntimeError("❌ YAML support requires PyYAML. Please install it.")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_user_config(config_path: Optional[str]) -> Dict[str, Any]:
    if not config_path:
        return {}
    p = Path(config_path)
    if not p.exists():
        raise FileNotFoundError(f"❌ Config file not found: {config_path}")
    if p.suffix.lower() == ".json":
        return _read_json(p)
    return _read_yaml(p)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_file(path: Path, content: str, overwrite: bool, dry_run: bool) -> None:
    ensure_dir(path.parent)
    exists = path.exists()
    if exists and not overwrite:
        return
    if dry_run:
        action = "overwrite" if exists else "create"
        console.print(f"[yellow][dry-run][/yellow] 📝 Would {action} file: {path}")
        return
    path.write_text(content, encoding="utf-8")


def render_content(template: str, project_name: str, distribution_name: str) -> str:
    return template.format(project_name=project_name, distribution_name=distribution_name)


def create_structure(
    root: Path,
    project_name: str,
    distribution_name: str,
    folders: Optional[List[str]],
    files: Optional[List[Dict[str, str]]],
    overwrite: bool = False,
    dry_run: bool = False,
) -> None:
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeRemainingColumn(),
    ) as progress:
        # Create folders
        folder_task = progress.add_task("📁 Creating folders...", total=len(folders or []))
        for d in folders or []:
            p = root / d
            if dry_run:
                console.print(f"[yellow][dry-run][/yellow] 📁 Would create dir: {p}")
            else:
                ensure_dir(p)
            progress.advance(folder_task)

        # Create files
        file_task = progress.add_task("📝 Creating files...", total=len(files or []))
        for f in files or []:
            name = f.get("name")
            if not name:
                continue
            content = render_content(f.get("content", ""), project_name, distribution_name)
            write_file(root / name, content, overwrite=overwrite, dry_run=dry_run)
            progress.advance(file_task)

def create_conda_env(env_name: str, python_version: str, dry_run: bool = False) -> bool:
    cmd = ["conda", "create", "-y", "-n", env_name, f"python={python_version}"]
    if dry_run:
        print(f"[dry-run] would run: {' '.join(cmd)}")
        return True

    print(f"🐍 Creating conda env '{env_name}' with Python {python_version}...")
    try:
        subprocess.run(cmd, check=True)
        print(f"✅ Conda environment '{env_name}' ready. Activate it with: conda activate {env_name}")
        return True
    except FileNotFoundError:
        print("❌ 'conda' not found on PATH. Please install Miniconda/Anaconda or ensure 'conda' is available.")
        return False
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to create conda environment: {e}")
        return False


# def create_conda_env(env_name: str, python_version: str, dry_run: bool = False) -> None:
#     cmd = ["conda", "create", "-y", "-n", env_name, f"python={python_version}"]
#     if dry_run:
#         console.print(f"[yellow][dry-run][/yellow] 🔧 Would run: {' '.join(cmd)}")
#         return
    
#     with Progress(
#         SpinnerColumn(),
#         TextColumn("[progress.description]{task.description}"),
#         BarColumn(),
#     ) as progress:
#         task = progress.add_task(f"🔧 Creating conda environment '{env_name}'...", total=1)
#         try:
#             subprocess.run(cmd, check=True, capture_output=True)
#             progress.advance(task)
#             console.print(f"[green]✅ Conda environment '{env_name}' created successfully![/green]")
#             console.print(f"[blue]💡 Activate it with:[/blue] conda activate {env_name}")
#         except subprocess.CalledProcessError as e:
#             console.print(f"[red]❌ Failed to create conda environment: {e}[/red]", file=sys.stderr)

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="protoswift",
        description="🕊️ Swiftly scaffold a Python project (optionally with a conda environment).",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=textwrap.dedent(
            """\
            Examples:
              protoswift my-app
              protoswift my-app --conda
              protoswift my-app --conda --python-version 3.10 --env-name customenv
            """
        ),
    )
    parser.add_argument("project_name", help="Directory to create.")
    parser.add_argument("--dist-name", help="Override distribution name.")
    parser.add_argument("--config", help="Path to YAML/JSON config file.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files.")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing files.")
    parser.add_argument("--conda", action="store_true", help="Also create a conda environment.")
    parser.add_argument(
        "--python-version", default="3.11", help="Python version for conda environment (default: 3.11)."
    )
    parser.add_argument("--env-name", default=None, help="Name for conda env (default: project_name).")

    args = parser.parse_args(argv)

    root = Path(args.project_name).resolve()
    project_name = root.name
    distribution_name = (args.dist_name or project_name).replace("-", "_")

    print(f"🚀 Starting project creation: {project_name}")

    cfg = load_user_config(args.config) if args.config else DEFAULT_SCAFFOLD

    folders = cfg.get("folders", [])
    files = cfg.get("files", [])

    if args.dry_run:
        print(f"[dry-run] 📁 Would create project at: {root}")
    else:
        ensure_dir(root)

    create_structure(
        root=root,
        project_name=project_name,
        distribution_name=distribution_name,
        folders=folders,
        files=files,
        overwrite=args.force,
        dry_run=args.dry_run,
    )

    if not args.dry_run:
        print(f"✨ Project swiftly created at {root}")

    if args.conda:
        env_name = args.env_name or project_name
        create_conda_env(env_name=env_name, python_version=args.python_version, dry_run=args.dry_run)

    print("🎉 All done! Happy coding!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
