# ARCHITEKTUR — Ringedingeding

> Bildet das **vollständige** Produktkonzept aus `UI-SPEC.md` ab, nicht nur die erste
> Stufe. Nichts ist gestrichen; was später kommt, hat hier schon seinen Platz im
> Datenmodell. Gebaut wird in Stufen — **entworfen wird einmal.**
>
> Vorgelagerte Dokumente: `AGENTS.md` (Regeln), `FINDINGS.md` (gemessenes Verhalten),
> `SPEC.md` (Bauauftrag Kern), `UI-SPEC.md` (Produktkonzept des Nutzers).

---

## 1. Der eine Gedanke: ein Ablauf, drei Zugänge

```
                    ┌──────────────────────────────┐
   CLI  ───────────►│                              │
                    │   service.py                 │
   SKILL.md ───────►│   ein Ablauf, eine Logik     │──► store ──► SQLite
   (fremder Agent)  │                              │
                    │                              │──► runner ──► transports ──► CALL-E
   Web-Oberfläche ─►│                              │
                    └──────────────────────────────┘
```

`service.py` ist die **einzige** Stelle, an der der Ablauf steht. Die Weboberfläche ist
eine Sicht darauf, die CLI ist eine zweite, `SKILL.md` beschreibt dieselbe Folge für einen
fremden Agenten. Keine der drei Schichten darf Logik enthalten, die die anderen zwei nicht
haben — sonst zerfällt das Werkzeug in drei Werkzeuge.

**Entwurfsrichtung:** Erst die Fragefolge eines Agenten formulieren, daraus die Feldliste
ableiten. Genau deshalb steht `SKILL.md` neben diesem Dokument und nicht hinterher.

### Die Fragefolge (der Ablauf, sprachlich)

| # | Frage | Feld | Stufe |
|---|---|---|---|
| 1 | Um was geht's? Wozu möchtest du einladen? | `project.occasion` | 1 |
| 2 | Terminfindung oder Meinungen einholen? | `project.mode` | 1 (nur Termin) / 2 |
| 3 | Welche Art von Termin? | `project.date_kind` | 1 (2 Arten) / 2 (6) |
| 4 | An welchen Tagen? | `project_slot.day_date` | 1 |
| 5 | Zu welcher Uhrzeit — für alle Tage gleich? | Standardzeiten | 1 |
| 6 | Weicht ein Tag ab? | Slots je Tag | 1 |
| 7 | Wen möchtest du einladen? | `project_invitee` | 1 |
| 8 | Wie soll begrüßt und verabschiedet werden? | `phrase` | 1 |
| 9 | *(Auftragstext zeigen)* Trockenlauf, Probelauf oder echte Anrufe? | `round.mode` | 1 |
| 10 | *(Anrufe laufen — Live-Ansicht)* | `call` | 1 |
| 11 | Gibt es einen Lieblingstermin? Wer muss dabei sein? Wie viele reichen? | `project_criteria` | 1 |
| 12 | Welcher Termin wird es? | `decision` | 1 |
| 13 | Wie sollen die anderen informiert werden? | Einladungsrunde | 1 (Telefon) / 2 (Mail) |

Fragen 2, 3, 8 haben in Stufe 2 mehr Optionen — **dieselben Felder**, nicht neue.

---

## 2. Die Architekturentscheidung, die jetzt fallen muss

> *„Muss man das Fenster immer offen haben?"* — **Nein.**

**Der Browser zeigt nur an, er treibt nicht.**

```
Browser ──POST /rounds──►  FastAPI  ──►  RunJob (Thread im Server)
                                             │
   ◄──SSE /live/stream────  EventBus  ◄──────┘  on_event / on_activity
                                             │
                                             └──►  Store (eigene Verbindung)  ──► SQLite
```

* Das Abfragen des Anrufstands läuft im **Serverprozess**, nicht im Browser.
* Fenster zu → die Runde läuft weiter. Fenster wieder auf → Stand kommt aus der
  **Datenbank**, danach hängt sich der Stream wieder an.
