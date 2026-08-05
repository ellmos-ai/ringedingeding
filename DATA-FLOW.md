# Ringedingeding data flow

Status: code review refreshed on 2026-08-05. No live call was placed. This document describes the current implementation, not a planned deployment.

In the table, “leaves the computer” means leaving the machine that runs the Python process. If the app is remotely hosted, browser-to-host form uploads already disclose data to the app operator and its infrastructure even in fixture mode.

## Operating modes

- Fixture/dry-run calls remain in the local process and persist simulated outcomes to the same database used by the app.
- Live mode is separately confirmed and sends recipient data and the task to CALL-E.
- The web command binds to `127.0.0.1` by default, but accepts another host. Binding to loopback is not authentication or tenant isolation.

## Data switchboard

| Data | Collection and use | Storage | Retention implemented in code | Who can see it | Leaves the computer? | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Poll/project data: occasion, organizer, question, mode, language/region/locale, time slots, wording, criteria, decisions and notes | Creates and operates a scheduling or advice project | Shared SQLite file (`ringedingeding.db` by default) | No automatic expiry. Manual project deletion transactionally removes the project, FK-backed children, project-scoped `phrase`/`project_question` rows and the linked `poll`/`participant`/`answer` tree; reset clears only simulated answers | Every visitor able to reach the unauthenticated project routes while linked; database operators retain access until deletion | Not beyond the Python host in fixture mode; the relevant task and metadata leave in live mode | `ringedingeding/projects.py` (`delete_project`); `ringedingeding/web/app.py` (`project_delete`); regression `test_project_deletion_erases_private_call_data_and_scoped_text` |
| Contacts and groups: name, note, phone/email channel, group membership, source connector/external ID | Address book, invitee selection and group management | Shared SQLite tables `contact`, `contact_channel`, `contact_group` and related tables | Manual contact deletion transactionally removes the contact and participant copies carrying its name/phone, cascading to their answers/transcripts; group deletion removes its membership links. No scheduled retention was found | Every visitor able to reach the contacts/groups routes | Selected recipient name/phone leave for CALL-E in live mode | `ringedingeding/projects.py` (`delete_contact`, `delete_group`); regression `test_contact_deletion_erases_copied_number_name_and_interview` |
| Contact photo | Optional upload and contact display | Photo bytes and MIME type in the shared SQLite `contact` row; uploads are capped at 2 MB by the web route | Until manual contact deletion or replacement; no automatic expiry found | The unauthenticated photo route returns it by contact ID | No third-party transfer by this code | `ringedingeding/projects.py:139-150, 680-693`; `ringedingeding/web/app.py:952-1024` |
| Participant reference, name and raw E.164 phone number | Defines call recipients and call state. If no explicit reference is supplied, the reference is derived from the participant name | Shared `participant` table | Removed when its project or source contact is manually deleted; answer rows cascade with it. No automatic expiry exists | App process and visitors to shared project/result views | **Yes in live mode:** raw number, task, poll ID and potentially identifying name-derived participant reference are sent to CALL-E | `ringedingeding/store.py` (`participant`, `answer` schema); `ringedingeding/projects.py` (`delete_project`, `delete_contact`) |
| Live call task: participant given name by default, organizer, questions/slots, opening/closing, urgency, locale, raw phone, poll ID and participant reference | Starts a CALL-E call and maps the returned result to the participant | Task is sent to CALL-E; local run IDs and returned outcome are persisted | Provider-side retention is not specified in this repository; local records have no automatic expiry | Participant, CALL-E, app process and visitors to shared result views | **Yes, live mode only:** to the configured URL (default HTTPS); the code does not enforce an HTTPS scheme for overrides | `ringedingeding/runner.py:61-115`; `ringedingeding/schemas.py:394-429`; `ringedingeding/transports/base.py:36-64`; `ringedingeding/transports/calle.py` |
| Answer material: call status, structured JSON, raw answer text, phone-masked transcript text, receive time, run ID and error | Shows and aggregates responses | Shared SQLite `answer` table | Reset clears answers only for simulated polls. Manual project deletion removes the complete linked call tree; manual contact deletion removes that contact's participant copies and cascading answers/transcripts. No general automatic expiry exists | Every visitor able to reach the shared project/board/live routes while linked; database operators retain access until deletion | Returned from CALL-E in live mode; no additional transfer at local save | `ringedingeding/store.py` (`answer` schema); `ringedingeding/projects.py` (`delete_project`, `delete_contact`); deletion regressions in `tests/test_projects.py` |
| Calendar export | Builds `.ics` and `.xlsx` views of selected project entries | Generated in memory and returned as a browser download; no server-side export file write was found | Browser/download location is controlled by the user | Visitor requesting the export | No third-party transfer by this code; later import into another calendar is outside the app | `ringedingeding/web/app.py:879-929`; calendar helpers used there |
| Language preference | Selects interface language | `rd_lang` cookie | One year | Browser and app host | Sent with requests to the app host | `ringedingeding/web/app.py:213-220` |
| CALL-E API key and base URL | Authenticates live API requests | One process environment, project `.env`, or repository-level `config.local.json`; the settings route can write the latter | Until changed/deleted outside the database | Server process; any visitor can replace the shared key through the current unauthenticated settings route | **Yes, live mode only:** used as the authorization credential | `ringedingeding/calle_credentials.py:18-35, 86-178`; `ringedingeding/web/app.py:222-249` |
| Running-job state | Coordinates a project run and SSE updates | One process-wide `JobRegistry` attached to the app | Process lifetime | Visitors to the associated unauthenticated job routes | No transfer by itself | `ringedingeding/web/app.py:122-153, 540-691`; `ringedingeding/web/jobs.py` |

