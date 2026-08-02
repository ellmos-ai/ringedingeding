# Initial EU AI Act assessment: RingeDingeDing

**Date:** 2 August 2026
**Scope:** AI-assisted calls to multiple private individuals to collect and aggregate dates or opinions
**Notice:** This is a technical and editorial initial assessment, not legal advice. The specific operator must obtain legal review of the purpose, recipients, data source, contracts, and applicable jurisdiction before live calls.

## Executive finding

RingeDingeDing's documented intended purpose is not a high-risk use case under Annex III. Article 50(1) and (5) still applies: no later than the first interaction, the called person must be clearly and distinguishably informed that they are interacting with an AI system. The duty applies from 2 August 2026.

Of the three projects reviewed, RingeDingeDing has the strongest technical ordering. Its opening is mandatory, quoted for verbatim delivery, and placed before user-supplied greetings. It says “automatischer Assistent” or “automated assistant”, however, not “KI” or “AI”. The result path also does not inspect the transcript to prove actual first-utterance disclosure. Article 50 is therefore **partially implemented but not demonstrated as fulfilled**.

The preceding contact issue is especially important here: several private individuals are called using numbers entered by an organiser. Neither the organiser's live confirmation nor asking “Is now a good time?” proves a legal basis for the dialling that already occurred.

## 1. Applicable duties

| Issue | Initial assessment | Reason |
| --- | --- | --- |
| AI Act Article 50(1), (5) | **Applies.** | The system is intended for direct voice interaction with natural persons. Information must be clear, distinguishable, accessible, and provided no later than the first interaction. |
| AI Act Article 4 | **Applies by role.** | Providers and deployers must take measures supporting AI literacy for the people working with the system, including purpose limits, release, refusal handling, privacy, and escalation. |
| AI Act Article 6 and Annex III | **Not high-risk for the current purpose.** | Date polling and simple opinion aggregation are not listed decisions about education, employment, essential services, law enforcement, migration, justice, or democratic processes. |
| Article 53 / GPAI Code of Practice | **No direct project duty evidenced.** | The repository does not provide a general-purpose AI model. It is a downstream application of a calling service. |
| GDPR | **Applies.** | Phone numbers, names, availability, opinions, free text, and transcripts can be personal data. Political, religious, health, or trade-union views can engage Article 9. |

An opinion poll is not high-risk merely because it concerns opinions. If the system is later intended to influence voting behaviour or election outcomes, assess people for employment or education, or support another Annex III decision, it must be reclassified before use. Profiling in a relevant Annex III use case strengthens the high-risk classification under Article 6(3). Regulation (EU) 2026/1744 moved the Annex III high-risk duties to 2 December 2027; Article 50 applies now.

## 2. What the code does and does not establish

### Existing controls

- The German rules require this exact, unprompted first sentence: “Guten Tag, hier ist ein automatischer Assistent im Auftrag von … Ich habe eine kurze Frage.” (`ringedingeding/schemas.py:307-327`).
- The English rules likewise require “automated assistant” (`ringedingeding/schemas.py:285-305`).
- User-supplied greetings are deliberately placed **after** the mandatory disclosure (`ringedingeding/schemas.py:330-353`).
- Refusal is accepted without persuasion; if the time is unsuitable, the agent says it will not call back automatically (`ringedingeding/schemas.py:316-326`).
- The live transport cannot be constructed without explicit confirmation (`ringedingeding/transports/calle.py:105-125`), and the central service requires the exact live-confirmation phrase (`ringedingeding/service.py:573-614`).
- The result carries a masked transcript (`ringedingeding/transports/calle.py:393-407`) that could support disclosure evidence.

### Open Article 50 gap

“Automated assistant” describes automation but does not expressly identify an AI system. The repository does not establish that the wording is sufficient in every context, and deployment should not rely on the obviousness exception. Nor does the code verify that the actual first bot utterance contained the mandatory disclosure.

The status is **a strong technical basis, with legal evidence still open**. The opening should expressly say:

> “Hello, this is an AI assistant calling on behalf of [organiser]. I have one short question.”

and, in German:

> „Guten Tag, hier spricht ein KI-Assistent im Auftrag von [Organisator]. Ich habe eine kurze Frage.“

Regression tests should protect first position in both languages and all project types. Result validation should inspect the first BOT segment and mark absent or late disclosure as non-compliant. These gaps are recorded in `AUFGABEN.txt`.

## 3. The called person did not consent in advance

The organiser can enter a number and confirm a live run. The code does not prove that the affected person supplied the number for this purpose or agreed to the call, transcription, or aggregation of their answer.

Asking whether now is a good time is respectful, but it occurs after number processing, onward disclosure, and dialling. Agreement to answer the question cannot retrospectively cure those steps. Each live project therefore needs a documented contact route:

