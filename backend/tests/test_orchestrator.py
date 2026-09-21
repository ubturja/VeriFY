from pathlib import Path

from verify.domain.enums import ReviewReason, Status
from verify.domain.models import AttachmentRef, EmailMessage
from verify.pipeline.orchestrator import run_pipeline

SI_TEXT = """SHIPPING INSTRUCTION
========================================
Shipper (Principal or Seller): ASIA PACIFIC PAPERBOARD TRADING PTE LTD
CONSIGNEE: PACIFIC OFFICE (M) SDN BHD
NOTIFY PARTY: PACIFIC OFFICE (M) SDN BHD
Load Port: PORT KLANG (WESTPORT), MALAYSIA (MYPKG)
Discharge Port: MERSIN, TURKEY (TRMER)
No. of Containers or Packages: 1 x 40'HC
Gross Wt (kgs): 20,381 KG
"""

BL_TEXT = """BILL OF LADING (DRAFT)
========================================
Shipper/Exporter: ASIA PACIFIC PAPERBOARD TRADING PTE LTD
Consignee (Non-Negotiable): PACIFIC OFFICE (M) SDN BHD
Notify: PACIFIC OFFICE (M) SDN BHD
POL: PORT KLANG (WESTPORT), MALAYSIA (MYPKG)
Discharge Port: MERSIN, TURKEY (TRMER)
No. of Containers or Packages: 1 x 40'HC
Gross Weight (KG): 20,381 KG
"""


def _write_pair(tmp_path: Path, si_name: str, bl_name: str) -> EmailMessage:
    si = tmp_path / si_name
    bl = tmp_path / bl_name
    si.write_text(SI_TEXT)
    bl.write_text(BL_TEXT)
    return EmailMessage(
        email_id="live-1",
        sender="ops@carrier.test",
        subject="Please check draft BL against SI",
        body="Please compare the attached shipping instruction with the draft BL.",
        attachments=[
            AttachmentRef(path=str(si), filename=si_name),
            AttachmentRef(path=str(bl), filename=bl_name),
        ],
        source="imap",
    )


async def test_live_gmail_filenames_are_compared(tmp_path):
    email = _write_pair(tmp_path, "SI-live-test.txt", "draft-BL-live-test.txt")
    result = await run_pipeline(email, lambda path: Path(path).read_bytes(), llm=None)
    assert result.review_reason is None
    assert result.status == Status.OK
    assert len(result.comparisons) == 7
    assert all(item.match is True for item in result.comparisons)


async def test_hackathon_filenames_still_compared(tmp_path):
    email = _write_pair(tmp_path, "email_009_SI.txt", "email_009_BL.txt")
    result = await run_pipeline(email, lambda path: Path(path).read_bytes(), llm=None)
    assert result.status == Status.OK
    assert result.comparisons


async def test_compare_request_without_docs_is_missing_attachment():
    email = EmailMessage(
        email_id="empty",
        sender="ops@carrier.test",
        subject="Please check draft BL against SI",
        body="Please compare the attached shipping instruction with the draft BL.",
        attachments=[],
    )
    result = await run_pipeline(email, lambda path: Path(path).read_bytes(), llm=None)
    assert result.status == Status.NEEDS_REVIEW
    assert result.review_reason == ReviewReason.MISSING_ATTACHMENT
