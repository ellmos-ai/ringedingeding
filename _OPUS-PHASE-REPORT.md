# Phasenbericht — autonomer Lauf, 2026-08-02

> Operator: Claude Code (Opus 5, ASUS-GEI). Ablauf nach dem Skill
> `hackathon-operator`. Arbeitsbereich ausschließlich
> `C:\_Local_DEV\repos\ringedingeding`; außerhalb wurde nur gelesen.

---

## Kurzfassung

| Phase | Vorher | Jetzt |
|---|---|---|
| 4 Bau | fertig, 297 Tests | fertig, **308 Tests** |
| 5 Abnahme & Beweis | nur Trockenlauf, keine Kernprobe | **Kernprobe gebaut, belegt, selbstprüfend** — Feldversuch weiterhin offen (Nutzersache) |
| 6 Medien | **nichts** | **`STORYBOARD.md` fertig, am Gate** — kein Frame gerendert |
| 7 Einreichung | — | **`DEVPOST.md` als Entwurf**, vier Felder als blockiert markiert |

Zwei lokale Commits, kein Push, kein Anruf, keine Veröffentlichung.

---

## A — Phase 5: die Beweisführung

### Was gebaut wurde

**`ringedingeding proof`** — ein Befehl, eine Sekunde, kein Konto, kein Netz,
kein Telefon. Er baut eine Siebenpersonen-Runde in einer temporären Datenbank,
spielt gescriptete Antworten ab und **prüft danach sein eigenes Ergebnis**,
statt es zu beschreiben.

Das Szenario (`ringedingeding/fixtures/weekend-hike.json`, gebündelt wie die
anderen drei) provoziert absichtlich die vier Arten, wie eine Zusammenführung
still lügen kann:

- **Widerspruch** — Nora kann Sa 14-18, Paul kann nicht. Beide stehen in
  derselben Zeile; keiner gewinnt durch Zählen.
- **Halbe Zusage** — Rike nennt nur Sa 09-13 und schweigt zu den anderen zwei.
  Die stehen als `silent`, nicht als `cannot`.
- **Nichterreichbarkeit, differenziert** — Tara `NO_ANSWER`, Uwe `BUSY`,
  Sven hat abgenommen und die Antwort verweigert. Drei Zustände, nicht einer.
- **Gar nicht anrufbar** — Vera steht auf der Gästeliste, im Adressbuch fehlt
  ihre Nummer. Sie wird nicht angerufen und **steht trotzdem im Ergebnis**.

Acht Prüfungen laufen anschließend gegen genau diese Punkte, plus: das Ergebnis
trägt seinen Nenner, keine vollständige Rufnummer erscheint in der Ausgabe, der
nachgeholte Lauf ruft genau eine Person an.

### Der Schluss, der die Sache trägt

Solange Vera keine Nummer hat, meldet die Runde:

```
=> Works for all 3 who answered: Sat 09-13
```

Nummer nachtragen, dieselbe Runde noch einmal — **ein** Anruf:

```
outstanding calls: 1  (Vera)
already answered, not called again: Nora, Paul, Rike, Sven, Tara, Uwe

4 of 7 invited people answered.
=> No slot works for all 4 who answered.
```

Ein Werkzeug, das Vera hätte fallen lassen, hätte einen Termin gemeldet, der
nicht funktioniert. Das ist die Kernaussage des Projekts in fünf Zeilen echter
Ausgabe.

### Läufe mit echter Ausgabe

| Lauf | Ergebnis |
|---|---|
| `python -m ringedingeding proof` (3×, gemessen mit `perf_counter` um `subprocess.run`) | **Exit 0**, `1.05 / 0.76 / 0.84 s`, 96 Zeilen, `8 of 8 checks passed` |
| `python -m pytest` | **308 passed** in 54.59 s (vorher 297) |
| `python -m pytest tests/test_proof.py` | **10 passed** in 3.53 s |
| `python -m ringedingeding demo` | Exit 0, jetzt `# 4/4 weekend-hike`, „Dry run complete. No call was placed" |
| AST-Import-Scan über das Paket (ohne `web/`) | „NOT in the standard library: **none**" — `proof.py` bringt nur `tempfile` mit |

**Die Prüfungen können auch scheitern**, und das ist getestet:
`tests/test_proof.py` manipuliert je einen gescripteten Antwortsatz und verlangt,
dass der Befehl fällt (Paul zur Zustimmung gebracht, Rikes Schweigen in ein Nein
verwandelt, Vera mit allen einig gemacht). Ohne diese drei Fälle wäre
„8 of 8 passed" Dekoration.

