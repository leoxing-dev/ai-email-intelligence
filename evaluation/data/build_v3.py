"""Build the blind synthetic-email-benchmark-v3 dataset without classifiers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re

from evaluation.schemas import EvaluationCase


ROOT = Path(__file__).resolve().parent
PACIFIC_STANDARD = timezone(timedelta(hours=-8))
PACIFIC_DAYLIGHT = timezone(timedelta(hours=-7))
DATASET_VERSION = "synthetic-email-benchmark-v3-blind"
CASES_PER_FAMILY = 6


@dataclass(frozen=True)
class Spec:
    split: str
    family_id: str
    theme: str
    pattern: str
    difficulty: str
    email_type: str
    action_kind: str
    needs_reply: str
    contains_event: bool
    event_status: str
    registration_available: str
    registration_required: str
    registration_completed: str
    date_roles: tuple[str, ...]
    route: str
    tags: tuple[str, ...]
    rationale: str
    long_form: bool = False
    html: bool = False
    encoding_mode: str = "valid"


def S(
    split: str,
    family_id: str,
    theme: str,
    pattern: str,
    difficulty: str,
    email_type: str,
    action_kind: str,
    needs_reply: str,
    contains_event: bool,
    event_status: str,
    registration_available: str,
    registration_required: str,
    registration_completed: str,
    date_roles: tuple[str, ...],
    route: str,
    tags: tuple[str, ...],
    rationale: str,
    *,
    long_form: bool = False,
    html: bool = False,
    encoding_mode: str = "valid",
) -> Spec:
    return Spec(
        split,
        family_id,
        theme,
        pattern,
        difficulty,
        email_type,
        action_kind,
        needs_reply,
        contains_event,
        event_status,
        registration_available,
        registration_required,
        registration_completed,
        date_roles,
        route,
        tags,
        rationale,
        long_form,
        html,
        encoding_mode,
    )


SPECS = [
    # Blind test families: conventional but realistic operational mail.
    S("v3_test", "credential_access_consequence", "Aster Credential Desk", "implicit_required", "medium", "administrative", "required", "false", False, "uncertain", "false", "false", "false", ("deadline",), "needs_action", ("administrative", "implicit_obligation", "deadline", "required_action"), "The recipient's credential remains blocked unless the missing item is supplied before the stated cutoff."),
    S("v3_test", "benefit_eligibility_gap", "Cobalt Benefit Ledger", "implicit_required", "hard", "administrative", "required", "false", False, "uncertain", "false", "false", "false", ("deadline",), "needs_action", ("administrative", "implicit_obligation", "deadline", "eligibility"), "Loss of eligibility is an applicable consequence, making the unstated submission an obligation."),
    S("v3_test", "optional_studio_session", "Lantern Studio Circle", "optional_event", "easy", "event", "optional", "false", True, "upcoming", "true", "false", "false", ("event_time",), "upcoming_events", ("event", "optional_action", "registration"), "The future session is real and registration is offered, but attendance and registration are optional."),
    S("v3_test", "conditional_travel_preference", "Juniper Travel Sandbox", "conditional_reply", "medium", "administrative", "optional", "true", False, "uncertain", "false", "false", "false", (), "needs_reply", ("conditional", "direct_question", "reply"), "The recipient is asked a direct preference question; the underlying travel step applies only if they choose to participate."),
    S("v3_test", "profile_change_completed", "Harbor Profile Service", "completed_action", "easy", "automated", "none", "false", False, "uncertain", "false", "false", "false", ("publication_date",), "informational", ("automated", "completed_action", "confirmation"), "The requested profile change is already complete, so no current action or reply remains."),
    S("v3_test", "neighborhood_science_talk", "Quartz Neighborhood Lab", "event_announcement", "easy", "event", "none", "false", True, "upcoming", "false", "false", "false", ("event_time",), "upcoming_events", ("event", "informational"), "The message announces a concrete future talk without requesting attendance or registration."),
    S("v3_test", "recording_archive_recap", "Mica Archive Room", "past_event", "medium", "event", "none", "false", True, "past", "false", "false", "false", ("event_time", "publication_date"), "informational", ("event", "past_event", "historical_date", "multiple_dates"), "The gathering already occurred; the current message only publishes its recording."),
    S("v3_test", "symposium_signup_choice", "Pineglass Symposium", "optional_registration", "medium", "event", "optional", "false", True, "upcoming", "true", "false", "false", ("registration_deadline", "event_time"), "upcoming_events", ("event", "registration", "optional_action", "multiple_dates"), "Registration has a cutoff but is explicitly optional; the event remains upcoming."),
    S("v3_test", "facility_orientation_gate", "Orchid Facility Office", "required_registration", "hard", "administrative", "required", "false", True, "upcoming", "true", "true", "false", ("registration_deadline", "event_time"), "needs_action", ("event", "registration", "required_action", "deadline", "multiple_dates"), "Facility entry depends on completing registration before the cutoff, so registration is required."),
    S("v3_test", "workshop_registration_receipt", "Silverleaf Workshop", "registration_completed", "medium", "event", "none", "false", True, "upcoming", "true", "false", "true", ("publication_date", "event_time"), "upcoming_events", ("event", "registration_completed", "confirmation", "multiple_dates"), "The registration receipt confirms completion; stale signup language does not create a new obligation."),
    S("v3_test", "certification_booking_window", "Ember Certification Hub", "required_registration", "hard", "administrative", "required", "false", True, "upcoming", "true", "true", "false", ("registration_deadline", "event_time"), "needs_action", ("registration", "required_action", "deadline", "event", "multiple_dates"), "The mandatory certification appointment cannot be attended until the recipient books within the window."),
    S("v3_test", "parallel_program_schedule", "Willow Program Board", "multiple_events", "hard", "event", "none", "false", True, "upcoming", "false", "false", "false", ("event_time", "event_time", "event_time"), "upcoming_events", ("event", "multiple_events", "multiple_dates", "long_form"), "Several distinct future sessions are announced; none imposes an obligation.", long_form=True),
    S("v3_test", "editorial_release_calendar", "Marble Editorial Desk", "multi_role_dates", "hard", "newsletter", "none", "false", False, "uncertain", "false", "false", "false", ("publication_date", "referenced_date", "historical_date"), "informational", ("newsletter", "multiple_dates", "publication_date", "long_form"), "The dates describe publication and historical references, not deadlines or events.", long_form=True),
    S("v3_test", "district_bulletin_sections", "Auburn District Bulletin", "long_newsletter", "hard", "newsletter", "none", "false", True, "upcoming", "false", "false", "false", ("publication_date", "event_time", "event_time"), "upcoming_events", ("newsletter", "event", "multiple_events", "multiple_dates", "html_noise", "long_form"), "The bulletin directly announces two future public sessions; footer promotions create no action.", long_form=True, html=True),
    S("v3_test", "service_digest_container", "Indigo Service Digest", "digest_container", "hard", "digest", "none", "false", False, "uncertain", "false", "false", "false", ("referenced_date", "referenced_date"), "informational", ("digest", "container", "multiple_dates", "long_form"), "Child snippets are quoted summaries and are not adopted as direct obligations or events by the container.", long_form=True),
    S("v3_test", "quoted_design_question", "Bramble Design Thread", "quoted_reply", "medium", "personal", "none", "true", False, "uncertain", "false", "false", "false", (), "needs_reply", ("quoted_content", "direct_question", "reply"), "The current human-authored paragraph asks the recipient a direct question; older quoted instructions are context only."),
    S("v3_test", "forwarded_expired_checklist", "Flint Forwarding Desk", "forwarded_stale", "hard", "administrative", "none", "false", False, "uncertain", "false", "false", "false", ("historical_date",), "informational", ("forwarded_content", "historical_date", "trigger_negative"), "The forwarded checklist and its cutoff are explicitly obsolete and do not apply to the recipient."),
    S("v3_test", "background_sync_notice", "Nimbus Sync Monitor", "automated_notice", "easy", "automated", "none", "false", False, "uncertain", "false", "false", "false", ("publication_date",), "informational", ("automated", "notification"), "The system reports a completed background process and requests neither action nor reply."),
    S("v3_test", "mentor_choice_question", "Saffron Mentor Exchange", "direct_question", "medium", "personal", "none", "true", False, "uncertain", "false", "false", "false", (), "needs_reply", ("personal", "direct_question", "reply"), "A direct interpersonal question requires a response even though it is not a separate required task."),
    S("v3_test", "device_recovery_lock", "Violet Security Console", "security_required", "hard", "security", "required", "false", False, "uncertain", "false", "false", "false", ("deadline",), "urgent", ("security", "required_action", "deadline", "urgent"), "An active security lock affects the recipient and requires a recovery step before the cutoff."),
    S("v3_test", "policy_revision_question", "Maple Policy Office", "administrative_reply", "medium", "administrative", "none", "true", False, "uncertain", "false", "false", "false", ("publication_date",), "needs_reply", ("administrative", "direct_question", "reply", "publication_date"), "The policy is informational, but the closing direct question requires a human response."),
    S("v3_test", "winter_catalog_offer", "Copper Catalog Studio", "promotion", "easy", "promotional", "optional", "false", False, "uncertain", "false", "false", "false", ("promotion_date",), "low_priority", ("promotion", "optional_action", "trigger_negative"), "The urgency is advertising language; purchasing and viewing the offer remain optional."),
    S("v3_test", "portal_html_summary", "Teal Portal Robot", "html_summary", "medium", "administrative", "none", "false", False, "uncertain", "false", "false", "false", ("publication_date", "referenced_date"), "informational", ("html_noise", "multiple_dates", "administrative", "long_form"), "The HTML table summarizes status dates and contains no applicable request.", long_form=True, html=True),
    S("v3_test", "bilingual_document_window", "Lotus Synthetic Office", "mixed_language_required", "hard", "administrative", "required", "false", False, "uncertain", "false", "false", "false", ("deadline",), "needs_action", ("multilingual", "encoding", "deadline", "required_action"), "The mixed English-Chinese message clearly identifies an applicable document obligation and cutoff."),
    S("v3_test", "global_showcase_clock", "Aurora Showcase Grid", "timezone_event", "hard", "event", "none", "false", True, "upcoming", "false", "false", "false", ("event_time", "referenced_date"), "upcoming_events", ("event", "timezone", "multiple_dates"), "The same future showcase is expressed in two time zones; it is one event, not two deadlines."),
    S("v3_test", "spring_shift_clinic", "Cedar Time Clinic", "dst_event", "hard", "event", "none", "false", True, "upcoming", "false", "false", "false", ("event_time",), "upcoming_events", ("event", "timezone", "dst_boundary"), "The clinic occurs after the spring offset change and has a specific future local time."),
    S("v3_test", "relative_planning_circle", "Moonstone Planning Circle", "relative_event", "hard", "event", "none", "false", True, "upcoming", "false", "false", "false", ("event_time",), "upcoming_events", ("event", "relative_date", "timezone"), "The relative phrase resolves from received_at to a concrete future event time."),
    S("v3_test", "unclear_delegated_authority", "Fogbank Coordination Note", "ambiguous", "hard", "unknown", "uncertain", "uncertain", False, "uncertain", "uncertain", "uncertain", "uncertain", (), "manual_review", ("ambiguous", "manual_review", "applicability"), "The message does not establish whether the recipient or another team owns the request, so action and routing remain uncertain."),
    S("v3_test", "sealed_no_reply_receipt", "Slate Receipt Engine", "no_reply_confirmation", "medium", "automated", "none", "false", False, "uncertain", "false", "false", "false", ("publication_date",), "informational", ("automated", "no_reply", "confirmation"), "The address is explicitly unmonitored and the receipt confirms completion; quoted reply language is not current."),
    S("v3_test", "seminar_enrollment_confirmed", "Opal Seminar Registry", "registration_completed", "medium", "event", "none", "false", True, "upcoming", "true", "false", "true", ("publication_date", "event_time"), "upcoming_events", ("event", "registration_completed", "confirmation", "multiple_dates"), "Enrollment is confirmed and no further registration is required; the future seminar remains useful."),

    # Blind challenge families: adversarial structure and boundary behavior.
    S("v3_challenge", "imperative_advertising_banner", "Crimson Market Lab", "advertising_must", "adversarial", "promotional", "optional", "false", False, "uncertain", "false", "false", "false", ("promotion_date",), "low_priority", ("adversarial", "promotion", "trigger_negative", "html_noise"), "Imperative marketing copy does not create an obligation; the offer is optional.", html=True),
    S("v3_challenge", "historical_required_quote", "Archive Quotation Service", "quoted_required", "adversarial", "administrative", "none", "false", False, "uncertain", "false", "false", "false", ("historical_date",), "informational", ("adversarial", "quoted_content", "trigger_negative", "historical_date"), "The word required appears only in a historical quotation that the current sender disclaims."),
    S("v3_challenge", "voluntary_registration_prompt", "Glasswing Open House", "optional_registration", "hard", "event", "optional", "false", True, "upcoming", "true", "false", "false", ("registration_deadline", "event_time"), "upcoming_events", ("registration", "event", "trigger_negative", "optional_action", "multiple_dates"), "Registration is available and time-limited but participation is expressly voluntary."),
    S("v3_challenge", "anniversary_event_reference", "Topaz Memory Journal", "past_event", "adversarial", "event", "none", "false", True, "past", "false", "false", "false", ("event_time", "publication_date"), "informational", ("event", "past_event", "trigger_negative", "multiple_dates"), "Event vocabulary describes an anniversary recap, not an upcoming occurrence."),
    S("v3_challenge", "superseded_cutoff_history", "Driftwood Records Vault", "historical_deadline", "adversarial", "administrative", "none", "false", False, "uncertain", "false", "false", "false", ("historical_date", "referenced_date"), "informational", ("deadline", "historical_date", "trigger_negative", "multiple_dates"), "Both dates document prior policy versions; neither is a current cutoff."),
    S("v3_challenge", "unmonitored_reply_excerpt", "Granite No-Reply Relay", "no_reply_language", "adversarial", "automated", "none", "false", False, "uncertain", "false", "false", "false", (), "informational", ("automated", "no_reply", "quoted_content", "trigger_negative"), "Reply wording exists only in a quoted template while the current automated notice says the mailbox is unmonitored."),
    S("v3_challenge", "forward_chain_closed_task", "Riverstone Forward Chain", "forwarded_stale", "adversarial", "administrative", "none", "false", False, "uncertain", "false", "false", "false", ("historical_date",), "informational", ("forwarded_content", "deadline", "trigger_negative", "nested_quote"), "The forwarded deadline belongs to a closed task and the current message explicitly says no action is needed."),
    S("v3_challenge", "nested_authority_conflict", "Ashen Thread Collector", "nested_conflict", "adversarial", "unknown", "uncertain", "uncertain", False, "uncertain", "uncertain", "uncertain", "uncertain", ("referenced_date",), "manual_review", ("nested_quote", "ambiguous", "manual_review", "contradiction", "long_form"), "Current and nested instructions conflict without establishing which authority controls, requiring manual review.", long_form=True),
    S("v3_challenge", "silent_access_revocation", "Cerulean Access Gate", "implicit_required", "hard", "security", "required", "false", False, "uncertain", "false", "false", "false", ("deadline",), "needs_action", ("implicit_obligation", "security", "deadline", "required_action"), "Access will be revoked unless the recipient supplies the missing factor, which implies an obligation without imperative wording."),
    S("v3_challenge", "question_without_reply_word", "Lime Human Exchange", "direct_question", "hard", "personal", "none", "true", False, "uncertain", "false", "false", "false", (), "needs_reply", ("implicit_reply", "direct_question", "personal"), "A direct question addressed to the recipient needs a reply even though the word reply is absent."),
    S("v3_challenge", "attendance_requires_enrollment", "Sable Practicum Gate", "required_registration", "hard", "event", "required", "false", True, "upcoming", "true", "true", "false", ("registration_deadline", "event_time"), "needs_action", ("implicit_obligation", "registration", "deadline", "event", "multiple_dates"), "Attendance is assigned and entry is conditional on enrollment, making registration required."),
    S("v3_challenge", "schedule_grid_implied_event", "Kestrel Schedule Grid", "structured_event", "hard", "event", "none", "false", True, "upcoming", "false", "false", "false", ("event_time", "event_time"), "upcoming_events", ("implicit_event", "multiple_events", "multiple_dates", "structured_content"), "The structured schedule establishes two future sessions despite avoiding event-announcement vocabulary."),
    S("v3_challenge", "contradictory_section_bundle", "Umber Section Bundle", "section_conflict", "adversarial", "unknown", "uncertain", "uncertain", True, "uncertain", "uncertain", "uncertain", "uncertain", ("referenced_date", "event_time", "historical_date"), "manual_review", ("contradiction", "ambiguous", "manual_review", "multiple_dates", "multiple_events", "html_noise", "long_form"), "Different current-looking sections conflict about applicability, timing, and completion; safe resolution requires review.", long_form=True, html=True),
    S("v3_challenge", "damaged_transfer_payload", "Ivory Transfer Decoder", "malformed_encoding", "adversarial", "unknown", "uncertain", "uncertain", False, "uncertain", "uncertain", "uncertain", "uncertain", (), "manual_review", ("malformed_encoding", "encoding", "ambiguous", "manual_review", "multilingual"), "The payload is too damaged to determine action, reply, event, or registration semantics safely.", encoding_mode="invalid_utf8"),
    S("v3_challenge", "zero_width_compliance_line", "Azure Compliance Strip", "zero_width_required", "adversarial", "administrative", "required", "false", False, "uncertain", "false", "false", "false", ("deadline",), "needs_action", ("encoding", "zero_width", "required_action", "deadline", "multilingual"), "Zero-width characters split the typography but not the clear applicable compliance obligation."),
    S("v3_challenge", "autumn_clock_overlap", "Bronze Clock Forum", "dst_ambiguous_event", "adversarial", "event", "none", "false", True, "upcoming", "false", "false", "false", ("event_time",), "manual_review", ("event", "dst_boundary", "timezone", "ambiguous", "manual_review"), "The event is real and upcoming, but the repeated local clock time lacks an offset, so routing requires review."),
    S("v3_challenge", "midnight_zone_crossover", "Pearl Meridian Board", "timezone_event", "hard", "event", "none", "true", True, "upcoming", "false", "false", "false", ("event_time", "referenced_date"), "upcoming_events", ("event", "timezone", "utc_boundary", "direct_question", "reply", "multiple_dates"), "One future event crosses calendar dates by zone, and the sender also asks a direct attendance question."),
    S("v3_challenge", "confirmed_signup_with_stale_steps", "Rosewood Signup Archive", "completion_over_stale", "adversarial", "event", "none", "false", True, "upcoming", "true", "false", "true", ("publication_date", "registration_deadline", "event_time"), "upcoming_events", ("registration_completed", "quoted_content", "deadline", "event", "multiple_dates"), "The current confirmation proves registration is complete; stale quoted signup steps do not restore a requirement."),
    S("v3_challenge", "digest_child_obligation_trap", "Onyx Container Digest", "digest_container", "adversarial", "digest", "none", "false", False, "uncertain", "false", "false", "false", ("referenced_date", "referenced_date", "historical_date"), "informational", ("digest", "container", "quoted_content", "trigger_negative", "multiple_dates", "long_form"), "Apparent obligations and events belong to child excerpts and are not adopted by the digest itself.", long_form=True, html=True),
    S("v3_challenge", "completion_body_overrides_subject", "Heliotrope Enrollment Record", "completion_over_subject", "adversarial", "event", "none", "false", True, "upcoming", "true", "false", "true", ("publication_date", "event_time", "registration_deadline"), "upcoming_events", ("registration_completed", "contradictory_subject", "event", "multiple_dates"), "The alarming subject is stale; the authoritative body confirms enrollment and says no further step is needed."),
    # Additional isolated families keep required-registration positives large
    # enough for useful blind-split confidence intervals.
    S("v3_test", "instrument_access_enrollment", "Magnolia Instrument Annex", "required_registration", "hard", "administrative", "required", "false", True, "upcoming", "true", "true", "false", ("registration_deadline", "event_time"), "needs_action", ("administrative", "event", "registration", "required_action", "deadline", "multiple_dates"), "The recipient has an assigned instrument session, and a recorded access enrollment is a prerequisite for entry."),
    S("v3_challenge", "simulation_roster_gate", "Obsidian Simulation Roster", "required_registration", "adversarial", "event", "required", "false", True, "upcoming", "true", "true", "false", ("registration_deadline", "event_time"), "needs_action", ("adversarial", "event", "implicit_obligation", "registration", "required_action", "deadline", "multiple_dates"), "The assigned simulation is not optional, and the roster gate admits only recipients whose enrollment is recorded before the cutoff."),
]


TEST_CONTEXT = (
    "The identifier is synthetic and is included only to distinguish this scenario.",
    "A status panel and a short explanatory paragraph appear together.",
    "The sender separates the current note from an older reference block.",
    "A mobile-rendered copy repeats the subject in a compact banner.",
    "The footer contains generic navigation and an invented support code.",
    "The message was generated for a fictional participant in a closed simulation.",
)

CHALLENGE_CONTEXT = (
    "A deliberately adversarial wrapper separates authoritative text from visual bait.",
    "The transfer contains nested provenance markers and a fictional checksum fragment.",
    "Typography and semantic scope disagree, so only the current authoritative section controls.",
    "A boundary-condition rendering mixes compact labels with a longer synthetic explanation.",
    "Several tempting trigger words occur outside the portion that governs the recipient.",
    "This blind challenge record uses an invented entity, channel, and correlation token.",
)


def _date_values(spec: Spec, received: datetime, variant: int) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for index, role in enumerate(spec.date_roles):
        if role == "event_time":
            day = received.date() + timedelta(days=9 + variant + index * 4)
            value = datetime.combine(day, time(18 - (index % 3), 30), tzinfo=received.tzinfo)
            if spec.event_status == "past":
                value = datetime.combine(
                    received.date() - timedelta(days=24 + variant + index),
                    time(15, 0),
                    tzinfo=received.tzinfo,
                )
            output.append({"value": value.isoformat(), "semantic_type": role})
        elif role in {"historical_date"}:
            value = received.date() - timedelta(days=40 + variant + index)
            output.append({"value": value.isoformat(), "semantic_type": role})
        elif role == "publication_date":
            value = received.date() - timedelta(days=index)
            output.append({"value": value.isoformat(), "semantic_type": role})
        elif role == "referenced_date":
            value = received.date() + timedelta(days=18 + variant + index * 3)
            output.append({"value": value.isoformat(), "semantic_type": role})
        elif role == "promotion_date":
            value = received.date() + timedelta(days=3 + variant)
            output.append({"value": value.isoformat(), "semantic_type": role})
        else:
            value = received.date() + timedelta(days=6 + variant + index * 3)
            output.append({"value": value.isoformat(), "semantic_type": role})
    return output


def _date_lines(spec: Spec, dates: list[dict[str, str]], variant: int) -> list[str]:
    lines: list[str] = []
    relative_words = ("the day after tomorrow", "next Tuesday", "in three days", "this coming Friday", "tomorrow evening", "early next week")
    for index, item in enumerate(dates):
        role = item["semantic_type"]
        value = item["value"]
        if spec.pattern == "relative_event" and role == "event_time":
            lines.append(f"Schedule: {relative_words[variant]} at 6:30 PM local time.")
        elif spec.split == "v3_challenge" and role == "deadline":
            lines.append(f"Operational consequence begins after {value}; the date governs the current recipient.")
        elif spec.split == "v3_challenge" and role == "registration_deadline":
            qualifier = "assigned entry" if spec.registration_required == "true" else "voluntary placement"
            lines.append(f"The enrollment window for {qualifier} closes at {value}.")
        elif spec.split == "v3_challenge" and role == "event_time":
            tense = "was recorded" if spec.event_status == "past" else "occupies the schedule grid"
            lines.append(f"A session {tense} at {value}.")
        elif spec.split == "v3_challenge" and role == "historical_date":
            lines.append(f"Superseded ledger date {value} is preserved solely as provenance.")
        elif spec.split == "v3_challenge" and role == "publication_date":
            lines.append(f"The authoritative status record was emitted at {value}.")
        elif spec.split == "v3_challenge" and role == "promotion_date":
            lines.append(f"Decorative campaign counters stop displaying after {value}.")
        elif spec.split == "v3_challenge" and role == "referenced_date":
            lines.append(f"A non-governing embedded reference points to {value}.")
        elif role == "deadline":
            lines.append(f"The applicable processing cutoff is {value}.")
        elif role == "registration_deadline":
            if spec.registration_required == "true":
                lines.append(f"Enrollment must be recorded by {value} for the assigned session.")
            else:
                lines.append(f"Optional signups remain open until {value}.")
        elif role == "event_time":
            verb = "occurred" if spec.event_status == "past" else "is scheduled"
            lines.append(f"The session {verb} at {value}.")
        elif role == "historical_date":
            lines.append(f"Archive reference: the former cycle closed on {value}; it is no longer active.")
        elif role == "publication_date":
            lines.append(f"Record generated on {value}.")
        elif role == "promotion_date":
            lines.append(f"The fictional offer display ends on {value}.")
        else:
            lines.append(f"Background reference date: {value}.")
    return lines


def _semantic_lines(spec: Spec, variant: int) -> list[str]:
    challenge = spec.split == "v3_challenge"
    if spec.pattern in {"implicit_required"} and challenge:
        action = "Continuation silently depends on restoring the absent factor; without it, access disappears when the boundary passes."
    elif spec.pattern in {"implicit_required"}:
        action = "The account remains unavailable after the cutoff unless the outstanding item is supplied."
    elif spec.pattern == "security_required":
        action = "Recovery verification is the only way to prevent the active lock from becoming permanent."
    elif spec.pattern == "required_registration" and challenge:
        action = "A roster assignment exists, yet the gate admits only names whose enrollment state has been established."
    elif spec.pattern == "required_registration":
        action = "The assigned activity cannot be entered without a completed enrollment record."
    elif spec.pattern == "zero_width_required":
        action = "合成通知: rec​ord the compliance att​estation before access is suspended."
    elif spec.pattern == "advertising_must":
        action = "<strong>You must see this deal!</strong> The purchase, preview, and coupon are entirely optional."
    elif spec.pattern == "quoted_required":
        action = "Archived quotation: ‘submission was required.’ Current note: that instruction belonged to a retired cycle and does not apply now."
    elif spec.pattern in {"forwarded_stale", "historical_deadline"}:
        action = "The material below is retained for history. Its old instruction and cutoff are closed; no current step is requested."
    elif spec.action_kind == "required" and challenge:
        action = "The controlling section makes continued access or assigned participation depend on a recipient-owned step."
    elif spec.action_kind == "required":
        action = "This notice applies to the recipient, and the listed step must be completed to keep the stated service available."
    elif spec.action_kind == "optional" and challenge:
        action = "The visually forceful invitation carries no consequence when ignored; engagement remains voluntary."
    elif spec.action_kind == "optional":
        action = "Participation is a choice. Ignoring this invitation has no consequence for the recipient."
    elif spec.action_kind == "recommended":
        action = "The sender recommends the step but does not make it mandatory."
    elif spec.action_kind == "uncertain" and challenge:
        action = "Competing provenance layers point to different owners, and none is marked as the controlling instruction."
    elif spec.action_kind == "uncertain":
        action = "One section assigns the step to ‘your group,’ while another assigns it elsewhere; the intended owner is not established."
    elif challenge:
        action = "Nothing in the authoritative wrapper assigns fresh work to this recipient."
    else:
        action = "The current message does not assign a new task to the recipient."

    if spec.pattern == "no_reply_language":
        reply = "Quoted template: ‘please reply with approval.’ Current transport notice: this mailbox is unmonitored and the quotation is inactive."
    elif spec.needs_reply == "true" and challenge:
        reply = "Would the recipient choose the amber slot or the violet slot?"
    elif spec.needs_reply == "true":
        reply = "Which of the two synthetic options should be recorded for you?"
    elif spec.needs_reply == "uncertain" and challenge:
        reply = "An orphaned phrase requests feedback but supplies neither an addressee nor a live response channel."
    elif spec.needs_reply == "uncertain":
        reply = "The note says ‘let us know’ without identifying a recipient, channel, or applicable decision."
    elif challenge:
        reply = "The governing layer contains no unanswered human question."
    else:
        reply = "No current question or response request is directed to the recipient."

    if spec.registration_completed == "true" and challenge:
        registration = "Final ledger state is CONFIRMED; any enrollment verbs in cached fragments precede that terminal state."
    elif spec.registration_completed == "true":
        registration = "Authoritative status: enrollment confirmed. Earlier signup steps are retained only as a receipt trail; no new registration is needed."
    elif spec.registration_required == "true" and challenge:
        registration = "A roster record is a prerequisite for the assigned attendance slot."
    elif spec.registration_required == "true":
        registration = "Enrollment is a condition of entry for this assigned activity."
    elif spec.registration_available == "true" and challenge:
        registration = "A voluntary enrollment control is exposed, but declining it changes no obligation."
    elif spec.registration_available == "true":
        registration = "A signup link is available for convenience, but registration is not required."
    elif spec.registration_available == "uncertain" and challenge:
        registration = "Corrupted provenance prevents a safe conclusion about the existence or force of enrollment."
    elif spec.registration_available == "uncertain":
        registration = "The damaged or conflicting sections do not establish whether registration exists."
    elif challenge:
        registration = "No live enrollment mechanism governs the authoritative content."
    else:
        registration = "No registration process is offered or required."

    if spec.pattern == "digest_container":
        registration = "Digest boundary: all action, registration, and schedule language below belongs to quoted child cards and is not adopted by this container."
    context = CHALLENGE_CONTEXT[variant] if challenge else TEST_CONTEXT[variant]
    return [action, reply, registration, context]


def _body(spec: Spec, dates: list[dict[str, str]], variant: int, code: str) -> str:
    lead = (
        f"Blind challenge envelope {code} from {spec.theme}."
        if spec.split == "v3_challenge"
        else f"{spec.theme} — synthetic scenario {code}."
    )
    # Each scenario family carries distinct, semantically inert routing codes.
    # This mirrors realistic internal correlation noise and makes it possible to
    # detect accidental cross-family template reuse without changing labels.
    family_codes = " ".join(
        "ref" + hashlib.sha256(f"{spec.family_id}:{index}".encode()).hexdigest()[:10]
        for index in range(10)
    )
    lines = [
        lead,
        f"Fictional workflow references: {family_codes}.",
        *_semantic_lines(spec, variant),
        *_date_lines(spec, dates, variant),
    ]
    if spec.pattern == "nested_conflict":
        lines.extend([
            "Current header: ownership still under review.",
            "> Prior sender: complete the item immediately.",
            ">> Earlier desk: do not complete it; another group owns it.",
        ])
    elif spec.pattern == "section_conflict":
        lines.extend([
            "SECTION A — CURRENT: status appears pending but names no owner.",
            "SECTION B — CALENDAR: one time is labeled tentative and another cancelled.",
            "SECTION C — FOOTER: says completed, while the summary says unresolved.",
        ])
    elif spec.pattern == "structured_event":
        lines.append("GRID ROWS: Room C | 18:30 | Module One; Room F | 17:30 | Module Two.")
    elif spec.pattern == "malformed_encoding":
        lines.extend(["Payload fragment: â€™ï¿½ 合成 ?= c29tZV9kYW1hZ2Vk", "Transfer ended before the decisive segment."])
    elif spec.pattern == "completion_over_subject":
        lines.insert(1, "Subject banner was cached before processing; the body status below is authoritative.")
    elif spec.pattern == "completion_over_stale":
        lines.append("> Old instructions: choose Register and submit the form. [Archived after confirmation]")
    elif spec.pattern == "quoted_reply":
        lines.append("> Earlier context: a different participant was asked to upload a draft last month.")

    if spec.long_form:
        if spec.split == "v3_challenge":
            lines.extend([
                f"LAYER ALPHA — {spec.theme}: correlation lane {variant + 1} distinguishes governing text from nested artifacts.",
                "LAYER BETA — PROVENANCE: banners, inherited buttons, and quoted imperatives are visually prominent but may be semantically inactive.",
                "LAYER GAMMA — TEMPORAL MAP: several eras and zones appear together; labels beside each timestamp determine its role.",
                "TRAILER — Entirely invented blind-benchmark material | checksum | transport | archive controls.",
            ])
        else:
            lines.extend([
                f"SECTION ONE — {spec.theme}: This section provides background for synthetic cohort {variant + 1} and separates current scope from quoted material.",
                "SECTION TWO — NOTES: Decorative calls to action, navigation labels, and unrelated footer dates carry no semantic authority.",
                "SECTION THREE — CONTEXT: Past, current, and future references are intentionally mixed; each date keeps the role stated beside it.",
                "FOOTER — Fictional benchmark content only. Preferences | archive | accessibility | promotional placeholder.",
            ])

    body = "\n\n".join(lines)
    if spec.html:
        chunks = "".join(f"<section><p>{line}</p></section>" for line in lines)
        body = f"<html><body><header>{spec.theme} &amp; Synthetic Notices</header>{chunks}<footer>Manage&nbsp;fictional&nbsp;preferences</footer></body></html>"
    return body


def _subject(spec: Spec, variant: int) -> str:
    prefixes = ("Status", "Update", "Record", "Brief", "Notice", "Summary")
    if spec.pattern == "advertising_must":
        return f"MUST ACT NOW — fictional offer {variant + 1}"
    if spec.pattern == "completion_over_subject":
        return f"ACTION REQUIRED: enrollment not found [{variant + 1}]"
    if spec.pattern == "malformed_encoding":
        return f"TrÃ¤nsfer fragment {variant + 1}"
    return f"{prefixes[variant]}: {spec.theme} scenario {variant + 1}"


def build_case(spec: Spec, family_index: int, variant: int) -> tuple[dict, dict]:
    split_code = "t" if spec.split == "v3_test" else "c"
    case_id = f"v3{split_code}_{family_index:02d}_{variant + 1:02d}"
    month = 1 + ((family_index + variant) % 10)
    day = 2 + ((family_index * 3 + variant * 2) % 20)
    # Sufficient for fixture construction: dates in March-October use daylight
    # offset, while winter dates use standard offset. DST-boundary scenarios
    # state ambiguity explicitly rather than pretending a missing fold is known.
    pacific = PACIFIC_DAYLIGHT if 3 <= month <= 10 else PACIFIC_STANDARD
    received = datetime(2027, month, day, 9 + variant, 15, tzinfo=pacific)
    dates = _date_values(spec, received, variant)
    code = hashlib.sha256(case_id.encode()).hexdigest()[:8].upper()
    tags = sorted(set(spec.tags) | {spec.difficulty, "v3_blind"})
    body_format = "html" if spec.html else "plain"
    case = {
        "id": case_id,
        "family_id": spec.family_id,
        "input": {
            "subject": _subject(spec, variant),
            "body": _body(spec, dates, variant, code),
            "received_at": received.isoformat(),
            "sender": f"Synthetic {family_index:02d} Desk <notice-{family_index:02d}@v3.example>",
            "body_format": body_format,
            "mime_structure": "nested_multipart" if spec.long_form else ("multipart_alternative" if spec.html else "simple"),
            "encoding_mode": spec.encoding_mode,
            "labels": ["INBOX", "UNREAD"],
            "headers": {"X-Synthetic-Benchmark": DATASET_VERSION},
        },
        "ground_truth": {
            "email_type": spec.email_type,
            "action_kind": spec.action_kind,
            "needs_reply": spec.needs_reply,
            "contains_event": spec.contains_event,
            "event_status": spec.event_status,
            "registration_available": spec.registration_available,
            "registration_required": spec.registration_required,
            "registration_completed": spec.registration_completed,
            "dates": dates,
            "expected_route": spec.route,
        },
        "tags": tags,
    }
    EvaluationCase.model_validate(case)
    metadata = {
        "id": case_id,
        "split": spec.split,
        "scenario_family": spec.family_id,
        "difficulty": spec.difficulty,
        "ground_truth_rationale": spec.rationale,
    }
    return case, metadata


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _tokens(case: dict) -> set[str]:
    text = case["input"]["subject"] + " " + case["input"]["body"]
    return set(re.findall(r"[a-z0-9\u4e00-\u9fff]+", text.casefold()))


def _similarity(first: dict, second: dict) -> float:
    left, right = _tokens(first), _tokens(second)
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def build() -> None:
    if len(SPECS) != 52:
        raise RuntimeError(f"expected 52 families, found {len(SPECS)}")
    split_cases: dict[str, list[dict]] = {"v3_test": [], "v3_challenge": []}
    metadata: list[dict] = []
    family_map: dict[str, dict] = {}
    for family_index, spec in enumerate(SPECS, start=1):
        if spec.family_id in family_map:
            raise RuntimeError(f"duplicate family: {spec.family_id}")
        family_map[spec.family_id] = {
            "split": spec.split,
            "difficulty": spec.difficulty,
            "pattern": spec.pattern,
            "case_ids": [],
        }
        for variant in range(CASES_PER_FAMILY):
            case, item_metadata = build_case(spec, family_index, variant)
            split_cases[spec.split].append(case)
            metadata.append(item_metadata)
            family_map[spec.family_id]["case_ids"].append(case["id"])

    ids = [case["id"] for cases in split_cases.values() for case in cases]
    if len(ids) != len(set(ids)):
        raise RuntimeError("duplicate case IDs")
    if set(c["family_id"] for c in split_cases["v3_test"]) & set(
        c["family_id"] for c in split_cases["v3_challenge"]
    ):
        raise RuntimeError("scenario family crosses V3 splits")

    for split, cases in split_cases.items():
        path = ROOT / split / "cases.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(_canonical_json(case) for case in cases) + "\n", encoding="utf-8")
    (ROOT / "v3_case_metadata.jsonl").write_text(
        "\n".join(_canonical_json(item) for item in metadata) + "\n", encoding="utf-8"
    )
    (ROOT / "v3_family_mapping.json").write_text(
        json.dumps(family_map, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "dataset_version": DATASET_VERSION,
        "default_timezone": "America/Los_Angeles",
        "split_order": ["v3_test", "v3_challenge"],
        "split_files": {
            "v3_test": "v3_test/cases.jsonl",
            "v3_challenge": "v3_challenge/cases.jsonl",
        },
        "assignment_policy": "All V3 scenario families are synthetic and isolated to exactly one blind split. V3 has no tuning split. Labels come only from authored scenario specifications; classifier predictions are prohibited during construction.",
    }
    (ROOT / "manifest_v3.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    # Machine-readable audit input. It records construction facts, never model output.
    all_cases = split_cases["v3_test"] + split_cases["v3_challenge"]
    exact = len(all_cases) - len({hashlib.sha256(_canonical_json(c["input"]).encode()).hexdigest() for c in all_cases})
    near_cross_split = []
    for first in split_cases["v3_test"]:
        for second in split_cases["v3_challenge"]:
            score = _similarity(first, second)
            if score >= 0.55:
                near_cross_split.append({"first": first["id"], "second": second["id"], "score": round(score, 4)})
    near_cross_split.sort(key=lambda x: -x["score"])
    audit_seed = {
        "case_count": len(all_cases),
        "split_counts": {name: len(cases) for name, cases in split_cases.items()},
        "family_count": len(family_map),
        "exact_duplicate_count": exact,
        "cross_split_near_duplicate_count_at_0_55": len(near_cross_split),
        "cross_split_near_duplicates_top_25": near_cross_split[:25],
    }
    (ROOT / "v3_construction_audit.json").write_text(
        json.dumps(audit_seed, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    build()
