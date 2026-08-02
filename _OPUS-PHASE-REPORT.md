# Phasenbericht — autonomer Lauf, 2026-08-02

> Operator: Claude Code (Opus 5, ASUS-GEI). Ablauf nach dem Skill
> `hackathon-operator`. Arbeitsbereiche: `C:\_Local_DEV\repos\ringedingeding`
> (Repo) und `C:\_Local_DEV\_calle-videos\ringedingeding` (Videoprojekt).
> Außerhalb dieser beiden wurde nur gelesen.

---

## Kurzfassung

| Phase | Vorher | Jetzt |
|---|---|---|
| 4 Bau | fertig, 297 Tests | fertig, **308 Tests** |
| 5 Abnahme & Beweis | nur Trockenlauf, keine Kernprobe | **Kernprobe gebaut, belegt, selbstprüfend** — Feldversuch weiterhin offen (Nutzersache) |
| 6 Medien | **nichts** | **Storyboard + gerendertes Video**, 88,8 s, selbst per Einzelbildern geprüft |
| 7 Einreichung | — | **DevPost-Entwurf**, vier Felder als blockiert markiert |

Lokale Commits im Repo, kein Push, kein Anruf, keine Veröffentlichung.

---

## A — Phase 5: die Beweisführung

**`ringedingeding proof`** — ein Befehl, rund eine Sekunde, kein Konto, kein Netz,
kein Telefon. Er baut eine Siebenpersonen-Runde in einer temporären Datenbank,
spielt gescriptete Antworten ab und **prüft danach sein eigenes Ergebnis**.

Das Szenario (`ringedingeding/fixtures/weekend-hike.json`) provoziert absichtlich
die vier Arten, wie eine Zusammenführung still lügen kann — Widerspruch, halbe
Zusage, differenzierte Nichterreichbarkeit, gar nicht anrufbar — und acht
Prüfungen belegen anschließend, dass keine davon eingetreten ist.

**Der Schluss trägt die Sache:** Solange Vera keine Nummer hat, meldet die Runde
`Works for all 3 who answered: Sat 09-13`. Nummer nachtragen, dieselbe Runde noch
einmal — **ein** Anruf — und das Ergebnis kippt auf
`No slot works for all 4 who answered.`

| Lauf | Ergebnis |
|---|---|
| `python -m ringedingeding proof` (3×, `perf_counter` um `subprocess.run`) | **Exit 0**, `1,05 / 0,76 / 0,84 s`, 96 Zeilen, `8 of 8 checks passed` |
| `python -m pytest` | **308 passed** (vorher 297) |
| `python -m pytest tests/test_proof.py` | **10 passed**, davon 3 Sabotage-Fälle |
| `python -m ringedingeding demo` | Exit 0, jetzt `# 4/4 weekend-hike` |
| AST-Import-Scan | „NOT in the standard library: **none**" |

**Die Prüfungen können auch scheitern**, und das ist getestet: `tests/test_proof.py`
manipuliert je einen gescripteten Antwortsatz und verlangt, dass der Befehl fällt.
Ein Zwischenfehler steht im Protokoll, weil er zur selben Klasse gehört: Meine
erste Sabotage war zu schwach und ging durch (`EVIDENCE.md` §20).

---

## B — Phase 6: Storyboard **und** Videoentwurf

### Story zuerst

`STORYBOARD.md` folgt der vorgeschriebenen Reihenfolge: Hook → Narration im
Wortlaut → erst dann Bilder → Policies fürs ganze Video. Der Hook ist eine Zeile
echter Programmausgabe (`=> Works for all 3 who answered: Sat 09-13`), gefolgt von
*„Seven people were invited."*

**238 Wörter → 88,79 Sekunden. Gemessen, nicht gerechnet.**

### Der gebaute Entwurf

`C:\_Local_DEV\_calle-videos\ringedingeding` — HyperFrames-Projekt, CLI lokal auf
`0.7.88` installiert.

| Schritt | Ergebnis |
|---|---|
| **Vertonung** | `edge-tts`, `en-US-ChristopherNeural`; `make_vo.py` misst mit `ffprobe` und erhöht bei Überlänge die Sprechrate. Zwei Abschnitte auf +12 %, vier bei +0 %. Der Wortlaut wurde nie gekürzt. |
| **Untertitel** | 21 Cues, aus den gemessenen Sprechzeiten abgeleitet, englisch, eingebrannt |
| **Musik** | `compose_music.py` aus einer Storyline mit **denselben sechs Abschnitten**: `ambient`, `seed 1908`, 446 Noten. `climax` 56,5–61,0 s auf die Wendung, `damp` bei 60,6 s exakt auf den Satz *„Her answer overturns the result."*, `outro` ab 83,0 s |
| **Komposition** | eine `index.html`, sechs Szenen, GSAP-Zeitachse, gebündelte Schriften (Inter / JetBrains Mono), kein CDN für Assets |
| **`hyperframes check`** | **bestanden** — 0 Fehler, 2 Warnungen (Spurdichte), **53/53 Kontrastprüfungen WCAG AA** |
| **Render** | 1920×1080, 30 fps, h264 + AAC stereo, 2664 Frames, **5 min 6 s**, 4,7 MB, **88,8 s** |

