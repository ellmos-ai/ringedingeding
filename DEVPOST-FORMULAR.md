# DevPost submission form — Ringedingeding

> **Copy-and-paste sheet.** Every heading below is a field of the DevPost submission
> form. The text under it is finished and goes into that field unchanged.
> It supersedes `DEVPOST.md`, which holds the same material in prose form.
>
> **Nothing here has been submitted.** Submitting, publishing the repository and
> uploading the video are the user's steps.
>
> **No Markdown tables anywhere below.** The DevPost editor does not render them, so
> everything comparative is written as a list on purpose.
>
> **Every placeholder is marked with an `ATTRAPPE` comment.** Search this file for
> `ATTRAPPE` before submitting and replace each one. The list is repeated at the end.

---

## Project name

```
Ringedingeding
```

---

## Elevator pitch

*(DevPost limit: 200 characters. The text below is 140.)*

```
Ask several people the same question by telephone and merge the replies into one result — including, by name, the people it could not reach.
```

---

## Project story

*(DevPost calls this "About the project". The headings below are DevPost's own suggested
structure — keep them as headings in the editor.)*

### Inspiration

Anyone who has tried to arrange one date for six people knows the shape of the problem:
three reply to the group chat straight away, two never do, and one calls back and tells you
out loud. A poll link does not fix it, because the people who ignore links are exactly the
people whose answer is missing.

So you call them. And then you do the part that actually goes wrong: you work out the
overlap in your head, over the people who answered — and quietly treat the two who never
answered as fine with anything.

That is the mistake this project exists to make impossible. An intersection over four of
six people is a different fact from an intersection over six of six, and it has to look
different.

### What it does

- Takes one brief — the occasion, some candidate dates, a guest list — and turns it into
  one call per person through the CALL-E batch API.
- Shows exactly what would happen before anything is dialled: who gets called, the complete
  order text as it will leave the machine, how many calls that is, and what it costs.
- Merges the replies into a single board that keeps five states apart: can, cannot, said
  nothing about that one, not reached — which is itself `NO_ANSWER` or `BUSY` or
  `VOICEMAIL` or `DECLINED`, never one lump — and has no phone number at all.
- Never reports an aggregate over "everyone". Every result carries its denominator and
  names who is missing.
- Catches up later without a special mode: add a number that was missing, run the same
  round again, and exactly that one call is placed.
- Runs the whole flow with no account, no network and no telephone, against bundled
  scripted answers.

There are two products on the same mechanism. **Find a Date** asks "when can you?" and
intersects availability. **Ask Your Advisor** asks "what do you think?" and reports the
leading tendency, the countervoices, the reasons and the concerns — it never turns dissent
into a false consensus.

### The one thing to try first

One command, about a second, no account and no API key:

- `python -m ringedingeding proof`

It builds a seven-person round in a temporary database, replays scripted answers, and then
checks its own result against the four ways a merge can quietly lie — a disagreement
counted as a majority, silence read as a "no", three kinds of absence folded into one
failure, and the invitee whose number is missing dropped from the report. Exit code 0
means all eight checks passed.

Its last step is the argument in miniature. One invitee has no phone number, so she is
never called, and the round reports a slot that "works for all 3 who answered". Add her
number, run the same round again — one call is placed, and that earlier result turns out
to be wrong.

### Why not just use the CALL-E app?

Use it. For a single call the CALL-E chat is faster than anything anyone could build here,
and this project does not try to replace it.

The difference is the set, not the call:

- **Count** — the app makes one call, started by hand. This makes many from one brief.
- **Answer shape** — the app returns prose plus the agent's reading of it. This returns a
  schema-validated result per recipient, so answers are comparable.
- **Outcome** — the app leaves a human reading N transcripts. This produces one merged
  result, with the number of people it rests on attached.
- **State** — every chat starts fresh. This remembers who has answered, who is still open,
  and who cannot be called at all, between runs.