* SSE ist ein **Beschleuniger, keine Voraussetzung**: jede Live-Ansicht ist auch ohne
  JavaScript vollständig (die Seite trägt ein `<meta refresh>`), und der Datenstand steht
  immer in SQLite.
* **Jeder Thread bekommt seine eigene `Store`-Instanz.** SQLite-Verbindungen sind nicht
  thread-sicher; eine geteilte Verbindung wäre der erste Bug gewesen.

**Kein versteckter Dauerlauf.** Ein `RunJob` endet, wenn seine Runde fertig ist. Es gibt
keinen Scheduler, keine Wiederholschleife, keinen Daemon — das verlangt `AGENTS.md`, und
die Weboberfläche weicht davon nicht ab. Wiederholung stößt der Mensch an.

---

## 3. Datenmodell

**Grundsatz: Eine Runde IST eine Umfrage.** Die vorhandenen Tabellen `poll` /
`participant` / `answer` bleiben, wie sie sind, und werden zur **Runden-Schicht** eines
Projekts. Damit fahren CLI, Skill und Oberfläche denselben Motor (`runner.py`,
`merge.py`, `transports/`), und eine im Browser gestartete Runde erscheint in
`ringedingeding list`. Das Projekt liegt als eigene Schicht **darüber**.

Ein Projekt hat mehrere Runden, und das ist keine Spitzfindigkeit: die Verfügbarkeits­abfrage,
das spätere **Einladungs­telefonat** und **nachgeholte Anrufe** sind drei Runden desselben
Projekts. Wer das nicht vorsieht, kann die Einladung am Ende nicht verschicken.

```
contact ──┬── contact_channel (phone | email | …)          Kontaktbuch, projektunabhängig
          └── contact_group_member ── contact_group        Gruppenprofile        [Stufe 2]

project ──┬── project_slot        Termin-Kandidaten (alle sechs Terminarten)
          ├── project_invitee ─── contact
          ├── project_question    frei benennbare Fragen   [Stufe 2]
          ├── phrase              Begrüßung/Schluss/Policy
          ├── project_criteria ── project_must_have
          ├── decision            der festgelegte Termin
          └── poll (= Runde) ──── participant ──── answer     ← vorhandener Motor

connector                          Kontakt-Import           [Stufe 3]
```

### Tabellen im Einzelnen

| Tabelle | Zweck | Ab Stufe |
|---|---|---|
| `contact` | Person im eigenen Kontaktbuch. `photo_blob`/`photo_mime` für das Bild, `source_connector_id`/`external_id` für späteren Import | 1 (Import-Spalten leer) |
| `contact_channel` | `(contact_id, kind, value, position)`. **Kein `phone`-Feld am Kontakt** — sonst ist der E-Mail-Weg in Stufe 2 eine Migration statt einer Zeile | 1 (`phone`), 2 (`email`) |
| `contact_group` / `contact_group_member` | „meine Ritterrunde". Trägt eigene `phrase`-Sätze und `project_question`-Fragen | 2 (Tabellen ab 1) |
| `project` | `occasion`, `mode` (`schedule`\|`roundtable`), `date_kind`, `organizer`, `language`, `state`, `fixture_name` | 1 |
| `project_slot` | **Ein Zeilenformat für alle sechs Terminarten**: `day_date`, `end_date`, `weekday`, `start_time`, `end_time`, `all_day`, `label` | 1 |
| `project_invitee` | `(project_id, contact_id, position)` | 1 |
| `project_question` | Frei benennbare Frage je Projekt/Gruppe | 2 |
| `phrase` | `(scope, kind, text)`; `kind` = `greeting`\|`closing`\|`policy`, `scope` = `global`\|`project`\|`group`. Das ist der PromptBoard-Anschluss | 1 (greeting/closing) |
| `project_criteria` / `project_must_have` | Lieblingstermin, Pflichtpersonen, Mindestanzahl | 1 |
| `decision` | Der terminierte Slot | 1 |
| `poll` **+ `project_id`, `round_kind`, `simulated`** | Eine Runde. `round_kind` = `availability`\|`roundtable`\|`invitation` | 1 |
| `participant` **+ `contact_id`** | Teilnehmer einer Runde, rückgebunden an den Kontakt | 1 |
| `answer` | unverändert | vorhanden |
| `connector` | Mail-/Adressbuch-Konnektor | 3 (Tabelle ab 1) |

