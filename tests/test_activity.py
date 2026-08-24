"""Reading a live call, and reading the transcript afterwards.

Every payload in this file is shaped after the one real call that was observed
(FINDINGS.md sections 1-3). Where the real shape is unknown — the JSON form of
an ``activity`` entry was only ever seen rendered — the tests pin down that
several plausible shapes are accepted, not that one particular guess is right.
"""

from __future__ import annotations

from ringedingeding.activity import (
    Speaker,
    dedupe,
    extract_activity,
    extract_transcript,
    parse_activity,
    parse_transcript,
)

# A synthetic reconstruction preserving the measured activity shape.
SYNTHETIC_ACTIVITY = [
    "00:00:00.000 | Call is ringing.",
    "00:00:04.000 | Call connected.",
    "00:00:05.000 | Bot is speaking: Dies ist ein synthetischer Testdialog.",
    "00:00:06.000 | Callee said: beispielantwort",
    "00:00:07.000 | Callee said: Beispielantwort.",
    "00:00:20.000 | Callee said: synthetische Kategorie zwei",
    "00:00:25.000 | Call ended; syncing final Calling result.",
]


# --------------------------------------------------------------------------
# parsing
# --------------------------------------------------------------------------


def test_the_synthetic_log_parses_into_speakers_and_text():
    lines = parse_activity(SYNTHETIC_ACTIVITY)
    assert [line.speaker for line in lines] == [
        Speaker.SYSTEM,
        Speaker.SYSTEM,
        Speaker.BOT,
        Speaker.CALLEE,
        Speaker.CALLEE,
        Speaker.CALLEE,
        Speaker.SYSTEM,
    ]
    assert lines[2].text.startswith("Dies ist ein synthetischer Testdialog")
    assert lines[0].timestamp == "00:00:00.000"


def test_the_prefix_is_stripped_but_the_original_line_is_kept():
    line = parse_activity(["00:00:06.000 | Callee said: beispielantwort"])[0]
    assert line.text == "beispielantwort"
    assert "Callee said" in line.raw


def test_dictionary_entries_work_too():
    """The JSON shape is unverified, so the parser must not insist on one."""
    lines = parse_activity(
        [
            {"timestamp": "00:00:00.000", "message": "Call is ringing."},
            {"time": "00:00:05.000", "text": "Bot is speaking: Hello."},
            {"at": "00:00:06.000", "speaker": "callee", "text": "example"},
        ]
    )
    assert [line.speaker for line in lines] == [Speaker.SYSTEM, Speaker.BOT, Speaker.CALLEE]
    assert lines[1].text == "Hello."
    assert lines[2].timestamp == "00:00:06.000"


def test_an_explicit_role_beats_the_sentence_prefix():
    line = parse_activity([{"role": "bot", "text": "Callee said: something odd"}])[0]
    assert line.speaker is Speaker.BOT


def test_nothing_is_dropped_when_the_shape_is_unrecognised():
    lines = parse_activity([12345])
    assert len(lines) == 1
    assert "12345" in lines[0].raw


def test_empty_input_is_not_an_error():
    assert parse_activity(None) == []
    assert parse_activity([]) == []
    assert parse_activity("") == []


# --------------------------------------------------------------------------
# the correction problem
# --------------------------------------------------------------------------


def test_a_streamed_correction_replaces_its_rough_version():
    """A rough synthetic answer followed by punctuation is one utterance."""
    lines = dedupe(parse_activity(SYNTHETIC_ACTIVITY))
    spoken = [line.text for line in lines if line.speaker is Speaker.CALLEE]
    assert spoken == ["Beispielantwort.", "synthetische Kategorie zwei"]


def test_a_correction_that_only_grows_the_sentence_is_folded_too():
    lines = dedupe(
        parse_activity(
            [
                "00:00:19.100 | Callee said: synthetische Kategorie",
                "00:00:20.000 | Callee said: synthetische Kategorie zwei",
            ]
        )
    )
    assert [line.text for line in lines] == ["synthetische Kategorie zwei"]


