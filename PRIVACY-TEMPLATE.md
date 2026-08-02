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

## Pre-publication checklist

- [ ] Every placeholder is replaced or removed.
- [ ] Controller, processor and joint-controller roles are documented.
- [ ] Legal bases exist for contact storage, invitations/calls, answers and transcription.
- [ ] Provider identity, location, retention, subprocessors, DPA and transfer safeguards are verified.
- [ ] Retention/deletion is implemented and tested across rows, photos, transcripts, logs and backups.
- [ ] Authentication and tenant authorization protect every page, action, photo and download.
- [ ] Call-layer Articles 13/14 information and withdrawal/objection handling are tested.
- [ ] A qualified lawyer has reviewed the completed deployment-specific notice and workflow.