1. **Source and expectation:** where did the name and number come from? Was the person invited in advance, or what other basis supports contact? Public availability or an organiser's address book is not automatically sufficient.
2. **Legal basis by phase:** GDPR Article 6 must be documented separately for list import, dialling, conversation, aggregation, and retention. Article 6(1)(f) requires a concrete assessment of purpose, necessity, reasonable expectations, safeguards, and consequences of objection.
3. **Articles 13/14 information:** if the organiser or another source supplied the number, Article 14 is normally relevant no later than first communication. Data requested directly engages Article 13. The spoken first layer should identify the controller, purpose, number source, transcription or recording, voluntariness, and a full notice route.
4. **Refusal, objection, and suppression:** the existing conversational stop must feed a durable suppression process. A later aggregation run must not inadvertently call the person again where purpose-limited suppression is lawful and necessary.
5. **Sensitive topics:** questions must be screened for Article 9 special-category data. Incidental political, health, religious, or trade-union information must not be stored or disclosed without a suitable basis and safeguards.
6. **Advertising and recording:** German UWG section 7 applies additionally only when the actual call is advertising; it then imposes strict prior-consent rules, especially for automatic calling machines. The repository does not establish whether CALL-E records audio. If it does, German Criminal Code section 201 requires a separate assessment before recording.

Voluntary participation and lawful initial contact are separate questions. For calls to private individuals, a documented prior invitation or opt-in route is the strongest product default unless another sound legal basis has been established.

## 4. Hosting duties by server mode

Actual purposes, means, contracts, and branding determine legal roles. Depending on the design, a host may be an AI Act provider or deployer and a GDPR controller, joint controller, or processor. Visitor-owned keys and browser storage do not decide that by themselves.

| Mode in `../huckepack/KONZEPT.md` | Operator requirement |
| --- | --- |
| `local` | A shared address/project database without accounts is not suitable for untrusted multi-user access (`HOST-READINESS.md:3-30`). Authentication, tenant isolation, object authorisation, retention, rights, and credential boundaries are prerequisites. |
| `huckepack-gift` | The host provides the key and call execution. Browser persistence does not alter the fact that numbers, tasks, and answers pass through the host and CALL-E. Disclosure, lawful basis, provider review, quotas, misuse controls, and a rights channel remain required. |
| `huckepack-only-host` | The visitor pays with their own key, but the host still supplies the UI and call relay. Transit data, key handling, legal roles, the contract chain, and security must be documented and controlled. |
| `pay-membership` | Stub only. Accounts, billing, tenant/data isolation, secret management, rights, deletion, export, and incident procedures are required before release. |

`DATA-FLOW.md:17-32, 37-66` documents phone numbers, responses, transcripts, and remaining transit/export limits in piggyback modes. `PRIVACY-TEMPLATE.md:20-75` deliberately requires a concrete legal basis, first-communication information, and verified service-provider facts; placeholders are not release evidence.

### Release criteria before live hosting

- Explicit AI disclosure as the first verbatim sentence, with automated proof from the first bot segment.
- Project-level contact evidence: number source, prior invitation or another basis, purpose, recipient group, and legitimate-interests assessment where used.
- Articles 13/14 first-layer and full notices, plus objection and suppression procedures.
- Article 9 content screening and boundaries against profiling, persuasion, and repurposing.
- Verified CALL-E roles, contracting entity, subprocessors, countries, retention, deletion, Article 28 terms, and any Chapter V mechanism.
- Mode-appropriate security, rate/cost limits, tenant isolation, export, and deletion.
- Article 4 AI-literacy measures and a documented Annex III reassessment on every purpose change.

## 5. Sources and evidence limits

This assessment builds on, but does not reproduce, the following in-house Um:bruch analyses:

- `C:\Users\User\OneDrive\.TOPICS\.UMBRUCH\website\src\content\blog\ai-act-transparenzpflichten-ab-august-2026.md`, the primary editorial analysis.
- `...\ki-reviews\eu-ai-act-transparenz-code-of-practice.md` and `eu-ai-act-transparency-code-of-practice.md`.
- `...\ki-reviews\eu-ai-act-haftungsluecke.md` and `eu-ai-act-liability-gap.md`.
- `C:\Users\User\OneDrive\.TOPICS\.UMBRUCH\_editorial\entwuerfe\2026-07-03_eu-ai-act_leitartikel_synthese.md`, treated as a draft.

Primary and authority sources: [Regulation (EU) 2024/1689](https://eur-lex.europa.eu/eli/reg/2024/1689/oj), [Regulation (EU) 2026/1744](https://eur-lex.europa.eu/eli/reg/2026/1744/oj), [Article 50](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50), [Annex III](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-3), [implementation timeline](https://ai-act-service-desk.ec.europa.eu/en/ai-act/timeline/timeline-implementation-eu-ai-act), [GDPR](https://eur-lex.europa.eu/eli/reg/2016/679/2016-05-04/eng), [German UWG section 7](https://www.gesetze-im-internet.de/uwg_2004/__7.html), and [German Criminal Code section 201](https://www.gesetze-im-internet.de/stgb/__201.html).

Prior consent or invitations for specific contacts, CALL-E audio behaviour and contract facts, provider retention, processing countries, subprocessors, and the specific project's legal basis are not evidenced and remain open.