Die neuen Spalten an `poll` und `participant` gehen über den vorhandenen additiven
Migrationsweg (`_ADDED_COLUMNS`) — es wird nie etwas gelöscht oder umgeschrieben.

### Warum `project_slot` so aussieht

Die sechs Terminarten aus `UI-SPEC.md` sind **eine** Zeilenform, nicht sechs:

| Terminart | `day_date` | `end_date` | `weekday` | `start`/`end` | `all_day` |
|---|---|---|---|---|---|
| Tagestermin (Slots) | Tag | – | – | ✓ | 0 |
| ganzer Tag | Tag | – | – | – | 1 |
| Woche anbieten | Montag | Sonntag | – | – | 1 |
| Monat anbieten | 1. | letzter | – | – | 1 |
| mehrere Tage zusammenhängend | erster | letzter | – | ✓ (erster/letzter) | 0 |
| regelmäßiger Wochentermin | – | – | `2` (Di) | ✓ | 0 |

`label` ist der **kanonische Text**, der in `poll.slots` wandert, den der Sprach-Agent
zurückgibt und über den `merge.py` zusammenführt. Slot-Zeile und Merge-Zeile sind
dieselbe Sache — ohne diese Kopplung stimmt die Kalenderansicht nicht mit dem Ergebnis
überein.

### Die vier Zustände

Der Nutzer verlangt ausdrücklich vier getrennte Zustände je Slot. Sie werden **abgeleitet,
nicht gespeichert** — abgeleiteter Zustand, der doppelt liegt, geht auseinander:

| Zustand | Herkunft | Darstellung |
|---|---|---|
| **kann** | `available_slots` enthält den Slot | grün |
| **kann nicht** | `cannot` enthält den Slot | rot |
| **nicht erreicht** | `Coverage.unreached` / `pending` — `NO_ANSWER` ≠ `BUSY` ≠ `DECLINED` | Fragezeichen, ausgegraut |
| **gar nicht anrufbar** | Kontakt hat **keinen** `contact_channel` vom Typ `phone` | eigene Liste darunter, Nummer nachtragbar |

Der vierte Zustand entsteht damit **eine Ebene über** dem Anruf: Wer keine Nummer hat,
wird nie Teilnehmer einer Runde. Genau deshalb liegt die Nummer in `contact_channel` und
nicht am Kontakt.

**Nachtragen braucht keinen Sonderweg.** Die Verfügbarkeitsrunde ist **eine** `poll`, die
mehrfach *gelaufen* werden kann; der Runner überspringt jeden, der schon eine Antwort hat.
Wird eine Nummer ergänzt, macht `service.resync_contact()` die Person zum Teilnehmer
derselben Runde, und der nächste Lauf ruft genau sie an — sonst niemanden. Ohne diesen
Schritt verschwände sie stattdessen aus dem Bericht, weder angerufen noch als „nicht
kontaktierbar" gelistet; das war ein echter Fehler im Bau und ist durch einen Test
festgenagelt.

Schweigen zu einem Slot ist **kein Nein**: Wer nur „Samstag geht" gesagt hat, steht bei
Sonntag unter *unbekannt*. Das ist bereits die Regel in `merge.py` und bleibt es.

---

## 4. Die drei Betriebsarten

Durchgehend sichtbar, nie vermischt:

