# PR preview — `CALLE-AI/awesome-phone-call-agents`

> **GATE. Nothing here has been sent.** No pull request opened, no `git push`, no
> repository made public, no submission. This file is a preparation document for
> the user to review and, if they want it, to copy from.
>
> **One honesty note up front.** The requirement list below is derived from
> `SPEC.md` and from this project's own behaviour. The target repository's
> submission rules were **not fetched or re-read during this run**, so treat
> section 1 as *what this project can demonstrate*, not as *what the maintainers
> currently demand*. Confirm against the live CONTRIBUTING before opening a PR.

---

## 1. The gap this entry fills

Every contribution in the target repository calls **exactly one person**.
`callback-window-coordinator` negotiates time windows with one person;
`call-on-behalf` runs one delegated errand. The vendor's own app is built the
same way — its four categories (Personal Message, Ask a Business, Book or
Reschedule, Follow Up) are all one-to-one patterns.

**Nobody merges the answers of several people.** That is the contribution.

It is not a workaround either: CALL-E supports it natively. `POST /v1/calls`
takes `recipients: [...]` as a batch and returns a schema-validated result per
recipient (`recipient_result_schema`).

### Why aggregation is a different problem, not a bigger one

A single call ends when someone answers. An aggregation only *starts* there,
because four things appear that one call never produces:

- **Disagreement.** Nora can make Saturday afternoon, Paul cannot. Both stay on
  the row; neither wins by being counted. A tool that resolves this silently by
  majority has invented a decision nobody made.
- **Half commitment.** Rike named one slot and said nothing about the other two.
  *Said nothing* is not *no*. It is carried as its own state — the one most tools
  round away.
- **Unreachability, which is not one state.** `NO_ANSWER`, `BUSY`, `DECLINED`
  and `VOICEMAIL` are four different pieces of news, and "has no phone number at
  all" is a fifth. Collapsing them throws away exactly what the report needs.
- **The denominator.** An intersection over three of seven people is a different
  fact from one over seven of seven, and it has to *look* different. Every result
  carries how many answers it rests on and names who is missing.

### The demonstration, in one command

```
python -m ringedingeding proof
```

Measured on 2026-08-02, three consecutive runs: **exit 0**, **0.68 / 0.83 /
0.90 s**, 96 lines of output, **8 of 8 checks passed**. No account, no API key,
no network, no telephone — a seven-person round in a temporary database against
scripted answers.

Its last step is the whole argument in miniature. One invitee has no phone
number, so she is never called, and the round reports
`Works for all 3 who answered: Sat 09-13`. Add her number, run the same round
again — **exactly one** call is placed, and the result becomes
`No slot works for all 4 who answered.` The earlier answer was not wrong about
the three; it was wrong about being an answer.

---

## 2. What this project can demonstrate

Everything below was checked during this run. The right-hand column says where.

### Runs without an account

- Dry run is the **default of every command**; `--live` is the only way to place
  a real call — `ringedingeding/cli.py`
- CLI and the entire dry run import **nothing outside the standard library** —
  AST scan over the package on 2026-08-02: *"not in the standard library: none"*
  once `ringedingeding/web/` is excluded. FastAPI and uvicorn are imported in
  `ringedingeding/web/app.py` only, and the web interface is optional.
- Python **≥ 3.11**, licence **MIT** — `pyproject.toml`
- **308 tests pass**, fresh run 2026-08-02, 68.24 s — `python -m pytest`

### Safety

- **Typed confirmation on top of `--live`** before anything is dialled —
  `ringedingeding/safety.py`
- **Sensitive content refused at creation time, not at dial time** — medical,
  legal, financial and emergency traffic never gets as far as storing a number.
  The keyword lists are deliberately narrow so an ordinary family question about
  a budget still passes — `ringedingeding/safety.py`
- **Deterministic idempotency key** per (poll, participant, attempt), so a
  repeated run cannot produce a second call for the same intent —
  `ringedingeding/safety.py`
- **E.164 normalisation** on every stored number — `ringedingeding/phone.py`,
  `models.py`
- **Phone numbers masked in every output channel** — and this is not a claim but
  a test: one of the eight checks in `proof` runs `\+\d{6,}` over everything the
  command printed and fails if it matches.
- **Interruption is safe.** Tested with a real signal, not simulated: answers
  already received are saved, re-running resumes without dialling anyone twice.

### Honesty about what has *not* happened

- **No real call has ever been placed from this repository.** The one real call
  behind `FINDINGS.md` was made to measure CALL-E's behaviour, before this code
  existed. The field test with real, informed participants is still open.
