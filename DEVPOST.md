# DevPost submission — draft

> **Draft. Nothing here has been submitted.** Submitting, publishing the
> repository and uploading the video are the user's steps, not the operator's.
>
> **No Markdown tables anywhere below.** The DevPost editor does not render
> them; everything comparative is written as a list on purpose.
>
> Fields marked `<<< … >>>` cannot be filled in yet and say why.

---

## Project name

Ringedingeding

## Elevator pitch (one line, ~200 characters)

Ask several people the same question by telephone and merge the replies into one
result — including, by name, the people it could not reach.

---

## About the project

### Inspiration

Anyone who has tried to arrange one date for six people knows the shape of the
problem: three reply to the group chat straight away, two never do, and one
calls back and tells you out loud. A poll link does not fix it, because the
people who ignore links are exactly the people whose answer is missing.

So you call them. And then you do the part that actually goes wrong: you work
out the overlap in your head, over the people who answered — and quietly treat
the two who never answered as fine with anything.

That is the mistake this project exists to make impossible. An intersection over
four of six people is a different fact from an intersection over six of six, and
it has to look different.

### What it does

- Takes one brief — the occasion, some candidate dates, a guest list — and turns
  it into one call per person through the CALL-E batch API.
- Shows exactly what would happen before anything is dialled: who gets called,
  the complete order text as it will leave the machine, how many calls that is,
  and what it costs.
- Merges the replies into a single board that keeps five states apart: *can*,
  *cannot*, *said nothing about that one*, *not reached* (which is itself
  `NO_ANSWER` or `BUSY` or `VOICEMAIL` or `DECLINED`, never one lump), and
  *has no phone number at all*.
- Never reports an aggregate over "everyone". Every result carries its
  denominator and names who is missing.
- Catches up later without a special mode: add a number that was missing, run
  the same round again, and exactly that one call is placed.
- Runs the whole flow with no account, no network and no telephone, against
  bundled scripted answers.

### The one thing to try first

One command, about a second, no account and no API key:

- `python -m ringedingeding proof`

It builds a seven-person round in a temporary database, replays scripted
answers, and then checks its own result against the four ways a merge can
quietly lie — a disagreement counted as a majority, silence read as a "no",
three kinds of absence folded into one failure, and the invitee whose number is
missing dropped from the report. Exit code 0 means all eight checks passed.

Its last step is the argument in miniature. One invitee has no phone number, so
she is never called, and the round reports a slot that "works for all 3 who
answered". Add her number, run the same round again — one call is placed, and
that earlier result turns out to be wrong.

### Why not just use the CALL-E app?

Use it. For a single call the CALL-E chat is faster than anything anyone could
build here, and this project does not try to replace it.

The difference is the set, not the call:

- **Count** — the app makes one call, started by hand. This makes many from one
  brief.
- **Answer shape** — the app returns prose plus the agent's reading of it. This
  returns a schema-validated result per recipient, so answers are comparable.
- **Outcome** — the app leaves a human reading N transcripts. This produces one
  merged result, with the number of people it rests on attached.
- **State** — every chat starts fresh. This remembers who has answered, who is
  still open, and who cannot be called at all, between runs.

The four categories the app offers — Personal Message, Ask a Business, Book or
Reschedule, Follow Up — are all one-to-one patterns, and so are the other
integrations in the ecosystem. Asking a group the same thing and merging the
answers is the gap.

### How we built it

- Python 3.11+, standard library only for the command line and the whole dry
  run. The optional web interface adds FastAPI, uvicorn and Jinja2; htmx is
  vendored into the package so no page needs a CDN.
- SQLite for everything that persists. Answers are written the moment they
  arrive, so an interrupted run resumes exactly where it stopped.
- One flow, three ways in: a command line, a `SKILL.md` for somebody else's
  agent, and a browser interface. All three call the same `service.py`. If a
  rule appears in one of them that the other two do not have, that is a bug.
- The result schema is designed first and the spoken instructions written to
  match it. Whatever the schema demands, the voice agent has to find out during
  the call — it is the stronger of the only two levers CALL-E offers.
- The browser displays; the server drives. Placing calls happens in a thread
  inside the server process, so the window can be closed and reopened without
  ending a round.

### Challenges we ran into

Everything below was measured against the real service, in one real call, and
several of these contradict the documentation:

- **`status` is useless as a progress indicator.** It sat on `PREPARING` for an
  entire conversation and only moved to `COMPLETED` about 24 seconds after the
  call had ended. Progress is readable, but from `activity`, not from `status`.
