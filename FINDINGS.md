# FINDINGS — gemessen am echten Dienst, 2026-08-01

> Ergänzt `AGENTS.md`. **Diese Befunde stammen aus einem echten Anruf und echten
> API-Aufrufen**, nicht aus der Doku. Wo sie der Doku widersprechen, gilt die Messung.
> Belegt in `.HACKATHONS/2026-call-e/_evidence/EVIDENCE-001` und `-002` (Operator).

## 1. Man KANN live mitlesen — über `activity`, nicht über `transcript`

Während des Gesprächs bleibt `transcript` **`null`**. Aber `activity` enthält den
Gesprächsverlauf in Echtzeit, beide Sprecher, mit Millisekunden-Zeitstempeln:

```
17:37:45.146 | Call is ringing.
17:37:49.509 | Call connected.
17:37:50.769 | Bot is speaking: Dies ist ein automatisierter Testanruf im Auftrag von Lukas.
17:37:51.577 | Callee said: hallo
17:37:52.245 | Callee said: Hallo.
17:38:15.892 | Callee said: 2. Ja, unzufrieden.
17:38:21.375 | Call ended; syncing final Calling result.
```

**Achtung Dubletten:** „Callee said" kommt teils zweimal — erst eine Rohfassung
(`hallo`), Sekundenbruchteile später die korrigierte (`Hallo.`). Die Spracherkennung
liefert streamend und bessert nach. Wer mitliest, muss zusammenführen.

## 2. `status` ist als Fortschrittsanzeige unbrauchbar ⚠️

Der Status blieb auf **`PREPARING`**, während bereits gesprochen wurde — und sprang erst
nach Gesprächsende auf `COMPLETED`:

```
17:37:53Z | status=PREPARING | activity=12 | last: Callee said: Hallo.
17:38:09Z | status=PREPARING | activity=15 | last: Bot is speaking: Bitte antworten Sie mit…
17:38:45Z | status=COMPLETED | activity=21 | last: Call ended from realtime events.
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

„2. Ja, unzufrieden." wurde eigenständig als *unzufrieden* kategorisiert;
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

## Weiterhin ungeprüft

- **Parallelität.** Ob mehrere Anrufe gleichzeitig laufen, ist offen. „concurrency
  controls" sind dokumentiert, die Grenze nicht. **Im Code beide Fälle offenhalten.**
- Verhalten bei Besetzt und Nicht-Abheben (`BUSY`, `NO_ANSWER`) — bisher nur
  `COMPLETED` (Abschnitt 1) sowie Mailbox und Ablehnung (Abschnitt 9) gesehen.
- Ob `recipients[].attempts[]` bei mehreren automatischen Nachwahlversuchen jemals
  mehr als einen Eintrag zeigt — im beobachteten Ablehnungsfall war es trotz „bis zu
  3× Nachwahl" genau einer.
- Ob REST- und MCP-Weg dasselbe Kontingent teilen.
- **Batch-Dispatch mit zwei identischen Empfängernummern in einem Live-Request**
  (Testdesign 2026-08-11 für Punkt E): ob der Dienst das als zwei getrennte
  Anrufe behandelt oder die Empfängerliste dedupliziert/kürzt, ist unbeobachtet —
  nur die Code-Reaktion auf eine mengenmäßig abweichende Antwortliste ist bekannt
  (siehe Abschnitt 10 oben).
