# Audit report: privacy and hosting — 2026-08-02

> **A record, not a current state.** This is the report of an examination
> carried out on **2 August 2026**. It describes the applications as they were
> on that day — before the rebuild it caused. It is kept here because an
> examination that actually happened is worth more than a spotless document
> with no history.
>
> **What became of the findings is in the protection concept:**
> [`PROTECTION-CONCEPT.md`](../../PROTECTION-CONCEPT.md) — every finding appears
> there with its answer. Today's data flow is in [`DATA-FLOW.md`](../../DATA-FLOW.md).
>
> Cleaned for publication: local file paths of the examining machine were
> replaced by a description. Otherwise unchanged.
>
> **Translation of the German original**
> ([`2026-08-02-datenschutzpruefung.md`](2026-08-02-datenschutzpruefung.md)),
> which examines German and EU law and governs in case of doubt.

---

Date: 2 August 2026<br>
Subject of examination: `hungrycall`, `ringedingeding`, `researchcall`

> **Legal first assessment with sources — not legal advice.** This is
> AI-assisted first orientation and no substitute for individual examination by
> an admitted lawyer. The actual controller, purpose, group of people involved,
> provider contract, hosting location and questionnaire can change the result.
> No deadline monitoring; in case of official mail, a warning letter or any
> running deadline, obtain qualified legal advice immediately.

## The result in one sentence

The user's assumption is only partly right: processing exclusively for personal
or family purposes by a natural person **can** fall under the household
exemption, but not because the file sits on their own PC. Even with a hosted
service the private end user's activity may fall under it in a given case;
operators and hosts remain covered for their own processing. None of the three
applications is technically host-ready.

## Findings at a glance

| Project | Local private use | Do data leave the machine? | Multi-user capable? | Hosting finding |
| --- | --- | --- | --- | --- |
| HungryCall | A purely private ordering or reservation can in principle fall under the household exemption. Purpose and actual use decide. | With remote hosting always browser → app host. Beyond that, even the ordinary non-test search uses Nominatim/Overpass; maps load OSM tiles. Live additionally CALL-E and the restaurant. | No: shared process state, one SQLite file, no accounts or authorisation, one CALL-E key | **Do not publish; high risk.** History, result and transcript would be visible across visitors. |
| Ringedingeding | Purely private family or friend coordination can in principle be covered. Club, organisational, professional or commercial use must be assessed separately and is regularly not "exclusively" private or familial. | With purely local fixture runs no provider transfer; with remote hosting always browser → app host. Live additionally phone number, name/task, reference and answers/transcript to CALL-E and to the people called. | No: shared contacts, photos, projects, transcripts, jobs, SQLite file and a key that the unprotected settings route can replace | **Do not publish; high risk.** |
| ResearchCall | A planned survey for scientific, institutional, professional or publication-related purposes is regularly not an exclusively personal or family activity. | With purely local workbench runs no provider transfer; with remote hosting always browser → app host. The live CLI additionally sends phone number, questionnaire task, schema, language and sample ID to CALL-E. | No: one shared workspace and one shared workbench database; web without login. Live only separately via CLI with one process key | **Do not publish; high risk, possibly higher with extensive Article 9 data.** Research law/ethics and possibly a DPIA to be examined additionally. |

These are risk assessments for the contemplated publication in the **present**
state, not a finding that a data protection breach has already occurred.

## Examination of the user's assumption

The starting thesis, normalised:

> "If the apps are used privately, the user stores the data on their PC — then
> no privacy notice is needed. But if someone hosted it, that person would have
> to make one."

### What is right about it

Art. 2(2)(c) GDPR excludes processing by natural persons in the course of
**exclusively personal or household activities**. Recital 18 names as possible
examples private correspondence, address books, social networking and online
activity within that private or family setting. Where a particular user really
does fall entirely under this exemption, the GDPR obligations do not apply to
them for that particular processing.

### What is not right about it

1. **The storage location does not decide.** Local automated storage is
   processing within the meaning of Art. 2(1) and Art. 4(2) GDPR. The exemption
   depends on the purpose and context of the activity, not on "PC instead of
   cloud".
