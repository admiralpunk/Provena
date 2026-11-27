"""Run the memory-poisoning benchmark against a disposable PostgreSQL database.

    python benchmarks/poisoning/run.py --database-url postgresql+psycopg://... \
        --json benchmarks/poisoning/results.json --markdown benchmarks/poisoning/RESULTS.md

The database must be migrated (`alembic upgrade head`). The run creates its own
organizations and projects; use a disposable database, because Provena never
deletes evidence.
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import report, run  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--database-url", default=os.getenv("TEST_DATABASE_URL"), required=not os.getenv("TEST_DATABASE_URL"))
    parser.add_argument("--json", type=Path, help="Write the full results as JSON.")
    parser.add_argument("--markdown", type=Path, help="Write the Markdown summary.")
    args = parser.parse_args()
    results = run(args.database_url)
    summary = report(results)
    if args.json:
        args.json.write_text(json.dumps(results, indent=2) + "\n")
    if args.markdown:
        args.markdown.write_text(summary)
    print(summary)
    return 0 if results["summary"]["passed"] == results["summary"]["checks"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