| Art | Auslöser | Was passiert | Kennzeichnung |
|---|---|---|---|
| **Trockenlauf** | Standardschaltfläche | Kein Anruf. Zeigt den Auftragstext, wer angerufen würde, Kosten, Dauer. Bei Fixture-Projekten werden die hinterlegten Antworten abgespielt | neutral |
| **Probelauf** | eigene Schaltfläche | Erzeugt **erfundene**, schema-gültige Antworten (deterministisch je Kontakt), damit Kalender, Kriterien und Entscheidung ohne Konto vorführbar sind | Runde `simulated=1`, Banner auf **jeder** Ansicht |
| **Echte Anrufe** | eigener, rot abgesetzter Bereich | Verlangt die getippte Bestätigung `CALL THEM`, zeigt Anzahl und Kosten daneben, verweigert Beispielnummern, verlangt `CALLE_API_KEY` in der Umgebung | rot |

**Keine Zugangsdaten in der Oberfläche.** Der Schlüssel wird ausschließlich aus der
Umgebung gelesen; fehlt er, erklärt die Seite das und bietet **kein Eingabefeld** an.

Warum es den Probelauf gibt: Die CLI verweigert zu Recht, Antworten für echte Menschen zu
erfinden. Für die Oberfläche wäre das aber eine Sackgasse — ohne Antworten sieht man
Kalender, Kriterien und Einladung nie. Der Probelauf löst das, ohne zu lügen: Die Daten
sind als erfunden markiert, liegen in einer eigenen Runde und lassen sich mit einem Klick
wegwerfen.

---

## 5. Rufnummern, Daten, Sichtbarkeit