The four categories the app offers — Personal Message, Ask a Business, Book or Reschedule,
Follow Up — are all one-to-one patterns, and so are the other integrations in the
ecosystem. Asking a group the same thing and merging the answers is the gap.

### How we built it

- Python 3.11+, standard library only for the command line and the whole dry run. The
  optional web interface adds FastAPI, uvicorn and Jinja2; htmx is vendored into the
  package so no page needs a CDN.
- SQLite for everything that persists. Answers are written the moment they arrive, so an
  interrupted run resumes exactly where it stopped.
- One flow, three ways in: a command line, a `SKILL.md` for somebody else's agent, and a
  browser interface. All three call the same `service.py`. If a rule appears in one of them
  that the other two do not have, that is a bug.
- The result schema is designed first and the spoken instructions written to match it.
  Whatever the schema demands, the voice agent has to find out during the call — it is the
  stronger of the only two levers CALL-E offers.
- The browser displays; the server drives. Placing calls happens in a thread inside the
  server process, so the window can be closed and reopened without ending a round.

### Challenges we ran into

Everything below was measured against the real service, in one real call, and several of
these contradict the documentation:

- **`status` is useless as a progress indicator.** It sat on `PREPARING` for an entire
  conversation and only moved to `COMPLETED` about 24 seconds after the call had ended.
  Progress is readable, but from `activity`, not from `status`.
- **That measurement found a real bug by inspection.** `PREPARING` was not in our status
  enum, an unrecognised status parsed to `FAILED`, and `FAILED` counted as terminal — so
  every live call would have been abandoned and recorded as failed on the first poll,
  roughly 40 seconds in, while the person was still speaking. Fixed by splitting "map a
  status" from "decide whether to keep waiting"; an unfamiliar status now keeps the call
  alive.
- **The transcript is not where the documentation puts it.** Top-level `transcript` stayed
  `null`; the text is in `result.transcript`, as a string.
- **Result schemas are a REST-only feature.** `plan_call` over MCP/CLI has no
  `result_schema`, and a call started over MCP is not retrievable over REST at all — the
  two are separate ID spaces. Anything that needs comparable answers has to start the call
  over REST.
- **Speech recognition streams and corrects itself.** The same line arrives twice, a rough
  version and a correction fractions of a second later, so the newest line is held back for
  one poll rather than shown and then contradicted.
- **A late phone number made somebody disappear.** Adding a number to a contact who was
  already on the guest list did not make them a participant of the running round: they were
  then neither called nor listed as uncontactable — they simply vanished from the report,
  which is the one outcome the whole project is built to prevent. Found by hand, fixed, and
  pinned by a test.

### Accomplishments that we're proud of

- The dry run is not a stub that returns "OK". It runs schema generation, per-recipient
  payload assembly, status mapping, merging and reporting, and validates every scripted
  answer against the schema a real call would have received. A fixture that could not have
  come out of a real call fails the dry run instead of quietly passing it.
- The core sample checks itself, and the test suite tampers with the scenario one answer at
  a time to prove the checks can actually fail.
- Interrupting mid-run was tested with a real signal, not simulated: three answers saved,
  three never started, exit code 130, and re-running picked up exactly where it stopped
  without dialling anybody twice.
- `EVIDENCE.md` records what was executed with real output, and — at greater length — what
  was not.

### What we learned

- Design the result schema before the prose. What the agent must fill in determines what it
  must find out.
- Text in quotation marks is spoken verbatim, character for character; text outside them is
  rephrased and even extended by the planning agent. A deliberate typo in a quoted sentence
  came back in the transcript unchanged. So the question and the disclosure sentence are
  quoted and the rest is guidance, on purpose.
- Keep the upstream status set intact. `NO_ANSWER`, `BUSY`, `DECLINED` and `VOICEMAIL` are
  four different pieces of news, and collapsing them throws away precisely what the report
  needs.
- Roughly 40 seconds of every call is dialling before a word is spoken, independent of how
  long anybody talks. Cost is per call; time is not.

