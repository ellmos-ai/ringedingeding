# Ringedingeding

**Ask everyone, get one answer.**

Ask one question to several people by telephone and merge the replies into a
single result. Built on [CALL-E](https://github.com/CALLE-AI/call-e-integrations).

Anyone who has tried to arrange a family dinner knows the problem: three people
reply immediately, two never do, and one calls back and tells you out loud. A
poll link does not fix that, because the people who do not answer links are
exactly the people whose answer you are missing.

So this calls them, asks the question, and puts the answers into one table —
including, prominently, the people it could not reach.

```
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
NOTE     : Based on 4 of 6 participants. not reached: Erik (NO_ANSWER),
           Frida (BUSY). These are not counted as indifferent.
```

(Real output of `ringedingeding demo`, line-wrapped in the NOTE only.)

That last line is the point of the whole program. An intersection over four of
six people is a different fact from an intersection over six of six, and it has
to look different.

## What makes this different from other CALL-E integrations

Every other integration in the ecosystem calls **one** person. This one asks
**several people the same question and merges the answers** — which is what the
CALL-E batch API and its per-recipient result schema were built for.

## Install

Python 3.11 or newer. No third-party dependencies at all — the dry run has to
work on a machine with nothing installed and no network.

```bash
git clone <this repo>
cd ringedingeding
pip install -e .
```

Or run it straight from the source tree without installing:

```bash
python -m ringedingeding demo
```

## Try it without an account

`demo` runs three complete polls against scripted answers. No account, no
network, no telephone:

```bash
ringedingeding demo
```

It plays through a scheduling question, a decision between two options with an
abstention and a refusal, and an open question — and writes a Markdown report
for each into `out/`.

## Use it for real

### 1. Create a poll

```bash
ringedingeding create \
  --question "When can you make it this weekend?" \
  --kind slot \
  --organizer "Lukas" \
  --slot "Sat 14-18" --slot "Sat 18-21" --slot "Sun 10-14" \
  --participant "Anna=+15555550100" \
  --participant "Ben=+15555550101"
```

`--kind` is one of:

| kind     | question                        | result                         |
|----------|---------------------------------|--------------------------------|
| `slot`   | "When can you make it?"         | intersection, plus who cannot  |
| `choice` | "Photo book or voucher?"        | tally, plus abstentions        |
| `open`   | "What should we do about X?"    | answers quoted, never summarised |

Numbers must be E.164 (`+49…`). They are validated before storage and again
before dialling.

### 2. Look at what would happen

```bash
ringedingeding plan --poll poll_ab12cd34ef
```

This prints who would be called, the exact instructions the voice agent would
receive, the JSON schema it would have to fill in, the estimated cost and the
estimated duration. It dials nothing.

### 3. Place the calls

```bash
ringedingeding run --poll poll_ab12cd34ef --markdown result.md
```

Without `--live` this refuses to run against real people — there is nothing
honest to simulate a real person's answer with. Add `--live` and type the
confirmation when asked:

```bash
export CALLE_API_KEY="…"
ringedingeding run --poll poll_ab12cd34ef --live --markdown result.md
```

### 4. Read the result again later

```bash
ringedingeding report --poll poll_ab12cd34ef --markdown result.md
```

### Commands

| command    | what it does                                        |
|------------|-----------------------------------------------------|
| `demo`     | run every bundled fixture end to end (dry run)      |
| `fixtures` | list the bundled fixtures                           |
| `create`   | create a poll                                       |
| `list`     | list stored polls and their progress                |
| `plan`     | show who would be called, and with what             |
| `run`      | place the calls (dry run unless `--live`)           |
| `report`   | show or export the merged result                    |

Useful flags for `run`: `--serial` (one API request per person instead of one
batch), `--concurrency N`, `--retry` (call people who already answered),
`--no-names` (send no name at all), `--fresh` (drop earlier answers).

## Where your data goes — read this before using `--live`

**The voice agent does not run on your machine.** It runs at CALL-E / AiRudder
in **Singapore**. Everything placed into a call instruction leaves your computer
and is processed there.

What is sent per call:

* the **question**, and the options or time slots you defined,
* the **organizer's name**, so the call can say whose behalf it is on,
* the participant's **first name only** — never the full name,
* the participant's **telephone number**, because you cannot dial a mask,
* the participant's local reference id and the poll id, which mean nothing
  outside your own database,
* the result schema the agent must fill in.

What is **not** sent: any other participant, anybody else's answer, previous
polls, full names, notes, or anything kept "just in case". `--no-names` drops
the first name too.

What comes **back** and is stored locally: the filled-in schema, a short
summary and — when the service provides one — the transcript of the
conversation. The transcript is kept deliberately: the voice agent *interprets*
free answers, so without the wording underneath, its categorisation could never
be checked. Everything stays in a local SQLite file (`ringedingeding.db`) which
is git-ignored.

Under the GDPR you are the controller for this processing. Tell people
beforehand, and only call people who expect it.

## Safety

These are not settings. They are how the program is built.

* **The dry run is the default.** `--live` is the only path to a telephone, and
  it is not enough on its own: you also have to type `CALL THEM`. For
  unattended runs both `RINGEDINGEDING_LIVE_CONFIRM=CALL THEM` in the
  environment **and** `--yes` are required. There is no silent live mode.
* **The bundled example numbers can never ring.** Running `--live` against a
  shipped fixture is refused by name.
* **Numbers never appear in output.** Not in the console, the Markdown report,
  the logs or an error message — including text that came back from the call
  side, which is scrubbed on the way out.
* **The call discloses itself in its first sentence**, unprompted, quoting the
  organizer's name. Not on request — from the start.
* **A refusal is a result.** The instructions forbid persuading, asking twice,
  or offering reasons.
* **Medical, legal, financial and emergency questions are refused** at creation
  time, so the number is never even stored. There is no override flag.
* **Nobody is called twice for the same intent.** Every call carries a
  deterministic `Idempotency-Key`, and a participant with an answer is skipped
  unless you pass `--retry`.
* **No hidden schedule.** No daemon, no retry loop, no background timer. One
  invocation makes at most one attempt per person and exits. If you want it
  repeated, your Task Scheduler or cron does it, where you can see it.
* **Credentials come from the environment only** (`CALLE_API_KEY`), never from
  a file, a flag, or a commit.

### If you interrupt it

`Ctrl-C` stops **new** calls from starting; calls already in progress are
allowed to finish, because hanging up on somebody mid-sentence is worse than
waiting a moment. A second `Ctrl-C` gives up immediately.

Either way the state on disk stays consistent: every answer is written the
moment it arrives, so what finished is saved and what never started stays
`PENDING`. Run the same command again and it picks up exactly there. The exit
code is `130`.

| exit code | meaning                                   |
|-----------|-------------------------------------------|
| 0         | success                                   |
| 1         | an error                                  |
| 2         | refused: sensitive content                |
| 3         | refused: live calling blocked or unconfirmed |
| 130       | interrupted; state on disk is consistent  |

## What it costs, and how long it takes

CALL-E charges **per call, not per minute** — about $0.05, with 20 free. Six
people cost about 30 cents whatever they say.

Time behaves differently. Roughly **40 seconds of every call is dialling and
connecting** before a word is spoken, measured and independent of how long
anybody talks. Six people one after another therefore take around a quarter of
an hour, most of it silence. `plan` prints both figures.

Calls can be placed one batch request at a time (default) or one request per
person (`--serial`), and `--concurrency N` fans out. **Whether CALL-E actually
runs calls in parallel has not been verified**, so the code supports both and
the estimate tells you which number to trust.

## While a call is running

A live run prints the conversation as it happens:

```
  dialing  anna (+49*****01)
     00:00:00.000 --     | Call is ringing.
     00:00:04.000 --     | Call connected.
     00:00:05.000 bot    | Hello, this is an automated assistant on behalf of Lukas.
     00:00:07.000 callee | Yes, go ahead.
  <- anna: COMPLETED
```

(Shape of the output, produced from a replayed `activity` payload. The
timestamps and wording of a real call will differ.)

This comes from the API's `activity` field, not from `status`. The status field
is useless as a progress indicator: it was measured sitting on `PREPARING`
throughout an entire conversation and only moved to `COMPLETED` about
24 seconds *after* the call had ended.

Speech recognition streams a rough transcription and corrects it a fraction of
a second later, so the newest line is held back for one poll rather than shown
and then contradicted.

## How the conversation is steered

CALL-E has no field for tone, persona or script. There are exactly two levers,
and the second is the strong one:

1. the `task` free text — the instructions read above,
2. the **`recipient_result_schema`** — the JSON the agent must fill in.

Whatever the schema demands, the agent has to find out during the call. So the
schema is designed first and the prose written to match it. Every schema here
carries three fields that exist purely to keep the merge honest:

* `reachable` — false when somebody answered, but not the person we wanted,
* `refused` — true when the person was reached and chose not to answer,
* `note` / `condition` — the qualifier a tally would otherwise flatten
  ("yes, but only under 50 euros").

One measured detail shapes the wording: **text in quotation marks is spoken
verbatim**, character for character, while text outside quotation marks is
rephrased and even extended by the planning agent. So the question itself and
the sentence disclosing that this is an automated call are quoted; the rest is
guidance on purpose.

## How the answers are merged

Two rules, both of which exist to stop the program inventing agreement:

**A person who was not reached is never counted as "doesn't mind."** No
aggregate is computed over "everyone". It is computed over the people who
actually answered, and everyone else is reported by name with their concrete
status — `NO_ANSWER`, `BUSY`, `DECLINED` and `VOICEMAIL` are four different
pieces of news and stay four different pieces of news.

**Silence about a slot is not a "no."** If somebody was asked about Saturday
and Sunday and only said "Saturday works", Sunday is listed as *unclear*, not
as *cannot*.

Answers outside the offered options, abstentions and conditions attached to a
vote are all reported separately rather than being folded into the tally.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

The whole suite runs without an account, without a network and without dialling
anything. Where the live path is exercised, it stops at a guard before any
socket is opened.

## Project layout

```
ringedingeding/
  cli.py            commands, the confirmation gate, exit codes
  models.py         polls, participants, call statuses, buckets
  schemas.py        result schemas and the spoken instructions
  merge.py          many answers into one result
  render.py         console tables and the Markdown report
  runner.py         poll -> calls -> stored answers
  store.py          SQLite
  safety.py         refused categories, live gate, idempotency
  phone.py          E.164 validation and masking
  activity.py       reading a call live, and its transcript
  timings.py        measured timing of the service
  transports/
    fixture.py      the dry run
    calle.py        the only code that can dial
  fixtures/         scripted polls for the dry run
```

`FINDINGS.md` records what was measured against the real service and where that
contradicts the documentation. `EVIDENCE.md` records what was actually executed
in this repository, including what was not.

## Licence

MIT.
