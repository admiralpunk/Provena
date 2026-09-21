"""Create a local organization, project scope, and review credential."""

import argparse
import json
import os
import shlex
import sys
import urllib.error
import urllib.request


def post(base_url: str, path: str, body: dict, headers: dict[str, str]) -> dict:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")
        raise SystemExit(f"Provena returned HTTP {error.code} for {path}: {detail}") from error
    except urllib.error.URLError as error:
        raise SystemExit(f"Could not reach Provena at {base_url}: {error.reason}") from error


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default=os.getenv("PROVENA_API_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--organization", default="Local development")
    parser.add_argument("--project", default="provena-demo")
    parser.add_argument("--format", choices=("json", "shell"), default="json")
    args = parser.parse_args()

    bootstrap_token = os.getenv("BOOTSTRAP_TOKEN")
    if not bootstrap_token:
        raise SystemExit("BOOTSTRAP_TOKEN is required")

    bootstrap_headers = {"X-Bootstrap-Token": bootstrap_token}
    organization = post(args.api_url, "/organizations", {"name": args.organization}, bootstrap_headers)
    agent_headers = {"X-API-Key": organization["api_key"]}
    project = post(args.api_url, "/projects", {"name": args.project}, agent_headers)
    reviewer = post(
        args.api_url,
        f"/organizations/{organization['id']}/credentials",
        {"role": "human", "label": "local reviewer"},
        bootstrap_headers,
    )
    values = {
        "PROVENA_ORG_ID": str(organization["id"]),
        "PROVENA_PROJECT_ID": str(project["id"]),
        "PROVENA_SCOPE_ID": str(project["scope_id"]),
        "PROVENA_AGENT_KEY": organization["api_key"],
        "PROVENA_HUMAN_KEY": reviewer["api_key"],
    }
    if args.format == "shell":
        for key, value in values.items():
            print(f"export {key}={shlex.quote(value)}")
    else:
        json.dump(values, sys.stdout, indent=2)
        print()


if __name__ == "__main__":
    main()