def test_a_correction_that_inserts_punctuation_is_folded_too():
    """Corrections usually add punctuation in the middle, not only at the end."""
    lines = dedupe(
        parse_activity(
            [
                "17:37:51.100 | Callee said: yes go",
                "17:37:51.900 | Callee said: Yes, go ahead.",
            ]
        )
    )
    assert [line.text for line in lines] == ["Yes, go ahead."]


def test_a_longer_word_is_not_treated_as_a_continuation():
    """'yes go' must not look like the start of 'yes gorilla'."""
    lines = dedupe(
        parse_activity(
            [
                "17:37:51.100 | Callee said: yes go",
                "17:37:51.900 | Callee said: yes gorilla",
            ]
        )
    )
    assert len(lines) == 2


def test_the_same_word_much_later_is_not_a_correction():
    """Somebody saying 'ja' twice in a conversation said it twice."""
    lines = dedupe(
        parse_activity(
            [
                "17:37:10.000 | Callee said: Ja.",
                "17:38:40.000 | Callee said: Ja.",
            ]
        )
    )
    assert len(lines) == 2


def test_a_different_sentence_is_never_folded_away():
    lines = dedupe(
        parse_activity(
            [
                "17:37:51.100 | Callee said: Ja gerne.",
                "17:37:51.900 | Callee said: Nein doch nicht.",
            ]
        )
    )
    assert [line.text for line in lines] == ["Ja gerne.", "Nein doch nicht."]


def test_lifecycle_lines_are_never_folded():
    """Two 'Call is ringing' entries are two events, not a re-transcription."""
    lines = dedupe(
        parse_activity(
            [
                "17:37:45.100 | Call is ringing.",
                "17:37:45.900 | Call is ringing.",
            ]
        )
    )
    assert len(lines) == 2


def test_deduping_survives_missing_timestamps():
    lines = dedupe(parse_activity(["Callee said: hallo", "Callee said: Hallo."]))
    assert [line.text for line in lines] == ["Hallo."]


def test_the_display_line_masks_phone_numbers():
    line = parse_activity(["00:00:06.000 | Callee said: Ruf mich auf +44 7700 900000 an"])[0]
    assert "3920000" not in line.display()
    assert "Ruf mich" in line.display()


# --------------------------------------------------------------------------
# digging the fields out of a response
# --------------------------------------------------------------------------


def test_the_transcript_is_read_from_result_not_from_the_top_level():
    """Measured: the top-level field is null even after the call finished."""
    payload = {
        "status": "COMPLETED",
        "transcript": None,
        "result": {"transcript": "[00:01] BOT: Hello.\n[00:03] USER: Hi."},
    }
    assert extract_transcript(payload).startswith("[00:01] BOT: Hello.")


def test_the_mcp_style_wrapper_is_understood_as_well():
    payload = {
        "structuredContent": {
            "transcript": None,
            "result": {"transcript": "[00:01] BOT: Hello."},
        }
    }
    assert extract_transcript(payload) == "[00:01] BOT: Hello."


def test_a_top_level_transcript_is_still_used_if_it_ever_arrives():
    assert extract_transcript({"transcript": "[00:01] BOT: Hi."}) == "[00:01] BOT: Hi."


def test_no_transcript_yields_an_empty_string_not_none():
    assert extract_transcript({"status": "PREPARING", "transcript": None}) == ""
    assert extract_transcript({}) == ""


def test_activity_is_found_wherever_the_response_keeps_it():
    for payload in (
        {"activity": SYNTHETIC_ACTIVITY},
        {"result": {"activity": SYNTHETIC_ACTIVITY}},
        {"structuredContent": {"activity": SYNTHETIC_ACTIVITY}},
        {"structuredContent": {"result": {"activity": SYNTHETIC_ACTIVITY}}},
    ):
        assert len(extract_activity(payload)) == len(SYNTHETIC_ACTIVITY)


def test_a_response_without_activity_is_empty_not_an_error():
    assert extract_activity({"status": "PREPARING"}) == []


