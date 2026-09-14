"""Build the committed v1 synthetic benchmark deterministically.

This file contains synthetic scenarios only. It never reads Gmail, environment
credentials, repository exports, or network resources.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evaluation.schemas import EvaluationCase


ROOT = Path(__file__).resolve().parent
DEFAULT_RECEIVED = "2026-09-01T10:00:00-07:00"


def expected_date(value: str, semantic_type: str) -> dict[str, str]:
    return {"value": value, "semantic_type": semantic_type}


def case(
    case_id: str,
    subject: str,
    body: str,
    *,
    email_type: str,
    action_kind: str = "none",
    needs_reply: str = "false",
    contains_event: bool = False,
    event_status: str = "uncertain",
    registration_available: str = "false",
    registration_required: str = "false",
    registration_completed: str = "false",
    dates: list[dict[str, str]] | None = None,
    route: str = "informational",
    tags: list[str],
    received_at: str = DEFAULT_RECEIVED,
    sender: str = "Synthetic Sender <sender@benchmark.example>",
    body_format: str = "plain",
    labels: list[str] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    payload = {
        "id": case_id,
        "input": {
            "subject": subject,
            "body": body,
            "received_at": received_at,
            "sender": sender,
            "body_format": body_format,
            "labels": labels or ["INBOX", "UNREAD"],
            "headers": headers or {},
        },
        "ground_truth": {
            "email_type": email_type,
            "action_kind": action_kind,
            "needs_reply": needs_reply,
            "contains_event": contains_event,
            "event_status": event_status,
            "registration_available": registration_available,
            "registration_required": registration_required,
            "registration_completed": registration_completed,
            "dates": dates or [],
            "expected_route": route,
        },
        "tags": tags,
    }
    return EvaluationCase.model_validate(payload).model_dump(mode="json")


DEV_CASES = [
    case("act_dev_001", "Laboratory access form required", "You must complete the course laboratory access form by September 8, 2026.", email_type="academic", action_kind="required", dates=[expected_date("2026-09-08", "deadline")], route="needs_action", tags=["academic", "required_action", "deadline"]),
    case("act_dev_002", "Enrollment documentation incomplete", "Required documentation is missing. Submit it by September 12, 2026 or an enrollment hold will be placed.", email_type="administrative", action_kind="required", dates=[expected_date("2026-09-12", "deadline")], route="needs_action", tags=["administrative", "required_action", "deadline"]),
    case("act_dev_003", "Payment due notice", "Your synthetic program fee is due September 15, 2026. Payment is required to keep the account current.", email_type="administrative", action_kind="required", dates=[expected_date("2026-09-15", "deadline")], route="needs_action", tags=["administrative", "financial", "required_action", "deadline"]),
    case("act_dev_004", "Missing verification document", "Please provide the required verification document no later than September 18, 2026.", email_type="administrative", action_kind="required", dates=[expected_date("2026-09-18", "deadline")], route="needs_action", tags=["administrative", "required_action", "deadline"]),
    case("act_dev_005", "Urgent account security verification", "Action required: verify your account immediately after unusual sign-in activity.", email_type="security", action_kind="required", route="urgent", tags=["security", "required_action"]),
    case("act_dev_006", "Submit the capstone declaration", "The course declaration must be submitted by October 2, 2026.", email_type="academic", action_kind="required", dates=[expected_date("2026-10-02", "deadline")], route="needs_action", tags=["academic", "required_action", "deadline"]),
    case("act_dev_007", "Compliance requirement remains incomplete", "Complete the required compliance steps. Failure to complete them will place a registration hold.", email_type="administrative", action_kind="required", route="needs_action", tags=["administrative", "required_action"]),
    case("act_dev_008", "Tax document required", "You must submit the required tax documentation by December 30, 2026.", email_type="administrative", action_kind="required", dates=[expected_date("2026-12-30", "deadline")], route="needs_action", tags=["administrative", "financial", "required_action", "deadline"]),
    case("act_dev_009", "Enrollment task", "A required form is incomplete. Complete it to avoid an enrollment problem.", email_type="administrative", action_kind="required", route="needs_action", tags=["administrative", "required_action"]),
    case("act_dev_010", "Mandatory evacuation order", "Mandatory evacuation: you must leave the synthetic facility immediately.", email_type="security", action_kind="required", route="urgent", tags=["security", "required_action", "emergency"]),
    case("act_dev_011", "Response required for course placement", "Please respond by September 5, 2026 with your course placement selection.", email_type="academic", action_kind="required", needs_reply="true", dates=[expected_date("2026-09-05", "deadline")], route="needs_action", tags=["academic", "reply", "required_action", "deadline"]),
    case("act_dev_012", "Financial aid verification", "Action required. Provide the verification information by September 20, 2026 or processing will stop.", email_type="administrative", action_kind="required", dates=[expected_date("2026-09-20", "deadline")], route="needs_action", tags=["administrative", "financial", "required_action", "deadline"]),

    case("opt_dev_001", "Optional research application", "You may apply for the synthetic research program if interested.", email_type="academic", action_kind="optional", route="informational", tags=["academic", "conditional"]),
    case("opt_dev_002", "Conditional benefit document", "If you want the optional benefit, submit the document by December 30, 2026.", email_type="administrative", action_kind="optional", dates=[expected_date("2026-12-30", "deadline")], route="informational", tags=["administrative", "conditional", "deadline"]),
    case("opt_dev_003", "Unlock a synthetic discount", "Claim your discount and save on an optional purchase.", email_type="promotional", action_kind="optional", route="low_priority", tags=["promotion", "conditional"], sender="Synthetic Offers <offers@market.example>", labels=["INBOX", "UNREAD", "CATEGORY_PROMOTIONS"]),
    case("opt_dev_004", "Earn points this week", "Get rewards when you choose to make a purchase. No response is needed.", email_type="promotional", action_kind="optional", route="low_priority", tags=["promotion"], sender="Synthetic Rewards <no-reply@rewards.example>", labels=["INBOX", "UNREAD", "CATEGORY_PROMOTIONS"]),
    case("opt_dev_005", "Share your optional feedback", "Please take our optional satisfaction survey if you have time.", email_type="promotional", action_kind="optional", route="low_priority", tags=["promotion", "survey"], labels=["INBOX", "UNREAD", "CATEGORY_PROMOTIONS"]),
    case("opt_dev_006", "Open House September 14, 2026", "Register here if interested in attending the open house.", email_type="event", action_kind="optional", contains_event=True, event_status="upcoming", registration_available="true", dates=[expected_date("2026-09-14", "event_time")], route="upcoming_events", tags=["event", "registration", "conditional"]),
    case("opt_dev_007", "Recommended account review", "Please review your synthetic account settings when convenient. No action is required.", email_type="administrative", action_kind="none", route="informational", tags=["administrative", "informational"]),
    case("opt_dev_008", "Program information update", "This notice is for your information. You can explore the optional resources.", email_type="unknown", action_kind="optional", route="informational", tags=["conditional", "informational"]),
    case("opt_dev_009", "Free membership offer", "Unlock free membership and upgrade if you choose. This is not required.", email_type="promotional", action_kind="optional", route="low_priority", tags=["promotion"], labels=["INBOX", "UNREAD", "CATEGORY_PROMOTIONS"]),
    case("opt_dev_010", "Optional scholarship materials", "If you plan to apply, provide the essay by November 1, 2026.", email_type="academic", action_kind="optional", dates=[expected_date("2026-11-01", "deadline")], route="informational", tags=["academic", "conditional", "deadline"]),

    case("evt_dev_001", "Writing Workshop September 10, 2026", "The workshop begins at 2 PM and covers synthetic writing examples.", email_type="event", contains_event=True, event_status="upcoming", registration_available="uncertain", registration_required="uncertain", registration_completed="false", dates=[expected_date("2026-09-10", "event_time")], route="upcoming_events", tags=["event", "date"]),
    case("evt_dev_002", "Career Fair - Sept 9", "Meet synthetic recruiters at the career fair.", email_type="recruiting", contains_event=True, event_status="upcoming", registration_available="uncertain", registration_required="uncertain", registration_completed="false", dates=[expected_date("2026-09-09", "event_time")], route="upcoming_events", tags=["event", "recruiting", "date"]),
    case("evt_dev_003", "Seminar Tomorrow at 1 PM", "The seminar discusses synthetic systems.", email_type="event", contains_event=True, event_status="upcoming", registration_available="uncertain", registration_required="uncertain", registration_completed="false", dates=[expected_date("2026-09-02T13:00:00-07:00", "event_time")], route="upcoming_events", tags=["event", "relative_date", "timezone"]),
    case("evt_dev_004", "Online webinar September 16, 2026 at 11 AM PDT", "Join the online event for a synthetic demonstration.", email_type="event", contains_event=True, event_status="upcoming", registration_available="uncertain", registration_required="uncertain", registration_completed="false", dates=[expected_date("2026-09-16T11:00:00-07:00", "event_time")], route="upcoming_events", tags=["event", "timezone", "date"]),
    case("evt_dev_005", "Graduate Open House October 3, 2026", "An open house for prospective participants will be held on campus.", email_type="event", contains_event=True, event_status="upcoming", registration_available="uncertain", registration_required="uncertain", registration_completed="false", dates=[expected_date("2026-10-03", "event_time")], route="upcoming_events", tags=["event", "date"]),
    case("evt_dev_006", "Orientation September 4, 2026", "New participants are invited to the orientation. Attendance is optional.", email_type="event", action_kind="optional", contains_event=True, event_status="upcoming", registration_available="uncertain", registration_required="uncertain", registration_completed="false", dates=[expected_date("2026-09-04", "event_time")], route="upcoming_events", tags=["event", "conditional"]),
    case("evt_dev_007", "Reminder: workshop September 7, 2026", "This is a reminder for the previously announced workshop.", email_type="event", contains_event=True, event_status="upcoming", registration_available="uncertain", registration_required="uncertain", registration_completed="false", dates=[expected_date("2026-09-07", "event_time")], route="upcoming_events", tags=["event", "reminder"]),
    case("evt_dev_008", "You're registered for the Seminar September 11, 2026", "Registration confirmed. Event details are included below.", email_type="event", contains_event=True, event_status="upcoming", registration_available="true", registration_required="false", registration_completed="true", dates=[expected_date("2026-09-11", "event_time")], route="upcoming_events", tags=["event", "registration"]),
    case("evt_dev_009", "Workshop recap", "The previous workshop occurred August 20, 2026.", email_type="event", contains_event=True, event_status="past", registration_available="uncertain", registration_required="uncertain", registration_completed="false", dates=[expected_date("2026-08-20", "historical_date")], route="informational", tags=["event", "historical_date"]),
    case("evt_dev_010", "RSVP required for Career Fair September 18, 2026", "Registration is required to attend the fair.", email_type="recruiting", action_kind="required", contains_event=True, event_status="upcoming", registration_available="true", registration_required="true", registration_completed="false", dates=[expected_date("2026-09-18", "event_time")], route="needs_action", tags=["event", "registration", "recruiting", "required_action"]),
    case("evt_dev_011", "Public Seminar September 19, 2026", "No registration is required for this seminar.", email_type="event", contains_event=True, event_status="upcoming", registration_available="false", registration_required="false", registration_completed="false", dates=[expected_date("2026-09-19", "event_time")], route="upcoming_events", tags=["event", "registration"]),
    case("evt_dev_012", "Career Fair September 22, 2026", "Register by September 15, 2026. The fair begins at 10 AM.", email_type="recruiting", action_kind="required", contains_event=True, event_status="upcoming", registration_available="true", registration_required="true", registration_completed="false", dates=[expected_date("2026-09-22", "event_time"), expected_date("2026-09-15", "registration_deadline")], route="needs_action", tags=["event", "registration", "deadline", "recruiting"]),
    case("evt_dev_013", "Three upcoming workshops", "Design workshop September 8, 2026. Writing workshop September 15, 2026. Planning workshop September 29, 2026.", email_type="event", contains_event=True, event_status="upcoming", registration_available="uncertain", registration_required="uncertain", registration_completed="false", dates=[expected_date("2026-09-08", "event_time"), expected_date("2026-09-15", "event_time"), expected_date("2026-09-29", "event_time")], route="upcoming_events", tags=["event", "multiple_dates"]),
    case("evt_dev_014", "Community Expo October 8, 2026", "The all-day expo features synthetic community projects.", email_type="event", contains_event=True, event_status="upcoming", registration_available="uncertain", registration_required="uncertain", registration_completed="false", dates=[expected_date("2026-10-08", "event_time")], route="upcoming_events", tags=["event", "all_day"]),
    case("evt_dev_015", "Technical panel this Friday at 3 PM", "The panel covers practical synthetic engineering topics.", email_type="event", contains_event=True, event_status="upcoming", registration_available="uncertain", registration_required="uncertain", registration_completed="false", dates=[expected_date("2026-09-04T15:00:00-07:00", "event_time")], route="upcoming_events", tags=["event", "relative_date", "timezone"]),
    case("evt_dev_016", "Workshop Today at 6 PM", "The workshop is scheduled for this evening.", email_type="event", contains_event=True, event_status="ongoing", registration_available="uncertain", registration_required="uncertain", registration_completed="false", dates=[expected_date("2026-09-03T18:00:00-07:00", "event_time")], route="upcoming_events", tags=["event", "relative_date", "timezone", "utc_boundary"], received_at="2026-09-03T23:30:00+00:00"),
    case("evt_dev_017", "Interview session next Monday at 9 AM", "The interview session introduces a synthetic recruiting process.", email_type="recruiting", contains_event=True, event_status="upcoming", registration_available="uncertain", registration_required="uncertain", registration_completed="false", dates=[expected_date("2026-09-07T09:00:00-07:00", "event_time")], route="upcoming_events", tags=["event", "relative_date", "recruiting"]),
    case("evt_dev_018", "Research seminar September 25, 2026", "The announcement was published September 1, 2026. The seminar takes place September 25, 2026.", email_type="event", contains_event=True, event_status="upcoming", registration_available="uncertain", registration_required="uncertain", registration_completed="false", dates=[expected_date("2026-09-25", "event_time"), expected_date("2026-09-01", "publication_date")], route="upcoming_events", tags=["event", "publication_date", "multiple_dates"]),

    case("news_dev_001", "Synthetic monthly newsletter", "Community stories and general updates are included in this edition.", email_type="newsletter", route="low_priority", tags=["newsletter"]),
    case("news_dev_002", "Opportunities newsletter", "A career workshop takes place September 17, 2026 at 2 PM.", email_type="newsletter", contains_event=True, event_status="upcoming", registration_available="uncertain", registration_required="uncertain", registration_completed="false", dates=[expected_date("2026-09-17T14:00:00-07:00", "event_time")], route="upcoming_events", tags=["newsletter", "event"]),
    case("news_dev_003", "Weekly workshops newsletter", "Workshop one is September 9, 2026. Workshop two is September 16, 2026. Workshop three is September 23, 2026.", email_type="newsletter", contains_event=True, event_status="upcoming", registration_available="uncertain", registration_required="uncertain", registration_completed="false", dates=[expected_date("2026-09-09", "event_time"), expected_date("2026-09-16", "event_time"), expected_date("2026-09-23", "event_time")], route="upcoming_events", tags=["newsletter", "event", "multiple_dates"]),
    case("news_dev_004", "Career events newsletter", "RSVP required by September 6, 2026. The career fair takes place September 12, 2026.", email_type="newsletter", action_kind="required", contains_event=True, event_status="upcoming", registration_available="true", registration_required="true", registration_completed="false", dates=[expected_date("2026-09-06", "registration_deadline"), expected_date("2026-09-12", "event_time")], route="needs_action", tags=["newsletter", "event", "registration", "deadline"]),
    case("news_dev_005", "Rewards newsletter", "Explore a special offer and claim synthetic rewards this week.", email_type="newsletter", action_kind="optional", route="low_priority", tags=["newsletter", "promotion"], labels=["INBOX", "UNREAD", "CATEGORY_PROMOTIONS"]),
    case("dig_dev_001", "Synthetic Spam Digest", "Held item: Workshop Tomorrow at 4 PM. RSVP required for the embedded message.", email_type="digest", route="informational", tags=["digest", "relative_date"]),
    case("dig_dev_002", "Synthetic Security Quarantine Digest", "Embedded item received September 2, 2026 at 9 AM. Career Fair September 10, 2026.", email_type="digest", route="informational", tags=["digest", "security", "multiple_dates"]),
    case("dig_dev_003", "Synthetic Daily Digest", "First child says action required by September 8, 2026. Second child is a seminar September 14, 2026.", email_type="digest", route="informational", tags=["digest", "deadline", "event"]),
    case("dig_dev_004", "Synthetic Notification Digest", "Embedded RSVP required. Embedded webinar tomorrow. These are child summaries only.", email_type="digest", route="informational", tags=["digest", "registration", "event"]),
    case("dig_dev_005", "Synthetic Quarantined Message Digest", "Three held timestamps: 2026-09-01 08:00, 2026-09-01 09:00, and 2026-09-01 10:00.", email_type="digest", route="informational", tags=["digest", "multiple_dates"]),

    case("sec_dev_001", "Public safety advisory", "Wear a helmet, lock your scooter, stay alert, and take precautions.", email_type="security", action_kind="recommended", route="informational", tags=["security", "recommended_action"]),
    case("sec_dev_002", "Urgent emergency information", "Shelter in place immediately. This mandatory order applies to everyone in the synthetic facility.", email_type="security", action_kind="required", route="urgent", tags=["security", "emergency", "required_action"]),
    case("sec_dev_003", "Account security notice", "A new sign-in was detected. No action is required if this was you.", email_type="security", route="informational", tags=["security", "informational"]),
    case("sec_dev_004", "Password reset required", "Action required: reset your password immediately because the account may be compromised.", email_type="security", action_kind="required", route="urgent", tags=["security", "required_action"]),
    case("rep_dev_001", "Question about the synthetic outline", "Can you confirm whether the revised outline is ready?", email_type="personal", needs_reply="true", route="needs_reply", tags=["reply", "personal"]),
    case("rep_dev_002", "Please respond with your selection", "Please reply by September 6, 2026 with your preferred option.", email_type="personal", action_kind="required", needs_reply="true", dates=[expected_date("2026-09-06", "deadline")], route="needs_action", tags=["reply", "deadline", "required_action"]),
    case("rep_dev_003", "Automated receipt", "Payment received. This automatic notification does not accept replies.", email_type="receipt", route="informational", tags=["reply", "automated"], sender="Synthetic Billing <no-reply@billing.example>", headers={"Auto-Submitted": "auto-generated"}),
    case("rep_dev_004", "Learn more about rewards", "Reply online to learn more about this optional promotional offer.", email_type="promotional", action_kind="optional", route="low_priority", tags=["reply", "promotion"], sender="Synthetic Offers <no-reply@offers.example>", labels=["INBOX", "UNREAD", "CATEGORY_PROMOTIONS"]),

    case("html_dev_001", "Synthetic event announcement", "<style>table.button table td { color:red; }</style><script>track()</script><p>The workshop takes place September 21, 2026.</p>", email_type="event", contains_event=True, event_status="upcoming", registration_available="uncertain", registration_required="uncertain", registration_completed="false", dates=[expected_date("2026-09-21", "event_time")], route="upcoming_events", tags=["html_noise", "event"], body_format="html"),
    case("html_dev_002", "Open House September 24, 2026", "<div style='display:none'>Preview: discount tomorrow</div><p>The open house welcomes synthetic visitors.</p>", email_type="event", contains_event=True, event_status="upcoming", registration_available="uncertain", registration_required="uncertain", registration_completed="false", dates=[expected_date("2026-09-24", "event_time")], route="upcoming_events", tags=["html_noise", "event"], body_format="html"),
    case("html_dev_003", "Program notice", "\u200b\u200c\u200dView this email as a web page.\nThe synthetic program published a meaningful update.", email_type="unknown", route="manual_review", tags=["html_noise", "boilerplate"]),
    case("html_dev_004", "Seminar October 1, 2026", "This email was sent on behalf of Synthetic Communications.\nTo view this email as a web page, click here.\nThe seminar explains practical research methods.", email_type="event", contains_event=True, event_status="upcoming", registration_available="uncertain", registration_required="uncertain", registration_completed="false", dates=[expected_date("2026-10-01", "event_time")], route="upcoming_events", tags=["boilerplate", "event"]),
    case("date_dev_001", "Appointment record", "The previous appointment was on August 12, 2026.", email_type="event", contains_event=True, event_status="past", registration_available="uncertain", registration_required="uncertain", registration_completed="false", dates=[expected_date("2026-08-12", "historical_date")], route="informational", tags=["historical_date", "date"]),
    case("date_dev_002", "Publication notice", "The synthetic report was published August 30, 2026. No action is required.", email_type="unknown", dates=[expected_date("2026-08-30", "publication_date")], route="informational", tags=["publication_date", "date"]),
    case("date_dev_003", "Event Tomorrow at 1 PM", "The event contains a synthetic presentation.", email_type="event", contains_event=True, event_status="upcoming", registration_available="uncertain", registration_required="uncertain", registration_completed="false", dates=[expected_date("2026-09-03T13:00:00-07:00", "event_time")], route="upcoming_events", tags=["event", "relative_date", "timezone", "utc_boundary"], received_at="2026-09-03T01:30:00+00:00"),
]


# Held-out phrasing. Do not alter classifier behavior from failures in this split.
TEST_CASES = [
    case("act_test_001", "Training acknowledgment overdue", "The required course acknowledgment must be completed by September 13, 2026.", email_type="academic", action_kind="required", dates=[expected_date("2026-09-13", "deadline")], route="needs_action", tags=["academic", "required_action", "deadline"]),
    case("act_test_002", "Resolve the account balance", "Payment is due September 28, 2026. Failure to pay may suspend access.", email_type="administrative", action_kind="required", dates=[expected_date("2026-09-28", "deadline")], route="needs_action", tags=["administrative", "financial", "required_action", "deadline"]),
    case("act_test_003", "Upload missing residency document", "Your verification document is incomplete; provide it no later than October 4, 2026.", email_type="administrative", action_kind="required", dates=[expected_date("2026-10-04", "deadline")], route="needs_action", tags=["administrative", "required_action", "deadline"]),
    case("act_test_004", "Registration hold pending", "Complete the compliance requirement or a hold will be placed on enrollment.", email_type="administrative", action_kind="required", route="needs_action", tags=["administrative", "required_action"]),
    case("act_test_005", "Secure your account", "Unusual sign-in activity was found. You must change the password immediately.", email_type="security", action_kind="required", route="urgent", tags=["security", "required_action"]),
    case("act_test_006", "Required declaration", "Submit the required academic declaration by October 9, 2026.", email_type="academic", action_kind="required", dates=[expected_date("2026-10-09", "deadline")], route="needs_action", tags=["academic", "required_action", "deadline"]),
    case("act_test_007", "Emergency evacuation", "Evacuate immediately under this mandatory emergency order.", email_type="security", action_kind="required", route="urgent", tags=["security", "emergency", "required_action"]),

    case("opt_test_001", "Apply if the program fits", "If you plan to apply for the optional fellowship, submit an essay by November 10, 2026.", email_type="academic", action_kind="optional", dates=[expected_date("2026-11-10", "deadline")], route="informational", tags=["academic", "conditional", "deadline"]),
    case("opt_test_002", "Claim a sample discount", "Unlock savings and claim the optional discount before shopping.", email_type="promotional", action_kind="optional", route="low_priority", tags=["promotion"], labels=["INBOX", "UNREAD", "CATEGORY_PROMOTIONS"]),
    case("opt_test_003", "Tell us about your visit", "You can complete this optional survey if you wish.", email_type="promotional", action_kind="optional", route="low_priority", tags=["promotion", "survey"], labels=["INBOX", "UNREAD", "CATEGORY_PROMOTIONS"]),
    case("opt_test_004", "Optional benefit filing", "If you choose to claim the benefit, file the tax form by December 20, 2026.", email_type="administrative", action_kind="optional", dates=[expected_date("2026-12-20", "deadline")], route="informational", tags=["administrative", "conditional", "deadline"]),
    case("opt_test_005", "Explore synthetic membership", "Get free membership, earn points, or upgrade when convenient.", email_type="promotional", action_kind="optional", route="low_priority", tags=["promotion"], labels=["INBOX", "UNREAD", "CATEGORY_PROMOTIONS"]),

    case("evt_test_001", "Data Seminar 9/14", "The seminar presents a synthetic dataset.", email_type="event", contains_event=True, event_status="upcoming", registration_available="uncertain", registration_required="uncertain", registration_completed="false", dates=[expected_date("2026-09-14", "event_time")], route="upcoming_events", tags=["event", "date"]),
    case("evt_test_002", "Tomorrow! Meet Recruiters", "Representatives will discuss synthetic internships at 1 PM.", email_type="recruiting", contains_event=True, event_status="upcoming", registration_available="uncertain", registration_required="uncertain", registration_completed="false", dates=[expected_date("2026-09-02T13:00:00-07:00", "event_time")], route="upcoming_events", tags=["event", "recruiting", "relative_date"]),
    case("evt_test_003", "Information Session September 20, 2026 at 4 PM PST", "The online session explains a synthetic program.", email_type="event", contains_event=True, event_status="upcoming", registration_available="uncertain", registration_required="uncertain", registration_completed="false", dates=[expected_date("2026-09-20T16:00:00-08:00", "event_time")], route="upcoming_events", tags=["event", "timezone"]),
    case("evt_test_004", "Community orientation this Friday", "Orientation begins at 10 AM for new participants.", email_type="event", contains_event=True, event_status="upcoming", registration_available="uncertain", registration_required="uncertain", registration_completed="false", dates=[expected_date("2026-09-04", "event_time")], route="upcoming_events", tags=["event", "relative_date"]),
    case("evt_test_005", "RSVP required: Technical Panel September 26, 2026", "You must register to attend the panel.", email_type="event", action_kind="required", contains_event=True, event_status="upcoming", registration_available="true", registration_required="true", registration_completed="false", dates=[expected_date("2026-09-26", "event_time")], route="needs_action", tags=["event", "registration", "required_action"]),
    case("evt_test_006", "You're registered: Open House September 27, 2026", "Your registration was successful. No further registration action is needed.", email_type="event", contains_event=True, event_status="upcoming", registration_available="true", registration_required="false", registration_completed="true", dates=[expected_date("2026-09-27", "event_time")], route="upcoming_events", tags=["event", "registration"]),
    case("evt_test_007", "Public Workshop October 5, 2026", "Attendance is optional and no registration is required.", email_type="event", action_kind="optional", contains_event=True, event_status="upcoming", registration_available="false", registration_required="false", registration_completed="false", dates=[expected_date("2026-10-05", "event_time")], route="upcoming_events", tags=["event", "registration", "conditional"]),
    case("evt_test_008", "Workshop series", "First workshop September 6, 2026; second workshop September 13, 2026; final workshop September 20, 2026.", email_type="event", contains_event=True, event_status="upcoming", registration_available="uncertain", registration_required="uncertain", registration_completed="false", dates=[expected_date("2026-09-06", "event_time"), expected_date("2026-09-13", "event_time"), expected_date("2026-09-20", "event_time")], route="upcoming_events", tags=["event", "multiple_dates"]),
    case("evt_test_009", "Yesterday's seminar recap", "The seminar occurred August 31, 2026 and materials are now available.", email_type="event", contains_event=True, event_status="past", registration_available="uncertain", registration_required="uncertain", registration_completed="false", dates=[expected_date("2026-08-31", "historical_date")], route="informational", tags=["event", "historical_date"]),

    case("news_test_001", "Community weekly newsletter", "General stories, announcements, and optional links for the synthetic community.", email_type="newsletter", route="low_priority", tags=["newsletter"]),
    case("news_test_002", "Events newsletter", "A technical talk takes place September 30, 2026. A workshop follows October 7, 2026.", email_type="newsletter", contains_event=True, event_status="upcoming", registration_available="uncertain", registration_required="uncertain", registration_completed="false", dates=[expected_date("2026-09-30", "event_time"), expected_date("2026-10-07", "event_time")], route="upcoming_events", tags=["newsletter", "event", "multiple_dates"]),
    case("news_test_003", "Registration newsletter", "Register by September 21, 2026 for the career fair on September 25, 2026. RSVP is required.", email_type="newsletter", action_kind="required", contains_event=True, event_status="upcoming", registration_available="true", registration_required="true", registration_completed="false", dates=[expected_date("2026-09-21", "registration_deadline"), expected_date("2026-09-25", "event_time")], route="needs_action", tags=["newsletter", "event", "registration", "deadline"]),
    case("dig_test_001", "Synthetic Spam Digest", "Child one: RSVP required tomorrow. Child two: workshop September 28, 2026.", email_type="digest", route="informational", tags=["digest", "event", "registration"]),
    case("dig_test_002", "Synthetic Daily Notification Digest", "Embedded messages arrived at 8 AM, 9 AM, and 10 AM. One says action required by September 9, 2026.", email_type="digest", route="informational", tags=["digest", "deadline", "multiple_dates"]),

    case("sec_test_001", "Mobility safety advisory", "Stay alert, wear a helmet, and use caution near traffic.", email_type="security", action_kind="recommended", route="informational", tags=["security", "recommended_action"]),
    case("sec_test_002", "Mandatory lockdown order", "Do not enter the synthetic building. A mandatory lockdown is in effect immediately.", email_type="security", action_kind="required", route="urgent", tags=["security", "emergency", "required_action"]),
    case("sec_test_003", "Security sign-in notification", "A sign-in was recorded from a new browser. If it was you, no action is required.", email_type="security", route="informational", tags=["security", "conditional"]),
    case("rep_test_001", "Could we revise the meeting time?", "Could you reply with a time that works for you?", email_type="personal", needs_reply="true", route="needs_reply", tags=["reply", "personal"]),
    case("rep_test_002", "Automated status update", "This no-reply notification confirms that the synthetic request was received.", email_type="automated", route="informational", tags=["reply", "automated"], sender="Synthetic System <no-reply@system.example>", headers={"Auto-Submitted": "auto-generated"}),

    case("html_test_001", "Workshop September 23, 2026", "<style>table.button td { padding:12px; }</style><div class='preheader'>Hidden sale tomorrow</div><p>The workshop explores synthetic design methods.</p>", email_type="event", contains_event=True, event_status="upcoming", registration_available="uncertain", registration_required="uncertain", registration_completed="false", dates=[expected_date("2026-09-23", "event_time")], route="upcoming_events", tags=["html_noise", "event"], body_format="html"),
    case("html_test_002", "Meaningful schedule notice", "<script>collect()</script><p>To view this email as a web page, click here.</p><p>The synthetic schedule has been updated.</p>", email_type="unknown", route="manual_review", tags=["html_noise", "boilerplate"], body_format="html"),
    case("date_test_001", "Event Tomorrow at 1 PM", "The event presents a synthetic topic.", email_type="event", contains_event=True, event_status="upcoming", registration_available="uncertain", registration_required="uncertain", registration_completed="false", dates=[expected_date("2026-09-03T13:00:00-07:00", "event_time")], route="upcoming_events", tags=["event", "relative_date", "timezone", "utc_boundary"], received_at="2026-09-03T01:30:00+00:00"),
    case("date_test_002", "Spring event tomorrow at 1 PM", "The event occurs after the daylight-saving transition.", email_type="event", contains_event=True, event_status="upcoming", registration_available="uncertain", registration_required="uncertain", registration_completed="false", dates=[expected_date("2026-03-08T13:00:00-07:00", "event_time")], route="upcoming_events", tags=["event", "relative_date", "timezone", "dst_boundary"], received_at="2026-03-08T07:30:00+00:00"),
]


def write_split(name: str, cases: list[dict[str, Any]]) -> None:
    destination = ROOT / name / "cases.jsonl"
    destination.parent.mkdir(parents=True, exist_ok=True)
    serialized = "\n".join(
        json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for item in cases
    )
    destination.write_text(f"{serialized}\n", encoding="utf-8")


def main() -> None:
    all_cases = DEV_CASES + TEST_CASES
    ids = [item["id"] for item in all_cases]
    if len(all_cases) != 100:
        raise RuntimeError(f"expected 100 cases, found {len(all_cases)}")
    if len(ids) != len(set(ids)):
        raise RuntimeError("evaluation case IDs must be unique")
    write_split("dev", DEV_CASES)
    write_split("test", TEST_CASES)


if __name__ == "__main__":
    main()