**Ein Zwischenfehler steht im Protokoll**, weil er zur selben Klasse gehört:
Meine erste Sabotage von Vera war zu schwach und ging durch — eine Prüfung, die
nicht scheiterte, obwohl sie sollte. Notiert in `EVIDENCE.md` §20.

**Der Befehl fasst die Datenbank nicht an, die er bekommt.** Er arbeitet in einem
`tempfile.TemporaryDirectory`; ein Test liest die Bytes der übergebenen Datei
vorher und nachher und verlangt Gleichheit.

### Wie das zum Bestand steht

Die Zusammenführungsregeln waren schon in `tests/test_merge.py` festgenagelt
(19 Tests, u. a. `test_unreached_are_not_counted_as_indifferent`,
`test_silence_about_a_slot_is_unknown_not_a_no`,
`test_declined_is_its_own_bucket_not_unreached`). Was fehlte, war die Ebene
darüber: **eine Vorführung, die ein Mensch ohne Zugänge in einer Sekunde selbst
ausführen kann** und die dabei ihre eigenen Aussagen prüft. Die Kernprobe
ersetzt die Unit-Tests nicht, sie macht sie vorzeigbar.

---

## B — Phase 6: das Storyboard

`STORYBOARD.md`, in der vom Skill vorgeschriebenen Reihenfolge:

1. **Hook** (8 s): auf dem Schirm steht `=> Works for all 3 who answered: Sat 09-13`.
   Der Zuschauer liest ein Ergebnis. Dann: *Seven people were asked.*
2. **Narration im Wortlaut**, englisch, sechs Abschnitte, **238 Wörter**.
   Bei ~155 Wörtern/Minute rund 92 Sekunden — **als Rechnung gekennzeichnet,
   nicht als Messung**; die Ist-Längen werden nach der Vertonung eingetragen.
3. **Erst danach die Bilder** je Abschnitt, mit Quelle und Status.
4. **Policies fürs ganze Video** — Farbe, Schnitt, Bewegung, Typografie, Ton,
   Untertitel, Kennzeichnung.

**Was dabei auffiel und den Entwurf besser macht:** Sechs von acht Bildern sind
**echte Programmausgabe**. Die Kernprobe aus Teil A liefert die komplette
Herzensszene in einem Durchlauf. Die Kennzeichnung `CONCEPT DRAFT — NOT BOUND TO
REAL DATA` gilt damit der *Inszenierung*, nicht den Daten — es gibt fast nichts
zu erfinden.

Die Learnings des Schwesterprojekts sind eingearbeitet: englische Stimme
(`en-US-ChristopherNeural`) für englischen Text, 90 statt 138 Sekunden,
Kennzeichnung über ein **umgetextetes vorhandenes** Badge statt einer neuen
Ebene, `id` an jedem Audio-Element, `hyperframes check` **vor** dem Render,
Renderdauer eingeplant.

**Zwei Platzhalter, beide mit Notiz** (ein Platzhalter ohne Notiz wäre eine
Lücke): die Vergleichskarte zur Anbieter-App (Text steht, Layout fehlt) und die
Schlusskarte, deren Repo-Adresse **leer bleibt, bis der Nutzer veröffentlicht** —
eine erfundene Repository-Adresse ist genau der Fehler, den `AGENTS.md` verbietet.

**Bewusst nicht im Entwurf: die Weboberfläche.** Sie ist gebaut und getestet, aber
laut `EVIDENCE.md` §14 hat sie **nie ein Mensch im Browser angesehen**. Ein
Bildschirmvideo davon würde etwas behaupten, das niemand geprüft hat.

