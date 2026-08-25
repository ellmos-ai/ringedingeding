# FINDINGS — gemessen am echten Dienst, 2026-08-01

> Ergänzt `AGENTS.md`. Die technischen Schlussfolgerungen und Datumsangaben stammen
> aus beaufsichtigten Messungen gegen den echten Dienst. Seit der öffentlichen
> Datenschutzbereinigung vom 2026-08-24 sind jedoch alle konkreten Rufnummern,
> Personenbezüge, Dienst-IDs, Zeitstempel, Antworttexte und Transkriptzeilen in dieser
> Datei **synthetische Rekonstruktionen**. Die nicht redigierten Rohartefakte sind kein
> Bestandteil des öffentlichen Repositorys oder seiner erreichbaren Git-Historie.

## 1. Man KANN live mitlesen — über `activity`, nicht über `transcript`

Während des Gesprächs bleibt `transcript` **`null`**. Aber `activity` enthält den
Gesprächsverlauf in Echtzeit, beide Sprecher, mit Millisekunden-Zeitstempeln:

```
00:00:00.000 | Call is ringing.
00:00:04.000 | Call connected.
00:00:05.000 | Bot is speaking: Dies ist ein synthetisch rekonstruierter Testdialog.
00:00:06.000 | Callee said: beispielantwort
00:00:07.000 | Callee said: Beispielantwort.
00:00:20.000 | Callee said: synthetische Kategorie zwei
00:00:25.000 | Call ended; syncing final Calling result.
```

**Achtung Dubletten:** „Callee said" kommt teils zweimal — erst eine Rohfassung
(`hallo`), Sekundenbruchteile später die korrigierte (`Hallo.`). Die Spracherkennung
liefert streamend und bessert nach. Wer mitliest, muss zusammenführen.

## 2. `status` ist als Fortschrittsanzeige unbrauchbar ⚠️

Der Status blieb auf **`PREPARING`**, während bereits gesprochen wurde — und sprang erst
nach Gesprächsende auf `COMPLETED`:

```
00:00:08Z | status=PREPARING | activity=12 | last: Callee said: Beispielantwort.
00:00:14Z | status=PREPARING | activity=15 | last: Bot is speaking: Bitte antworten Sie mit…
00:00:40Z | status=COMPLETED | activity=21 | last: Call ended from realtime events.
```

**Wer auf `status` wartet, verpasst das Gespräch.** Fortschritt kommt aus `activity`.

## 3. Das Transkript liegt in `result.transcript` ⚠️

`structuredContent.transcript` ist `null` — auch nach Abschluss.
Das Transkript steht in **`structuredContent.result.transcript`**, als **String**
(nicht als Liste), Format `[mm:ss] SPRECHER: Text`, Sprecher `BOT` / `USER`.

## 4. Wörtliche Vorgaben halten bis ins gesprochene Wort ✅

