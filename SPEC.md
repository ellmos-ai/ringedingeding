# SPEC — Ringedingeding

> **Lies zuerst `AGENTS.md`.** Dort stehen die nicht verhandelbaren Regeln
> (Trockenlauf, Safety, Datensparsamkeit, was CALL-E kann).
> Untertitel des Projekts: *ask everyone, get one answer*.

## Das Problem

Eine Frage an mehrere Menschen stellen und **eine** Antwort daraus machen — ohne dass
alle einen Link anklicken müssen. Wer Terminabstimmungen in einer Familie kennt, kennt
das Problem: Drei antworten sofort, zwei nie, einer ruft zurück und sagt es mündlich.

## Warum das eine echte Lücke ist

Im offiziellen Ziel-Repo (`CALLE-AI/awesome-phone-call-agents`) ruft **jeder** Beitrag
genau **eine** Person an. Der `callback-window-coordinator` bespricht Zeitfenster mit
einer Person; `call-on-behalf` erledigt einen delegierten Auftrag. **Niemand führt die
Antworten mehrerer Menschen zusammen.** Genau das ist hier der Beitrag.

Die CALL-E-API unterstützt es nativ: `POST /v1/calls` nimmt `recipients: [...]` als Batch
und liefert je Empfänger ein schema-validiertes Ergebnis (`recipient_result_schema`).

## Was es können muss

### Zwei Fragearten

**1. Termin** — „Wann kannst du am Wochenende?"
- Ergebnis: **Schnittmenge** über alle Befragten
- Mindestens ebenso wichtig: **wer kann wann nicht** — das ist die Information, die man
  am Ende wirklich braucht, um einen Termin zu setzen
- Vorschlagsfenster sind vorgebbar („Sa 14–18, So 10–14") oder offen

**2. Meinung / Entscheidung** — „Sollen wir Oma ein Fotobuch schenken?"
- Optionen vorgebbar → Ergebnis ist eine **Auszählung**
- Enthaltungen und abweichende Meinungen erscheinen **eigenständig**, nicht als
  Rundungsfehler
- Freitext-Zusätze werden erfasst („ja, aber nur wenn es unter 50 € bleibt")

### Ablauf

1. Umfrage anlegen: Frage, Typ (`slot` | `choice` | `open`), Beteiligte (Name + E.164)
2. Trockenlauf zeigt: wer würde angerufen, mit welchem `goal`-Text, welches Schema
3. Anrufe ausführen (nur mit `--live`)
4. Ergebnis zusammenführen und **übersichtlich** ausgeben: Konsolentabelle + Markdown-Export

### Harte Anforderung an die Auswertung

**Nicht erreichte Beteiligte werden nie als „egal" verrechnet.** Sie erscheinen als eigene
Kategorie mit ihrem Endstatus (`NO_ANSWER` ≠ `DECLINED` ≠ `BUSY`). Eine Schnittmenge über
4 von 6 Befragten ist ein anderes Ergebnis als eine über 6 von 6 — und muss auch so
dastehen.

## Datenmodell (Vorschlag, darf begründet abweichen)

SQLite:

```
poll(id, question, kind, options_json, window_json, created_at, status)
participant(id, poll_id, name, phone_e164, status, call_run_id, attempted_at)
answer(participant_id, raw_text, structured_json, received_at, call_status)
```

## Schema-Arbeit (das ist der Kern, nicht Beiwerk)

`recipient_result_schema` je Fragetyp. Beispiel Termin:

```json
{
  "type": "object",
  "required": ["reachable", "refused"],
  "properties": {
    "reachable":      {"type": "boolean"},
    "refused":        {"type": "boolean"},
    "available_slots":{"type": "array", "items": {"type": "string"}},
    "cannot":         {"type": "array", "items": {"type": "string"}},
    "note":           {"type": "string"}
  }
}
```

Beispiel Wahl: `{"choice": {"enum": [...]}, "abstained": bool, "condition": string}`.

Das Schema ist die eigentliche Steuerung des Gesprächs — der Agent muss diese Felder
füllen und wird deshalb danach fragen.

## Parallel oder seriell

**Beides im Code vorsehen.** Ob CALL-E mehrere Anrufe gleichzeitig ausführt, ist
**ungeprüft**. Der Unterschied ist erheblich: 6 Beteiligte à 2 Minuten sind parallel in
2 Minuten erledigt, seriell in 12. Ein Schalter, der beides erlaubt, plus Fortschritts-
anzeige, die in beiden Fällen brauchbar ist.

## Fallstricke

- **Beteiligte sind Privatpersonen.** Der Beweis läuft ausschließlich über eingeweihte
  eigene Kontakte. Keine fremden Nummern, nirgends.
- Der Anruf muss **im ersten Satz** offenlegen, dass hier automatisiert im Auftrag von
  <Name> angerufen wird. Nicht auf Nachfrage — von sich aus.
- Wer nicht antworten will, wird **nicht überredet**. Ein `refused` ist ein gültiges
  Ergebnis.

## Was Erfolg bedeutet

Ein Trockenlauf mit sechs fiktiven Beteiligten, der eine Terminfrage und eine
Meinungsfrage vollständig durchspielt, das Zusammenführen zeigt (inklusive zweier
Nichterreichter) und eine Übersicht ausgibt, die man einer Familie zeigen könnte, ohne
etwas zu erklären.
