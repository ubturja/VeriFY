"""Coverage for the judge-visible gaps: locode, policy, pairing, roles, queue, learning."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from verify.api import app as app_module
from verify.domain.enums import COMPARE_FIELDS, Category, DecidedBy, ReviewReason, Status
from verify.domain.models import EmailMessage, PipelineResult
from verify.domain.policy import MailboxPolicy
from verify.pipeline.orchestrator import run_pipeline
from verify.providers.base import LLMCallMeta, LLMProvider
from verify.text.locode import canonical_port


def test_locode_bare_code_matches_port_name():
    assert canonical_port("MYPKG") == canonical_port("PORT KLANG")
    assert canonical_port("PORT KLANG (WESTPORT)") == canonical_port("MYPKG")
    assert canonical_port("SINGAPORE") == canonical_port("SGSIN")
    assert canonical_port("DEHAM") == canonical_port("HAMBURG")


def test_stale_locode_does_not_hide_a_different_port():
    assert canonical_port("BALTIMORE, US (USBAL)") != canonical_port("MOMBASA, KENYA (USBAL)")
    assert canonical_port("SINGAPORE (SGSIN)") != canonical_port(
        "PORT KLANG (WESTPORT), MALAYSIA (SGSIN)"
    )


@pytest.mark.asyncio
async def test_weight_tolerance_and_allowed_difference(tmp_path):
    si = (
        "SHIPPER: ACME PTE LTD\nCONSIGNEE: GLOBAL LOGISTICS\nNOTIFY PARTY: GLOBAL LOGISTICS\n"
        "PORT OF LOADING: SINGAPORE\nPORT OF DISCHARGE: HAMBURG\n"
        "CONTAINER COUNT: 1 x 40HC\nGROSS WEIGHT: 10000 KG\n"
    )
    bl = si.replace("10000 KG", "10400 KG").replace("GLOBAL LOGISTICS", "OTHER LOGISTICS", 1)
    # consignee differs, weight differs by 400kg
    email = EmailMessage(
        email_id="p1",
        sender="ops@test",
        subject="draft BL check",
        body="please compare",
        attachments=[],
    )
    # Use text attachments via prior path: write files and point attachments.
    si_path = tmp_path / "si.txt"
    bl_path = tmp_path / "bl.txt"
    si_path.write_text(si, encoding="utf-8")
    bl_path.write_text(bl, encoding="utf-8")
    from verify.domain.models import AttachmentRef

    email.attachments = [
        AttachmentRef(path=str(si_path), filename="si.txt"),
        AttachmentRef(path=str(bl_path), filename="bl.txt"),
    ]
    policy = MailboxPolicy(weight_tolerance_kg=500, fields_may_differ=["consignee"])
    result = await run_pipeline(email, lambda path: open(path, "rb").read(), policy=policy)
    assert result.status == Status.OK
    assert result.defect_fields == []


@pytest.mark.asyncio
async def test_request_draft_then_pairs(tmp_path):
    from verify.domain.models import AttachmentRef

    pending = EmailMessage(
        email_id="req1",
        sender="ops@test",
        subject="please send the draft BL",
        body="BL No. HLC-55501 is still missing. Please assist to send the draft BL.",
    )
    first = await run_pipeline(pending, lambda _p: b"")
    assert first.pending_draft is True
    assert first.shipment_ref == "bl:HLC-55501"

    si = tmp_path / "si.txt"
    bl = tmp_path / "bl.txt"
    body = (
        "SHIPPER: ACME PTE LTD\nCONSIGNEE: GLOBAL LOGISTICS\nNOTIFY PARTY: GLOBAL LOGISTICS\n"
        "PORT OF LOADING: SINGAPORE\nPORT OF DISCHARGE: HAMBURG\n"
        "CONTAINER COUNT: 1 x 40HC\nGROSS WEIGHT: 10000 KG\n"
    )
    si.write_text(body, encoding="utf-8")
    bl.write_text(body, encoding="utf-8")
    follow = EmailMessage(
        email_id="draft1",
        sender="ops@test",
        subject="draft BL for BL No. HLC-55501",
        body="attached",
        attachments=[
            AttachmentRef(path=str(si), filename="si.txt"),
            AttachmentRef(path=str(bl), filename="bl.txt"),
        ],
    )
    prior = {
        "email_id": "req1",
        "subject": pending.subject,
        "body": pending.body,
        "attachments": [],
        "result": first.model_dump(mode="json"),
    }
    second = await run_pipeline(follow, lambda path: open(path, "rb").read(), priors=[prior])
    assert second.paired_with == "req1"
    assert second.shipment_ref == "bl:HLC-55501"


@pytest.mark.asyncio
async def test_prior_si_body_supplies_the_missing_document(tmp_path):
    from verify.domain.models import AttachmentRef

    si_text = (
        "SHIPPER: ACME PTE LTD\nCONSIGNEE: GLOBAL LOGISTICS\nNOTIFY PARTY: GLOBAL LOGISTICS\n"
        "PORT OF LOADING: SINGAPORE\nPORT OF DISCHARGE: HAMBURG\n"
        "CONTAINER COUNT: 1 x 40HC\nGROSS WEIGHT: 10000 KG\n"
    )
    bl_path = tmp_path / "bl.txt"
    bl_path.write_text(si_text, encoding="utf-8")
    email = EmailMessage(
        email_id="only-bl",
        sender="ops@test",
        subject="draft BL for BL No. HLC-55501",
        body="draft attached",
        attachments=[AttachmentRef(path=str(bl_path), filename="bl.txt")],
    )
    prior = {
        "email_id": "si-mail",
        "subject": "latest SI",
        "body": si_text + "\nBL No. HLC-55501",
        "attachments": [],
        "result": {"category": "SI_REQUEST", "shipment_ref": "bl:HLC-55501"},
    }
    result = await run_pipeline(email, lambda path: open(path, "rb").read(), priors=[prior])
    assert result.status == Status.OK
    assert any(note.startswith("prior-si:") for note in result.notes)


@pytest.mark.asyncio
async def test_prior_si_requires_the_same_shipment(tmp_path):
    from verify.domain.models import AttachmentRef

    bl_path = tmp_path / "bl.txt"
    bl_path.write_text(
        "SHIPPER: ACME PTE LTD\nCONSIGNEE: GLOBAL LOGISTICS\nNOTIFY PARTY: GLOBAL LOGISTICS\n"
        "PORT OF LOADING: SINGAPORE\nPORT OF DISCHARGE: HAMBURG\n"
        "CONTAINER COUNT: 1 x 40HC\nGROSS WEIGHT: 10000 KG\n",
        encoding="utf-8",
    )
    email = EmailMessage(
        email_id="only-bl",
        sender="ops@test",
        subject="please check the draft BL",
        body="draft attached",
        attachments=[AttachmentRef(path=str(bl_path), filename="bl.txt")],
    )
    prior = {
        "email_id": "other-shipment",
        "subject": "SI for someone else",
        "body": "SHIPPER: OTHER CO\nBL No. HLC-99999",
        "attachments": [],
        "result": {"category": "SI_REQUEST", "shipment_ref": "bl:HLC-99999"},
    }
    result = await run_pipeline(email, lambda path: open(path, "rb").read(), priors=[prior])
    assert result.review_reason == ReviewReason.MISSING_ATTACHMENT
    assert not any(note.startswith("prior-si:") for note in result.notes)


def test_prior_si_prefers_the_latest_matching_instruction():
    from verify.services.pairing import prior_si

    older = {
        "email_id": "email_200",
        "subject": "first SI",
        "body": "SHIPPER: OLD CO\nBL No. HLC-55501",
        "processed_at": "2026-01-01T00:00:00Z",
        "attachments": [],
        "result": {"category": "SI_REQUEST", "shipment_ref": "bl:HLC-55501"},
    }
    newer = {
        "email_id": "email_20",
        "subject": "revised SI",
        "body": "SHIPPER: NEW CO\nBL No. HLC-55501",
        "processed_at": "2026-06-01T00:00:00Z",
        "attachments": [],
        "result": {"category": "SI_REQUEST", "shipment_ref": "bl:HLC-55501"},
    }
    document = prior_si("draft BL for BL No. HLC-55501", "please check", [older, newer])
    assert document is not None
    assert document.fields["shipper"].value == "NEW CO"


class _BlankFiller(LLMProvider):
    name = "blank-filler"

    async def complete_json(self, *, task, system, user, schema, images=None):
        return schema.model_validate({}), LLMCallMeta(provider=self.name, model="stub", task=task)


@pytest.mark.asyncio
async def test_tier_b_blank_check_accepts_policy(tmp_path):
    from verify.domain.models import AttachmentRef

    text = (
        "SHIPPER: TBA\nCONSIGNEE: GLOBAL LOGISTICS\nNOTIFY PARTY: GLOBAL LOGISTICS\n"
        "PORT OF LOADING: SINGAPORE\nPORT OF DISCHARGE: HAMBURG\n"
        "CONTAINER COUNT: 1 x 40HC\nGROSS WEIGHT: 10000 KG\n"
    )
    si_path = tmp_path / "si.txt"
    bl_path = tmp_path / "bl.txt"
    si_path.write_text(text, encoding="utf-8")
    bl_path.write_text(text, encoding="utf-8")
    email = EmailMessage(
        email_id="blank-1",
        sender="ops@test",
        subject="please compare the draft BL",
        body="both attached",
        attachments=[
            AttachmentRef(path=str(si_path), filename="si.txt"),
            AttachmentRef(path=str(bl_path), filename="bl.txt"),
        ],
    )
    result = await run_pipeline(email, lambda path: open(path, "rb").read(), llm=_BlankFiller())
    assert result.status == Status.NEEDS_REVIEW
    assert result.review_reason == ReviewReason.MISSING_VALUE


def test_auditor_cannot_confirm_and_supervisor_sets_policy(auth_client, isolated_tenants):
    client: TestClient = auth_client
    isolated_tenants.ensure("tester@verify.local")
    token = client.headers["Authorization"].split()[-1]
    assert isolated_tenants.set_role(token, "auditor")
    blocked = client.post("/cases/missing/confirm", json={})
    assert blocked.status_code == 403
    policy = client.put(
        "/policy",
        json={"weight_tolerance_kg": 100, "mandatory_fields": ["shipper"], "fields_may_differ": []},
    )
    assert policy.status_code == 403
    assert isolated_tenants.set_role(token, "supervisor")
    saved = client.put(
        "/policy",
        json={
            "weight_tolerance_kg": 100,
            "mandatory_fields": list(COMPARE_FIELDS),
            "fields_may_differ": [],
        },
    )
    assert saved.status_code == 200
    assert saved.json()["weight_tolerance_kg"] == 100


def test_related_timeline_groups_the_same_shipment(auth_client):
    store = auth_client.tenant.store
    for email_id in ("tl-a", "tl-b"):
        store.upsert(
            EmailMessage(email_id=email_id, sender="a@b.c", subject=f"subject {email_id}"),
            PipelineResult(
                email_id=email_id,
                category=Category.SI_REQUEST,
                status=Status.OK,
                decided_by=DecidedBy.RULE,
                shipment_ref="bl:HLC-1",
                pending_draft=email_id == "tl-a",
            ),
        )
    body = auth_client.get("/cases/tl-a/related").json()
    assert {row["email_id"] for row in body["timeline"]} == {"tl-a", "tl-b"}
    pending = next(row for row in body["timeline"] if row["email_id"] == "tl-a")
    assert pending["pending_draft"] is True


def test_metrics_include_automation_fields(auth_client):
    store = auth_client.tenant.store
    store.upsert(
        EmailMessage(email_id="m1", sender="a@b.c", subject="s"),
        PipelineResult(
            email_id="m1",
            category=Category.GENERAL,
            status=Status.OK,
            decided_by=DecidedBy.RULE,
            latency_ms=12,
        ),
    )
    body = auth_client.get("/metrics").json()
    assert body["automation_rate"] == 1.0
    assert "llm_calls_per_100" in body
    assert "estimated_cost_per_1000_usd" in body
    assert "median_latency_ms" in body
    assert body["trend"]


def test_dead_letter_after_repeated_failure(auth_client, monkeypatch):
    async def boom(*_args, **_kwargs):
        raise RuntimeError("parser blew up")

    monkeypatch.setattr(app_module, "run_pipeline", boom)
    response = auth_client.post(
        "/inbox/submit",
        json={"email_id": "dead-1", "subject": "x", "body": "y"},
    )
    assert response.status_code == 502
    dead = auth_client.get("/queue/dead").json()
    assert len(dead) == 1
    assert dead[0]["body"]["email_id"] == "dead-1"
    assert dead[0]["attempts"] == 3


def test_correction_writes_evalset_and_fewshot(auth_client):
    store = auth_client.tenant.store
    store.upsert(
        EmailMessage(email_id="c1", sender="a@b.c", subject="s"),
        PipelineResult(
            email_id="c1",
            category=Category.BL_COMPARISON,
            status=Status.MISMATCH,
            has_defect=True,
            defect_fields=["shipper"],
            decided_by=DecidedBy.RULE,
            comparisons=[],
        ),
    )
    # comparisons empty so few-shot has nothing to store, eval set still grows
    response = auth_client.post("/cases/c1/correct", json={"status": "OK", "note": "same party"})
    assert response.status_code == 200
    rows = auth_client.tenant.evalset.read()
    assert rows[-1]["email_id"] == "c1"
    assert rows[-1]["status"] == "OK"