# --------------------------------------------------------------------------
# transcript_turns inside attempts — measured 2026-08-11 (FINDINGS.md section 9)
#
# A recipient that answers, or that reaches a mailbox, carries no top-level
# ``result.transcript`` string at all. What is there instead is
# ``attempts[].transcript_turns``, a list of ``{offset_seconds, speaker,
# text}`` dictionaries — one attempt per dial try, though only ever one entry
# was observed even when the service redials internally.
# --------------------------------------------------------------------------


def test_transcript_turns_inside_attempts_are_read():
    recipient = {
        "status": "completed",
        "attempts": [
            {
                "status": "completed",
                "transcript_turns": [
                    {"offset_seconds": 0, "speaker": "bot", "text": "Hello, this is a test."},
                    {"offset_seconds": 4, "speaker": "user", "text": "Hallo."},
                ],
            }
        ],
    }
    assert extract_transcript(recipient) == (
        "[00:00] BOT: Hello, this is a test.\n[00:04] USER: Hallo."
    )


def test_empty_transcript_turns_yield_no_transcript():
    """The declined case: the attempt is terminal but nobody ever spoke."""
    recipient = {
        "status": "failed",
        "attempts": [{"status": "failed", "transcript_turns": []}],
    }
    assert extract_transcript(recipient) == ""


def test_a_string_transcript_still_wins_over_transcript_turns():
    """The measured, documented location (section 3) is checked first."""
    payload = {
        "result": {"transcript": "[00:01] BOT: Hello."},
        "attempts": [
            {"transcript_turns": [{"offset_seconds": 9, "speaker": "user", "text": "ignored"}]}
        ],
    }
    assert extract_transcript(payload) == "[00:01] BOT: Hello."


def test_transcript_turns_speaker_labels_are_normalised():
    """``callee``/``customer``/``human`` all mean the same thing as ``user``."""
    for label in ("user", "callee", "customer", "human"):
        recipient = {
            "attempts": [
                {"transcript_turns": [{"offset_seconds": 1, "speaker": label, "text": "hi"}]}
            ]
        }
        assert extract_transcript(recipient) == "[00:01] USER: hi"


def test_a_turn_without_text_is_skipped_not_blank():
    recipient = {
        "attempts": [
            {
                "transcript_turns": [
                    {"offset_seconds": 0, "speaker": "bot", "text": ""},
                    {"offset_seconds": 2, "speaker": "user", "text": "hallo"},
                ]
            }
        ]
    }
    assert extract_transcript(recipient) == "[00:02] USER: hallo"


def test_only_the_last_attempt_with_turns_is_used():
    """Not observed with more than one entry, but the shape is a list —

    a retried call should not hand back the transcript of the failed first
    try once a later attempt actually connected."""
    recipient = {
        "attempts": [
            {"transcript_turns": [{"offset_seconds": 0, "speaker": "bot", "text": "first try"}]},
            {"transcript_turns": [{"offset_seconds": 0, "speaker": "bot", "text": "second try"}]},
        ]
    }
    assert extract_transcript(recipient) == "[00:00] BOT: second try"


def test_a_response_without_attempts_at_all_still_yields_no_transcript():
    assert extract_transcript({"status": "no_answer"}) == ""


# --------------------------------------------------------------------------
# the transcript format
# --------------------------------------------------------------------------


def test_the_transcript_format_is_split_into_lines():
    lines = parse_transcript(
        "[00:00] BOT: Guten Tag.\n[00:06] USER: Ja, passt.\n[00:22] BOT: Danke."
    )
    assert [line.speaker for line in lines] == ["BOT", "USER", "BOT"]
    assert lines[1].offset == "00:06"
    assert lines[1].text == "Ja, passt."


def test_a_wrapped_utterance_stays_with_its_speaker():
    lines = parse_transcript("[00:06] USER: Ja, passt gerade,\nspaeter aber nicht mehr.")
    assert len(lines) == 1
    assert lines[0].text.endswith("spaeter aber nicht mehr.")


def test_an_unparseable_transcript_is_kept_rather_than_lost():
    lines = parse_transcript("just some text without any markers")
    assert len(lines) == 1
    assert lines[0].text == "just some text without any markers"