### What's next for Ringedingeding

- A field test with real, informed participants. It has not happened yet.
- The four remaining kinds of date (a whole week, a month, several consecutive days, a
  recurring weekday), which need a new slot generator and nothing else.
- E-mail as a second channel for the people a telephone cannot reach.
- Group profiles, so "my hiking club" is a thing you name once.

---

## Built with

*(DevPost expects a list of tags. Enter them one at a time.)*

```
python
sqlite
fastapi
jinja2
htmx
call-e
rest-api
pytest
```

---

## Try it out links

<!-- ATTRAPPE: the repository is private. Replace with the real URL once the user
     publishes it, or delete the line if the repository stays private. -->

```
https://www.youtube.de/coming-soon
```

Intended content once available:

- Repository: the public GitHub URL of this repository.
- Pull request to `CALLE-AI/awesome-phone-call-agents`: the PR URL. The entry, title and
  description are already drafted in `PR-VORSCHAU.md`.

---

## Video demo link

<!-- ATTRAPPE: uploaded nowhere yet. The file exists and is finished: 88.8 s,
     1920x1080, rendered 2026-08-02, at
     C:\_Local_DEV\_calle-videos\ringedingeding\renders\.
     What is missing is a public link, not the video. -->

```
https://www.youtube.de/coming-soon
```

Requirements to check at upload time: under three minutes (88.8 s, well inside), publicly
visible, English narration with burned-in English subtitles, and it must show the project
functioning.

---

## Repository link

<!-- ATTRAPPE: the repository is private; the URL only exists after the user publishes
     it. Replace with the real GitHub URL. -->

```
https://www.youtube.de/coming-soon
```

---

## Pull request URL

*(Hackathon-specific required field: the PR to `CALLE-AI/awesome-phone-call-agents`.)*

<!-- ATTRAPPE: not opened yet — user step. The drafted entry, title and description are
     in PR-VORSCHAU.md. -->

```
https://www.youtube.de/coming-soon
```

---

## CALL-E account e-mail

<!-- ATTRAPPE: the user supplies this at submission time. It is deliberately never
     written into the repository. -->

```
<the user enters this directly in the form>
```

---

## Pre-existing project?

```
No. This repository was created during the hackathon submission period and every commit
in it is dated after 2026-07-23.
```

---

## Image gallery / thumbnail

Three thumbnail drafts, 1280x720, at
`C:\_Local_DEV\_calle-videos\ringedingeding\thumbnails\`:

- `ringedingeding-thumb-a.png` — "3 of 7" and the seven people with their four distinct
  kinds of absence. Recommended: it states the whole argument without a sentence of
  explanation.
- `ringedingeding-thumb-b.png` — the invitee with no phone number, and the result being
  overturned.
- `ringedingeding-thumb-c.png` — one brief in, one board out.

The repository banner (1200x300) is `banner.png` in the repository root.

---

## Checklist of every ATTRAPPE in this file

Replace all of these before submitting:

1. **Try it out links** — placeholder `https://www.youtube.de/coming-soon`; needs the
   public repository URL and the pull-request URL.
2. **Video demo link** — placeholder `https://www.youtube.de/coming-soon`; needs the real
   YouTube URL after upload. The video file itself is finished.
3. **Repository link** — placeholder `https://www.youtube.de/coming-soon`; needs the
   public GitHub URL after the repository is made public.
4. **Pull request URL** — placeholder `https://www.youtube.de/coming-soon`; needs the real
   PR URL after it is opened.
5. **CALL-E account e-mail** — the user types it into the form directly; it is not stored
   here.

---

## Notes for whoever fills the form in

- Paste the sections as plain text. There is no Markdown table anywhere in this file
  because the DevPost editor will not render one.
- Do not add a number that is not in this file. `EVIDENCE.md` is the record of what was
  measured; anything else is invention.
- The five items in the checklist above are the only things blocking the form, and every
  one of them is a decision or an action that belongs to the user.
