# Privacy notice template — Ringedingeding

> **Template only — adaptation required.** This is not a deployable privacy notice and is not legal advice. The operator must replace every `[REPLACE: ...]` marker, remove inapplicable options, verify provider facts and obtain a case-specific legal review before processing real data.

Last updated: `[REPLACE: date]`

## 1. Controller

`[REPLACE: legal name of the party deciding why and how Ringedingeding is used]`<br>
`[REPLACE: postal address]`<br>
Email: `[REPLACE: privacy contact]`<br>
Data protection officer, if applicable: `[REPLACE or remove]`

Infrastructure hosting provider: `[REPLACE: provider, address and role; do not automatically label the infrastructure host as controller]`

## 2. Scope and people affected

This notice covers `[REPLACE: deployment URL and version]`. It may concern users/organizers, saved contacts, group members, invitees, survey/advice participants and people included in uploaded contact photos or notes.

## 3. Processing purposes and legal bases

| Purpose | Data used | Legal basis | Required or optional / consequence |
| --- | --- | --- | --- |
| Maintain contacts and groups | Name, notes, phone/email channel, memberships, photo and source reference | `[REPLACE: exact Article 6 basis and reasoning]` | `[REPLACE]` |
| Create a scheduling/advice project | Occasion, organizer, questions, slots, wording, invitees, criteria and decisions | `[REPLACE]` | `[REPLACE]` |
| Place automated calls, if enabled | Recipient phone, given name by default, locale and the call task | `[REPLACE]` | `[REPLACE]` |
| Receive and present answers | Status, structured/raw answer, transcript, run ID and errors | `[REPLACE]` | `[REPLACE]` |
| Produce calendar downloads | Selected project/date/decision information | `[REPLACE]` | `[REPLACE]` |
| Secure and operate the service | `[REPLACE: verified server, security and audit log fields]` | `[REPLACE]` | `[REPLACE]` |

Do not use consent as a generic fallback. If consent is selected, document how it is informed, specific, voluntary, evidenced and withdrawn. Assess call admissibility and transcription separately.

## 4. Fixture and live modes

- **Fixture/dry-run:** no call provider is contacted; simulated results are still written to the application's shared SQLite database.
- **Live mode:** the app sends the recipient phone number, call task, locale, poll ID and participant reference to the configured CALL-E endpoint and receives result/transcript data. A participant reference can be derived from the person's name and must not be assumed anonymous.

`[REPLACE: state which modes this deployment exposes and the visible user controls]`

## 5. Recipients, processors and transfers

| Recipient/category | Data and purpose | Role and location | Safeguard/contract |
| --- | --- | --- | --- |
| `[REPLACE: infrastructure host]` | `[REPLACE]` | `[REPLACE]` | `[REPLACE: Article 28 agreement if applicable]` |
| `[REPLACE: CALL-E contracting entity and subprocessors, or remove live mode]` | Phone, given name/task, locale, metadata and returned call material | `[REPLACE: verified role and processing countries]` | `[REPLACE: DPA and, if needed, Chapter V mechanism]` |
| Call recipient | Hears the call wording and organizer/project context | Data subject/recipient; `[REPLACE: role analysis]` | `[REPLACE]` |
| Calendar service chosen by the user after download | Only if the user later imports an export | Outside this application's direct transfer; `[REPLACE if an integration is added]` | `[REPLACE]` |

The endpoint in source code does not prove provider identity, actual processing countries, subprocessors, retention or safeguards. Verify all of them from current contracts.

## 6. Storage and deletion

The current application stores contacts, channels, photos, projects, participant phone numbers, answers and transcripts in one SQLite database. It has no automatic expiry. Its current project deletion leaves phrase/question rows and the separate poll/participant/answer records, reset clears only simulated answers, and contact deletion does not remove participant copies. A host must repair and test these deletion paths before promising any period below.

| Record | Period or deletion criterion |
| --- | --- |
| Contacts, channels, groups and photos | `[REPLACE; implement it in code]` |
| Projects, invitees and decisions | `[REPLACE; implement it in code]` |
| Raw phone numbers, answers and transcripts | `[REPLACE; implement it in code]` |
| Generated downloads on the user's device | `[REPLACE: user instruction; app does not control the device copy]` |
| Server/security logs | `[REPLACE after checking infrastructure]` |
| Backups | `[REPLACE: cycle and irreversible deletion point]` |
| Provider-side call data | `[REPLACE from verified contracts]` |

## 7. Browser storage

The current code sets an `rd_lang` language cookie for one year. `[REPLACE: list authentication, reverse-proxy, consent, analytics or other deployed cookies/storage, or state that none are used after verification]`.

## 8. Source of contact data and information during calls

Contact data comes from `[REPLACE: organizer entry, imports/connectors and any public sources]`. Where the GDPR applies, data obtained from another person/source require an Article 14 analysis, normally with information no later than the first communication when the data are used to contact the person. Answers collected directly in the call require an Article 13 analysis. Provide a concise first layer during the call and the full notice at `[REPLACE: URL/non-digital channel]`, as confirmed by legal review.

## 9. Automated decisions

Ringedingeding aggregates availability/advice and can apply configured criteria to a decision board. `[REPLACE: explain logic, significance and effects, and state whether any Article 22 decision occurs. Do not assume inapplicability.]`

## 10. Rights and complaints