### Selbst angesehen — und dabei einen Sachfehler gefunden

`ai-media-editor` → `editor.py frames` zog 15 Übersichts- und 3 Zoom-Einzelbilder
mit Zeitstempel. Befund beim Ansehen:

- Layout trägt: das Badge oben rechts kollidiert mit nichts, die Untertitel
  stehen frei, die Farben tragen genau drei Bedeutungen, und das Kippen der
  Ergebniszeile sitzt (bei 61,5 s steht die korrigierte Zeile, der Kopf ist
  ausgegraut).
- **Ein Sachfehler:** Der gesprochene Satz lautete *„Seven people were **asked**"* —
  Vera wurde **nie gefragt**, sie hatte keine Nummer. Auf dem Bildschirm stand
  daneben korrekt *„invited"*. Das ist genau die Ungenauigkeit, die der Film
  anprangert, **im Film selbst**.

Korrigiert zu *„Seven people were invited."*, neu vertont, Untertitel neu
erzeugt, Check erneut bestanden, **neu gerendert**. Der Glücksfall dabei: die
Korrektur war exakt gleich lang (7,97 s), die Zeitachse blieb stehen. Das ist als
Learning notiert — beim nächsten Bau wird die Zeitachse generiert statt abgetippt.

Alle Learnings dieses Laufs: `_calle-videos/ringedingeding/LEARNINGS.md`.

---

## C — Die Entscheidungen, die ich getroffen habe

Fünf Präferenzfragen standen als Nutzer-Gate im Storyboard. Nach der Freigabe
„alle Gates bis Phase 6 sind weiche Gates" sind sie entschieden — über den
`tom-lm`-Loop, dessen belegte Kernregel lautet: **Overclaims sind die härteste,
nicht verhandelbare Grenze** (häufigste Korrektur im gesamten Korpus). Diese eine
Regel entscheidet vier der fünf Fragen. Volltext mit Begründungen in
`STORYBOARD.md` §8.

| # | Entscheidung | Tragende Begründung | Konfidenz |
|---|---|---|---|
| D1 | Hook bleibt die echte Ausgabezeile + *„Seven people were invited."* | Nimmt dem Zuschauer eine Gewissheit weg, die er sich gerade selbst gegeben hat — und behauptet nichts, weil es echte Ausgabe ist | hoch |
| D2 | Herzensszene ist **Vera**, nicht der Bestätigungsschritt | Sicherheit ist Hygiene und wird in S3 ohnehin gezeigt; Ehrlichkeit ist die Aussage | hoch |
| D3 | Abgrenzung zur Anbieter-App **bleibt** (14 s von 89) | `_analysis/abgrenzung-zur-anbieter-app.md` wörtlich: *„Diese Frage wird die Jury stellen"* | hoch |
| D4 | Musik **geduckt** (`data-volume="0.17"`) | Der `music-composer` sagt es selbst: Bett, nicht Melodie | hoch |
| D5 | Weboberfläche **bleibt draußen** | `EVIDENCE.md` §14 — nie von einem Menschen im Browser angesehen; sie zu zeigen hieße, Ungeprüftes zu behaupten | hoch |

**Varianten statt Iteration**, wie es der Skill verlangt — und wo eine Alternative
ernsthaft im Rennen war, steht sie daneben statt im Papierkorb:

