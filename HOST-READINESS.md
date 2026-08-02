# Ringedingeding host-readiness finding

## Verdict

**Not ready for untrusted multi-user hosting.** The source explicitly implements a local app without login. All visitors share the address book, projects, answer transcripts, job registry, database and CALL-E credential.

## Evidence

| Question | Current implementation | Consequence | Evidence |
| --- | --- | --- | --- |
| Accounts or authenticated sessions? | None. The code comments that there is no login; the only cookie is a language preference. | There is no authenticated user or owner for authorization. | `ringedingeding/web/app.py:19-27, 122-220` |
| Per-user state? | No. One `Store`, project service and `JobRegistry` are attached to the app. | All project/job state is process-wide. | `ringedingeding/web/app.py:122-153` |
| Per-user database? | No. One SQLite path, `ringedingeding.db` by default, backs polls, contacts, projects and answers. | Every visitor shares one namespace and one address book. | `ringedingeding/store.py:32-107`; `ringedingeding/projects.py:139-263` |
| Object-level authorization? | No ownership checks are present on project, contact, group, calendar, photo, settings or run routes. | A visitor can read or mutate shared data by using the routes/IDs. | `ringedingeding/web/app.py:195-1049` |
| Can each user provide their own API key? | No. Resolution selects one process/repository key, and `/settings` writes one repository-level `config.local.json`. | All users share quota, billing and authority; any visitor can replace the credential in the current UI. | `ringedingeding/calle_credentials.py:86-178`; `ringedingeding/web/app.py:222-249` |
| Safe retention controls? | No automatic policy. Project deletion leaves phrase/question rows and the separate poll/participant/answer tree, reset clears only simulated answers, and contact deletion does not remove copied participant data. | Wording/questions, raw phones and live answers/transcripts can remain orphaned; current deletion controls cannot support a truthful retention promise. | `ringedingeding/store.py`; `ringedingeding/projects.py`; `ringedingeding/web/app.py:1028-1049` |
| Network exposure? | CLI default is `127.0.0.1`, but `--host` accepts another value. Outbound `CALLE_BASE_URL` overrides are not restricted to HTTPS. | The app is easy to expose while remaining unauthenticated; an unsafe override could also remove transport encryption. | `ringedingeding/cli.py:634-636`; `ringedingeding/web/app.py:1151-1157`; `ringedingeding/calle_credentials.py`; `ringedingeding/transports/calle.py` |

## Required work before multi-user hosting

1. Add accounts, secure authenticated sessions and explicit user/admin roles.
2. Add a tenant/user owner to every poll, participant, answer, contact, group, project, slot, decision and connector record. Enforce object-level authorization in every route and download.
3. Isolate in-process jobs by tenant, move durable execution to an authenticated queue, and design concurrency/idempotency for multiple workers.
4. Replace the global settings credential with per-tenant encrypted secrets in a proper secret store, or reserve calls for an operator-only account. Add rotation, deletion, quota and billing controls. Remove public credential mutation.
5. Implement and test retention, withdrawal/objection handling, deletion and export across relational rows, photos, transcripts, logs and backups.
6. Add CSRF protection, secure cookie settings, TLS, rate limits, upload/content hardening, audit events and monitoring. Enforce HTTPS for every outbound CALL-E base URL. Perform a separate security review.
7. Verify and document CALL-E's contracting entity, roles, processing countries, subprocessors, retention and international-transfer safeguards.
8. Complete the controller/processor allocation, legal bases, processor agreements, call-layer Articles 13/14 information and any Chapter V transfer mechanism before launch.

The privacy notice template is only one launch artifact. Completing it does not create tenant isolation or make live calls lawful.