2. **Calling a third party does not automatically end the exemption.** For the
   CJEU, "personal or household" refers to the activity of the processing
   person, not to the person whose data are processed. A private scheduling
   round with family members can therefore stay private despite involving other
   people's phone numbers.
3. **The outward orientation still matters.** Organised research, professional
   or commercial use, club or organisational operation, or publication to an
   indeterminate group of people regularly exceed the exclusively private
   sphere. The CJEU reads the exemption narrowly.
4. **External providers are not automatically exempt.** Recital 18 says
   expressly that the GDPR applies to controllers or processors which provide
   the means for processing personal data for such personal or household
   activities. CALL-E, a SaaS operator or a hosting provider must examine their
   own role even where an end user acts personally.
5. **"The host writes the privacy notice" is too sweeping.** The body that
   determines purposes and means is the controller (Art. 4(7)). A pure
   infrastructure host is typically a processor (Art. 4(8), Art. 28); the
   application or service operator is often the controller. Depending on the
   product design, operator and user may hold separate or joint
   responsibilities. These roles must be determined from the actual decisions
   and contracts.

## What changes as soon as third parties are called

Phone number, name, conversation content, answers, callback request and
transcript can be personal data of the person called. In ResearchCall the
freely designed questions may additionally concern special categories under
Art. 9(1) GDPR.

Where the household exemption does not apply:

- Before any processing, a sound legal basis under Art. 6 must be determined;
  for special categories additionally an exception under Art. 9(2) and possibly
  national research law.
- Where the phone number comes from an address book, from the organiser, from
  OSM or from a sampling file, Art. 14 must be examined. Where it is used to
  make contact, the information must in principle be given at the latest at the
  first communication (Art. 14(3)(b)), unless an exception applies.
- Answers the person gives during the conversation are collected from them;
  Art. 13 governs, and the information is in principle to be provided at the
  time of collection.
- A short, comprehensible first-layer notice during the call plus a reachable
  full text is the obvious technical route, but must be confirmed legally and
  ethically for the purpose, audience and legal basis.
- Whether automated calls, call recording/transcription, advertising, research
  consent or profession- and sector-specific rules are permissible is a further
  examination. These documents do not decide it.

## Statutes and subsumption

Local statute text used: law-checker `_data/gesetze/DSGVO.txt`, official EUR-Lex
source, consolidated version `02016R0679-20160504`, retrieved on 19 July 2026.

Verbatim core sources from the verified official texts:

- Art. 2(2)(c) GDPR: "by a natural person in the course of a purely personal or
  household activity".
- Recital 18 GDPR: "purely personal or household activity and thus with no
  connection to a professional or commercial activity"; the following sentence
  expressly keeps providers of the means of processing within scope.
- Art. 8(1) CFR: "Everyone has the right to the protection of personal data
  concerning him or her." Local law-checker text: official EUR-Lex version
  2012/C 326/02, retrieved on 19 July 2026.

- **Art. 2(1) GDPR:** covers wholly or partly automated processing of personal
  data. The three applications store in a structured way in SQLite/JSON; local
  processing is therefore not exempt merely because of where it is stored.
- **Art. 2(2)(c) GDPR:** the exemption applies only to processing "by a natural
  person in the course of a purely personal or household activity".
  "Exclusively" is the decisive limit.
- **Recital 18:** no connection to professional or commercial activity; private
  address books and online activity can be covered; providers of the means of
  processing remain in scope.
- **Art. 4(1), (2), (7) and (8) GDPR:** phone numbers, names, free text and
  transcripts can be personal data; storing, reading and transmitting are
  processing; controller and processor are to be determined from the actual
  decision-making and instruction relationship.
- **Art. 5(1)(c), (e), (f) and (2) GDPR:** data minimisation, storage
  limitation, confidentiality and accountability. All three applications lack
  general automatic deletion periods; shared, unprotected data spaces run
  counter to the confidentiality goal of hosted operation.
- **Art. 6 GDPR:** at least one fitting legal basis is required; the templates
  therefore deliberately leave it open and do not invent one.
- **Art. 9 GDPR:** ResearchCall may process special categories depending on the
  questionnaire; Art. 6 alone is then not enough.