- **That measurement found a real bug by inspection.** `PREPARING` was not in
  our status enum, an unrecognised status parsed to `FAILED`, and `FAILED`
  counted as terminal — so every live call would have been abandoned and
  recorded as failed on the first poll, roughly 40 seconds in, while the person
  was still speaking. Fixed by splitting "map a status" from "decide whether to
  keep waiting"; an unfamiliar status now keeps the call alive.
- **The transcript is not where the documentation puts it.** Top-level
  `transcript` stayed `null`; the text is in `result.transcript`, as a string.
- **Result schemas are a REST-only feature.** `plan_call` over MCP/CLI has no
  `result_schema`, and a call started over MCP is not retrievable over REST at
  all — the two are separate ID spaces. Anything that needs comparable answers
  has to start the call over REST.
- **Speech recognition streams and corrects itself.** The same line arrives
  twice, a rough version and a correction fractions of a second later, so the
  newest line is held back for one poll rather than shown and then contradicted.
- **A late phone number made somebody disappear.** Adding a number to a contact
  who was already on the guest list did not make them a participant of the
  running round: they were then neither called nor listed as uncontactable —
  they simply vanished from the report, which is the one outcome the whole
  project is built to prevent. Found by hand, fixed, and pinned by a test.

### Accomplishments that we're proud of

- The dry run is not a stub that returns "OK". It runs schema generation,
  per-recipient payload assembly, status mapping, merging and reporting, and
  validates every scripted answer against the schema a real call would have
  received. A fixture that could not have come out of a real call fails the dry
  run instead of quietly passing it.
- The core sample checks itself, and the test suite tampers with the scenario
  one answer at a time to prove the checks can actually fail.
- Interrupting mid-run was tested with a real signal, not simulated: three
  answers saved, three never started, exit code 130, and re-running picked up
  exactly where it stopped without dialling anybody twice.
- `EVIDENCE.md` records what was executed with real output, and — at greater
  length — what was not.

### What we learned

- Design the result schema before the prose. What the agent must fill in
  determines what it must find out.
- Text in quotation marks is spoken verbatim, character for character; text
  outside them is rephrased and even extended by the planning agent. A
  deliberate typo in a quoted sentence came back spoken. So the question and the
  disclosure sentence are quoted and the rest is guidance, on purpose.
- Keep the upstream status set intact. `NO_ANSWER`, `BUSY`, `DECLINED` and
  `VOICEMAIL` are four different pieces of news, and collapsing them throws away
  precisely what the report needs.
- Roughly 40 seconds of every call is dialling before a word is spoken,
  independent of how long anybody talks. Cost is per call; time is not.

### What's next for Ringedingeding

- A field test with real, informed participants. It has not happened yet.
- The round-table mode: ask a group an opinion question instead of a date. The
  tables for it exist and are empty.
- The four remaining kinds of date (a whole week, a month, several consecutive
  days, a recurring weekday), which need a new slot generator and nothing else.
- E-mail as a second channel for the people a telephone cannot reach.
- Group profiles, so "my hiking club" is a thing you name once.

---

## Built with

- python
- sqlite
- fastapi
- jinja2
- htmx
- call-e
- rest-api

## Try it out

- Repository: `<<< the repository is private; the URL exists only after the user publishes it >>>`
- Pull request to `CALLE-AI/awesome-phone-call-agents`: `<<< not opened yet — user step >>>`
  (the entry, the title and the description are drafted in `PR-VORSCHAU.md`)
- Video: `<<< uploaded nowhere yet — user step >>>`
  The file exists and is finished: 88.8 s, 1920×1080, rendered 2026-08-02, at
  `_calle-videos/ringedingeding/renders/`. What is missing is a public link, not
  the video.

## Required by the rules

- CALL-E account e-mail: `<<< the user supplies this; it is never written into the repository >>>`
- Pre-existing code? No. This repository was created during the hackathon window
  and every commit in it is dated after 2026-07-23.
- Video is public, under three minutes, English narration: `<<< to be confirmed on upload >>>`

---

## Notes for whoever fills the form in

- Paste the sections above as plain text. The DevPost editor will not render a
  Markdown table, which is why there is none here.
- Do not add a number that is not in this file. `EVIDENCE.md` is the record of
  what was measured; anything else is invention.
- The four `<<< … >>>` fields are the only things blocking the form, and every
  one of them is a decision or an action that belongs to the user.