`STORYBOARD.md` §5 listet **jede Zahl, die im Video vorkommen darf, mit Herkunft**
— und die, die verboten bleiben („spart X Minuten").

---

## C — README

- Neuer Abschnitt **„Why not just use the CALL-E app?"** ganz vorn: erst das Lob
  für die Anbieter-App (für den Einzelanruf schneller als alles Selbstgebaute),
  dann der Unterschied — viele Anrufe aus einem Auftrag, schema-validierte statt
  prosaischer Antworten, ein Ergebnis statt sechs Protokolle. Direkt darunter der
  Startbefehl der Kernprobe.
- **„Try it without an account"** führt jetzt mit `proof` (kurz) und dann `demo`
  (breit).
- Befehlstabelle, Projektstruktur und `SKILL.md` um `proof` ergänzt. In `SKILL.md`
  steht ausdrücklich, wann ein fremder Agent ihn zeigen soll: wenn jemand fragt
  *„und was, wenn nicht alle antworten?"*.

---

## D — Phase 7 vorbereitet, nicht ausgeführt

`DEVPOST.md` — vollständiger Einreichungstext, **Listen statt Tabellen**, weil
die Plattform keine Markdown-Tabellen rendert. Enthält Elevator Pitch,
Inspiration, What it does, die Abgrenzung zur Anbieter-App, How we built it,
Challenges (die sechs gemessenen Befunde inkl. des `PREPARING`-Bugs), What we
learned, What's next, Built with.

**Vier Felder sind als blockiert markiert**, jedes ist eine Nutzeraktion:
Repository-URL (existiert erst nach Veröffentlichung), Pull Request, Video-Link,
CALL-E-Konto-E-Mail (steht bewusst nirgends im Repo).

Eine Regelangabe wurde nachgeprüft statt behauptet: „kein Bestandscode" —
`git log` zeigt den ersten Commit am **2026-08-01 19:18 +0200**, also nach dem
Stichtag 2026-07-23.

---

## Wo mich ein Gate gestoppt hat

| Gate | Wo genau |
|---|---|
| **Kein echter Anruf** | Der Feldversuch mit echten, eingeweihten Teilnehmern ist der einzige noch offene Punkt der Phase 5. Er ist keine Bauaufgabe: er braucht ein CALL-E-Konto mit Guthaben — der Stand lag nach dem einen gemessenen Anruf bei **−0,05 USD**, die 20 Freianrufe der Ausschreibung waren nicht gutgeschrieben. In `EVIDENCE.md` §22 als „still not executed" festgehalten. |
| **Kein Render** | Das Storyboard **ist** das Gate. Vertont und gerendert wird erst nach der Freigabe. |
| **Kein Push, keine Veröffentlichung** | Zwei lokale Commits, `git status` sauber, kein Remote-Kontakt. Repo-URL und PR bleiben in `DEVPOST.md` leer. |
| **Keine Zugangsdaten** | Der API-Schlüssel wird nirgends gelesen oder genannt; nur der Fundort steht in den Systemnotizen des Operators, nicht hier. Rufnummern sind überall maskiert — eine der acht Prüfungen der Kernprobe misst das mit `\+\d{6,}` über die eigene Ausgabe. |

---

## Was der Nutzer jetzt entscheiden muss

**Fünf Fragen zum Storyboard** (ausführlich in `STORYBOARD.md` §8):

1. **Trägt der Hook?** *„Works for all three who answered." So — Saturday, then?*
   Sitzt der nicht, ist alles Weitere verfrüht.
2. **Ist Vera die richtige Herzensszene** (Ehrlichkeit) — oder soll der
   Bestätigungsschritt vor dem Wählen die Hauptszene sein (Sicherheit)?
3. **Bleibt die Abgrenzung zur Anbieter-App drin?** Sie kostet 14 von 90
   Sekunden und beantwortet die Frage, die die Jury ohnehin stellt.
4. **Musik geduckt oder ungeduckt** — es werden zwei Fassungen gebaut.
5. **Soll die Weboberfläche in den Einreichungsschnitt?** Dann muss sie vorher
   jemand aufmachen und ansehen.

**Zwei Entscheidungen darüber hinaus:**

6. **Guthaben aufladen für den Feldversuch?** Ohne das bleibt Phase 5 im
   Trockenlauf-Zustand, und `FINDINGS.md` beruht weiterhin auf genau einem echten
   Anruf. Größenordnung für alle drei Beiträge zusammen: wenige USD.
7. **Sprache von `STORYBOARD.md`.** Es ist ein Arbeitsdokument und deshalb
   deutsch (alles Gesprochene und alles im Bild ist englisch). `AGENTS.md`
   verlangt Englisch für das Repo — falls es öffentlich gehen soll, wäre es zu
   übersetzen oder aus dem öffentlichen Stand herauszunehmen. Das ist eine
   Entscheidung, keine Panne.

---

## Dateien

Neu:

- `ringedingeding/proof.py` — die Kernprobe und ihre Prüfungen
- `ringedingeding/fixtures/weekend-hike.json` — das Szenario
- `tests/test_proof.py` — 10 Tests, davon 3 Sabotage-Fälle
- `STORYBOARD.md`, `DEVPOST.md`, `_OPUS-PHASE-REPORT.md`

Geändert:

- `EVIDENCE.md` — §19–22 (dritte Sitzung)
- `README.md` — Abgrenzung, Kernprobe, Befehlstabelle, Projektstruktur
- `SKILL.md` — wann ein fremder Agent die Kernprobe zeigt
- `ringedingeding/cli.py` — Unterbefehl `proof`
- `tests/test_fixtures.py` — gebündeltes Set: drei Fixtures wurden vier
- `.gitignore` — `LOCK*.txt` (lokale Agenten-Koordination, nicht Teil des Projekts)

Commits (lokal, nicht gepusht):

```
619d1f4  docs: STORYBOARD (story first, no frames) and a DevPost draft
41ca829  feat: a core sample a juror can run in a second
```
