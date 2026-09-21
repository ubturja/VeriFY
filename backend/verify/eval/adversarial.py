"""Run the pipeline over a fixed adversarial bundle (mixed-language: English,
Chinese, Malay) and emit a metrics report. Intentionally rules-only so it can
run in CI without any LLM keys."""

from __future__ import annotations

import asyncio
import json
import random
from pathlib import Path
from typing import Any

from verify.eval.score import score_submission
from verify.pipeline.orchestrator import run_pipeline
from verify.providers.mail.hackathon import HackathonMailSource

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BUNDLE = REPO_ROOT / "bundles" / "adversarial"


async def _run_once(bundle: Path, seed: int) -> dict[str, Any]:
    source = HackathonMailSource(bundle)
    emails = list(source.emails())
    random.Random(seed).shuffle(emails)
    submission: dict[str, Any] = {}
    for email in emails:
        result = await run_pipeline(email, source.read_bytes, llm=None)
        submission[email.email_id] = result.to_submission()
    return submission


async def evaluate(bundle: Path = DEFAULT_BUNDLE, *, seeds: tuple[int, ...] = (1, 7, 42)) -> dict[str, Any]:
    truth = json.loads((bundle / "ground_truth.json").read_text(encoding="utf-8"))
    runs: list[dict[str, Any]] = []
    for seed in seeds:
        submission = await _run_once(bundle, seed)
        runs.append({"seed": seed, "score": score_submission(truth, submission)})
    keys = list(runs[0]["score"].keys())
    aggregate = {}
    for key in keys:
        if not isinstance(runs[0]["score"][key], int | float):
            continue
        values = [run["score"][key] for run in runs]
        aggregate[key] = {
            "min": round(min(values), 4),
            "mean": round(sum(values) / len(values), 4),
            "max": round(max(values), 4),
        }
    return {"bundle": str(bundle), "seeds": list(seeds), "runs": runs, "aggregate": aggregate}


def main() -> None:
    report = asyncio.run(evaluate())
    out = REPO_ROOT / "artifacts" / "adversarial_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