* **Maskiert überall.** Die Oberfläche zeigt nie eine vollständige Rufnummer — auch nicht
  im Bearbeiten-Formular des eigenen Kontaktbuchs (dort: leeres Feld, „leer lassen =
  unverändert").
* **Der Auftragstext ist vor dem Absenden sichtbar**, wörtlich, so wie er das Haus
  verlässt.
* **Datensparsamkeit:** An CALL-E gehen nur Vorname, Rufnummer und der Auftragstext.
  Keine Vorgeschichte, keine anderen Teilnehmer, kein Bild.
* Bilder liegen als Blob in der lokalen SQLite und werden unter
  `/contacts/{id}/photo` ausgeliefert; ohne Bild erzeugt der Server ein Initialen-SVG.

---

## 6. Stufenplan

### Stufe 1 — der Kern *(dieser Bauabschnitt)*

Anlass → Terminart **Tagestermin** und **ganzer Tag** → Kontakte aus eigener Liste (mit
Bild; ohne Telefonnummer ausgegraut und nicht berücksichtigt) → Begrüßungs- und
Schlussformel → Auftragstext-Vorschau → Anrufe mit Live-Ansicht → Projekt-Kalenderansicht
mit Zahl je Slot, Detail bei Klick, vier Zuständen und der Liste der Nichtanrufbaren →
Kriterien mit „3 von 3" → Termin festlegen → Einladung telefonisch verschicken mit
Übersicht, wer erreicht wurde.

### Stufe 2

* **Runder Tisch** — `project.mode = roundtable`, Runde `round_kind = roundtable`.
  Nutzt `PollKind.OPEN`/`CHOICE`, die es schon gibt. Chat-artige Antwortansicht.
* **Gruppenprofile** — `contact_group` bekommt eigene `phrase`- und
  `project_question`-Sätze. Ein Projekt kann aus einem Gruppenprofil erzeugt werden.
* **Frei benennbare Fragen** — `project_question`, Standardvorschläge plus Pluszeichen.
* **Restliche Terminarten** — Woche, Monat, mehrere Tage, regelmäßig. Nur der
  Slot-Erzeuger und die Kalenderansicht ändern sich; `project_slot` bleibt.
* **E-Mail als zweiter Kanal** — `contact_channel.kind = 'email'`, ein zweiter Transport
  neben `transports/calle.py`. Die Einladungsrunde bekommt „nur Mail / nur Telefon /
  Telefon, sonst Mail / ich informiere selbst".
* **Policies und Skills je Projekt** — `phrase.kind = 'policy'`, PromptBoard-Muster:
  gespeicherte Sätze und Regeln werden zum Gesamt-Auftragstext zusammengesetzt.
  `schemas.build_task_text()` bekommt dafür einen Einschub, keine Umschreibung.

### Stufe 3

* **Konnektoren** — `connector` + `contact.source_connector_id`/`external_id`. Import ist
  ein Schreibvorgang auf `contact`/`contact_channel`, kein neues Modell.
* **Zugriff der eigenen lokalen KI auf Kontakte** — dieselbe `service.py`-Schicht, als
  MCP-Werkzeug oder über `SKILL.md`. Lesend, maskiert, mit ausdrücklicher Freigabe.
* **Export in fremde Kalender** — Google, Microsoft, Android/iOS. Quelle ist `decision`
  plus `project_slot`; ICS ist der gemeinsame Nenner und braucht keine Modelländerung.
* **LLM-Zusammenfassung und Berichte** — PDF/Markdown. `render.py` liefert das Markdown
  bereits; die Zusammenfassung ist ein Aufruf nach außen, der die Rohantwort **nicht**
  ersetzt (FINDINGS 7: der Agent deutet, also muss die Deutung prüfbar bleiben).

---

## 7. Modulschnitt

```
ringedingeding/
  models.py schemas.py merge.py slots.py store.py runner.py phone.py
  safety.py activity.py timings.py render.py validate.py fixtures.py   ← vorhanden
  projects.py      Projekt-Schicht: Tabellen, Kontakte, Slots, Kriterien, Entscheidung
  service.py       DER Ablauf. Die einzige Schicht, die CLI und Web gemeinsam aufrufen
  transports/
    base.py calle.py fixture.py                                        ← vorhanden
    rehearsal.py   erfundene, schema-gültige Antworten für den Probelauf
  web/
    app.py         FastAPI-Routen, dünn
    jobs.py        RunJob + EventBus — hier wohnt „der Browser treibt nicht"
    ui.py          Aufbereitung fürs Template (Kalenderraster, Zustände, Bewertung)
    templates/     Jinja2, server-gerendert
    static/        app.css, app.js, htmx.min.js (vendort, kein CDN, kein npm)
SKILL.md           derselbe Ablauf für einen fremden Agenten
```

**Abhängigkeiten:** Die CLI bleibt **abhängigkeitsfrei**. FastAPI, uvicorn und Jinja2
liegen im Extra `[web]`. Wer nur die CLI nutzt, installiert nichts. `htmx.min.js` ist
vendort — ein CDN-Verweis würde die Oberfläche offline unbrauchbar machen und wäre damit
ein Verstoß gegen die Trockenlauf-Pflicht.

---

## 8. Abgleich mit `ABLAUF.md`

`ABLAUF.md` ist die Formalisierung desselben Konzepts als Fragebaum und die
verbindliche Grundlage für Skill **und** Oberfläche. Dieser Abschnitt hält fest, wo jeder
Knoten im Datenmodell landet — und wo abgewichen wird.

| Knoten | Art | Wohin im Modell | Stufe |
|---|---|---|---|
| A1 Anlass | PFLICHT | `project.occasion` → `service.question_for()` | 1 |
| A2 / B1 wen | PFLICHT | `project_invitee` → `contact` | 1 |
| B1a Nummern beschaffen | ABLEITBAR | `contact_channel`; Mail/Kalender über `connector` | 1 / 3 |
| B1b ohne Nummer | SONDERFALL | kein `contact_channel` vom Typ `phone` → `service.uncallable()`, Nachholen über `resync_contact()` | 1 |
| B1c Gruppe merken | OPTIONAL | `contact_group` | 2 |
| A3 Terminart | PFLICHT | `project.date_kind` | 1 (2 von 6) |
| A4a–A4d Slots | PFLICHT | `project_slot` — **ein** Zeilenformat | 1 (a, b) |
| B2 Frage | PFLICHT | `poll.question` | 2 |
| B2a Antwortform | ABLEITBAR | `PollKind` `slot`/`choice`/`open` | 2 |
| **B3 Dringlichkeit** | OPTIONAL | **`project.urgency`** — am 2026-08-02 nachgetragen | 1 |
| A5 / B4 Sätze, Policy | OPTIONAL | `phrase` (`greeting`/`closing`/`policy`) | 1 / 2 |
| A6 / B5 Vorlegen | GATE | `service.preview()` + `RunMode` | 1 |
| A7 Kanal | PFLICHT | Einladungsrunde; E-Mail über `contact_channel` | 1 / 2 |
| A8 Einladungstext | ABLEITBAR | `default_invitation_text()`, in `poll.question` überschreibbar | 1 |
| A9 nachträglich informieren | OPTIONAL | `set_invitees()` gleicht **beide** Runden ab | 1 |
| A10 Übersicht | — | Live-Ansicht der Einladungsrunde | 1 |

### Die eine Lücke, die der Abgleich fand

**B3 Dringlichkeit** hatte im Modell keinen Platz. Nachgetragen als
`project.urgency` (Freitext, additive Spaltenmigration). Sie geht als **unzitierte**
Anweisung in den Auftragstext — zitiert würde die private Notiz vorgelesen —, verändert
also den Ton und sonst nichts. Die Regel „nicht überreden" steht davor und bleibt.

### Zwei Stellen, an denen die Quellen sich widersprechen

**1. Farben der Live-Ansicht.** `UI-SPEC.md` sagt für die laufenden Anrufe
*„nicht erreicht → rot, durchgestrichen"*. `ABLAUF.md` §2 trennt feiner:
`DECLINED` (weggedrückt) → **rot**, `NO_ANSWER`/`BUSY`/`VOICEMAIL` → **Fragezeichen,
ausgegraut**. **Gebaut ist ABLAUF**, weil es dieselbe Unterscheidung durchhält, die
`UI-SPEC` für die Ergebnisansicht ausdrücklich verlangt (*„bewusst unterschieden!"*), und
weil ein durchgestrichener Name bei einem klingelnden Telefon Wissen behauptet, das
niemand hat. `FAILED`/`EXPIRED`/`CANCELED` bekommen rot **mit Grund**.

**2. Reihenfolge der Fragen.** `UI-SPEC` stellt die Kontakte **nach** der Terminart,
`ABLAUF` (A2 vor A3) davor. Die Oberfläche folgt `UI-SPEC` (Termine → Personen), weil die
Schritte dort ohnehin frei anspringbar sind; der Skill folgt `ABLAUF`. Das ist folgenlos —
kein Schritt hängt vom anderen ab.

### Was Abschnitt 6 für die Oberfläche bedeutet

PFLICHT → Feld mit `required`. ABLEITBAR → vorausgefülltes, änderbares Feld (in Stufe 1
ist das der Einladungstext). OPTIONAL → `<details class="optional">`, **zugeklappt**,
solange nichts darin steht — ein aufgeklappter optionaler Abschnitt wird abgearbeitet, und
dann war er nicht optional. GATE → die Auftragsseite mit Anzahl, Kosten und getippter
Bestätigung.

---

## 9. Was bewusst nicht gebaut wird

* **Kein Nutzerkonto, keine Anmeldung.** Die Oberfläche bindet an `127.0.0.1`. Ein
  Mehrbenutzerbetrieb würde Rechteverwaltung erfordern, die niemand verlangt hat.
* **Keine Intervall-Arithmetik auf Slots.** „Sa 14–18" und „Sa 15–17" bleiben zwei Slots
  (siehe `slots.py`). Ein Parser für frei gesprochene Zeitangaben erzeugt
  selbstbewussten Unsinn.
* **Kein Eingriff ins laufende Gespräch.** CALL-E kann es nicht, und dagegen anzubauen
  wäre Selbstbetrug.
* **Keine automatische Zusammenfassung von Freitext.** Erst ab Stufe 3, und dann neben
  der Rohantwort, nie an ihrer Stelle.