- **Art. 12 to 14 GDPR:** transparency and information for application users and
  for people called. Art. 14 requires among other things the categories of data
  and the source; where contact is made, the first communication is in principle
  the limit.
- **Art. 24, 25 and 32 GDPR:** demonstrable, risk-appropriate measures, data
  protection by design and by default, and security. Art. 25(2) requires in
  particular that data are not made accessible to an indefinite number of people
  without the individual's intervention.
- **Art. 28 GDPR:** where processing is carried out on behalf of a controller, a
  selection assessment and a contract with the processor are required.
- **Art. 35 GDPR:** where processing is likely to result in a high risk, a data
  protection impact assessment is required; for ResearchCall this depends on the
  study and its scale and must be decided in advance.
- **Art. 44 et seq. GDPR:** a transfer to a third country requires the conditions
  of Chapter V. A source-code endpoint or a README statement proves neither the
  actual countries nor the safeguards.
- **Art. 7 and 8 CFR:** private and family life and personal data are protected
  as fundamental rights; these guarantees support the narrow reading of the
  exemption and the risk-oriented balancing.

Official full text: [EUR-Lex, Regulation (EU) 2016/679](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R0679).

## Case law on the household exemption

1. **CJEU, judgment of 10 July 2018, C-25/17, Tietosuojavaltuutettu/Jehovan
   todistajat, ECLI:EU:C:2018:551, paras. 40–42.** The comparable household
   exemption of the Data Protection Directive is narrow; what matters is the
   activity of the person processing, not the identity of the data subject.
   Outward-facing door-to-door data collection was not exclusively personal or
   household. [Official CJEU source](https://curia.europa.eu/juris/document/document.jsf?docid=203822&doclang=EN).
2. **CJEU, judgment of 11 December 2014, C-212/13, Ryneš, ECLI:EU:C:2014:2428,
   in particular paras. 29–33.** A private camera that also covered public space
   did not fall under the comparable exemption; the exemption is to be read
   narrowly in the light of fundamental rights.
   [Official CJEU source](https://curia.europa.eu/juris/document/document.jsf?docid=160561&doclang=EN).

Both decisions concern the predecessor directive, not Art. 2(2)(c) GDPR
directly. Their reading of the substantively comparable household exemption, and
the CJEU's reference in C-25/17, are meaningful for drawing the line; how it
applies today remains a question of the individual case.

## Technical evidence per repository

### HungryCall

- `hungrycall/db.py`: one SQLite file with name, request, delivery address,
  unmasked callback number and phone-masked transcript text; no automatic
  deletion.
- `hungrycall/web.py`: module-wide `ACTIVE_ORDERS`/`CANCELED_ORDERS`, unprotected
  history and result routes, no user identity.
- `hungrycall/location.py` and `hungrycall/static/app.js`: Nominatim/Overpass
  outside the explicit test mode; browser-side OSM tile connections even when
  the test-mode map is rendered.
- `hungrycall/call_client.py`/`engine.py`: one process key; live, the destination
  number and order-related data go to CALL-E.

Deliverables: `hungrycall/DATA-FLOW.md`, `hungrycall/PRIVACY-TEMPLATE.md`,
`hungrycall/HOST-READINESS.md` and an entry in `hungrycall/AUFGABEN.txt`.

### Ringedingeding

- `ringedingeding/store.py`/`projects.py`: one SQLite file with contacts,
  channels, photos, projects, raw numbers, answers and transcripts.
- `ringedingeding/web/app.py`: no login; all project, contact, photo, export and
  run routes share the same state. Deleting a project leaves phrase and question
  rows and the separate poll/participant/answer tree behind; live transcripts can
  remain orphaned.
- `ringedingeding/calle_credentials.py`: one process or project key; the current
  unprotected settings route can replace it in `config.local.json`.
- `ringedingeding/transports/base.py`/`runner.py`: live, the raw number, by
  default the first name, the task and metadata go to CALL-E.

Deliverables: `ringedingeding/DATA-FLOW.md`, `ringedingeding/PRIVACY-TEMPLATE.md`,
`ringedingeding/HOST-READINESS.md` and an entry in `ringedingeding/TODO.md` (the
existing `AUFGABEN.txt` was write-locked at the time of editing).

### ResearchCall

- `src/researchcall/web/workspace.py`/`web/app.py`: one shared `workspace.json`,
  unprotected stations, tasks, reports and exports; the web surface is fixtures
  only.
- `src/researchcall/database.py`/`sampling.py`: external reference and raw number
  in SQLite; sample, attempts and structured answers.
- `src/researchcall/calls.py`/`cli.py`: live only through the explicit CLI gate;
  one process key; raw number and questionnaire task to CALL-E.
- `src/researchcall/runner.py`: the full transcript is checked but not stored
  locally; the targeted withdrawal purge removes number, answer and provider run
  ID, but leaves sample and attempt metadata and the idempotency key, and does
  not delete at the provider.
- `src/researchcall/export.py`: export without phone number or external reference
  and without withdrawn records; free text can nevertheless identify a person.

Deliverables: `researchcall/DATA-FLOW.md`, `researchcall/PRIVACY-TEMPLATE.md`,
`researchcall/HOST-READINESS.md` and `researchcall/AUFGABEN.txt`.

## Minimum requirements before hosting

1. Block publication until login, secure sessions, tenant separation and
   object-level authorisation are implemented.
2. Every table, workspace, job, export and stream needs a documented
   owner/tenant and a server-side access check.
3. User-specific API keys only encrypted in a secret store, with rotation,
   deletion, quotas and billing limits; alternatively offer live telephony only
   on the operator's side.
4. Implement and test a deletion and retention plan in code, backups, logs and
   provider contracts.
5. Document controller and processor roles, legal bases, Art. 13/14 information,
   processing agreements and third-country mechanisms.
6. Establish contractually the CALL-E legal entity, the actual processing
   countries, subprocessors, logs and retention periods. The same applies for
   HungryCall to the Nominatim, Overpass and tile endpoints actually operated.
7. Add TLS, CSRF protection, secure cookies, rate limits, auditing, upload
   protection and an independent security review.
8. For ResearchCall additionally examine the questionnaire, Article 9 data,
   national research law, ethics, withdrawal and the DPIA threshold per study.

A completed privacy notice is only transparency documentation. It replaces
neither a legal basis nor contracts, security, tenant separation or deletion.

## law-checker protocol

A local installation of the `law-checker` tool was used (path omitted here; it is
a working copy on the examining machine). Registry: `config.json`, version 5;
local GDPR text with a source header and retrieval date 19 July 2026. The
`rechtsabteilung` skill was applied in addition for statute and case-law sources.

The active registry statutes were reviewed: Basic Law, Civil Code, Social Code
Book V, Copyright Act, Legal Services Act, Trade Mark Act, Tax Advisory Act,
Unfair Competition Act, GDPR, EHDS Regulation and the Charter of Fundamental
Rights. For this narrowly framed privacy and hosting assessment, the **GDPR** and,
for fundamental rights, the **Charter** were selected. The Unfair Competition Act
was examined as a possible fringe area for advertising, but not subsumed for want
of documented advertising calls. The Basic Law, Civil Code, Social Code Book V,
Copyright Act, Legal Services Act, Trade Mark Act, Tax Advisory Act and EHDS
Regulation were not decisive for the specific questions. The Criminal Code and
the Interstate Media Treaty, disabled in the registry, were not activated; call
recording/transcription and telephone advertising law in particular remain
separate fields of examination.

## Open facts for the lawyer's or deployment-specific examination

- Who operates which repository, for what purpose and for which group of people?
- Is an application operator, every using organiser, or both the controller?
- Which CALL-E contracting company, server regions, subprocessors, retention
  periods and transfer bases actually apply?
- Which specific Nominatim, Overpass and tile instances and terms of use are used
  in operation?
- Are conversations recorded or only machine-transcribed; how and when are the
  people called informed about it?
- Which legal basis applies per purpose, and does a ResearchCall questionnaire
  contain special categories?
- Which infrastructure, proxy, security, support and backup logs exist in the
  real hosting setup?