## Important boundaries

- The database contains raw phone numbers and phone-masked transcript contents. Masking phone-like strings does not anonymise the rest of a conversation.
- Project/contact IDs are references, not authorization. The route set has no user identity or ownership check.
- The repository text mentions a service infrastructure location, but the executable adapter's default is `https://api.heycall-e.com`. Corporate identity, actual processing countries, subprocessors, provider retention and transfer safeguards must be verified from current contracts; this review does not infer them.
- Browser, reverse-proxy, operating-system and infrastructure logs are deployment facts and must be added to the final data inventory and privacy notice.

See `HOST-READINESS.md` for the multi-user gap and `PRIVACY-TEMPLATE.md` for an operator-owned notice template.

## Server modes (added 2026-08-02)

> **On the name.** In English this hosting pattern is called *piggyback*:
> the application rides on infrastructure it does not own. The literal mode
> values are still spelled `huckepack-gift` and `huckepack-only-host` — that is
> the German working title the code was built under, and it is what an operator
> actually types. Prose says piggyback; configuration says huckepack.

The table above describes `local`, which is what an unconfigured installation is. `RINGEDINGEDING_SERVER_MODE` selects one of four modes (`ringedingeding/server_mode.py:25-76`); an unknown value is refused by name (`:78-90`), and the resolved mode is held for the process, so no request can switch it (`:98-113`).

| Mode | Where the database is | Whose key pays | Accounts |
| --- | --- | --- | --- |
| `local` (default) | SQLite file on the host, as before | environment, `.env` or `config.local.json` | none |
| `huckepack-gift` | the visitor's browser | the host's | none |
| `huckepack-only-host` | the visitor's browser | the visitor's, per request | none |
| `pay-membership` | — | — | would be required; **not built**, every page answers 503 (`ringedingeding/huckepack_web.py:47-50, 145-155`) |

### What changes in a piggyback mode

| Data | Collection and use | Storage | Retention implemented in code | Who can see it | Leaves the computer? | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Projects, contacts, participants, answers, transcripts — the whole database | Unchanged in purpose; the same schema and the same SQL | **Not on the host.** The durable copy is a SQLite file in the visitor's browser (IndexedDB); the host holds a copy in memory for the length of a browser session. Not even the database directory is created | Memory only: dropped after two hours without use, on session delete, and on process exit | The one browser session that supplied the session token | The database bytes travel between browser and host on load and after each change; they are never written to the host's disk | `ringedingeding/huckepack_storage.py:58-72, 74-163, 191-202`; `ringedingeding/store.py:107-120`; test `test_a_huckepack_mode_creates_neither_file_nor_directory` |
| Session token | Addresses the in-memory database of one browser | Browser `localStorage`, sent as `X-Huckepack-Session` | Until the visitor deletes the data | Browser and host process | Sent with every request | `ringedingeding/huckepack_web.py:27-40` |
| Session token and visitor key **inside a running round** | A round runs in a background thread and outlives the request that started it | Passed as arguments into the job and re-bound there; nothing is stored | Thread lifetime | The job thread | No | `ringedingeding/web/jobs.py:126-170`; `ringedingeding/web/app.py:585-600`; test `test_a_round_carries_session_and_key_into_its_thread` |
| Visitor's CALL-E key (`huckepack-only-host` only) | Authenticates that visitor's own live calls | **Browser `localStorage`**, displayed masked to the last four characters | Until the visitor presses "forget"; on the host only for the duration of one request or one round | The visitor's browser; the host process while the round runs; CALL-E | Sent as the `X-Calle-Key` request header, then on to CALL-E | `ringedingeding/huckepack_key.py:29-105`; `ringedingeding/service.py:604-616`; `ringedingeding/transports/calle.py:126-140` |
| Key on the **settings page** | — | **Refused.** `POST /settings` answers 409 in only-host instead of writing `config.local.json` | — | — | No | `ringedingeding/web/app.py:243-258`; test `test_the_settings_page_refuses_to_store_a_key_in_only_host` |
| Export / import file | The visitor's own backup and their way to another device | A `.sqlite` file wherever the visitor puts it | The visitor decides | Whoever can read that file — **it is the unmasked database, including raw phone numbers** | Leaves only on the visitor's own instruction | `ringedingeding/web/static/huckepack.js` (`exportData`, `importData`) |
| Receipt file | Optional file for a finished result | The visitor's file system — a folder chosen once, otherwise the download folder | The visitor's own file | Whoever can read that folder | No transfer | `ringedingeding/web/static/huckepack.js` (`saveReceipt`, `writeFile`) |

### Boundaries that remain

- **The row about live calls stays valid word for word.** Participant name, raw number and task still go to CALL-E, and real people are still called. The mode changes where records are kept, not what is transmitted.
- **The exported file carries raw phone numbers.** The database holds them because you cannot dial a mask; an export therefore is an address book. That belongs in the privacy notice, and in what the interface tells the visitor.
- **A cleared browser is a total loss.** No copy exists at the host. Export is a condition of the pattern, not a convenience.
- **The unauthenticated route set is unchanged** — but in a piggyback mode there is no shared database behind it: a visitor without the session token reaches an empty one. That removes the cross-visitor exposure `HOST-READINESS.md` describes; it does not add authentication.
- **`local` is unchanged.** One additional script tag in `base.html`, which in `local` mode does nothing but offer the receipt download.
