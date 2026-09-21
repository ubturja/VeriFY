"""Regenerate the organizer inbox for several seeds and score each one.

Rules only, so the spread is about the pipeline rather than a model.
Writes artifacts/multiseed_report.json.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

from verify.eval.report import full_report
from verify.pipeline.orchestrator import run_pipeline
from verify.providers.mail.hackathon import HackathonMailSource

REPO_ROOT = Path(__file__).resolve().parents[3]


def _generate_script() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "sdoc-hackathon-docker" / "data_v2" / "generate.py"
        if candidate.is_file():
            return candidate
    return Path(__file__).resolve().parents[5] / "sdoc-hackathon-docker" / "data_v2" / "generate.py"


GENERATE = _generate_script()


async def _score_dir(bundle: Path) -> dict:
    source = HackathonMailSource(bundle)
    submission = {}
    for email in source.emails():
        result = await run_pipeline(email, source.read_bytes, llm=None)
        submission[email.email_id] = result.to_submission()
    truth = json.loads((bundle / "ground_truth.json").read_text(encoding="utf-8"))
    return full_report(truth, submission)


def _generator_python() -> str:
    """The organizer generator needs reportlab, python-docx, and openpyxl.

    Those stay out of the product environment. A private virtualenv under
    artifacts/ is created the first time this report runs.
    """
    override = os.environ.get("VERIFY_GENERATOR_PYTHON")
    if override:
        return override
    probe = subprocess.run(
        [sys.executable, "-c", "import reportlab, docx, openpyxl"],
        capture_output=True,
    )
    if probe.returncode == 0:
        return sys.executable
    venv = REPO_ROOT / "artifacts" / "generator-venv"
    python = venv / "bin" / "python"
    if not python.is_file():
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    ready = subprocess.run(
        [str(python), "-c", "import reportlab, docx, openpyxl"],
        capture_output=True,
    )
    if ready.returncode != 0:
        subprocess.run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "reportlab",
                "python-docx",
                "openpyxl",
            ],
            check=True,
        )
    return str(python)


def _generate(seed: int, n: int, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [_generator_python(), str(GENERATE), "--seed", str(seed), "--n", str(n), "--out", str(out)],
        check=True,
        cwd=GENERATE.parent,
    )


async def run(seeds: tuple[int, ...] = (1, 2, 3, 4, 5), n: int = 2000) -> dict:
    if not GENERATE.is_file():
        raise FileNotFoundError(f"generate.py not found at {GENERATE}")
    root = REPO_ROOT / "artifacts" / "seeds"
    runs = []
    for seed in seeds:
        bundle = root / f"seed-{seed}"
        print(f"seed {seed}: generating {n} emails", flush=True)
        _generate(seed, n, bundle)
        print(f"seed {seed}: scoring", flush=True)
        report = await _score_dir(bundle)
        print(f"seed {seed}: final_score={report['score']['final_score']}", flush=True)
        runs.append({"seed": seed, "n": n, **report})
    scores = [run["score"]["final_score"] for run in runs]
    summary = {
        "seeds": list(seeds),
        "n": n,
        "final_score_min": min(scores),
        "final_score_max": max(scores),
        "final_score_mean": round(sum(scores) / len(scores), 4),
        "runs": [
            {
                "seed": item["seed"],
                "score": item["score"],
                "confusion_matrix": item["confusion_matrix"],
                "fields": item["fields"],
            }
            for item in runs
        ],
    }
    dest = REPO_ROOT / "artifacts" / "multiseed_report.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    print(json.dumps(asyncio.run(run()), indent=2))


if __name__ == "__main__":
    main()