Ein in **Anführungszeichen** gesetzter Fragetext wurde zeichengenau gesprochen —
einschließlich eines absichtlichen Tippfehlers („oeffentlichen"). Ein umformulierender
Agent hätte ihn korrigiert.

**Regel:** Was in Anführungszeichen steht, wird zitiert. Was außerhalb steht, wird
umformuliert **und ergänzt** — der Planer fügt eigenständig Verhaltensregeln hinzu
(z. B. Voicemail-Verhalten), die nicht in der Eingabe standen.

## 5. Kein Ergebnis-Schema über MCP/CLI ⚠️ betrifft die Architektur

`plan_call` kennt: `plan_id`, `to_phones`, `region`, `language`, `goal`, `scheduled_at`,
`retry_confirmation_action`, `user_input`, `ttl_seconds`.
**Kein `result_schema`, kein `recipient_result_schema`.**

Schema-validierte Ergebnisse gibt es nur über die **REST-API**
(`POST /v1/calls`, Header `Authorization: Bearer $CALLE_API_KEY`).

**Und beide Wege sind getrennte Welten:** Ein über MCP gestarteter Anruf ist über
`GET /v1/calls/{run_id}` **nicht** abrufbar (geprüft: HTTP 404 bei gültigem Key).
Wer Schemas will, muss den Anruf **über REST starten**, nicht nur dort abfragen.

→ Für Werkzeuge, die strukturierte Antworten brauchen, ist **REST der Hauptweg**;
MCP/CLI taugt für interaktive Einzelanrufe.

## 6. Zeitverhalten

| Ereignis | Abstand zum `run_call` |
|---|---|
| Bot wird erzeugt | +2 s |
| Anruf klingelt | **+39 s** |
| verbunden | +43 s |
| Gespräch beendet (32 s Gesprächszeit) | +75 s |
| `status` = COMPLETED | +99 s |

**Rund 40 Sekunden Vorlauf pro Anruf**, unabhängig von der Gesprächslänge. Seriell
gerechnet also ~1,5 Minuten pro Anruf, auch bei kurzen Gesprächen.

## 7. Der Agent interpretiert freie Antworten

„synthetische Kategorie zwei" wurde eigenständig als *unzufrieden* kategorisiert;
`completion_confidence` 0.92 („high"), dazu drei Belegsätze in `evidence`.

**Folge: Rohantwort immer mitführen, nicht nur die Deutung** — sonst ist nicht mehr
prüfbar, ob richtig kategorisiert wurde.

## 8. Kleinigkeiten

- API-Keys beginnen **nicht** mit `calle_live_` (so die Doku), sondern mit `iams_live_`.
  Nicht auf das Präfix prüfen.
- Es gibt ein viertes, undokumentiertes MCP-Werkzeug `track_ui_events` (UI-Telemetrie,
  für uns irrelevant).
- Ohne Rufnummer liefert `plan_call` `ready_to_run: false` und `confirm_token: null` —
  ein Anruf ist dann nicht auslösbar. Sauberer Schutz, auf den man sich verlassen kann.
- Pläne haben eine TTL von 24 Stunden.

## 9. Live-measured status matrix (2026-08-11)

> **Herkunft:** Diese Payloads stammen aus einer echten Messung des Operators gegen
> die live CALL-E-REST-API am 2026-08-11 (`GET /v1/calls/{id}`) und wurden dem
> Bau-Agenten als Auftrag mitgeteilt. Der Bau-Agent selbst hat **keinen** Anruf
> ausgeführt und keine eigene Live-Messung vorgenommen — siehe EVIDENCE.md für das,
> was in diesem Repo tatsächlich lief (Tests gegen die Payloads unten, keine Sockets).

### Mailbox / Anrufbeantworter kommt als `completed`, nicht als `VOICEMAIL`

Kein Feld auf der Leitung sagt „Anrufbeantworter". Der Anruf ist technisch
`status: "completed"`, `task_completed: true`, und der Beleg steckt im Transkript:

```json
{
  "status": "completed",
  "task_completed": true,
  "failure_code": null,
  "failure_message": null,
  "evidence": [
    "Die Ansage der Mailbox bat darum, nach dem Signalton eine Nachricht zu hinterlassen.",
    "..."
  ],
  "recipients": [
    {
      "status": "completed",
      "attempts": [
        {
          "status": "completed",
          "transcript_turns": [
            {"offset_seconds": 0, "speaker": "bot", "text": "..."},
            {
              "offset_seconds": 4,
              "speaker": "user",
              "text": "Die angerufene Person ist nicht erreichbar. bitte hinterlassen sie eine nachricht nach dem signalton"
            }
          ]
        }
      ]
    }
  ]
}
```

**Folge:** `transports/calle.py::_outcome_from` liest jetzt die Callee-/User-Zeilen des
Transkripts (nie die Bot-Zeilen — Abschnitt 4 oben zeigt, dass der Planer von sich aus
Voicemail-Verhalten in den Bot-Text einfügt) und ordnet einen `completed`-Anruf mit
eindeutigem Beleg (`signalton`, `anrufbeantworter`, `sprachbox`, `mailbox`, `voicemail`,
`answering machine`, `after the tone/beep`) als `VOICEMAIL` ein. Uneindeutige Wendungen
(„nicht erreichbar", „leave a message") zählen nur, wenn sie den ersten Callee-Turn
öffnen **und** der `evidence`-Freitext des Agenten dasselbe unabhängig bestätigt — ein
realer Umfrageteilnehmer kann plausibel „ich bin nächste Woche nicht erreichbar" sagen.

### Aktive Ablehnung kommt als generisches `failed`, mit dem echten Status in `failure_message`

```json
{
  "status": "failed",
  "failure_code": "call_failed",
  "failure_message": "calling task status=DECLINED (Hangup by: user)",
  "task_completed": false
}
```

Das System wählt bei Nichterreichen automatisch bis zu 3× nach, zeigt dabei aber nur
**einen** Eintrag in `recipients[].attempts[]`. Im beobachteten Ablehnungsfall war
`attempts[0].transcript_turns` leer (`[]`) — niemand hat gesprochen, der Anruf wurde
sofort aufgelegt.

**Folge:** `failure_message`/`failure_code` wurden vorher an keiner Stelle im Repo
gelesen — eine aktive Ablehnung landete als generisches `FAILED` und damit in
`Bucket.UNREACHED`, ununterscheidbar von einem Anruf, der schlicht nicht erreichbar
war. `_outcome_from` wertet `failure_message` jetzt per Regex (`status=([A-Za-z_]+)`)
aus; ein erkannter Token (hier `DECLINED`) ersetzt das generische `FAILED`, ein
unbekannter Token bleibt `FAILED`, wird aber (maskiert) in `CallOutcome.error`
festgehalten statt verworfen.

### Das Transkript steht nicht immer in `result.transcript`

Beide Payloads oben tragen **kein** `result.transcript`. Stattdessen liegt das
Gespräch in `recipients[].attempts[].transcript_turns` — einer Liste von
`{offset_seconds, speaker, text}`-Objekten, nicht als fertiger String.
`ringedingeding.activity.extract_transcript` formatiert das jetzt in dieselbe
`[mm:ss] SPRECHER: Text`-Form wie Abschnitt 3, damit nachgelagerter Code (Anzeige,
Voicemail-Erkennung, Export) nicht zwischen den beiden Formen unterscheiden muss.

## 10. Nachschärfung 2026-08-11: DECLINED ohne Gespräch, Identitäts-Gate, Nullable-Unions, Batch-Dispatch

> **Herkunft:** Der DECLINED-Befund unten ist **selbst verifiziert** — direkt gegen den
> Upstream-Tracker gelesen (`gh issue view 111` / `gh issue view 82`,
> `CALLE-AI/awesome-phone-call-agents`), nicht nur vom Operator relayed. Die
> Batch-Dispatch-Aussage ist **codegelesen** (`service.py::make_transport`,
> `transports/calle.py::CalleBatchTransport`), keine eigene Live-Messung — dieser
> Bau-Agent hat wie in Abschnitt 9 keinen Anruf ausgeführt.

### Abschnitt 9 war zu gutgläubig: DECLINED kommt auch ohne jedes Klingeln

Die dort gezeigte Ablehnungs-Payload (`failure_message: "calling task
status=DECLINED (Hangup by: user)"`, `attempts[0].transcript_turns: []`) wurde am
2026-08-11 unbesehen als aktive Ablehnung übernommen. Die Upstream-Issues #111 und
#82 beschreiben genau diesen Fall als **eigenständigen Fehler des Dienstes**: ein
Anruf, der nie klingelte — keine Verbindung, keine Dauer, niemand je in der
Leitung — kommt dennoch mit `status=DECLINED`/„Hangup by: user" zurück. Die
Payload aus Abschnitt 9 ist damit nicht als „Person hat aufgelegt" belegt, sondern
ebenso gut als „Anruf kam nie an" erklärbar — beides sieht auf der Leitung gleich
aus.

**Folge:** `transports/calle.py::_outcome_from` übernimmt ein aus `failure_message`
gelesenes `DECLINED` jetzt nur noch, wenn das Transkript tatsächlich Callee-/
User-Zeilen enthält (`_has_conversation_substance`, dieselbe Callee-Filterung wie
die Voicemail-Erkennung in Abschnitt 9). Ohne Gesprächssubstanz bleibt der Status
`FAILED`, die (maskierte) `failure_message` bleibt aber in `CallOutcome.error`
erhalten statt verworfen zu werden — `Answer.bucket` liefert dafür automatisch
`UNREACHED`, nicht `REFUSED`. Eine Dauer-basierte Zusatzprüfung (`duration > 0`)
ist bewusst **nicht** eingebaut: kein REST-Payload mit Dauer-Feld wurde bisher
gemessen (nur ein MCP-Beispiel in Issue #111 zeigt `duration_seconds: 0`), und ein
fehlendes Feld darf nicht als Null gelesen werden — dieselbe Regel, die dieses
Projekt an anderer Stelle schon befolgt.

### Identitäts-Gate: eine Ablehnung der falschen Person ist keine Antwort des Mitglieds

`models.py::Answer.bucket` prüfte bisher `refused` **vor** `reachable`. Für das neue
Identitäts-Gate in `schemas.py::build_task_text` (Schritt 2: „Spreche ich mit
{Name}?" / „Am I speaking with {name}?", nur wenn ein Name mitgegeben wurde) wurde
das zum konkreten Fehler: `{"reachable": false, "refused": true}` — die falsche
Person am Apparat, die für sich selbst ablehnt — landete als REFUSED für das
eigentliche Mitglied. Die Reihenfolge ist jetzt getauscht: `reachable` zuerst, dann
`refused`. Regressionstest: `tests/test_merge.py::
test_a_strangers_refusal_never_counts_as_this_participants_answer`.

### Sprachdirektive gegen englisch gesprochene wörtliche Sätze

Feldbefund aus dem Schwesterprojekt `hungrycall` (2026-08-11): ein wörtlich in
Anführungszeichen vorgegebener englischer Satz wurde englisch gesprochen, obwohl
der Anruf sonst deutsch lief. `_RULES_DE`/`_RULES_EN` in `schemas.py` tragen jetzt
je eine unquotierte Sprachdirektive vor der Regelliste („Führe das gesamte
Gespräch auf Deutsch…" / „Conduct the entire conversation in English…") —
außerhalb jeder Anführungszeichen, sonst würde die Direktive selbst vorgelesen statt
befolgt (Regressionstest: `test_the_language_directive...` bzw. der
`_unquoted()`-Helfer in `tests/test_schemas.py`).

### Keine nullable Union-Types in Schemas an die API (Upstream-Issue #120)

Bestätigt über den Upstream-Tracker (`gh issue view 120`) und im Schwesterprojekt
`researchcall` bereits behoben: CALL-E lehnt den gesamten Call-Create-Request mit
`result_schema_invalid` ab, sobald irgendwo im Schema ein nullable Union
(`{"type": ["string", "null"]}`), ein blankes `"type": "null"` oder ein `null` in
einem `enum` vorkommt. Das neue optionale Feld `callback_requested` in
`_COMMON_PROPERTIES` ist entsprechend ein einfaches `{"type": "string"}`,
**nicht** in `required` — Abwesenheit statt `null` für „trifft nicht zu".
Dauerhafter Regressionswächter: `tests/test_schemas.py::
test_no_schema_sent_to_calle_ever_contains_a_nullable_union` (rekursiver
Schema-Walker, prüft `recipient_result_schema` und `aggregate_result_schema` für
jede `PollKind`).

### Live-Dispatch ist immer Batch — der Projekt-/Web-UI-Pfad kennt kein `--serial`

`service.py::make_transport` liefert für `RunMode.LIVE` unbedingt
`CalleBatchTransport` — sowohl `cli_projects.py::cmd_project_call` (`project call`)
als auch `web/app.py::run_round_route` (`POST /projects/{id}/run`) rufen
ausschließlich diese Funktion auf; keiner der beiden hat einen `--serial`-Schalter
oder ein Formularfeld dafür. Der `--serial`-Schalter existiert nur auf der
eigenständigen, projektlosen `run`-CLI (`cli.py::_transport_for`).

Zwei Empfänger mit **identischer** Telefonnummer in einem Batch-Request sind vom
Code her nicht verhindert (`ProjectStore.create_contact`/`set_channel` prüfen
Rufnummern nicht auf Eindeutigkeit) — was der Dienst selbst mit zwei gleichen
Empfängern in einem Batch macht, ist unbeobachtet. Bekannt und bereits im Code
behandelt ist nur der Fall, dass der Dienst die Antwortliste **kürzt oder anders
zählt**: `transports/calle.py::CalleBatchTransport` prüft
`len(recipients) != len(requests)` und liefert dann für **alle** Teilnehmer
`FAILED` mit der Meldung „…; refusing to map answers by position. Re-run with
--serial." — ein Batch-Live-Lauf mit doppelter Nummer scheitert also so, nicht
mit einer stillen Verwechslung. Serieller Fallback über die projektlose CLI ist möglich
(`run --db <db> --poll <poll_id> --live --serial`, siehe Betreiber-Anleitung im
Abschlussbericht), da `ProjectStore` nur eine dünne Schicht über demselben
`Store`/derselben SQLite-Datei ist — die Poll-ID einer Projekt-Runde ist aber
nicht auto-generiert-vorhersagbar und muss per
`ProjectStore.round_ids(project_id, round_kind)` nachgeschlagen werden.

## 11. Live-Testdesign Block C: Region/Locale-Entkopplung und Ersatz-Umlaute

> **Herkunft:** Beide Befunde sind vom Operator selbst im Rahmen von Block C live
> beobachtet (2026-08-11/12). Der Bau-Agent hat keinen eigenen Anruf ausgeführt; die
> Fixes unten sind codegelesen und testgedeckt, nicht live nachgemessen.

### Sprache und Region/Locale waren drei unabhängige Defaults

`create --language de` ergab im `plan`-Kopf wörtlich `Language : de (en-US, region
US)` — deutscher Text, aber eine US-Region/en-US-Stimme wären beim Live-Anruf
verwendet worden. Ursache: `language`, `region` und `locale` hatten an **jeder**
Erzeugungsstelle ihre eigenen, unabhängigen Standardwerte, ohne jede Beziehung
zueinander — und das an mehr Stellen als nur der zitierten:

- `store.py::create_poll` (bare Poll, bare `create`-CLI): `en`/`US`/`en-US`.
- `projects.py::ProjectStore.create_project` UND `service.py::create_project`
  (Wrapper-Funktion mit eigenen, redundanten Defaults): `de`/`DE`/`de-DE`.
- `web/app.py::create()` (`/projects` POST): leitete `locale` bereits ad-hoc aus der
  Sprache ab, `region` aber gar nicht — ein englisches Web-UI-Projekt behielt
  unbemerkt `region=DE` (spiegelbildlicher Fehler, nur in der anderen Richtung, vom
  Operator nicht beobachtet, aber beim Codelesen gefunden).

**Fix:** Eine einzige Funktion `locales.py::region_locale_for(language, *,
region=None, locale=None)` — ein explizit gesetzter Wert (auch ein von einem
HTML-Formular gesendeter Leerstring) gewinnt immer; unbelegt wird aus der Sprache
abgeleitet (`de` → `DE`/`de-DE`, alles andere → der bisherige Gesamt-Default
`US`/`en-US`). Eingebaut **an der Wurzel** — in `store.create_poll` und
`ProjectStore.create_project` selbst, nicht nur an den CLI-Einstiegspunkten —, damit
jede künftige Aufrufstelle den Fix automatisch erbt. `service.py::create_project`s
eigene, bislang redundante Signatur-Defaults wurden entfernt (reiner Durchreicher),
sonst hätten sie die tiefere Ableitung verdeckt. `web/app.py::create()`s
handgeschriebene Locale-Ableitung wurde durch denselben, einen Mechanismus ersetzt.
`render.py::_poll_header` (genutzt von `plan` UND `result`) warnt jetzt zusätzlich
sichtbar, wenn ein gespeicherter Poll trotzdem eine Abweichung zeigt — ob durch einen
bewussten expliziten Override oder einen vor dem Fix angelegten Datensatz.
`render_markdown` (die familientaugliche Export-Ansicht) bekommt diese technische
Warnung bewusst **nicht** — dort steht ohnehin kein Sprach-/Regionsfeld.

**Wichtig für den Operator:** Der laufende Live-Lauf gegen Commit `6f2bb5d` nutzt noch
das alte, unverknüpfte Verhalten — Projekte/Polls, die VOR diesem Fix angelegt
wurden, tragen ihre damals zugewiesene (möglicherweise falsche) Region/Locale-Kombi
weiter und werden vom Fix nicht rückwirkend korrigiert. Erst neu angelegte
Runden profitieren.

### ASCII-Ersatzumlaute werden wörtlich vorgelesen

Eine Testfrage mit „fuer" wurde hörbar als „fuer" gesprochen, nicht als „für" — dieselbe
wortwörtliche Vorlese-Eigenschaft, die Abschnitt 4 schon für ganze zitierte Sätze maß,
gilt offenbar bis auf die Ebene eines einzelnen ersetzten Umlauts.

**Fix (nur Warnung, keine automatische Korrektur):** `umlaut_check.py` mit einer
**geschlossenen, exakten** Liste von 14 Ersatzwörtern (genau die vom Operator
genannten: fuer, ueber, moechte, waere, koennen, muessen, groesse, strasse, zurueck,
natuerlich, spaeter, gespraech, aenderung, oeffnung), wortgrenzen-genau und
case-insensitiv geprüft (`\bfuer\b` etc.) — bewusst **kein** allgemeines
ae/oe/ue-Muster, weil das auf „Feuer", „teuer", „neue" & Co. falsch anschlagen würde.
Erweiterbar mit einer Zeile, keine Heuristik.

Eingebunden, für deutsche Polls/Projekte:
- CLI `create` (Frage, Organizer, Optionen, Slots), `contact add` (nur der **erste
  Namensteil** — nur der reist per `Participant.given_name` tatsächlich zum
  Sprachagenten; ein Ersatz-Umlaut allein im Nachnamen würde nie gesprochen und wäre
  Fehlalarm), `project new` (Anlass, Organizer), `project question`
  (Advisor-Frage/Optionen), `project wording` (Begrüßung/Abschluss).
- Web-UI: bewusst **nur** auf `/preview` — dort steht bereits der vollständige,
  tatsächlich versendete `task_text` als eine einzige Zeichenkette zur Verfügung, ein
  einziger Check deckt damit Frage/Optionen/Slots/Organizer/Wording/Identitätsfrage
  gleichzeitig ab. Eine flächendeckende Warn-/Flash-Mechanik über vier weitere
  Web-Routen (die es im Projekt bisher gar nicht gibt) wurde bewusst **nicht** gebaut
  — der Aufwand stünde außer Verhältnis zum Befund, und der Operator sah die Meldung
  ohnehin zuerst auf der CLI.
- **Bekannte, bewusste Lücke:** Die Liste prüft nur die **Grundform**. Konjugierte
  Varianten wie „moechten"/„moechtet"/„koennten" matchen NICHT gegen „moechte" (exakte
  Wortgrenzen-Regex) — eine Erweiterung um Flexionsformen wäre eine bewusste,
  eigenständige Entscheidung, keine, die aus dem aktuellen Auftrag automatisch folgt.
- **Guard-Test:** `test_this_projects_own_german_task_text_never_contains_a_substitute_umlaut`
  rendert `build_task_text` über alle PollKinds, mit/ohne Namen, mit
  Opening/Closing/Urgency, und prüft: 0 Treffer. Hält den vom Operator bereits
  repo-weit geprüften sauberen Zustand fest.

## 12. Advisor-Tendenz bei Alternativfragen erzeugte den falschen Konsens, den das README ausdrücklich ausschließt ✅

> **Herkunft:** Live-Befund des Operators/Team-Lead (2026-08-11) aus einem echten
> Advisor-Lauf. Der Bau-Agent hat keinen eigenen Anruf ausgeführt; Diagnose und Fix
> unten sind codegelesen und testgedeckt (Live-Szenario als Regressionstest
> nachgebaut), nicht selbst live nachgemessen.

Frage: „Sollten wir ein Grillfest machen oder einen Ausflug ins Grüne — und wohin?"
(`kind=open`). Zwei Teilnehmer antworteten mit **entgegengesetzten** Wünschen — einer
Grillfest im Garten, eine Ausflug nach Todtnau, jeweils mit Begründung und einem
Gegenargument gegen die Wahl der/des anderen. Der Bericht meldete trotzdem:

> RESULT: Tendency: support (2 of 2 answers)

und führte beide unter derselben Tendenz „support". Die Detailerfassung war exakt
(Antwort, Gründe, Bedenken pro Person sauber getrennt und wörtlich) — der Fehler steckt
in der Aggregationsachse: `support`/`against` beschreibt eine Ja/Nein-Richtung zu EINEM
Vorschlag. Bei einer Entweder-oder-Frage gibt es keinen gemeinsamen Vorschlag — jede
Person „unterstützt" ihre eigene, andere Wahl, und der Sprachagent vergibt dafür beiden
dieselbe Stance „support", weil er (laut Schema-Anweisung in `schemas.py`) nur die
Richtung DER EIGENEN Antwort klassifiziert, nicht ob sie sich auf denselben Referenten
bezieht. Zwei Menschen mit gegensätzlichen Wünschen erschienen dadurch als einmütige
Zustimmung.

**Dokumentations-Abweichung, nicht nur ein UX-Mangel:** `README.md` verspricht für
„Ask Your Advisor" wörtlich: *„It never turns dissent into a false consensus."* — genau
das tat die App in diesem Fall. Der Befund ist damit als Doku↔Verhalten-Abweichung
zu werten, nicht als bloße Verbesserungsidee.

**Warum keine Fragetyp-Erkennung („oder" im Text):** Der Team-Lead hatte das selbst als
schwaches, riskantes Signal markiert. Geprüft und verworfen: (a) Erkennung über ein
„oder"/„or"-Muster im Fragetext — false positives/negatives unvermeidbar, echte
Semantik-Raterei. (b) Gruppierung nach wörtlich identischem Antworttext — hätte den
bestehenden, korrekten Ja/Nein-Testfall zerstört (`test_open_advice_reports_tendency_
countervoices_and_reasons`: „Yes"/„Yes, carefully" sind beide `support`, aber nicht
wortgleich; eine Gleichheitsprüfung hätte auch dort keine Tendenz mehr gemeldet).

**Fix — Diskriminator ist die Zahl der tatsächlich genutzten Stances, nicht ihr
Wortlaut:** In `merge.py::OpenMerge.primary_tendency` gilt jetzt zusätzlich: Eine
Tendenz wird nur behauptet, wenn unter den beantwortenden Personen **mehr als eine**
unterschiedliche, wertende Stance (`support`/`against`/`mixed`, `neutral`/`unclear`
zählen nicht) tatsächlich vorkommt. Kommt nur EINE Stance vor, hat niemand die
Support/Against-Achse genutzt, um sich von jemand anderem zu unterscheiden — das ist
keine Zustimmung, sondern Abwesenheit eines unterscheidenden Signals. Eine einzelne
Antwort (eine Person, niemand sonst der hätte widersprechen können) bleibt davon
unberührt und wird weiterhin als Tendenz gemeldet — das ist keine erzeugte Einmütigkeit,
da niemand sonst die Achse hätte nutzen können.

- Ja/Nein-Fall (Testfixture „Should we expand?": support, support, against) — **zwei**
  unterschiedliche Stances liegen vor → Tendenz „support" wird weiterhin gemeldet,
  Countervoice „C" weiterhin sichtbar. **Unverändert, mit bestehendem Test geprüft.**
- Alternativ-Fall (Grillfest/Ausflug: support, support) — **eine** Stance, geteilt von
  zwei Personen → `primary_tendency` liefert `None`, keine Tendenz wird behauptet.
- Die Tally-Tabelle „Tendency/Count/Who" (bereits vorhanden in jedem Report, zeigt
  „support | 2 | A, B") bleibt unverändert stehen — sie behauptet keine Übereinstimmung,
  sondern zählt nur Klassifikationen; nur die Ein-Zeilen-Schlagzeile „RESULT: Tendency:
  …" wurde geändert.
- **Ehrlicher Fallback statt Leerstelle:** Wenn keine Tendenz behauptet wird, listet die
  Schlagzeile jetzt die tatsächlichen, unterschiedlichen Positionen wörtlich auf (`"N
  answer(s) collected; no single tendency - positions: A: "…"; B: "…"."`) statt nur
  „no single tendency leads" — ein Leser sieht sofort zwei Positionen statt einer
  Abwesenheitsmeldung. Gilt auch für den vorbestehenden Fall eines echten Patts (z. B.
  2 support vs. 2 against).
- **Maskierung nicht vergessen:** Die neue Positions-Auflistung zitiert `entry.answer`
  wörtlich — dieser Text kommt ungefiltert vom Sprachagenten und kann (Testfixture
  `test_transcript_text_from_a_call_is_masked_before_display`) eine rohe Telefonnummer
  enthalten. `merge.py` maskiert jetzt selbst mit `phone.mask_text` (importiert aus
  `.phone`, keine Zirkularität — `phone.py` hat keine projektinternen Imports), statt
  sich auf die Maskierung im Render-Layer zu verlassen, die die Schlagzeile nie
  durchläuft. Ohne diesen Nachzieher hätte der ursprüngliche Fix die AGENTS.md-Regel
  „no raw phone number ever reaches an output surface" verletzt — beim ersten
  vollen Testlauf real aufgefallen (`test_transcript_text_from_a_call_is_masked_
  before_display`, rot, dann behoben).
- **Guard-Test:** `test_open_advice_alternative_question_is_not_reported_as_consensus`
  baut das Live-Szenario exakt nach (zwei Personen, zwei unvereinbare Antworten, beide
  `stance="support"`) und prüft: keine „Tendency: support (2 of 2)"-Zeile mehr, beide
  wörtlichen Antworten stehen stattdessen in der Schlagzeile.

## 13. Batch-Dedup nach Telefonnummer — jetzt gemessen, nicht mehr offen ✅

> **Herkunft:** Live-Endabnahme des Operators/Team-Lead, 2026-08-22 (E-4/E-5). Zwei
> unabhängige Runden desselben Projekts betroffen; Diagnose und Fix unten sind
> codegelesen und testgedeckt (Live-Szenario als Regressionstest nachgebaut), nicht
> selbst live nachgemessen — derselbe Bau-Agent hat wie in den Abschnitten oben keinen
> eigenen Anruf ausgeführt.

Abschnitt 10 und der Punkt „Weiterhin ungeprüft" unten hielten offen, was der Dienst
mit zwei identischen Empfängernummern in einem Batch-Request macht — beobachtet war
bis dahin nur die Code-Reaktion auf eine *mengenmäßig* abweichende Antwortliste.
Am 2026-08-22 wurde das live gemessen, zweimal in derselben Endabnahme:

- **Synthetisch dargestellte Verfügbarkeitsrunde:** Zwei neutrale Testteilnehmer
  („Teilnehmer A" und „Teilnehmer B") mit **derselben** einwilligenden Testnummer.
  Beide Teilnehmer-Datensätze bekamen `state=done`,
  `call_run_id=synthetic-call-collision-a` (identisch) und **byte-identisches**
  `structured_json`/`raw_text` — eine einzige Antwort wurde zwei Identitäten
  zugeschrieben.
- **Synthetisch dargestellte Advisor-/Roundtable-Runde, dieselben zwei Teilnehmer:**
  derselbe Effekt, ein Run (`synthetic-call-collision-b`), ein identisches
  `FAILED`-Ergebnis doppelt gebucht.

**Der Dienst dedupliziert identische Zielnummern, ohne die Antwortlisten-Länge zu
ändern.** Genau das lässt die bestehende Schutzmechanik in
`transports/calle.py::CalleBatchTransport.place_many` leerlaufen: Sie prüft nur
`len(recipients) != len(requests)` und „refusing to map answers by position" greift
folglich nicht — die Länge stimmte (2 Requests, 2 Recipient-Einträge), nur der
*Inhalt* beider Einträge war identisch, weil nur ein physisches Gespräch stattfand.
Eine reine Längenprüfung kann diesen Fall grundsätzlich nicht fangen.

**Warum „identische `run_id`" allein kein brauchbares Erkennungsmerkmal ist:** In
`CalleBatchTransport` trägt *jeder* Teilnehmer eines Batches ohnehin dieselbe `run_id`
(= die eine `call_id` des Batch-Requests, siehe `_outcome_from(run_id=call_id)`) — das
gilt für jeden Batch mit mehreren Empfängern, auch für völlig unauffällige. Als
alleiniges Erkennungsmerkmal würde es jede Mehrpersonen-Runde fälschlich als
Kollision melden. Das tatsächlich beobachtbare, unabhängige Signal ist die **geteilte
Telefonnummer der Teilnehmer selbst** — das ist bereits vor dem Absetzen des Requests
bekannt, ganz ohne die (weiterhin unbewiesenen) Interna des Dienstes zu unterstellen.

**Fix (Erstfassung 2026-08-22, R3) — die Prüfung saß vor dem Wählen, transportunabhängig:**
`runner.py::build_requests` gruppierte die Teilnehmer, die in diesem Lauf tatsächlich
angerufen würden, nach `phone_e164`. Für jede Nummer, die mehr als einer dieser Personen
gehörte, wurde **für keine von ihnen** ein `CallRequest` gebaut — auch nicht für den
seriellen `CalleTransport`, sicherheitshalber, obwohl dort pro Person ein eigener
`POST /v1/calls` läuft und die Zuordnung schon durch die getrennten Requests eindeutig
ist. Jede betroffene Person bekam sofort einen `Answer` mit `call_status=FAILED`.

**Korrektur (R17, live nachgemessen 2026-08-22,
`synthetic-poll-rt4c-a`/`synthetic-poll-rt4c-b`):**
Der RT-4-Retest bestätigte den Kern (Block greift präventiv, ehrliche 0-von-2-Meldung,
kein erfundener Konsens), zeigte aber zwei Folgeprobleme der transportunabhängigen
Platzierung: (1) `--serial` wurde ebenfalls geblockt, obwohl dort — wie oben schon
vermerkt — gar keine Kollision entstehen kann, womit der legitime Haushalts-Fall (zwei
Personen, ein Festnetz) gar nicht mehr bedienbar war; (2) weil der Block sofort ein
terminales `FAILED` schrieb, meldete ein Folgelauf „nothing to do (use --retry)", obwohl
`--retry` daran nichts änderte — eine in sich widersprüchliche Sackgasse. Die Prüfung
sitzt seither **ausschließlich** in `transports/calle.py::CalleBatchTransport.place_many`
— dem einzigen Ort, an dem zwei Empfänger tatsächlich im selben `POST /v1/calls`-Body
landen können. `runner.py::build_requests` kennt Telefonkollisionen seit R17 gar nicht
mehr (wieder ein 3-Tupel statt des R3-4-Tupels); `CalleTransport` (`--serial`) ruft
jeden Request unverändert einzeln auf. Der `--retry`-Sackgassen-Fund löst sich als
direkte Folge mit auf: da `build_requests()` Kollisions-Teilnehmer nicht mehr vorab aus
`due` herausfiltert, nimmt ein Retry sie wieder auf, und `store.record_answer()` (ein
UPSERT) überschreibt den alten `FAILED`-Eintrag beim nächsten echten Versuch von
selbst — kein separater Reset-Schritt nötig. Die bestehende Längenprüfung in
`CalleBatchTransport` bleibt unverändert als zweite Verteidigungslinie für den
weiterhin ungeprüften Fall einer *tatsächlich* abweichenden Antwortliste.

- **Regressionstests (R17-Stand):** `tests/test_calle_batch_transport.py` (neu, ohne
  Netzwerkzugriff, `_request`/`_sleep` gemockt wie in `test_polling.py`) — volle
  Kollision zweier Teilnehmer blockt beide vor jedem Netzwerkaufruf mit gegenseitiger
  Ref-Nennung in der Fehlermeldung; eine Teil-Kollision (2 von 3) lässt den dritten,
  nicht betroffenen Teilnehmer unverändert in einem 1er-Batch durchlaufen; ein Batch
  ohne Kollision ist unbeeinflusst. `tests/test_runner.py`, Abschnitt „two participants,
  one phone number" (umgebaut) — ein serieller/`place_one`-Fanout (was `--serial`
  verwendet) ruft beide Teilnehmer mit getrennten `run_id`s und getrennten Antworten an;
  ein `--retry`-Lauf gegen einen zuvor kollisionsbedingt `FAILED` markierten Teilnehmer
  ruft ihn erneut an und überschreibt die alte Antwort, während ein Lauf ohne `--retry`
  ihn korrekt unangetastet lässt.
- **Berichtsseite (R12, Konsens aus dupliziertem Mapping):** Auch mit diesem Fix bleiben
  in der Datenbank bereits gespeicherte Altfälle (die beiden Runden oben, DB-Stand
  2026-08-22) stehen — `merge.py` behandelt Antworten mit identischer, nicht-leerer
  `run_id` seither als **eine** gezählte Stimme mit sichtbarem Warnhinweis statt als
  zwei, unabhängig davon, wann/wie die Doppelung entstand. Siehe unten,
  „Geteilter Anruf wird nicht doppelt gezählt".

## Weiterhin ungeprüft

- **Parallelität.** Ob mehrere Anrufe gleichzeitig laufen, ist offen. „concurrency
  controls" sind dokumentiert, die Grenze nicht. **Im Code beide Fälle offenhalten.**
- Verhalten bei Besetzt und Nicht-Abheben (`BUSY`, `NO_ANSWER`) — bisher nur
  `COMPLETED` (Abschnitt 1) sowie Mailbox und Ablehnung (Abschnitt 9) gesehen.
- Ob `recipients[].attempts[]` bei mehreren automatischen Nachwahlversuchen jemals
  mehr als einen Eintrag zeigt — im beobachteten Ablehnungsfall war es trotz „bis zu
  3× Nachwahl" genau einer.
- Ob REST- und MCP-Weg dasselbe Kontingent teilen.
- ~~Batch-Dispatch mit zwei identischen Empfängernummern in einem Live-Request~~ —
  **gemessen 2026-08-22, siehe Abschnitt 13.** Der Dienst dedupliziert; der Code
  verhindert seit dem Fix, dass beide Teilnehmer je einen Request bekommen.
- Ob dieselbe Dedup-Kollaps auch bei getrennten seriellen `POST /v1/calls`-Aufrufen
  auftritt (statt einem gemeinsamen Batch-Request) — nicht gemessen, `runner.py`
  behandelt beide Transporte vorsorglich gleich, ohne dass das für den seriellen
  Pfad belegt wäre.
