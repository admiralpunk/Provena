"""Validate that versioned public release metadata stays synchronized."""

from __future__ import annotations

import argparse
import json
import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", help="Optional release tag such as v0.1.0")
    args = parser.parse_args()

    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    package_version = project["project"]["version"]
    distribution_name = project["project"]["name"]
    package_readme = project["project"]["readme"]
    frontend_version = json.loads((ROOT / "frontend/package.json").read_text())["version"]
    frontend_lock = json.loads((ROOT / "frontend/package-lock.json").read_text())
    frontend_lock_version = frontend_lock["version"]
    server = json.loads((ROOT / "server.json").read_text())
    deploy_env = (ROOT / "deploy/.env.example").read_text()
    readme = (ROOT / "README.md").read_text()
    pypi_readme = (ROOT / "PYPI.md").read_text()
    demo_video = ROOT / "docs/assets/provena-product-demo.mp4"
    demo_poster = ROOT / "docs/assets/provena-product-demo.jpg"

    expected = {
        "frontend/package.json": frontend_version,
        "frontend/package-lock.json": frontend_lock_version,
        "frontend/package-lock.json root package": frontend_lock["packages"][""]["version"],
        "server.json": server["version"],
        "server.json package": server["packages"][0]["version"],
    }
    mismatches = [f"{source} has {value}, expected {package_version}" for source, value in expected.items() if value != package_version]

    required_version_text = {
        "Dockerfile": f"ARG VERSION={package_version}",
        "frontend/Dockerfile": f"ARG VERSION={package_version}",
        "deploy/compose.yaml": f"PROVENA_VERSION:-{package_version}",
        "src/cli.py": f'return "{package_version}"',
        "src/web/app.py": f'version="{package_version}"',
        "README.md release downloads": f"/releases/download/v{package_version}/compose.yaml",
    }
    versioned_files = {
        "Dockerfile": ROOT / "Dockerfile",
        "frontend/Dockerfile": ROOT / "frontend/Dockerfile",
        "deploy/compose.yaml": ROOT / "deploy/compose.yaml",
        "src/cli.py": ROOT / "src/cli.py",
        "src/web/app.py": ROOT / "src/web/app.py",
        "README.md release downloads": ROOT / "README.md",
    }
    for source, expected_text in required_version_text.items():
        if expected_text not in versioned_files[source].read_text():
            mismatches.append(f"{source} does not use version {package_version}")
    if not re.search(rf"^PROVENA_VERSION={re.escape(package_version)}$", deploy_env, re.MULTILINE):
        mismatches.append("deploy/.env.example does not use the package version")
    if server["packages"][0]["identifier"] != distribution_name:
        mismatches.append("server.json package identifier differs from pyproject distribution name")
    marker = f"<!-- mcp-name: {server['name']} -->"
    if marker not in readme:
        mismatches.append("README is missing the MCP Registry ownership marker")
    if marker not in pypi_readme:
        mismatches.append("PYPI.md is missing the MCP Registry ownership marker")
    if package_readme != "PYPI.md":
        mismatches.append("pyproject must use PYPI.md as the package description")
    if "pipx install provena-agent-memory" not in pypi_readme:
        mismatches.append("PYPI.md is missing the managed pipx installation workflow")
    if "https://raw.githubusercontent.com/admiralpunk/Provena/master/frontend/public/logo.svg" not in pypi_readme:
        mismatches.append("PYPI.md is missing the absolute logo URL")
    for path in (demo_video, demo_poster):
        if not path.is_file() or path.stat().st_size == 0:
            mismatches.append(f"missing product demo asset: {path.relative_to(ROOT)}")
    github_demo_url = "https://github.com/user-attachments/assets/90180f49-6817-418f-9165-abcf6b79a94b"
    if github_demo_url not in readme:
        mismatches.append(f"README.md is missing native GitHub product demo: {github_demo_url}")
    pypi_demo_urls = (
        "https://cdn.jsdelivr.net/gh/admiralpunk/Provena@master/docs/assets/provena-product-demo.mp4",
        "https://raw.githubusercontent.com/admiralpunk/Provena/master/docs/assets/provena-product-demo.jpg",
    )
    for url in pypi_demo_urls:
        if url not in pypi_readme:
            mismatches.append(f"PYPI.md is missing product demo URL: {url}")
    required_pypi_text = (
        "Ask your Provena operator for these three values:",
        "releases/latest/download/default.env.example",
        "docker compose -f compose.yaml -f compose.ollama.yaml up -d",
        'eval "$(provena init --format shell)"',
        "~/.codex/config.toml",
        "codex mcp list",
        "--profile console up -d console",
        "PROVENA_HUMAN_KEY",
        "if [ ! -f .env ]; then",
        "Recover from a database password mismatch",
        "ALTER ROLE provena WITH PASSWORD",
        "provena quickstart codex",
        "provena connect codex --install",
        "without requiring you to mention Provena",
    )
    for expected_text in required_pypi_text:
        if expected_text not in pypi_readme:
            mismatches.append(f"PYPI.md is missing required onboarding text: {expected_text}")
    forbidden_pypi_commands = ("git clone", "uvx ")
    for command in forbidden_pypi_commands:
        if command in pypi_readme:
            mismatches.append(f"PYPI.md contains alternate setup command: {command.strip()}")
    if args.tag and args.tag != f"v{package_version}":
        mismatches.append(f"tag {args.tag} does not match v{package_version}")
    if mismatches:
        raise SystemExit("Release metadata is inconsistent:\n- " + "\n- ".join(mismatches))
    print(f"release metadata is consistent for {distribution_name} {package_version}")


if __name__ == "__main__":
    main()
