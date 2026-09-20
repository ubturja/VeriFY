from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from verify.config import get_settings
from verify.eval.score import score_submission
from verify.pipeline.orchestrator import run_pipeline
from verify.providers.llm.factory import NullLLMProvider, build_llm
from verify.providers.mail.hackathon import HackathonMailSource


async def evaluate() -> dict:
    settings = get_settings()
    data_dir = settings.data_dir.resolve()
    source = HackathonMailSource(settings.inbox_url or data_dir)

    llm = build_llm(settings)
    if isinstance(llm, NullLLMProvider):
        llm = None

    submission: dict = {}
    cases: list[dict] = []
    for email in source.emails():
        result = await run_pipeline(email, source.read_bytes, llm=llm)
        submission[email.email_id] = result.to_submission()
        cases.append(
            {
                "email_id": email.email_id,
                "subject": email.subject,
                "from": email.sender,
                "result": result.model_dump(mode="json"),
            }
        )

    artifacts = Path(__file__).resolve().parents[3] / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    out = artifacts / "submission.json"
    out.write_text(json.dumps(submission, indent=2), encoding="utf-8")
    (artifacts / "cases.json").write_text(json.dumps(cases, indent=2), encoding="utf-8")

    report = {"emails": len(submission), "submission_path": str(out)}
    truth_path = settings.ground_truth
    if truth_path and Path(truth_path).is_file():
        truth = json.loads(Path(truth_path).read_text(encoding="utf-8"))
        report["score"] = score_submission(truth, submission)
    print(json.dumps(report, indent=2))
    return report


def main() -> None:
    try:
        asyncio.run(evaluate())
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
