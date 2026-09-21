"""Guardrails for the adversarial bundle. The pipeline must:
  * classify every mixed-language email correctly
  * detect the two seeded mismatches with the right defect field
  * remain stable across multiple seeds (order should not change verdicts)
"""

from __future__ import annotations

import pytest

from verify.eval.adversarial import DEFAULT_BUNDLE, evaluate


@pytest.mark.asyncio
async def test_adversarial_bundle_scores_perfectly_across_seeds():
    report = await evaluate(DEFAULT_BUNDLE, seeds=(1, 7, 42))
    aggregate = report["aggregate"]
    assert aggregate["stage1_macro_f1"]["min"] == 1.0
    assert aggregate["stage3_defect_f1"]["min"] == 1.0
    assert aggregate["end_to_end"]["min"] == 1.0
    assert aggregate["final_score"]["min"] == 1.0
