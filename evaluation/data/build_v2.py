"""Build benchmark v2 without reading Gmail, credentials, or the network.

V1 records are retained as development material. New test and challenge
records are authored by scenario family; a family is assigned to one split
only, preventing minimal-pair and template variants from crossing splits.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evaluation.schemas import EvaluationCase


ROOT = Path(__file__).resolve().parent
DEFAULT_RECEIVED = "2026-09-01T10:00:00-07:00"


def d(value: str, semantic_type: str) -> dict[str, str]:
    return {"value": value, "semantic_type": semantic_type}


def c(
    case_id: str,
    family_id: str,
    subject: str,
    body: str,
    *,
    email_type: str = "unknown",
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
    mime_structure: str = "simple",
    encoding_mode: str = "valid",
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    payload = {
        "id": case_id,
        "family_id": family_id,
        "input": {
            "subject": subject,
            "body": body,
            "received_at": received_at,
            "sender": sender,
            "body_format": body_format,
            "mime_structure": mime_structure,
            "encoding_mode": encoding_mode,
            "labels": ["INBOX", "UNREAD"],
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


TEST_CASES = [
    c("v2t_obligation_01", "documentation_consequence", "Documentation status", "Students whose identity document remains incomplete after September 17, 2026 will be unable to enroll. Your checklist shows that item as incomplete.", email_type="administrative", action_kind="required", dates=[d("2026-09-17", "deadline")], route="needs_action", tags=["administrative", "required_action", "deadline", "implicit_obligation"]),
    c("v2t_obligation_02", "documentation_consequence", "Checklist complete", "Your identity documentation was accepted on August 29, 2026. The September 17 restriction applies only to incomplete records; nothing further is requested.", email_type="administrative", dates=[d("2026-08-29", "historical_date"), d("2026-09-17", "referenced_date")], route="informational", tags=["administrative", "conditional", "multiple_dates", "minimal_pair"]),
    c("v2t_optional_01", "feedback_incentive", "Tell us what you think", "Complete the optional questionnaire by Friday to enter a drawing. Participation has no effect on services or eligibility.", email_type="promotional", action_kind="optional", dates=[d("2026-09-04", "promotion_date")], route="low_priority", tags=["promotion", "conditional", "trigger_negative", "relative_date"]),
    c("v2t_optional_02", "feedback_incentive", "Course feedback requested", "Please send your assessment of the draft before Friday so the instructor can finalize your individual revision plan. A response is expected.", email_type="academic", action_kind="required", needs_reply="true", dates=[d("2026-09-04", "deadline")], route="needs_action", tags=["academic", "required_action", "reply", "minimal_pair", "relative_date"]),
    c("v2t_event_01", "archive_gallery", "Photos from the September 18 career fair", "The gallery documents last year's fair held September 18, 2025. Browse the album whenever convenient.", email_type="recruiting", contains_event=True, event_status="past", dates=[d("2025-09-18", "historical_date")], route="informational", tags=["event", "historical_date", "trigger_negative"]),
    c("v2t_event_02", "archive_gallery", "Career connections", "Employers will meet students September 18, 2026 from 10:00 AM to 2:00 PM in the civic hall.", email_type="recruiting", contains_event=True, event_status="upcoming", dates=[d("2026-09-18T10:00:00-07:00", "event_time")], route="upcoming_events", tags=["event", "recruiting", "implicit_event", "minimal_pair"]),
    c("v2t_register_01", "attendance_gate", "Access instructions for the lab tour", "Only names on the visitor list can enter. Add yours before September 12, 2026 if you intend to join the tour on September 15, 2026.", email_type="event", action_kind="required", contains_event=True, event_status="upcoming", registration_available="true", registration_required="true", dates=[d("2026-09-12", "registration_deadline"), d("2026-09-15", "event_time")], route="needs_action", tags=["event", "registration", "implicit_obligation", "multiple_dates"]),
    c("v2t_register_02", "attendance_gate", "Lab tour visitor list updated", "Your name was added successfully for the tour on September 15, 2026. No additional enrollment step is needed.", email_type="event", contains_event=True, event_status="upcoming", registration_available="true", registration_completed="true", dates=[d("2026-09-15", "event_time")], route="upcoming_events", tags=["event", "registration", "registration_completed", "minimal_pair"]),
    c("v2t_dates_01", "publication_and_deadline", "Revised handbook posted", "Version 3 was published August 28, 2026. Acknowledgments must reach the office by September 9, 2026.", email_type="administrative", action_kind="required", dates=[d("2026-08-28", "publication_date"), d("2026-09-09", "deadline")], route="needs_action", tags=["administrative", "deadline", "publication_date", "multiple_dates"]),
    c("v2t_dates_02", "publication_and_deadline", "Handbook archive notice", "The handbook was published September 9, 2025 and archived August 28, 2026. This message records those dates and asks for nothing.", email_type="administrative", dates=[d("2025-09-09", "publication_date"), d("2026-08-28", "historical_date")], route="informational", tags=["administrative", "historical_date", "multiple_dates", "trigger_negative"]),
    c("v2t_reply_01", "human_response", "Question about the proposed schedule", "Would Tuesday afternoon work for you? Please let me know which of the two times you prefer.", email_type="personal", needs_reply="true", route="needs_reply", tags=["reply", "personal", "implicit_obligation"]),
    c("v2t_reply_02", "human_response", "Schedule receipt", "This automated message confirms the schedule preference previously submitted. Replies to this mailbox are not monitored.", email_type="automated", route="informational", tags=["reply", "automated", "minimal_pair"], sender="Synthetic Scheduler <no-reply@scheduler.example>", headers={"Auto-Submitted": "auto-generated"}),
    c("v2t_ambiguous_01", "vague_followup", "A quick follow-up", "Please take care of this soon. The earlier context is not included.", action_kind="uncertain", needs_reply="uncertain", route="manual_review", tags=["ambiguous", "manual_review", "short_message"]),
    c("v2t_ambiguous_02", "vague_followup", "Program note", "You may need to submit documentation depending on your program and residency category. Check the applicable rules before acting.", email_type="administrative", action_kind="uncertain", route="manual_review", tags=["ambiguous", "manual_review", "conditional"]),
    c("v2t_news_01", "multi_section_bulletin", "September community bulletin", "SEPTEMBER BULLETIN\n\nResearch spotlight: a team released a public dataset on August 25, 2026.\n\nCampus programs: a lecture will take place September 21, 2026 at 4 PM. Attendance is optional and seats are open without registration.\n\nServices: maintenance is planned overnight. No response is requested.\n\nStudent offers: save on museum admission through September 30, 2026.\n\nThis bulletin combines unrelated announcements. Manage preferences | Privacy notice | Unsubscribe", email_type="newsletter", contains_event=True, event_status="upcoming", action_kind="optional", registration_available="false", dates=[d("2026-08-25", "publication_date"), d("2026-09-21T16:00:00-07:00", "event_time"), d("2026-09-30", "promotion_date")], route="upcoming_events", tags=["newsletter", "long_body", "multiple_dates", "multiple_sections", "event"]),
    c("v2t_html_01", "hidden_preheader", "Account notice", "<html><head><style>.hide{display:none}</style><script>track('required')</script></head><body><div style='display:none'>URGENT: discount expires today</div><p>Your mailing preferences were updated successfully. No action is needed.</p><img src='https://tracker.example/pixel.gif' width='1' height='1'><footer>View online | Unsubscribe</footer></body></html>", email_type="automated", route="informational", tags=["html_noise", "preheader", "tracking", "trigger_negative"], body_format="html"),
    c("v2t_forward_01", "obsolete_quote", "Re: form status", "The form is now accepted; no further action is needed.\n\nOn Mon, Aug 24, 2026 at 9:00 AM Synthetic Office wrote:\n> Action required: submit the form by August 28, 2026.", email_type="administrative", dates=[], route="informational", tags=["quoted_reply", "obsolete_deadline", "historical_date"]),
    c("v2t_forward_02", "current_forward", "Fwd: visiting speaker logistics", "Please confirm whether you can host the speaker by September 6, 2026.\n\n---------- Forwarded message ----------\nThe lecture is September 10, 2026 at 3 PM. Registration is open to the public.", email_type="personal", action_kind="required", needs_reply="true", contains_event=True, event_status="upcoming", registration_available="true", registration_required="false", dates=[d("2026-09-06", "deadline"), d("2026-09-10T15:00:00-07:00", "event_time")], route="needs_action", tags=["forwarded", "reply", "event", "multiple_dates"]),
    c("v2t_mime_01", "nested_mime", "Orientation packet", "Orientation takes place September 24, 2026 at 9 AM. The attached packet is not needed to identify the event.", email_type="event", contains_event=True, event_status="upcoming", dates=[d("2026-09-24T09:00:00-07:00", "event_time")], route="upcoming_events", tags=["event", "nested_mime", "attachment_excluded"], mime_structure="nested_multipart"),
    c("v2t_mime_02", "nested_mime", "Plain-text account summary", "Your monthly account summary is available. No response is requested.", email_type="automated", route="informational", tags=["nested_mime", "automated"], mime_structure="multipart_alternative"),
    c("v2t_tz_01", "midnight_boundary", "Session tomorrow at 12:30 AM", "The online session begins shortly after midnight local time.", email_type="event", contains_event=True, event_status="upcoming", dates=[d("2026-09-02T00:30:00-07:00", "event_time")], route="upcoming_events", tags=["event", "relative_date", "timezone", "utc_boundary"], received_at="2026-09-01T23:45:00-07:00"),
    c("v2t_tz_02", "midnight_boundary", "Release at 11:45 PM PDT", "The public release is scheduled for September 1, 2026 at 11:45 PM PDT.", email_type="event", contains_event=True, event_status="upcoming", dates=[d("2026-09-01T23:45:00-07:00", "event_time")], route="upcoming_events", tags=["event", "timezone", "utc_boundary"]),
    c("v2t_dst_01", "fall_dst", "Maintenance November 1 at 1:30 AM", "Maintenance begins November 1, 2026 at 1:30 AM after clocks fall back; the notice does not specify which 1:30.", email_type="event", contains_event=True, event_status="upcoming", dates=[d("2026-11-01", "event_time")], route="upcoming_events", tags=["event", "timezone", "dst_boundary", "ambiguous_time"]),
    c("v2t_dst_02", "spring_dst", "System window March 8 at 2:30 AM", "The planned local time falls in the spring-forward gap on March 8, 2026. Review the service page for clarification.", email_type="event", contains_event=True, event_status="upcoming", dates=[d("2026-03-08", "event_time")], route="upcoming_events", tags=["event", "timezone", "dst_boundary", "ambiguous_time"], received_at="2026-03-01T10:00:00-08:00"),
    c("v2t_security_01", "security_conditional", "New sign-in reviewed", "A sign-in occurred at 8:12 AM. If you recognize it, no action is required; otherwise secure the account immediately.", email_type="security", action_kind="uncertain", route="manual_review", tags=["security", "conditional", "manual_review"]),
    c("v2t_security_02", "security_conditional", "Password reset requested", "We received a password reset request. Use the secure account page immediately if you did not initiate it.", email_type="security", action_kind="uncertain", route="manual_review", tags=["security", "conditional", "manual_review"]),
    c("v2t_promo_01", "obligation_marketing", "You must see these weekend discounts", "Required reading for bargain hunters: prices are due to disappear Sunday. Buying is entirely optional.", email_type="promotional", action_kind="optional", dates=[d("2026-09-06", "promotion_date")], route="low_priority", tags=["promotion", "trigger_negative", "relative_date"]),
    c("v2t_promo_02", "obligation_marketing", "Mandatory style update", "Submit your order today to unlock a bonus. This advertisement creates no obligation.", email_type="promotional", action_kind="optional", dates=[d("2026-09-01", "promotion_date")], route="low_priority", tags=["promotion", "trigger_negative"]),
    c("v2t_digest_01", "container_isolation", "Daily message digest", "Three held messages are summarized below.\n1. Subject: RSVP required for workshop September 12.\n2. Subject: payment due September 8.\n3. Subject: urgent account verification.\nThese are embedded previews; review the original messages separately.", email_type="digest", route="informational", tags=["digest", "container", "event", "deadline", "trigger_negative"]),
    c("v2t_digest_02", "container_isolation", "Notification bundle", "A bundled feed contains: 'register by Friday', 'meeting tomorrow', and 'action required'. The bundle itself requests no action.", email_type="digest", route="informational", tags=["digest", "container", "relative_date", "trigger_negative"]),
    c("v2t_auto_01", "automated_receipts", "Submission received", "Your application was received September 1, 2026. Keep this confirmation for reference; do not reply.", email_type="automated", registration_completed="true", dates=[d("2026-09-01", "historical_date")], route="informational", tags=["automated", "registration_completed", "historical_date"]),
    c("v2t_auto_02", "automated_receipts", "Invoice available", "A new invoice is available for records. The balance is zero and no payment is due.", email_type="receipt", route="informational", tags=["automated", "financial", "trigger_negative"]),
    c("v2t_deadline_01", "indirect_cutoff", "Eligibility review", "Files arriving after October 2, 2026 cannot be considered. Your file has not yet arrived.", email_type="administrative", action_kind="required", dates=[d("2026-10-02", "deadline")], route="needs_action", tags=["deadline", "implicit_obligation", "administrative"]),
    c("v2t_deadline_02", "indirect_cutoff", "Eligibility review complete", "Your file arrived August 31, 2026. The October 2 cutoff is included for reference only.", email_type="administrative", dates=[d("2026-08-31", "historical_date"), d("2026-10-02", "referenced_date")], route="informational", tags=["historical_date", "reference_date", "minimal_pair"]),
    c("v2t_event_03", "event_without_noun", "Join us on the quad", "Faculty and students gather September 8, 2026 at noon for conversation and refreshments.", email_type="event", contains_event=True, event_status="upcoming", dates=[d("2026-09-08T12:00:00-07:00", "event_time")], route="upcoming_events", tags=["event", "implicit_event"]),
    c("v2t_event_04", "event_without_noun", "Yesterday on the quad", "Faculty and students gathered August 31, 2026. Here are highlights and photographs.", email_type="event", contains_event=True, event_status="past", dates=[d("2026-08-31", "historical_date")], route="informational", tags=["event", "historical_date", "minimal_pair"]),
    c("v2t_registration_03", "program_dependent", "Field placement orientation", "Registration may be necessary depending on your placement site. The orientation is September 29, 2026; consult your coordinator.", email_type="event", action_kind="uncertain", contains_event=True, event_status="upcoming", registration_available="uncertain", registration_required="uncertain", dates=[d("2026-09-29", "event_time")], route="upcoming_events", tags=["event", "registration", "conditional", "ambiguous"]),
    c("v2t_registration_04", "program_dependent", "Placement orientation requirement", "Your assigned site requires your name on the roster before you attend orientation September 29, 2026.", email_type="event", action_kind="required", contains_event=True, event_status="upcoming", registration_available="true", registration_required="true", dates=[d("2026-09-29", "event_time")], route="needs_action", tags=["event", "registration", "implicit_obligation", "minimal_pair"]),
    c("v2t_all_day_01", "all_day_conference", "Community conference October 12", "The conference runs all day October 12, 2026. Walk-ins are welcome.", email_type="event", action_kind="optional", contains_event=True, event_status="upcoming", registration_available="false", dates=[d("2026-10-12", "event_time")], route="upcoming_events", tags=["event", "all_day"]),
    c("v2t_short_01", "short_context", "Friday?", "Can you make it?", email_type="personal", needs_reply="true", route="needs_reply", tags=["reply", "short_message", "ambiguous"]),
    c("v2t_regscale_01", "restricted_training_roster", "Required safety lab", "Participants cannot enter the September 30, 2026 lab unless they add their name to the roster by September 22.", email_type="event", action_kind="required", contains_event=True, event_status="upcoming", registration_available="true", registration_required="true", dates=[d("2026-09-22", "registration_deadline"), d("2026-09-30", "event_time")], route="needs_action", tags=["event", "registration", "implicit_obligation", "multiple_dates"]),
    c("v2t_regscale_02", "restricted_training_roster", "Required safety lab confirmation", "Your roster entry for the September 30, 2026 lab was accepted. No further registration is needed.", email_type="event", contains_event=True, event_status="upcoming", registration_available="true", registration_completed="true", dates=[d("2026-09-30", "event_time")], route="upcoming_events", tags=["event", "registration_completed", "minimal_pair"]),
    c("v2t_regscale_03", "interview_booking", "Interview scheduling window", "Select one available interview slot before September 19, 2026. A booking is necessary to be interviewed.", email_type="recruiting", action_kind="required", contains_event=True, event_status="upcoming", registration_available="true", registration_required="true", dates=[d("2026-09-19", "registration_deadline")], route="needs_action", tags=["event", "registration", "recruiting", "deadline"]),
    c("v2t_regscale_04", "interview_booking", "Interview booked", "Your interview slot on September 24, 2026 at 11 AM is confirmed. Do not book another slot.", email_type="recruiting", contains_event=True, event_status="upcoming", registration_available="true", registration_completed="true", dates=[d("2026-09-24T11:00:00-07:00", "event_time")], route="upcoming_events", tags=["event", "registration_completed", "recruiting"]),
    c("v2t_regscale_05", "capacity_limited_orientation", "Orientation access", "Reserve a place by September 16 to receive the location for orientation September 21, 2026.", email_type="event", action_kind="required", contains_event=True, event_status="upcoming", registration_available="true", registration_required="true", dates=[d("2026-09-16", "registration_deadline"), d("2026-09-21", "event_time")], route="needs_action", tags=["event", "registration", "multiple_dates"]),
    c("v2t_regscale_06", "capacity_limited_orientation", "Orientation place reserved", "A place has been reserved for you for September 21, 2026. The location will be sent separately.", email_type="event", contains_event=True, event_status="upcoming", registration_available="true", registration_completed="true", dates=[d("2026-09-21", "event_time")], route="upcoming_events", tags=["event", "registration_completed", "minimal_pair"]),
    c("v2t_regscale_07", "credentialed_conference", "Conference credential", "Attendees need a credential to enter on October 3, 2026. Request yours no later than September 25.", email_type="event", action_kind="required", contains_event=True, event_status="upcoming", registration_available="true", registration_required="true", dates=[d("2026-09-25", "registration_deadline"), d("2026-10-03", "event_time")], route="needs_action", tags=["event", "registration", "implicit_obligation", "multiple_dates"]),
    c("v2t_regscale_08", "credentialed_conference", "Conference credential issued", "Your credential for October 3, 2026 has been issued. Keep this confirmation; no reply is needed.", email_type="event", contains_event=True, event_status="upcoming", registration_available="true", registration_completed="true", dates=[d("2026-10-03", "event_time")], route="upcoming_events", tags=["event", "registration_completed", "minimal_pair"]),
    c("v2t_replyscale_01", "advisor_decision", "Approval choice", "I can approve either option A or option B. Which should I use? Please answer by September 8.", email_type="personal", action_kind="required", needs_reply="true", dates=[d("2026-09-08", "deadline")], route="needs_action", tags=["reply", "required_action", "deadline"]),
    c("v2t_replyscale_02", "advisor_decision", "Approval recorded", "Option B was recorded and approved. This is a confirmation; no response is requested.", email_type="personal", route="informational", tags=["reply", "trigger_negative", "minimal_pair"]),
    c("v2t_deadlinescale_01", "license_expiration", "Access eligibility", "Your temporary access ends September 26, 2026 unless the acknowledgment reaches the office first.", email_type="administrative", action_kind="required", dates=[d("2026-09-26", "deadline")], route="needs_action", tags=["deadline", "implicit_obligation", "administrative"]),
    c("v2t_deadlinescale_02", "license_expiration", "Access renewed", "Your access was renewed through September 26, 2027. The prior September 26, 2026 expiration is historical.", email_type="administrative", dates=[d("2027-09-26", "referenced_date"), d("2026-09-26", "historical_date")], route="informational", tags=["historical_date", "multiple_dates", "minimal_pair"]),
]


CHALLENGE_CASES = [
    # Hard negatives containing high-weight trigger words.
    c("v2c_marketing_01", "marketing_triggers", "Action required: claim your reward", "You must click today to see these discounts. Participation and purchases are optional.", email_type="promotional", action_kind="optional", dates=[d("2026-09-01", "promotion_date")], route="low_priority", tags=["promotion", "trigger_negative", "adversarial"]),
    c("v2c_marketing_02", "marketing_triggers", "Payment due? Save instead", "Our prices are due for a refresh. Register for promotional alerts if interested; nothing is owed.", email_type="promotional", action_kind="optional", route="low_priority", tags=["promotion", "registration", "trigger_negative", "adversarial"]),
    c("v2c_marketing_03", "marketing_triggers", "Mandatory fun inside", "Submit an order before midnight for free shipping. This is an advertisement, not a requirement.", email_type="promotional", action_kind="optional", dates=[d("2026-09-01", "promotion_date")], route="low_priority", tags=["promotion", "deadline", "trigger_negative", "adversarial"]),
    c("v2c_marketing_04", "marketing_triggers", "Urgent webinar deal", "The sales webinar explains optional upgrades. RSVP is encouraged but never required.", email_type="promotional", action_kind="optional", contains_event=True, event_status="upcoming", registration_available="true", registration_required="false", route="upcoming_events", tags=["promotion", "event", "registration", "trigger_negative", "adversarial"]),
    # Obligations without the conventional words must/required/due/deadline.
    c("v2c_implicit_01", "implicit_consequences", "Enrollment file", "Unless the residency form reaches us before September 14, 2026, your courses will be dropped.", email_type="administrative", action_kind="required", dates=[d("2026-09-14", "deadline")], route="needs_action", tags=["required_action", "implicit_obligation", "deadline", "adversarial"]),
    c("v2c_implicit_02", "implicit_consequences", "Access renewal", "Accounts lacking a current acknowledgment after Friday will be suspended. We do not have yours.", email_type="security", action_kind="required", dates=[d("2026-09-04", "deadline")], route="needs_action", tags=["required_action", "implicit_obligation", "relative_date", "adversarial"]),
    c("v2c_implicit_03", "implicit_consequences", "Placement preference", "We cannot assign a site until we hear which region you can travel to. Send your preference by September 11, 2026.", email_type="academic", action_kind="required", needs_reply="true", dates=[d("2026-09-11", "deadline")], route="needs_action", tags=["required_action", "reply", "implicit_obligation", "adversarial"]),
    c("v2c_implicit_04", "implicit_consequences", "Missing emergency contact", "The portal shows no emergency contact. Students without one on file cannot begin the lab rotation September 22, 2026.", email_type="academic", action_kind="required", dates=[d("2026-09-22", "deadline")], route="needs_action", tags=["required_action", "implicit_obligation", "deadline", "adversarial"]),
    # Optional/required minimal pairs.
    c("v2c_pair_action_req", "action_minimal_pair", "Document upload", "Upload the consent document before Friday to keep your appointment.", email_type="administrative", action_kind="required", dates=[d("2026-09-04", "deadline")], route="needs_action", tags=["minimal_pair", "required_action", "relative_date"]),
    c("v2c_pair_action_opt", "action_minimal_pair", "Document upload", "Upload a sample document before Friday for a chance to win a bookstore voucher.", email_type="promotional", action_kind="optional", dates=[d("2026-09-04", "promotion_date")], route="low_priority", tags=["minimal_pair", "promotion", "relative_date"]),
    c("v2c_pair_reg_req", "registration_minimal_pair", "Studio session September 19", "Your name must be on the roster before attending.", email_type="event", action_kind="required", contains_event=True, event_status="upcoming", registration_available="true", registration_required="true", dates=[d("2026-09-19", "event_time")], route="needs_action", tags=["minimal_pair", "registration", "event"]),
    c("v2c_pair_reg_opt", "registration_minimal_pair", "Studio session September 19", "The roster is open for planning purposes, but walk-ins are welcome.", email_type="event", action_kind="optional", contains_event=True, event_status="upcoming", registration_available="true", registration_required="false", dates=[d("2026-09-19", "event_time")], route="upcoming_events", tags=["minimal_pair", "registration", "event"]),
    # Conditional and completed states.
    c("v2c_conditional_01", "conditional_registration", "Travel workshop October 6", "If you want lunch, add a meal selection by September 25. You may attend without doing so.", email_type="event", action_kind="optional", contains_event=True, event_status="upcoming", registration_available="true", registration_required="false", dates=[d("2026-09-25", "registration_deadline"), d("2026-10-06", "event_time")], route="upcoming_events", tags=["conditional", "registration", "multiple_dates", "event"]),
    c("v2c_conditional_02", "conditional_registration", "Travel workshop October 6", "Because you requested lunch, add your dietary selection by September 25. Your workshop seat is already confirmed.", email_type="event", action_kind="required", contains_event=True, event_status="upcoming", registration_available="true", registration_completed="true", dates=[d("2026-09-25", "deadline"), d("2026-10-06", "event_time")], route="needs_action", tags=["conditional", "registration_completed", "multiple_dates", "event"]),
    c("v2c_complete_01", "completed_registration", "You're all set for October 9", "We received your RSVP. Your seat is confirmed and there are no remaining steps.", email_type="event", contains_event=True, event_status="upcoming", registration_available="true", registration_completed="true", dates=[d("2026-10-09", "event_time")], route="upcoming_events", tags=["registration_completed", "event"]),
    c("v2c_complete_02", "completed_registration", "Roster confirmation", "Registration completed August 30, 2026 for the September 16 seminar. Do not submit the form again.", email_type="event", contains_event=True, event_status="upcoming", registration_available="true", registration_completed="true", dates=[d("2026-08-30", "historical_date"), d("2026-09-16", "event_time")], route="upcoming_events", tags=["registration_completed", "event", "multiple_dates"]),
    # Future versus historical events.
    c("v2c_history_01", "event_temporality", "Career fair September 18", "Employers will be available from 10 AM to 2 PM this September 18, 2026.", email_type="recruiting", contains_event=True, event_status="upcoming", dates=[d("2026-09-18T10:00:00-07:00", "event_time")], route="upcoming_events", tags=["event", "minimal_pair", "recruiting"]),
    c("v2c_history_02", "event_temporality", "Career fair September 18", "Thank you for attending the fair on September 18, 2025. Photos and recordings are available.", email_type="recruiting", contains_event=True, event_status="past", dates=[d("2025-09-18", "historical_date")], route="informational", tags=["event", "minimal_pair", "historical_date"]),
    c("v2c_history_03", "event_word_negative", "Event planning guide", "This guide explains how to budget for an event. It does not announce a scheduled gathering.", email_type="newsletter", contains_event=False, route="low_priority", tags=["event", "trigger_negative", "newsletter"]),
    c("v2c_history_04", "event_word_negative", "Deadline-management workshop notes", "These notes summarize a workshop held August 12, 2025. The word deadline appears only in the title of the archived training.", email_type="event", contains_event=True, event_status="past", dates=[d("2025-08-12", "historical_date")], route="informational", tags=["event", "deadline", "trigger_negative", "historical_date"]),
    # Multiple semantic date roles.
    c("v2c_roles_01", "date_roles", "Symposium details and response date", "The announcement was published August 20, 2026. Confirm attendance by September 7. The symposium begins September 14 at 9 AM.", email_type="event", action_kind="required", needs_reply="true", contains_event=True, event_status="upcoming", dates=[d("2026-08-20", "publication_date"), d("2026-09-07", "registration_deadline"), d("2026-09-14T09:00:00-07:00", "event_time")], route="needs_action", tags=["multiple_dates", "date_semantics", "registration", "reply", "event"]),
    c("v2c_roles_02", "date_roles", "Program timeline", "Applications opened August 15, 2026. Materials arrive by September 20. Interviews take place October 2 at 1 PM.", email_type="recruiting", action_kind="required", contains_event=True, event_status="upcoming", dates=[d("2026-08-15", "publication_date"), d("2026-09-20", "deadline"), d("2026-10-02T13:00:00-07:00", "event_time")], route="needs_action", tags=["multiple_dates", "date_semantics", "deadline", "event"]),
    c("v2c_roles_03", "date_roles", "Program archive", "Applications opened September 20, 2025. Interviews occurred October 2, 2025. The archive was published August 15, 2026.", email_type="recruiting", contains_event=True, event_status="past", dates=[d("2025-09-20", "historical_date"), d("2025-10-02", "historical_date"), d("2026-08-15", "publication_date")], route="informational", tags=["multiple_dates", "date_semantics", "historical_date"]),
    c("v2c_roles_04", "date_roles", "Conference and early registration", "Discount registration ends September 8, 2026, but registration remains optional. The conference is October 14, 2026.", email_type="event", action_kind="optional", contains_event=True, event_status="upcoming", registration_available="true", registration_required="false", dates=[d("2026-09-08", "promotion_date"), d("2026-10-14", "event_time")], route="upcoming_events", tags=["multiple_dates", "date_semantics", "registration", "event"]),
    # Relative dates, local/UTC boundaries, and DST ambiguity.
    c("v2c_time_01", "relative_time_boundaries", "Tomorrow at 12:15 AM", "The support session begins tomorrow at 12:15 AM Pacific time.", email_type="event", contains_event=True, event_status="upcoming", dates=[d("2026-09-02T00:15:00-07:00", "event_time")], route="upcoming_events", tags=["relative_date", "timezone", "utc_boundary", "event"], received_at="2026-09-01T23:50:00-07:00"),
    c("v2c_time_02", "relative_time_boundaries", "Today at 11:50 PM", "The briefing begins today at 11:50 PM in Los Angeles.", email_type="event", contains_event=True, event_status="ongoing", dates=[d("2026-09-01T23:50:00-07:00", "event_time")], route="upcoming_events", tags=["relative_date", "timezone", "utc_boundary", "event"], received_at="2026-09-02T06:30:00+00:00"),
    c("v2c_time_03", "weekday_semantics", "This Friday", "Office hours are this Friday at 3:30 PM.", email_type="event", contains_event=True, event_status="upcoming", dates=[d("2026-09-04T15:30:00-07:00", "event_time")], route="upcoming_events", tags=["relative_date", "timezone", "event"]),
    c("v2c_time_04", "weekday_semantics", "Next Friday", "Office hours move to next Friday at 3:30 PM.", email_type="event", contains_event=True, event_status="upcoming", dates=[d("2026-09-11T15:30:00-07:00", "event_time")], route="upcoming_events", tags=["relative_date", "timezone", "event", "minimal_pair"]),
    c("v2c_dst_01", "dst_ambiguity", "Fallback maintenance", "Maintenance is planned for November 1, 2026 at 1:30 AM local time. The notice does not disambiguate the repeated hour.", email_type="event", contains_event=True, event_status="upcoming", dates=[d("2026-11-01", "event_time")], route="upcoming_events", tags=["dst_boundary", "timezone", "ambiguous_time", "event"]),
    c("v2c_dst_02", "dst_ambiguity", "Spring maintenance", "Maintenance is listed for March 8, 2026 at 2:15 AM local time, which does not exist after the clock change. Confirmation is pending.", email_type="event", contains_event=True, event_status="upcoming", dates=[d("2026-03-08", "event_time")], route="upcoming_events", tags=["dst_boundary", "timezone", "ambiguous_time", "event"], received_at="2026-03-01T12:00:00-08:00"),
    # Quoted, forwarded, and nested/container content.
    c("v2c_quote_01", "obsolete_quoted_deadline", "Re: compliance form", "Thanks, your form was accepted and the hold was removed.\n\nOn Aug 20, 2026, Office wrote:\n> URGENT: form due August 25, 2026 or access will end.", email_type="administrative", route="informational", tags=["quoted_reply", "obsolete_deadline", "trigger_negative"]),
    c("v2c_quote_02", "obsolete_quoted_deadline", "Re: meeting registration", "Your cancellation is complete. No further action is needed.\n\n-----Original Message-----\nRSVP required by August 22 for the August 30 workshop.", email_type="event", contains_event=True, event_status="past", registration_completed="true", route="informational", tags=["quoted_reply", "registration_completed", "obsolete_deadline", "event"]),
    c("v2c_forward_01", "forwarded_current_request", "Fwd: room access", "Could you reply with approval by September 5?\n\n---------- Forwarded message ----------\nThe facilities team needs the host list for the September 8 tour.", email_type="personal", action_kind="required", needs_reply="true", contains_event=True, event_status="upcoming", dates=[d("2026-09-05", "deadline"), d("2026-09-08", "event_time")], route="needs_action", tags=["forwarded", "reply", "multiple_dates", "event"]),
    c("v2c_forward_02", "forwarded_current_request", "Fwd: archived agenda", "For reference only; no response needed.\n\n---------- Forwarded message ----------\nMandatory briefing August 10, 2025. Reply by August 5, 2025.", email_type="administrative", contains_event=True, event_status="past", dates=[d("2025-08-10", "historical_date"), d("2025-08-05", "historical_date")], route="informational", tags=["forwarded", "historical_date", "trigger_negative", "event"]),
    c("v2c_digest_01", "nested_digest", "Held-message digest", "This container previews four messages:\n• Action required by Friday\n• RSVP for a September 12 workshop\n• Payment due September 9\n• Security alert\nOpen each original message to assess it; the digest itself has no task.", email_type="digest", route="informational", tags=["digest", "container", "multiple_sections", "trigger_negative"]),
    c("v2c_digest_02", "nested_digest", "Discussion summary", "The digest quotes participants saying 'you must register' and 'the deadline is tomorrow.' Those statements belong to embedded threads, not this summary.", email_type="digest", route="informational", tags=["digest", "container", "quoted_reply", "trigger_negative"]),
    # Long and noisy structures.
    c("v2c_long_01", "long_newsletter", "Weekly opportunities and community news", "WEEKLY EDITION\n\nTop story\nA research group published a synthetic accessibility toolkit on August 18, 2026. The article describes its design and links to public documentation.\n\nUpcoming\nA career conversation takes place September 17, 2026 at 5 PM in the north hall. Attendance is optional; no registration is required.\n\nFrom the archive\nPhotos from the May 4, 2025 community event are now available.\n\nOffers\nMembers can save on museum admission through September 30, 2026.\n\nService notice\nA portal maintenance window is planned for September 6, 2026 at 2 AM. No response is requested.\n\nYou received this synthetic newsletter because you selected community updates. View in browser | Update preferences | Unsubscribe | Privacy", email_type="newsletter", action_kind="optional", contains_event=True, event_status="upcoming", registration_available="false", dates=[d("2026-08-18", "publication_date"), d("2026-09-17T17:00:00-07:00", "event_time"), d("2025-05-04", "historical_date"), d("2026-09-30", "promotion_date"), d("2026-09-06T02:00:00-07:00", "event_time")], route="upcoming_events", tags=["newsletter", "long_body", "multiple_sections", "multiple_dates", "event"]),
    c("v2c_long_02", "long_newsletter", "Alumni notes and optional programs", "ALUMNI NOTES\n\nProfile: A graduate reflects on a project completed July 7, 2024.\n\nLearning: The deadline-management workshop archive explains how teams plan due dates; there is no live session.\n\nSurvey: You must see our new optional questionnaire. Submit feedback by September 20, 2026 to enter a drawing.\n\nBenefits: Registration is open for discount alerts, but it is never required.\n\nFooter: This promotional bulletin is sent by a synthetic organization. Manage subscription | Unsubscribe | Terms | Tracking preferences", email_type="newsletter", action_kind="optional", dates=[d("2024-07-07", "historical_date"), d("2026-09-20", "promotion_date")], route="low_priority", tags=["newsletter", "long_body", "multiple_sections", "promotion", "trigger_negative"]),
    c("v2c_html_01", "html_noise", "Program confirmation", "<html><head><style>.preheader{display:none!important}</style><script>window.required=true</script></head><body><span class='preheader'>URGENT payment due today — save now</span><table role='presentation'><tr><td><h1>Confirmation</h1><p>Your program preference was recorded successfully. No reply or additional step is requested.</p></td></tr></table><img alt='' width='1' height='1' src='https://tracking.example/open'><div>View this email in your browser</div><footer>Privacy · Terms · Unsubscribe</footer></body></html>", email_type="automated", route="informational", tags=["html_noise", "preheader", "tracking", "boilerplate", "trigger_negative"], body_format="html"),
    c("v2c_html_02", "html_noise", "Required profile correction", "<html><head><style>body{font-family:sans-serif}.hidden{display:none}</style></head><body><div class='hidden'>Optional sale ends today</div><p>Your legal-name field is blank. Records without that field cannot be processed after <strong>September 13, 2026</strong>.</p><p>Update the field in the secure portal.</p><img width='1' height='1' src='https://tracking.example/pixel'><footer>Do not reply · Privacy</footer></body></html>", email_type="administrative", action_kind="required", dates=[d("2026-09-13", "deadline")], route="needs_action", tags=["html_noise", "preheader", "tracking", "required_action", "implicit_obligation"], body_format="html"),
    c("v2c_mime_01", "mime_complexity", "Nested event invitation", "A public talk begins September 28, 2026 at 6 PM. Registration is available but optional.", email_type="event", action_kind="optional", contains_event=True, event_status="upcoming", registration_available="true", registration_required="false", dates=[d("2026-09-28T18:00:00-07:00", "event_time")], route="upcoming_events", tags=["nested_mime", "attachment_excluded", "event", "registration"], mime_structure="nested_multipart"),
    c("v2c_mime_02", "mime_complexity", "Multipart response request", "Can you confirm the delivery location by September 7, 2026? A personal reply is needed.", email_type="personal", action_kind="required", needs_reply="true", dates=[d("2026-09-07", "deadline")], route="needs_action", tags=["nested_mime", "reply", "deadline"], mime_structure="multipart_alternative"),
    c("v2c_encoding_01", "malformed_encoding", "Unreadable synthetic payload", "This text is intentionally replaced by invalid transfer encoding.", action_kind="uncertain", needs_reply="uncertain", route="manual_review", tags=["malformed_encoding", "manual_review"], encoding_mode="invalid_base64url"),
    c("v2c_encoding_02", "malformed_encoding", "Unreadable byte sequence", "This text is intentionally replaced by invalid UTF-8 bytes.", action_kind="uncertain", needs_reply="uncertain", route="manual_review", tags=["malformed_encoding", "manual_review"], encoding_mode="invalid_utf8"),
    # Explicit ambiguity and abstention targets.
    c("v2c_ambiguous_01", "ambiguous_obligation", "Please handle this", "Please take care of this soon.", action_kind="uncertain", needs_reply="uncertain", route="manual_review", tags=["ambiguous", "manual_review", "short_message"]),
    c("v2c_ambiguous_02", "ambiguous_obligation", "Documentation note", "You may need to submit documentation. The message does not say who is affected or when.", email_type="administrative", action_kind="uncertain", route="manual_review", tags=["ambiguous", "manual_review", "conditional"]),
    c("v2c_ambiguous_03", "ambiguous_registration", "Program gathering", "Registration may be necessary depending on your program. The gathering is September 23, 2026.", email_type="event", action_kind="uncertain", contains_event=True, event_status="upcoming", registration_available="uncertain", registration_required="uncertain", dates=[d("2026-09-23", "event_time")], route="upcoming_events", tags=["ambiguous", "conditional", "registration", "event"]),
    c("v2c_ambiguous_04", "ambiguous_registration", "Program requirement", "Some participants have an additional step. Contact your coordinator if this applies to you.", email_type="administrative", action_kind="uncertain", needs_reply="uncertain", route="manual_review", tags=["ambiguous", "conditional", "manual_review"]),
    c("v2c_ambiguous_05", "ambiguous_time", "Meeting sometime Friday", "We may meet Friday afternoon, but the organizer has not confirmed whether it will happen.", email_type="personal", contains_event=True, event_status="uncertain", dates=[d("2026-09-04", "unknown")], route="manual_review", tags=["ambiguous", "manual_review", "relative_date", "event"]),
    c("v2c_ambiguous_06", "ambiguous_time", "Tentative plan", "Hold next Friday if possible. A final invitation will follow.", email_type="personal", contains_event=True, event_status="uncertain", dates=[d("2026-09-11", "unknown")], route="manual_review", tags=["ambiguous", "manual_review", "relative_date", "event"]),
    # More realistic automated and short cases.
    c("v2c_auto_01", "automated_state", "Verification complete", "Identity verification completed successfully at 2:14 PM. No action is required.", email_type="automated", registration_completed="true", route="informational", tags=["automated", "registration_completed", "trigger_negative"]),
    c("v2c_auto_02", "automated_state", "Verification could not complete", "We could not verify the submitted record. Open the secure portal and correct the highlighted field before September 10, 2026.", email_type="administrative", action_kind="required", dates=[d("2026-09-10", "deadline")], route="needs_action", tags=["automated", "required_action", "deadline"]),
    c("v2c_auto_03", "automated_state", "Payment processed", "Payment was processed August 31, 2026. Balance: zero. Do not reply to this receipt.", email_type="receipt", dates=[d("2026-08-31", "historical_date")], route="informational", tags=["automated", "financial", "historical_date"]),
    c("v2c_auto_04", "automated_state", "Payment unsuccessful", "The balance remains unpaid. Service ends September 15, 2026 unless payment is received first.", email_type="administrative", action_kind="required", dates=[d("2026-09-15", "deadline")], route="needs_action", tags=["automated", "financial", "implicit_obligation", "deadline"]),
    c("v2c_short_01", "short_messages", "Need your answer", "Yes or no?", email_type="personal", needs_reply="true", route="needs_reply", tags=["short_message", "reply", "ambiguous"]),
    c("v2c_short_02", "short_messages", "FYI", "Approved.", email_type="personal", route="informational", tags=["short_message", "personal"]),
    c("v2c_short_03", "short_messages", "Tomorrow", "Still on?", email_type="personal", needs_reply="true", contains_event=True, event_status="uncertain", dates=[d("2026-09-02", "unknown")], route="needs_reply", tags=["short_message", "reply", "relative_date", "ambiguous"]),
    c("v2c_short_04", "short_messages", "Canceled", "Tomorrow is off.", email_type="personal", contains_event=True, event_status="past", dates=[d("2026-09-02", "referenced_date")], route="informational", tags=["short_message", "relative_date", "event"]),
    # Date wording designed to separate deadline from reference/publication.
    c("v2c_datepair_01", "date_semantic_pair", "Application timeline", "Applications must arrive by September 20, 2026.", email_type="administrative", action_kind="required", dates=[d("2026-09-20", "deadline")], route="needs_action", tags=["minimal_pair", "deadline"]),
    c("v2c_datepair_02", "date_semantic_pair", "Application timeline", "Applications opened September 20, 2026.", email_type="administrative", dates=[d("2026-09-20", "publication_date")], route="informational", tags=["minimal_pair", "publication_date"]),
    c("v2c_datepair_03", "date_semantic_pair", "Application timeline", "The archived application closed September 20, 2025.", email_type="administrative", dates=[d("2025-09-20", "historical_date")], route="informational", tags=["minimal_pair", "historical_date"]),
    c("v2c_datepair_04", "date_semantic_pair", "Application planning", "A workshop about managing application deadlines meets September 20, 2026.", email_type="event", contains_event=True, event_status="upcoming", dates=[d("2026-09-20", "event_time")], route="upcoming_events", tags=["minimal_pair", "deadline", "trigger_negative", "event"]),
    # Registration deadline versus event time and explicit reply distinction.
    c("v2c_regdates_01", "registration_dates", "Design forum", "Reserve a seat no later than September 10. The forum begins September 18, 2026 at 1 PM.", email_type="event", action_kind="required", contains_event=True, event_status="upcoming", registration_available="true", registration_required="true", dates=[d("2026-09-10", "registration_deadline"), d("2026-09-18T13:00:00-07:00", "event_time")], route="needs_action", tags=["registration", "multiple_dates", "event", "deadline"]),
    c("v2c_regdates_02", "registration_dates", "Design forum confirmation", "Your seat for September 18, 2026 at 1 PM is confirmed. The September 10 registration cutoff no longer requires action from you.", email_type="event", contains_event=True, event_status="upcoming", registration_available="true", registration_completed="true", dates=[d("2026-09-18T13:00:00-07:00", "event_time"), d("2026-09-10", "referenced_date")], route="upcoming_events", tags=["registration_completed", "multiple_dates", "event", "trigger_negative"]),
    c("v2c_reply_01", "reply_distinction", "Choice needed", "Which of the two delivery windows should we use? Please reply by Thursday.", email_type="personal", action_kind="required", needs_reply="true", dates=[d("2026-09-03", "deadline")], route="needs_action", tags=["reply", "relative_date", "required_action"]),
    c("v2c_reply_02", "reply_distinction", "Choice recorded", "Your delivery-window choice was recorded. This automated inbox cannot receive replies.", email_type="automated", route="informational", tags=["reply", "automated", "trigger_negative"], sender="Synthetic Service <no-reply@service.example>", headers={"Auto-Submitted": "auto-generated"}),
]


def _legacy_dev() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for split in ("dev", "test"):
        path = ROOT / split / "cases.jsonl"
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            record["family_id"] = "legacy_v1"
            records.append(EvaluationCase.model_validate(record).model_dump(mode="json"))
    return records


def _write(relative: str, records: list[dict[str, Any]]) -> None:
    target = ROOT / relative / "cases.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(
        json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for item in records
    )
    target.write_text(content + "\n", encoding="utf-8")


def main() -> None:
    splits = {
        "v2_dev": _legacy_dev(),
        "v2_test": TEST_CASES,
        "challenge": CHALLENGE_CASES,
    }
    all_records = [item for records in splits.values() for item in records]
    ids = [item["id"] for item in all_records]
    if not 180 <= len(all_records) <= 250:
        raise RuntimeError(f"expected 180-250 cases, found {len(all_records)}")
    if len(ids) != len(set(ids)):
        raise RuntimeError("v2 case IDs must be unique")
    family_splits: dict[str, set[str]] = {}
    for split, records in splits.items():
        for item in records:
            family = item.get("family_id")
            if not family:
                raise RuntimeError(f"v2 case lacks family_id: {item['id']}")
            family_splits.setdefault(family, set()).add(split)
    leaked = {family: names for family, names in family_splits.items() if len(names) > 1}
    if leaked:
        raise RuntimeError(f"families cross v2 splits: {sorted(leaked)}")
    for name, records in splits.items():
        _write(name, records)


if __name__ == "__main__":
    main()
