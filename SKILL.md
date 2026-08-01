---
name: ringedingeding
description: Find one date that works for a group by calling everybody on the phone, then merge the answers into one result — including who could not be reached. Use when somebody wants to agree a time with several people without a poll link, when a group has to be asked the same question by telephone, or when a scheduling round has to be caught up for people who did not answer. Runs as a dry run by default; real calls need an explicit typed confirmation.
---

# Ringedingeding — ask everyone, get one answer

You are arranging a date for somebody by telephone. Several people, one
question, one result. The tool does the calling; you do the interview.

**The first thing to know:** nothing you run here dials a telephone unless the
mode is `live`, and `live` needs a confirmation the person has to type. Every
command below is safe to run while you are still working out what they want.

## What this is for, and what it is not for

Use it when several people have to be asked the same thing and a link in a chat
group will not work — because they do not use it, do not answer it, or would
rather say it out loud.

Do not use it for anything medical, legal, financial or urgent. The tool refuses
those subjects at creation time and there is no override; if that is what the
person needs, tell them to call themselves.

## The interview

Ask in this order. Each answer fills exactly one field, and you can stop after
any of them — the state is on disk.

### 1. "Um was geht's? Wozu möchtest du einladen?"

The occasion. One line, in their words: *Familienessen am Wochenende*,
*Vereinssitzung*, *Grillen bei mir*.

```
ringedingeding project new --occasion "Familienessen am Wochenende" --organizer "Lukas"
```

`--organizer` is whose name the call is made in. It is spoken in the first
sentence of every call, so use the name the people being called will recognise.

The command prints a project id. Everything after this takes `--project <id>`;
a prefix is enough.

### 2. "An welchen Tagen könnte es sein? Und zu welcher Uhrzeit?"

Ask for the days first, then for **one standard set of times that applies to all
of them**. Most people have one — "abends, so ab sechs". Only ask about
exceptions if they bring them up.

```
ringedingeding project dates --project <id> \
    --day 2026-08-08 --day 2026-08-09 \
    --time 18:00-21:00
```

Repeat `--time` for several slots per day. For a date with no time of day at
all, use `--whole-day` and leave `--time` off.

The command prints the candidate dates numbered. Those numbers are what you use
later for `--favourite` and `--slot`.

### 3. "Wen möchtest du einladen?"

From the person's own address book. If it is empty, fill it first:

```
ringedingeding contact add --name "Anna" --phone "+15555550101"
ringedingeding contact list
```

Phone numbers must be E.164 — a `+`, the country code, then the number without
its leading zero. An unusable number is refused with an explanation; do not
guess a country code on somebody's behalf.

```
ringedingeding project people --project <id> Anna Ben Clara
```

**Somebody without a phone number is not an error.** They are added to the guest
list, not called, and they appear in the result as "could not be contacted at
all". Say that out loud — do not quietly drop them.

### 4. "Wie soll begrüßt und verabschiedet werden?"

Optional, and worth offering because it is the one part that sounds like them.

```
ringedingeding project wording --project <id> \
    --greeting "Schön, dass ich dich erreiche." \
    --closing "Danke dir, bis bald!"
```

These sentences are spoken **word for word**. The mandatory disclosure — that
this is an automated call on somebody's behalf — always comes first and cannot
be replaced.

### 5. Show them what would happen, before it happens

```
ringedingeding project plan --project <id> --show-task
```

This prints who would be called with masked numbers, who would not be and why,
the cost, the time, and **the complete order text as it would leave the
machine**. Show the person the order text before you offer to run anything. It
is the whole payload the voice agent gets.

### 6. Place the calls

Three modes. Read the difference out to the person; do not choose for them.

```
# invents answers locally so they can see the rest of the flow — no call, no cost
ringedingeding project call --project <id> --mode rehearsal

# replays the scripted answers of a bundled example project
ringedingeding project call --project <id> --mode script

# real telephones — needs the typed confirmation and CALLE_API_KEY
ringedingeding project call --project <id> --mode live
```

A rehearsal marks its round as **simulated** and every screen and report says
so. Never present rehearsal answers as if somebody had said them.

`--mode live` asks for a phrase to be typed into the terminal. You cannot type
it for them; if you are running unattended, tell them so and stop.

Each run only calls people who do not have an answer yet. Running it again
after somebody's number is added catches that one call up and dials nobody else.

### 7. "Wer kann wann?"

```
ringedingeding project board --project <id>
```

Read the four states back to the person and keep them apart:

| | means |
|---|---|
| **can** | said yes to that slot |
| **cannot** | said no to that slot |
| **silent** | answered the call but said nothing about that slot — **not a no** |
| **not reached** | `NO_ANSWER`, `BUSY`, `VOICEMAIL`, `DECLINED` — each different |
| **no phone** | never called at all; a number can be added and the call caught up |

**Never report a result as if the people who were not reached had agreed.**
"Four of six can make Saturday" is a different sentence from "everybody can make
Saturday", and the second one is false.

### 8. "Was ist dir wichtig?"

Three optional criteria. Ask, do not assume.

```
ringedingeding project criteria --project <id> \
    --favourite 1 --must Anna --count 4
```

The board then shows "2 von 3 criteria" per slot and names the best fit. The
score counts only the criteria that were actually set.

### 9. "Welcher Termin wird es?"

The person decides, not you. Offer the best fit and say what it costs — who
cannot make it.

```
ringedingeding project decide --project <id> --slot 1
```

### 10. "Wie sollen die anderen es erfahren?"

```
ringedingeding project invite --project <id> --show     # read the text first
ringedingeding project invite --project <id>            # prepare the round
ringedingeding project call --project <id> --round invitation --mode rehearsal
```

The default announcement says openly that not everybody could make it. Leave
that in. If they want their own wording, pass `--text`.

## Catching up on somebody

This is the most common follow-up and it has no special mode:

```
ringedingeding contact phone Erik "+15555550199"
ringedingeding project call --project <id> --mode rehearsal
```

The second command calls Erik and nobody else.

## The web interface

Same flow, same data, for somebody who would rather click:

```
pip install -e ".[web]"
ringedingeding web
```

It opens on `http://127.0.0.1:8765`. The calls run in the server, so the browser
window can be closed and reopened without ending a round.

## Rules you do not get to bend

1. **Dry run is the default.** If you are unsure what somebody wants, plan; do
   not call.
2. **You cannot confirm a live run on somebody's behalf.** The phrase is typed
   by a person, in a terminal or in the page.
3. **Never print a full phone number**, in any summary you write. The tool masks
   them; do not undo that by quoting a number the person gave you earlier.
4. **Refused subjects stay refused.** Medical, legal, financial, emergency —
   there is no flag.
5. **Report the gaps as loudly as the result.** Somebody who was not reached is
   not somebody who agreed.
6. **No hidden repetition.** There is no scheduler here. If a round should run
   again later, tell the person to run it again — do not build a loop.

## Where the data goes

The voice agent is not local. Everything in the order text is processed by
CALL-E / AiRudder in Singapore. Only the given name, the phone number and the
order text are sent — no history, no other participants, no photographs. Say
this before the first live call, not after it.
