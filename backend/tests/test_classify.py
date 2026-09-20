from verify.domain.enums import Category, CompareIntent
from verify.domain.models import EmailMessage
from verify.pipeline.classify import score_rules


def test_request_draft_is_bl_comparison_not_missing_attachment():
    email = EmailMessage(
        email_id="x",
        sender="a@b.com",
        subject="TO CONFIRM DOCS _ 5RSG-00133 _ CALLAO",
        body="Please assist to send the draft BL for SIN832764835 for checking asap.",
        attachments=[],
    )
    category, intent, confidence, _ = score_rules(email)
    assert category == Category.BL_COMPARISON
    assert intent == CompareIntent.REQUEST_DRAFT
    assert confidence >= 0.8


def test_spam_subject():
    email = EmailMessage(
        email_id="s",
        sender="winner@prize-claims.info",
        subject="Congratulations! You have WON a $1,000 Gift Card - CLAIM NOW",
        body="Click here",
    )
    category, _, confidence, _ = score_rules(email)
    assert category == Category.SPAM
    assert confidence >= 0.9