Subject to the legal conditions, individuals may have rights of access, rectification, erasure, restriction, objection and data portability, and may withdraw consent without affecting prior processing. Requests: `[REPLACE: channel and identity-verification process]`.

Complaint authority: `[REPLACE: competent supervisory authority, address and URL]`.

## 11. Changes

We will update this notice when purposes, data, providers, retention or architecture change. Previous versions: `[REPLACE: location]`.

## Annex A — Server modes (huckepack)

> **Still a template.** Pick the one block that matches `RINGEDINGEDING_SERVER_MODE` on the deployed installation, delete the others, and keep replacing every marker. Choosing a mode changes what has to be written here; it does not remove the need to write it.

**Which mode is deployed:** `[REPLACE: local | huckepack-gift | huckepack-only-host]` — verifiable at `[REPLACE: deployment URL]/huckepack/mode`.

### A.1 If the mode is `local`

Sections 1–11 above apply unchanged. The database is a file on the host; the operator is the controller for everything in it, including the address book.

### A.2 If the mode is `huckepack-gift` or `huckepack-only-host`

**Replace section 6 (Storage and deletion) with:**

> This installation keeps no database of your projects. Contacts, groups, participants, answers and transcripts are stored by your browser on your device. While you are using the service, a copy is held in this server's working memory so that the same queries can run, and for as long as a round of calls is running; it is discarded at the latest `[REPLACE: confirm SESSION_TTL_SECONDS in ringedingeding/huckepack_storage.py]` after your last request, when you press "delete data", and whenever the server process restarts. No file is written on the server — not even the directory is created.
>
> Because of that, deleting your browser data deletes everything, and we cannot restore it. Use "back up data" to keep a copy. **That file is your address book**: it contains the telephone numbers in full, because a number cannot be dialled from a mask. Store it accordingly.
>
> `[REPLACE: server, proxy and infrastructure logs exist regardless of where the database is and must be described here after verification]`

**Replace section 7 (Browser storage) with:**

| Name | Purpose | Lifetime |
| --- | --- | --- |
| `rd_lang` cookie | Interface language | One year |
| `huckepack.session` (local storage) | Identifies your working copy on the server while you use it | Until you delete your data |
| `huckepack` database (IndexedDB) | **Your data**: projects, contacts, participants, answers, transcripts, plus the receipt folder you chose | Until you delete it |
| `huckepack.calle-key` (local storage) | *Only in `huckepack-only-host`:* your own CALL-E key | Until you press "forget" |

Under `[REPLACE: applicable national implementation of Article 5(3) ePrivacy Directive — in Germany § 25 TDDDG]`, storage on the user's device needs consent unless it is strictly necessary for a service the user explicitly requested. `[REPLACE: assess each row; the working position that these entries carry the user's own data for the function the user asked for is an argument, not a finding.]`

**Keep in full and read again:** sections 8 (source of contact data, information during calls), 9 (automated decisions) and 10 (rights). They concern the **people who are called** — whose numbers the organiser supplied and whose answers are recorded. Where those records are stored does not change their position, and this is the point most easily lost.

**One thing does change for them, and not in their favour:** rights requests. If the operator holds no copy, the operator cannot look anything up, correct anything or delete anything. `[REPLACE: describe who a called person turns to, and how the organiser is reached. Do not write "not applicable" — a right that no one can exercise is a problem to solve, not a section to delete.]`

### A.3 Only in `huckepack-only-host` — the visitor's own key

> You enter your own CALL-E key. It is stored by your browser, shown only by its last four characters, and sent to this server with a run so the calls can be placed in your name. This server does not store it, does not write it to a log and does not keep it after the round. The settings page refuses to save a key in this mode. Calls are billed to your own account with `[REPLACE: CALL-E contracting entity]`.

`[REPLACE: state who is controller for those calls under the deployed setup. Passing a key through does not by itself settle the role question — the operator still decides how the call is composed and what is asked.]`

### A.4 What the modes do not change

- Real people are called, and they answer.
- Transcripts contain their words.
- The organiser supplied their numbers, usually without those people being asked first — section 8 exists for that reason.
- Server, reverse-proxy and infrastructure logs are a fact of the deployment, not of the mode.

## Pre-publication checklist

- [ ] Every placeholder is replaced or removed.
- [ ] Controller, processor and joint-controller roles are documented.
- [ ] Legal bases exist for contact storage, invitations/calls, answers and transcription.
- [ ] Provider identity, location, retention, subprocessors, DPA and transfer safeguards are verified.
- [ ] Retention/deletion is implemented and tested across rows, photos, transcripts, logs and backups.
- [ ] Authentication and tenant authorization protect every page, action, photo and download.
- [ ] Call-layer Articles 13/14 information and withdrawal/objection handling are tested.
- [ ] A qualified lawyer has reviewed the completed deployment-specific notice and workflow.
- [ ] The deployed `RINGEDINGEDING_SERVER_MODE` is stated, and only the matching block of Annex A remains.
- [ ] In a huckepack mode: it has been checked on the running installation that no database file appears.
- [ ] In `huckepack-only-host`: the key is nowhere in logs, in the database, in `config.local.json` or in a response.
- [ ] It is written down how a called person exercises their rights when the operator holds no copy.
- [ ] Device-storage consent has been assessed for each browser entry in Annex A.2.
