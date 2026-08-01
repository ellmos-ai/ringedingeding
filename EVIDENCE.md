# EVIDENCE

What was **actually executed** in this repository, with real output. Anything
that was not run says so. No numbers here are estimated or reconstructed.

Two things this file is careful to separate:

* **measured against the real CALL-E service** — that is `FINDINGS.md`, produced
  by the operator from one real telephone call,
* **executed in this repository** — this file. Everything below ran on the
  local machine against fixtures. **No telephone call was ever placed from this
  code, and no CALL-E account exists.**

Environment: Windows 11, Python 3.12.10.
Date of the first run: 2026-08-01. **Sections 1–7 describe the command-line
build**, which has no third-party packages at all.

**Sections 8–14 were added by a second session on 2026-08-01**, which built the
project layer, the skill and the web interface. That part uses FastAPI 0.137.0,
uvicorn 0.49.0, Starlette 1.3.1 and Jinja2 3.1.6, installed as the optional
`[web]` extra. The command line still installs and runs with nothing.

---

## 1. Test suite — executed, passing

```
$ python -m pytest
........................................................................ [ 33%]
........................................................................ [ 66%]
........................................................................ [100%]
216 passed in 6.37s
```

By file:

```
tests/test_activity.py: 24      tests/test_render.py: 15
tests/test_cli.py: 31           tests/test_runner.py: 13
tests/test_fixtures.py: 15      tests/test_safety.py: 19
tests/test_live_guard.py: 17    tests/test_schemas.py: 15
tests/test_merge.py: 19         tests/test_store.py: 15
tests/test_phone.py: 19         tests/test_polling.py: 14
```

The starting point of this session was **166 passing tests**; the 50 added ones
cover the measured behaviour described below. No test opens a socket.

## 2. A bug the measurements uncovered — found and fixed

This is the most consequential thing in this session, so it goes first.

`FINDINGS.md` section 2 records that the service reports `PREPARING` while a
call is in progress. That status was not in this program's enum. Checked
directly:

```
$ python -c "from ringedingeding.models import CallStatus; s = CallStatus.parse('PREPARING'); print(s, s.is_terminal)"
CallStatus.FAILED | is_terminal = True
```

An unrecognised status parsed to `FAILED`, and `FAILED` counted as terminal. The
polling loop stops at the first terminal status, so **every live call would have
been abandoned and recorded as failed on the first poll, roughly 40 seconds in,
while the person was still speaking.** The subsequent run would then have dialled
the same person again, since a `FAILED` participant is eligible for a retry.

This was never observed happening — no call was placed — but it is a direct
consequence of the measured status behaviour, and it is reachable by inspection.

Fixed by:

* adding `PREPARING` to `CallStatus` as an explicitly non-terminal status,
* splitting `CallStatus.known()` (returns `None` for anything unrecognised) from
  `CallStatus.parse()` (falls back to `FAILED`). The poll loop uses `known()`, so
  an unfamiliar status keeps the call alive instead of killing it; the final
  mapping keeps `parse()`, so an uninterpretable status is never read as success,
* mapping `PREPARING` to the `PENDING` bucket, since an unfinished call is not
  an opinion.

Covered by `tests/test_polling.py::test_preparing_does_not_end_the_wait` and
four neighbouring tests.

## 3. Findings worked into the code

| Finding | What changed |
|---|---|
| §1 progress is readable via `activity` | new `ringedingeding/activity.py`; the poll loop forwards lines to a callback, the CLI prints them during a live run |
| §1 duplicate lines from streaming ASR | `dedupe()` folds a line into its correction; the newest line is held back one poll so the version about to be corrected is never printed |
| §2 `status` is not progress | poll loop reads `activity` for progress and `status` only for terminality; see §2 above for the bug this exposed |
| §3 transcript is in `result.transcript` | `extract_transcript()` looks there first; top-level `transcript` is checked last because it was measured `null`. Transcript now flows into `CallOutcome` → `Answer` → SQLite → report |
| §4 quoted text is spoken verbatim | the disclosure sentence is now quoted, like the question already was; both templates state the rule to the agent |
| §5 REST is the only path with schemas | documented in the transport docstring, including the measured HTTP 404 across ID spaces. The code already used REST with `CALLE_API_KEY`; no MCP path was added |
| §6 ~40 s lead time per call | new `ringedingeding/timings.py`; `plan` prints a duration estimate, first poll delay lowered from 60 s to 40 s |
| §7 the agent interprets free answers | the transcript is stored next to the structured result, and the Markdown report prints it under "What was actually said" |
| §8 keys start with `iams_live_`, not `calle_live_` | no prefix check existed; a test now pins that none is ever added |
| parallelism unverified | unchanged — both paths kept, and `plan` now says in words that the serial figure is the one to trust |

