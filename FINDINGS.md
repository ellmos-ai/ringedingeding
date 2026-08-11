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

## Weiterhin ungeprüft

- **Parallelität.** Ob mehrere Anrufe gleichzeitig laufen, ist offen. „concurrency
  controls" sind dokumentiert, die Grenze nicht. **Im Code beide Fälle offenhalten.**
- Verhalten bei Besetzt und Nicht-Abheben (`BUSY`, `NO_ANSWER`) — bisher nur
  `COMPLETED` (Abschnitt 1) sowie Mailbox und Ablehnung (Abschnitt 9) gesehen.
- Ob `recipients[].attempts[]` bei mehreren automatischen Nachwahlversuchen jemals
  mehr als einen Eintrag zeigt — im beobachteten Ablehnungsfall war es trotz „bis zu
  3× Nachwahl" genau einer.
- Ob REST- und MCP-Weg dasselbe Kontingent teilen.