- **Variante B, der Sicherheits-Schnitt** (`STORYBOARD.md` §8): S3 wird die
  Herzensszene und wächst auf ~22 s, S4 schrumpft auf ~16 s, Hook und Schluss
  bleiben. Ausformuliert samt Kosten (*„die Wendung ist das einzige Bild, das den
  Zuschauer überrascht"*) und der Bedingung, unter der sie besser wäre.
- **Variante Ton:** geduckt (0.17) oder präsent (0.30) — **eine Zahl in einer
  Zeile**, kein zweiter Entwurf. Der Score ist deterministisch (`seed 1908`),
  beide Fassungen teilen ihn.

**Warum keine zwei vollen Renders:** ein Render kostet gemessen 5 min 6 s. Zwei
Fassungen, die sich in einer Lautstärkezahl unterscheiden, rechtfertigen das
nicht — der Unterschied ist in einer Zeile beschreibbar und in einem Lauf
herstellbar. Bei Variante B ist es umgekehrt: sie ist ein anderes Video und
bräuchte einen eigenen Lauf; deshalb steht sie als ausformulierter Entwurf da,
nicht als halber Render.

**Nicht hier entschieden:** Guthaben aufladen (kostet Geld, irreversibel) und
alles jenseits von Phase 6.

---

## D — README, SKILL und Phase 7

- **README:** neuer Abschnitt *„Why not just use the CALL-E app?"* ganz vorn —
  erst das Lob für die Anbieter-App, dann der Unterschied, dann der Startbefehl
  der Kernprobe. *„Try it without an account"* führt mit `proof`, dann `demo`.
- **`SKILL.md`:** sagt einem fremden Agenten, wann er die Kernprobe zeigt —
  wenn jemand fragt *„und was, wenn nicht alle antworten?"*.
- **`DEVPOST.md`:** vollständiger Einreichungstext, **Listen statt Tabellen**.
  Vier Felder sind als blockiert markiert, jedes ist eine Nutzeraktion:
  Repository-URL, Pull Request, Video-Link, CALL-E-Konto-E-Mail.

Eine Regelangabe wurde nachgeprüft statt behauptet: „kein Bestandscode" —
`git log` zeigt den ersten Commit am **2026-08-01 19:18 +02:00**, nach dem
Stichtag 2026-07-23.

---

## Wo mich ein Gate gestoppt hat

| Gate | Wo genau |
|---|---|
| **Kein echter Anruf** | Der Feldversuch mit echten, eingeweihten Teilnehmern ist der einzige offene Punkt der Phase 5. Er braucht ein CALL-E-Konto mit Guthaben — der Stand lag nach dem einen gemessenen Anruf bei **−0,05 USD**. In `EVIDENCE.md` §22 als „still not executed" festgehalten. |
| **Kein Upload, keine Veröffentlichung, kein PR, keine Einreichung** | Das Video liegt als Datei in `renders/`. Repo-URL und PR-Link in `DEVPOST.md` bleiben leer; auf der Schlusskarte des Videos steht **bewusst keine Repository-Adresse**. |
| **Kein Push** | Lokale Commits, `git status` sauber, kein Remote-Kontakt. |
| **Keine Zugangsdaten** | Nirgends gelesen oder genannt. Rufnummern überall maskiert — eine der acht Prüfungen der Kernprobe misst das mit `\+\d{6,}` über die eigene Ausgabe. |
| **Keine erfundenen Zahlen** | `STORYBOARD.md` §5 listet **jede** Zahl, die im Video vorkommen darf, mit Herkunft — und die, die verboten bleiben. |
| **Avatar-Logbuch** | Die Einträge in `_TOM-lm` (`MY-ACTIONS.txt`, `WHAT-I-DID-…`) konnte ich **nicht** schreiben: der Avatar liegt in OneDrive, außerhalb der Schreibgrenze dieses Laufs. Die Entscheidungen sind stattdessen hier und in `STORYBOARD.md` §8 belegt. |

---

## Was der Nutzer jetzt entscheiden muss

Nur noch zwei Dinge, beide außerhalb der weichen Gates:

1. **Guthaben aufladen für den Feldversuch?** Ohne das bleibt Phase 5 im
   Trockenlauf-Zustand, und `FINDINGS.md` beruht weiter auf genau einem echten
   Anruf. Größenordnung für alle drei Beiträge zusammen: wenige USD.
2. **Sprache von `STORYBOARD.md`.** Es ist ein Arbeitsdokument und deshalb
   deutsch (alles Gesprochene und alles im Bild ist englisch). `AGENTS.md`
   verlangt Englisch fürs Repo — falls es öffentlich geht, wäre es zu übersetzen
   oder aus dem öffentlichen Stand herauszunehmen. Bewusste Abweichung, keine
   Panne.

**Zum Ansehen:** `C:\_Local_DEV\_calle-videos\ringedingeding\renders\`.
Danach gern eine Bewertung 0–10 je Entscheidung D1–D5 (§C) — daraus lernt der
Avatar, ob seine Konfidenzangaben kalibriert sind.

---

## Dateien

**Repo** (`C:\_Local_DEV\repos\ringedingeding`) — neu:
`ringedingeding/proof.py`, `ringedingeding/fixtures/weekend-hike.json`,
`tests/test_proof.py`, `STORYBOARD.md`, `DEVPOST.md`, `_OPUS-PHASE-REPORT.md`.
Geändert: `EVIDENCE.md` (§19–22), `README.md`, `SKILL.md`,
`ringedingeding/cli.py`, `tests/test_fixtures.py`, `.gitignore`.

**Videoprojekt** (`C:\_Local_DEV\_calle-videos\ringedingeding`):
`BRIEF.md`, `LEARNINGS.md`, `index.html`, `scripts/make_vo.py`,
`scripts/make_subs.py`, `scripts/storyline.json`, `audio/` (sechs Sprachspuren,
Score, `vo_report.json`, `subs.json`), `renders/` (das Video).
