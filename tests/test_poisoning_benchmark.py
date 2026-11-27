"""Guard the memory-poisoning benchmark's trust properties against regressions."""

import os
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="requires TEST_DATABASE_URL")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks" / "poisoning"))


def test_every_poisoning_check_passes():
    from harness import run

    results = run(os.environ["TEST_DATABASE_URL"])
    failures = [f"{case['category']} / {case['case']}: {check['property']} (observed {check['observed']})" for case in results["cases"] for check in case["checks"] if not check["passed"]]
    assert results["summary"]["cases"] == 23
    assert failures == []