- The web interface **has never been looked at by a human in a browser**
  (`EVIDENCE.md` §14). It is therefore deliberately absent from the demo video.
- No pre-existing code: the first commit is dated after the 2026-07-23 cut-off.
- No credentials anywhere. `.gitignore` excludes `.env*`, `CREDENTIALS*`,
  `secrets*`, `contacts.csv`, `_private/` and `*.db` from the first commit on.

---

## 3. Draft entry for the target `README.md`

Adjust the heading level and list style to whatever the file uses at the time.

```markdown
### 📞 [Ringedingeding](https://github.com/<user>/ringedingeding)
> Ask several people the same question by telephone and merge the replies into
> one result — including, by name, the people it could not reach.

* **The gap it fills**: every other entry here calls one person. This one runs a
  round across many recipients from a single brief and merges the answers.
* **What makes merging hard**: disagreement stays visible instead of being
  resolved by majority; "said nothing about that one" is kept apart from "no";
  NO_ANSWER, BUSY, DECLINED, VOICEMAIL and "no number at all" stay five states;
  and every result carries the number of answers it rests on.
* **Catch-up without a special mode**: add a number that was missing, run the
  same round again, and exactly the one outstanding call is placed.
* **Tech**: Python 3.11+, standard library only for the CLI and the dry run,
  SQLite, CALL-E REST batch API. Optional FastAPI web interface.
* **Safety**: dry run by default, typed confirmation on top of `--live`,
  E.164 validation, phone masking enforced by a test, deterministic idempotency
  keys, sensitive-topic refusal at creation time.
* **Try it without an account**: `python -m ringedingeding proof` — under a
  second, no key, no network, and it checks its own result.
```

---

## 4. Draft PR title and description

**Title**

```
feat(apps): add Ringedingeding — ask a group by phone, merge the answers into one result
```

**Description**

```markdown
## What this adds

Every application listed here places a single call. Ringedingeding places a
round: one brief becomes one call per person, and the replies are merged into a
single result.

CALL-E already supports this natively — `POST /v1/calls` accepts a `recipients`
batch with a per-recipient result schema — so this is an application of the
existing API, not a workaround around it.

## Why merging is its own problem

A single call ends when someone answers; an aggregation begins there.

1. **Disagreement stays visible.** Two people who contradict each other both
   appear; neither wins by being counted.
2. **Silence is not a no.** "Said nothing about that slot" is its own state.
3. **Not-reached is five states, not one.** NO_ANSWER, BUSY, DECLINED,
   VOICEMAIL, and "no number in the address book" are kept apart.
4. **Every result carries its denominator** and names who is missing. An
   intersection over 3 of 7 is never reported as an intersection.

## Try it without an account

`python -m ringedingeding proof` — under a second, no API key, no network, no
telephone. It builds a seven-person round in a temporary database, replays
scripted answers, and then runs eight checks against its own output, including a
regex that fails the run if any full phone number was printed. Exit 0 means all
eight passed.

The last step is the point: one invitee has no phone number and is never called,
so the round reports a slot that "works for all 3 who answered". Add her number,
run the same round — one call is placed, and that result turns out to be wrong.

## Safety

- [x] Dry run is the default of every command; `--live` plus a typed
      confirmation is the only path to a real call
- [x] Sensitive topics (medical, legal, financial, emergency) refused at
      creation time, before a number is even stored
- [x] E.164 normalisation; phone numbers masked in every output channel,
      enforced by a test rather than by convention
- [x] Deterministic idempotency key per (poll, participant, attempt)
- [x] Interruption mid-round is safe; re-running never dials anyone twice
- [x] No credentials in the repository or its history
- [x] Standard library only for the CLI and the dry run

## What has not happened

No real call has ever been placed from this repository. Everything demonstrated
runs against scripted answers, and the repository says so in its own
documentation rather than in this pull request only.
```

---

## 5. What is still blocking, and who owns it

Every one of these is a user action. None can be done from inside this run.

- **Repository is private.** The URL in section 3 exists only after publication.
- **No PR opened.** Requires a fork, a push and a submission.
- **Video not uploaded.** The file exists — `88.8 s`, rendered 2026-08-02 — but
  a public link requires an upload.
- **CALL-E account e-mail** for the submission form. It is never written into
  this repository.
- **Field test with real participants** remains the open item of phase 5. It
  needs credit on the CALL-E account; the balance stood at −0.05 USD after the
  one measured call.