## 4. Commands executed, with real output

### `demo` — three complete polls, no account, no network

```
$ python -m ringedingeding demo
[...]
RESULT   : Works for all 4 who answered: Sa 14-18

Slot by slot (blank means the person was not asked or did not say):
+----------+-----+-------------------------+------------+---------+
| Slot     | Can | Who can                 | Who cannot | Unclear |
+----------+-----+-------------------------+------------+---------+
| Sa 14-18 | 4   | Anna, Ben, Clara, David | -          | -       |
| Sa 18-21 | 2   | Anna, David             | Ben, Clara | -       |
| So 10-14 | 2   | Clara, David            | Anna, Ben  | -       |
+----------+-----+-------------------------+------------+---------+

Answers  : 4 of 6 participants
NOTE     : Based on 4 of 6 participants. not reached: Erik (NO_ANSWER), Frida (BUSY). These are not counted as indifferent.
[...]
Dry run complete. No call was placed and no account was used.
EXIT=0
```

427 lines of output, three Markdown reports written. This is the success
criterion from `SPEC.md` ("six fictional participants, a scheduling question and
an opinion question, two people not reached") and it is met.

### `fixtures`, `create`, `list`

```
$ python -m ringedingeding fixtures
family-dinner  [slot, 6 people]
    Scheduling question to six relatives. Four answer, two are not reached.
grandma-gift  [choice, 6 people]
    Decision between two options. Shows a tally, an abstention, an answer outside the options, a refusal and one person not reached.
team-retro  [open, 4 people]
    Open question in English. One person declines to answer, one is on voicemail. Free-text answers are quoted, never summarised.
EXIT=0

$ python -m ringedingeding create --question "When can you make it this weekend?" \
    --kind slot --organizer "Lukas" --slot "Sat 14-18" --slot "Sun 10-14" \
    --participant "Anna=+15555550100" --participant "Ben=+15555550101"
created poll poll_fb80e344ba with 2 participant(s)
next: ringedingeding plan --poll poll_fb80e344ba
EXIT=0

$ python -m ringedingeding list
poll_fb80e344ba  [slot] 0/2 answered  - When can you make it this weekend?
EXIT=0
```

### `plan` — the new time estimate

```
$ python -m ringedingeding plan --fixture family-dinner
[...]
Estimated cost if run live: $0.30 (6 x $0.05)
Estimated time if run live: about 13 min one after another, about 3 min if they run at once. Roughly 40 s per call is dialling before a word is spoken. Whether CALL-E permits calls at once is UNVERIFIED - the serial figure is the one to trust.
Everything in the call instructions leaves this machine and is processed by CALL-E / AiRudder in Singapore.
```

The 13 minutes are an estimate built on the measured 40 s lead time plus a
90 s working assumption per conversation. The 40 s is measured; the 90 s is
not — the one observed call lasted 32 s.

### Every refusal, with its exit code

All four were executed and all four refused:

```
$ python -m ringedingeding run --poll poll_fb80e344ba          # dry run of a real poll
Error: a dry run needs scripted answers: pass --fixture <name>, or pass --live to place
real calls. A poll of real people cannot be simulated - there is nothing to simulate it from.
EXIT=1

$ python -m ringedingeding run --fixture family-dinner --live  # example numbers
Live calling blocked: This poll uses example numbers from a bundled fixture: anna
(+49*****01), ben (+49*****02), [...] They are placeholders and are never dialed.
EXIT=3

$ python -m ringedingeding run --poll poll_3eaa584131 --live --yes
Live calling blocked: --yes only works together with RINGEDINGEDING_LIVE_CONFIRM='CALL THEM'
in the environment. There is no silent live mode.
EXIT=3

$ python -m ringedingeding create --question "Welche Dosierung soll Oma nehmen?" --kind open \
    --organizer Lukas --participant "Anna=+15555550100"
Refused: This question is not suitable for an automated phone poll:
- medical: matched 'Dosierung' — Medical questions need a qualified human, not a voice agent.

Ringedingeding refuses these categories by design. There is no override flag.
EXIT=2
```

The confirmation prompt was also reached and refused without a matching phrase:

```
About to place REAL phone calls to REAL people.
  * Everything in the call instructions leaves this machine and is processed by CALL-E / AiRudder in Singapore.
  * Cost is about $0.05 per call.
  * Everyone you call should know beforehand that this may happen.

Type 'CALL THEM' to continue: Live calling blocked: no confirmation received
EXIT=3
```

**Nothing beyond this point was executed**, because past it lies a telephone.

An incidental confirmation: a poll created with `Ben=+15555550101` was refused
for using a bundled example number. That was an accident on my part, and the
guard caught it before the `--live` confirmation was even reached.

### Interruption — executed with a real signal

A `SIGINT` was raised for real (`signal.raise_signal`) in the middle of a
six-person dry run, after the third answer:

```
  <- anna: COMPLETED
  <- ben: COMPLETED
  <- clara: COMPLETED
>>> raising SIGINT now
Interrupted. No new calls will be started; calls already in progress are allowed to
finish. Press Ctrl-C again to give up now.
  aborted: 3 finished, 3 never started

Answers  : 3 of 6 participants
NOTE     : Based on 3 of 6 participants. not called yet: David, Erik, Frida.
           These are not counted as indifferent.

EXIT CODE: 130
ANSWERS SAVED: 3 [('anna', 'COMPLETED'), ('ben', 'COMPLETED'), ('clara', 'COMPLETED')]
```

Re-running the same command afterwards picked up exactly where it stopped:

```
$ python -m ringedingeding --db sigint.db run --fixture family-dinner
[dry run] transport=fixture calls=3 concurrency=1
  would call david (+49*****04)
  would call erik (+49*****05)
  would call frida (+49*****06)
```

So the documented abort behaviour — exit 130, finished answers saved,
unattempted participants left `PENDING`, resume without repeating anyone — is
verified rather than asserted.

A separate attempt using `CTRL_BREAK_EVENT` against a subprocess was **also**
run. It did **not** exercise the graceful path: only `SIGINT` has a handler, so
Windows killed the process outright (exit code `3221225786` =
`STATUS_CONTROL_C_EXIT`). The database still held the three answers completed up
to that point, which confirms the write-as-you-go persistence but not the
graceful shutdown. **Ctrl-Break is therefore not handled gracefully on Windows**;
Ctrl-C is. This is recorded rather than fixed.

### Dependencies

```
$ python -c "<ast scan of every import in the package>"
imported top-level modules: ['__future__', 'argparse', 'concurrent', 'dataclasses',
 'datetime', 'enum', 'hashlib', 'json', 'os', 'pathlib', 're', 'signal', 'sqlite3',
 'sys', 'threading', 'time', 'typing', 'urllib', 'uuid']
NOT in the standard library: none
```

## 5. Not executed

* **Any telephone call.** No account exists, no API key was set, and
  `AGENTS.md` excludes it from this task.
* **`POST /v1/calls` and `GET /v1/calls/{id}` from this code.** Every test
  replaces `_request`. The HTTP layer itself — headers, URL building, error
  handling — has never spoken to a server.
* **`pip install -e .`** was not run. The package was exercised as
  `python -m ringedingeding` from the source tree. The `pyproject.toml` console
  script entry point is therefore untested.
* **Parallel calling.** `--concurrency > 1` is exercised against the fixture
  transport only. Whether CALL-E permits it remains unknown.
* **The 90-second conversation assumption** in `timings.py`. One observed call
  lasted 32 s; the estimate deliberately assumes longer.
* **Voicemail, busy and no-answer against the real service.** These are
  fixture-scripted here. `FINDINGS.md` notes only `COMPLETED` was ever observed.
* **The batch response shape.** `recipients` is assumed to be in request order
  and the code refuses rather than guesses when the length disagrees — but no
  real batch response has been seen.
* **`ringedingeding.db` in the repository root** is a leftover state file from
  an earlier session, git-ignored, not used by anything above.

## 6. Assumptions made and written down

Per `AGENTS.md` ("hold the assumption in writing and keep building"):

1. **The REST base URL** is `https://api.heycall-e.com`, from the documentation.
   The observed calls went through the MCP host `seleven-mcp-sg.airudder.com`,
   which is a different endpoint, so the REST host is unconfirmed. Overridable
   with `CALLE_BASE_URL`, and there is a test for that.
2. **The JSON shape of an `activity` entry** is unknown — only its rendered form
   (`17:37:45.146 | Callee said: …`) was ever seen. The parser accepts strings,
   dictionaries and several key spellings, and keeps anything it cannot
   interpret rather than dropping it.
3. **Correction detection is a heuristic.** A line is folded into the next only
   if the same speaker, within five seconds, repeats all of its words in order
   at the start of the new line. The observed gap was 0.67 s. This affects the
   live display only; the transcript is never altered.
4. **Per-recipient transcripts.** In a batch, a call-level transcript is *not*
   attributed to an individual — only a single-recipient call uses it. Whether
   the real batch response carries per-recipient transcripts is unknown.
5. **`PREPARING` is the only in-flight status** that has been seen. The code
   does not rely on that: anything outside the documented terminal list is
   treated as still running.
6. **The first poll now happens at 40 s instead of 60 s**, since nothing
   observable happened before +39 s. `activity` is cumulative, so a later first
   poll loses nothing — but this schedule has not been exercised against the
   real API.

## 7. Not touched, deliberately

`AGENTS.md` places these outside the build task, and none of them happened:
real calls, account registration, publishing the repository, a pull request to
the target repository, a video. `.gitignore` was not weakened. Nothing was
written outside this repository.

---

# Second session — the project layer, the skill and the web interface

Everything below ran on the local machine. **Still no telephone call, still no
CALL-E account.** The live path was exercised only up to the guard that refuses
it.

## 8. Test suite after the interface — executed, passing

```
$ python -m pytest
292 passed, 1 warning in 45.20s
```

The one warning is `StarletteDeprecationWarning: Using httpx with
starlette.testclient is deprecated; install httpx2 instead` — raised by
FastAPI's own test client on import, not by this project's code.

New files, run individually:

```
$ python -m pytest tests/test_projects.py       18 passed in 2.26s
$ python -m pytest tests/test_service.py        22 passed in 6.92s
$ python -m pytest tests/test_web.py            23 passed
$ python -m pytest tests/test_cli_projects.py   13 passed in 10.73s
```

The 216 tests of the first session still pass unchanged; the total went from
216 to 292.

## 9. The project flow on the command line — executed

Real output, from a throwaway database:

```
$ ringedingeding project demo --fixture family-dinner
created demo project prj_ed2ae4caac from fixture 'family-dinner'
next: ringedingeding project call --project prj_ed2ae4caac --mode script

$ ringedingeding project call --project prj_ed2ae4caac --mode script
  -> david (+49*****04)
  -> erik (+49*****05)
  -> frida (+49*****06)
  <- anna: COMPLETED
  <- ben: COMPLETED
  <- clara: COMPLETED
  <- david: COMPLETED
  <- erik: NO_ANSWER
  <- frida: BUSY

# Wann kannst du am Wochenende zum Familienessen?
4 of 6 answered.

  1. Sa 14-18                     4 can
       can   : Anna, Ben, Clara, David
  2. Sa 18-21                     2 can
       can   : Anna, David
       cannot: Ben, Clara
  3. So 10-14                     2 can
       can   : Clara, David
       cannot: Anna, Ben

not reached : Erik (NO_ANSWER), Frida (BUSY)
These are never counted as 'doesn't mind'.

$ ringedingeding project criteria --project prj_ed2ae4caac \
      --favourite 1 --must Anna --count 4
  2. Sa 18-21                     2 can  [1 von 3 criteria]
  3. So 10-14                     2 can  [0 von 3 criteria]
best fit    : Sa 14-18 (3 von 3 criteria)
```

## 10. The web server — executed over real HTTP

Not only through the test client. `uvicorn` was started as the CLI starts it and
addressed with `curl` from outside the process:

```
$ ringedingeding --db <tmp>/serve.db web --port 8791 &
GET /            200  2528 bytes
GET /contacts    200  1861 bytes
GET /static/htmx 200  50917 bytes
POST /demo       303 -> http://127.0.0.1:8791/projects/prj_e5e9cbe306/preview
front page bytes: 3007      (after the demo project existed)
```

The server was then stopped and the port confirmed closed.

## 11. Two bugs found by the tests, both fixed

Written down because both were real defects in this session's code, not
hypotheticals:

1. **A late phone number made somebody disappear.** Adding a number to a contact
   who was already on a guest list did not make them a participant of the
   running round. They were then neither called nor listed as "cannot be
   contacted" — they simply vanished from the report, which is the one outcome
   the whole project is built to prevent. Found by running the command line by
   hand, before the test existed. Fixed with `service.resync_contact()`, called
   from both the CLI and the web contact form, and pinned by
   `test_adding_a_number_later_puts_the_person_back_in_the_round`.

2. **A rejected phone number left half a contact behind.** `create_contact()`
   inserted the row and *then* validated the number, so an unusable number left
   a nameless contact in the address book. Found by
   `test_invalid_number_is_refused_before_storage`. Fixed by validating before
   the insert.

## 12. What the interface was verified to refuse

Each of these is a passing test in `tests/test_web.py`, not a claim:

* no page renders a full phone number — checked with the regular expression
  `\+\d{6,}` against `/`, `/contacts`, `/projects/{id}/preview`, `/board`,
  `/live` and `/invite`, after a completed round and a decision;
* `mode=live` without the exact phrase `CALL THEM` returns 403 and **no job is
  created at all**;
* `mode=live` *with* the phrase, against a demo project, still refuses — the
  example numbers of a bundled fixture are never dialled. The job fails with
  "example numbers" before any HTTP request to CALL-E;
* the pages contain the string `CALLE_API_KEY` (to say where the key belongs)
  but no `name="api_key"` and no `type="password"` field;
* a project whose occasion is "Notfall im Haus" is refused with 422 and never
  appears in the project list;
* a rehearsal shows "Erfundene Antworten" on both the live view and the board,
  and the banner disappears after `POST /reset`;
* `htmx.min.js` is served from the package and no page references `unpkg` or a
  `cdn.` host.

## 13. The architectural promise, tested

`test_a_round_survives_the_page_that_started_it` starts a round through the web
interface, never asks the interface for anything again, and then opens the
SQLite file directly — the same thing a browser opened an hour later would do.
All six answers are there. That is the "you may close the window" claim,
verified rather than asserted.

`test_the_live_panel_is_complete_without_the_stream` fetches the panel fragment
with no event stream involved and finds both "hat geantwortet" and "nicht
abgenommen" in it: the page is whole without JavaScript.

`test_the_stream_sends_a_panel_and_then_closes` reads the Server-Sent-Events
stream and asserts it emits a `panel` event and then `done`.

## 14. What was not done in this session

* **No real call, no account, no network request to CALL-E.** The live transport
  was never constructed with a working key; every live test stops at a guard.
* **`htmx.min.js` was downloaded once** from `unpkg.com` during the build and
  committed into the package (50,917 bytes,
  `sha256:e209dda5c8235479f3166defc7750e1dbcd5a5c1808b7792fc2e6733768fb447`).
  That is the only network access this session made. The interface itself never
  reaches the network.
* **Stage 2 and stage 3 were not built** — round table, group profiles, the four
  remaining kinds of date, e-mail, connectors, calendar export, LLM summaries.
  Their tables and columns exist and are empty; `ARCHITEKTUR.md` says where each
  one attaches. `projects.create_project()` refuses an unbuilt kind of date by
  name rather than half-accepting it.
* **The per-day exception editor is server-rendered, one row at a time.** There
  is no dynamic "add another slot" button; a blank extra row is provided and
  submitting adds it. This works without JavaScript and was chosen over a
  client-side row builder deliberately.
* **The interface was not opened in a browser by a human** in this session. It
  was exercised through the FastAPI test client and through `curl` against a
  real `uvicorn` process. Visual layout is therefore **unverified by eye** —
  the HTML and CSS are asserted only by the tests above.
