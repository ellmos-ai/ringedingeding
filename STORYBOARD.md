# STORYBOARD — Ringedingeding (Demo-Video, Entwurf)

> **Arbeitsdokument des Operators.** Auf Deutsch, weil hier entschieden wird;
> **alles Gesprochene und alles im Bild ist Englisch** — Zielpublikum ist die Jury
> des CALL-E-Hackathons.
>
> **Status: ENTWURF, gebaut und gerendert.** Die Story stand zuerst; die
> Präferenzentscheidungen sind in §8 getroffen und begründet, nicht offengelassen.
> Was hart bleibt: kein echter Anruf, kein Upload, keine Einreichung.
>
> Vorgaben, die hier eingearbeitet sind: `C:\_Local_DEV\_calle-videos\LEARNINGS.md`
> (aus dem ersten gerenderten Entwurf), `hackathon-operator`-Skill (Videokette),
> `AGENTS.md` (keine erfundenen Zahlen).

---

## Die drei harten Regeln für diesen Entwurf

1. **90 Sekunden anpeilen.** Der erste Entwurf des Schwesterprojekts wurde 2:18 min —
   erlaubt, aber die Ausschreibung sagt ausdrücklich, dass die Jury nicht länger
   schauen muss. Was in 90 Sekunden nicht erzählbar ist, gehört nicht hinein.
2. **Durchgehende Kennzeichnung** `CONCEPT DRAFT — NOT BOUND TO REAL DATA`.
   Ein Entwurf darf skizzieren; er darf nur nicht als Beleg missverstanden werden.
   Umgesetzt als **umgetextetes vorhandenes Badge**, nicht als neue Ebene darüber
   (Learning: jede zusätzliche Ebene kollidiert mit Titel, Badges oder Untertiteln).
3. **Keine erfundenen Zahlen.** Kein „spart 20 Minuten", kein „N % schneller",
   keine Nutzerzahlen. Was im Video als Zahl auftaucht, steht unten in §5 mit
   Herkunft.

---

## 1. Der Hook — die ersten acht Sekunden

**Die Frage, die sich der Zuschauer stellt:** *Moment — worauf beruht dieser Satz
eigentlich?*

Auf dem Bildschirm steht eine einzige Zeile echter Programmausgabe:

```
=> Works for all 3 who answered: Sat 09-13
```

Sie liest sich wie ein Ergebnis. Sie **ist** ein Ergebnis — über drei Leute.
Gefragt wurden sieben.

**Die Idee in einem Satz:** Ein Auftrag, viele Anrufe, ein Ergebnis — das ehrlich
sagt, auf wie vielen Antworten es beruht.

**Die Story in zwei Sätzen:** Wer eine Gruppe abtelefoniert, bildet die
Schnittmenge im Kopf — und zählt dabei still die mit, die nie geantwortet haben.
Ringedingeding macht genau das unmöglich, und die letzte Szene zeigt, was es
kostet, wenn man es doch tut.

---

## 2. Der Text — was gesagt wird, im Wortlaut

**Das ist die Wirbelsäule.** Bilder kommen erst in §3, und zwar zu diesem Text —
nicht umgekehrt.

Stimme: `edge-tts --voice=en-US-ChristopherNeural`. Englische Stimme für
englischen Text; eine deutsche Stimme betont englische Sätze falsch und das hört
jeder sofort (Learning aus Entwurf 1).

| # | Beginn | **gemessen** | Rate | Gesprochener Text (wortgenau) |
|---|---|---|---|---|
| **S1** | 0:00,00 | **7,97 s** | +0 % | *"‚Works for all three who answered.' So — Saturday, then?* **(Pause)** *Seven people were asked."* |
| **S2** | 0:08,32 | **13,70 s** | +0 % | *"Four are missing, and each for a different reason. A poll link won't fix that: the people who ignore links are the people whose answer you need. So you call them one by one, and work out the overlap in your head."* |
| **S3** | 0:22,37 | **13,99 s** | +0 % | *"Ringedingeding takes one brief and makes the calls. Before it dials, it shows who gets called, what they'll be asked, how many calls that is, and what it costs. Nothing rings until you say so."* |
| **S4** | 0:36,71 | **25,46 s** | +12 % | *"Then it merges the answers, and keeps apart what a person in a hurry runs together. Can. Cannot. Said nothing about that one — which is not a no. Didn't pick up. Line busy. Declined.* **(Pause)** *And Vera, who was never in the round, because the address book has no number for her.* **(Pause)** *Add her number: the same round places exactly one call. Her answer overturns the result."* |
| **S5** | 1:02,53 | **14,23 s** | +0 % | *"The CALL-E app already handles one call better than anything I could build. This is the other case: many calls from one brief, answers as data instead of seven transcripts, and a result that says out loud what it rests on."* |
| **S6** | 1:17,11 | **11,33 s** | +12 % | *"Dry run by default. Numbers masked everywhere. Nobody unreached is ever counted as a yes.* **(Pause)** *Ask everyone, get one answer — and know who didn't answer."* |

**238 Wörter → 88,79 Sekunden**, inklusive 0,35 s Pause zwischen den Abschnitten.
**Das ist gemessen, nicht gerechnet:** `scripts/make_vo.py` synthetisiert jeden
Abschnitt, misst ihn mit `ffprobe` und synthetisiert bei Überlänge mit erhöhter
Sprechrate neu — der Wortlaut bleibt unangetastet, nur das Tempo zieht an. Zwei
Abschnitte brauchten das (+12 %), vier nicht.

**Eine Korrektur nach der ersten Messung:** S6 lag bei einem 10-s-Fenster bei
**+29 %** Sprechrate — die Schlusspointe klang gehetzt. Fenster auf 11,5 s
geöffnet, Rate fiel auf +12 %, Gesamtlänge stieg von 87,3 s auf 88,79 s. Immer
noch unter 90.

**Warum der Text so gebaut ist:**

- **S1 nimmt dem Zuschauer eine Gewissheit weg**, die er sich gerade selbst
  gegeben hat. Das ist billiger als jede Behauptung über Nutzen.
- **S4 ist eine Aufzählung in kurzen Sätzen**, weil dort sechs Zustände
  unterschieden werden. Lange Sätze verwischen genau die Unterscheidung, um die
  es geht.
- **S5 lobt zuerst die Anbieter-App.** Die Jury kennt sie; sie so zu behandeln,
  als gäbe es sie nicht, wäre die erste Stelle, an der man unglaubwürdig wird.
- **S6 schließt den Kreis zum Hook** („know who didn't answer"), damit die
  letzten Worte die ersten beantworten.

---

## 3. Die Bilder — was den Text stützt

**Fast alles ist echte Programmausgabe.** Das ist kein Zufall, sondern ein
Ergebnis von Phase 5: `ringedingeding proof` erzeugt genau diese Szene in etwa
einer Sekunde, ohne Konto und ohne Netz. Für die Terminalbilder braucht es also
**gar keine Erfindung** — die Kennzeichnung `CONCEPT DRAFT` gilt der *Inszenierung*
(Übergänge, Beschriftungen, gesetzte Karten), nicht den Daten.

| # | Was man sieht | Quelle | Status |
|---|---|---|---|
| **S1** | Schwarzer Grund, eine Zeile Monospace: `=> Works for all 3 who answered: Sat 09-13`. Nach der Pause hebt sich `3 who answered` hervor, darunter erscheint `7 invited`. | echte Ausgabe `ringedingeding proof`, STEP 4 | **echt** |
| **S2** | Vier Zeilen wachsen unter das Ergebnis, jede mit eigenem Grund: `Tara (NO_ANSWER)`, `Uwe (BUSY)`, `Sven — declined`, `Vera — no phone`. Sie erscheinen einzeln, im Takt der Aufzählung. | echte Ausgabe, STEP 4 | **echt** |
| **S3** | Schnitt auf STEP 2 der Kernprobe: Frage im Wortlaut, drei Zeitfenster, `calls: 6 ($0.30 …)`, `not called: Vera`. Der Cursor steht still — nichts läuft, bis jemand bestätigt. | echte Ausgabe, STEP 2 | **echt** |
| **S4a** | Das Board, Zeile für Zeile: `can`, `cannot`, `silent (not a no)`. Grün / rot / grau, sonst nichts. | echte Ausgabe, STEP 4 | **echt** |
| **S4b** | `no phone : Vera` wandert an den unteren Rand in eine eigene Liste — sie **fällt nicht weg**, sie steht daneben. | echte Ausgabe, STEP 4 | **echt** |
| **S4c** | **Die Herzensszene.** Vera bekommt eine Nummer. `outstanding calls: 1 (Vera)` — ein einziger Anruf. Dann kippt die Ergebniszeile von `Works for all 3 who answered: Sat 09-13` auf `No slot works for all 4 who answered.` Harter Schnitt genau auf „overturns". | echte Ausgabe, STEP 5 | **echt** |
| **S5** | Zweispaltige Karte, gesetzt, keine Aufnahme: links *The CALL-E app* (ein Anruf, Prosa, ein Protokoll, jeder Chat beginnt neu), rechts *Ringedingeding* (viele Anrufe aus einem Auftrag, schema-validiert, ein Ergebnis mit Nenner, merkt sich Offenes). Darunter drei Wörter für den Musterwert: *family · club · survey*. | gesetzte Grafik | **gebaut** |
| **S6** | Drei Karten nacheinander: `dry run by default` · `numbers masked everywhere` · `not reached ≠ yes`. Schluss: Wortmarke **Ringedingeding**, darunter *ask everyone · get one answer · know who didn't*. **Ohne Repo-Adresse** — die trägt erst der Einreichungsschnitt. | gesetzte Grafik | **gebaut** |

**Der eine verbliebene Platzhalter, mit Notiz — das ist die Bedingung dafür,
dass er ein Platzhalter und keine Lücke ist:** Auf der Schlusskarte steht **keine
Repository-Adresse**. Sie kommt dorthin erst, wenn der Nutzer das Repo öffentlich
geschaltet hat; eine erfundene Adresse ist genau der Fehler, den `AGENTS.md`
verbietet. Die Vergleichskarte (S5) war der zweite Platzhalter und ist inzwischen
gebaut — ohne Abwertung der Anbieter-App, nur zwei Spalten nebeneinander.

**Nicht im Entwurf, bewusst:** die Weboberfläche. Sie ist gebaut und getestet,
aber laut `EVIDENCE.md` §14 **von keinem Menschen je im Browser angesehen worden** —
ihr Aussehen ist unbelegt. Ein Bildschirmvideo davon würde etwas behaupten, das
niemand geprüft hat. Sie kommt in den Einreichungsschnitt, **nachdem** jemand sie
aufgemacht und angesehen hat, nicht vorher.

---

## 4. Entscheidungen für das ganze Video

Einmal entschieden, überall gültig. Wer das je Szene neu entscheidet, bekommt
Flickwerk.

| | Entscheidung | Begründung |
|---|---|---|
| **Art** | Bildschirmaufnahme + gesetzte Textkarten. Kein Talking Head, keine Comicfigur, keine Kamerafahrt durch 3D. | Das Produkt **ist** Text auf einem Schirm. Und die Regel verlangt, das Projekt „functioning on intended device" zu zeigen. |
| **Farbe** | Genau drei Farben tragen Bedeutung: grün = *can*, rot = *cannot*, grau = *nicht erreicht / stumm*. Alles andere neutral (Off-White auf Anthrazit). | Dieselbe Zuordnung, die die Software selbst benutzt (`ABLAUF.md` §2). Ein Video, das andere Farben wählt, widerspricht dem Produkt. |
| **Was rot sein darf** | Nur `DECLINED` und echte Fehler. **Nicht** „hat nicht abgenommen". | Ein durchgestrichener Name bei einem Telefon, das nur geklingelt hat, behauptet Wissen, das niemand hat. Steht so in `ARCHITEKTUR.md` §8. |
| **Schnitt** | Harte Schnitte, auf Satzenden. Keine Überblendungen. | 90 Sekunden. Jede Blende kostet eine halbe Sekunde und trägt nichts. |
| **Bewegung** | Nur wo sie Information trägt: Zeilen, die einzeln erscheinen; die Ergebniszeile, die kippt. Kein dekoratives Schweben. | |
| **Typografie** | Eine Monospace für alles, was Programmausgabe ist (weil es welche ist). Eine Serifenlose für die gesetzten Karten. Zwei Familien, mehr nicht. | |
| **Kennzeichnung** | `CONCEPT DRAFT — NOT BOUND TO REAL DATA` durchgehend, als umgetextetes **vorhandenes** Badge. | Learning: neue Ebenen kollidieren mit Titel/Badges/Untertiteln — neun Layout-Stichproben im ersten Entwurf, alle drei Positionen verworfen. |
| **Ton** | `edge-tts`, `en-US-ChristopherNeural`, `--rate=+0%`, Ratenanpassung je Abschnitt nach `make_vo.py`. **Jedes Audio-Element bekommt eine `id`.** | Ohne `id` findet der Renderer die Spur nicht und das Video wird **stumm** (`media_missing_id`). |
| **Musik** | Ruhiges Bett, unter der Sprache geduckt. Wechsel der Stimmung an den Sinnabschnitten S1→S2 und S4c→S5. Zwei Fassungen (geduckt / ungeduckt) zur Wahl. | |
| **Untertitel** | Englisch, eingebrannt, unten. Der Bereich darunter bleibt **frei** von allem anderen. | Learning: eine untere Warnleiste hat im ersten Entwurf die Untertitel verdeckt. |
| **Format** | 1920×1080. | |

---

## 5. Jede Zahl im Video, mit Herkunft

Die Prüfliste für den Schnitt. Was hier nicht steht, kommt nicht ins Bild.

| Zahl | Herkunft | Im Entwurf | In der Einreichung |
|---|---|---|---|
| `3 of 7 answered`, `1 outstanding call` | echte Ausgabe von `ringedingeding proof` | ✓ | ✓ |
| `$0.05` je Anruf, `$0.30` für sechs | von CALL-E dokumentiert; unabhängig bestätigt, weil das Guthaben des Operators nach einem Anruf auf −0,05 USD stand | ✓ | ✓ |
| Namen Nora/Paul/Rike/Sven/Tara/Uwe/Vera | gebündeltes Fixture `weekend-hike.json`, erfundene Personen, Platzhalternummern | ✓ | ✓ (als Beispiel benannt) |
| Repository-Adresse | existiert erst nach der Veröffentlichung | ✗ leer | ✓ dann echt |
| „spart X Minuten", „N % schneller" | **nirgends gemessen** | ✗ | ✗ |
| Testanzahl, falls eingeblendet | `python -m pytest` → 308 passed (2026-08-02) | nur mit frischem Lauf | nur mit frischem Lauf |

---

## 6. Was das Video nicht zeigt, und warum

Gehört ins Video, nicht nur in die Doku — es ist der Unterschied zwischen einer
Demo und einer Behauptung.

1. **Kein echter Anruf.** Aus diesem Repository wurde nie telefoniert. Alles
   Gezeigte läuft gegen gescriptete Antworten. Das ist keine Schwäche der Demo,
   sondern eine Anforderung des Ziel-Repos: ein Beitrag muss ohne fremdes Konto
   nachvollziehbar sein.
2. **Kein Eingriff ins laufende Gespräch.** CALL-E hat dafür keine
   Schnittstelle — gemessen, nicht vermutet (`FINDINGS.md`). Das Video behauptet
   an keiner Stelle Mithören oder Mitsprechen.
3. **Keine Parallelität.** Ob CALL-E mehrere Anrufe gleichzeitig führt, ist
   ungeprüft. Wenn eine Dauer genannt wird, dann die serielle.
4. **Keine vollständige Rufnummer.** Alle Nummern im Bild sind maskiert — auch
   die erfundenen, weil der Umgang und nicht die Nummer die Aussage ist.
5. **Keine Weboberfläche im Entwurf** (siehe §3).

---

## 7. Produktion — was wirklich lief

**Reihenfolge, wie sie eingehalten wurde:** Story (§1–§2) → Entscheidungen (§8) →
Vertonung → Musik → Bilder → Check → Render → Einzelbilder ansehen → eine
Korrektur → Check → Render.

| Schritt | Werkzeug | Ergebnis |
|---|---|---|
| Vertonung | `edge-tts`, `en-US-ChristopherNeural`, Ratenanpassung per `ffprobe` | sechs Spuren, **88,79 s** gesamt; zwei Abschnitte auf +12 % |
| Untertitel | `scripts/make_subs.py`, Split nach Zeichenzahl je Satz | 21 Cues, letzter endet bei 88,44 s |
| Musik | `compose_music.py`, Storyline aus denselben sechs Abschnitten | `ambient`, `seed 1908`, 446 Noten; `climax` 56,5–61,0 s, `damp` 60,6 s, `outro` ab 83,0 s |
| Komposition | HyperFrames 0.7.88, eine `index.html` | sechs Szenen, GSAP-Zeitachse, gebündelte Schriften |
| Check | `hyperframes check` | **bestanden**: 0 Fehler, 2 Warnungen (Spurdichte), **53/53 Kontrastprüfungen WCAG AA** |
| Render | `hyperframes render` | 1920×1080, 30 fps, h264 + AAC, 2664 Frames, **5 min 6 s**, 4,7 MB |
| Sichtprüfung | `ai-media-editor` → `editor.py frames` | 15 Übersichts- + 3 Zoom-Einzelbilder, mit Zeitstempel |

**Zwei Fehler, die der Check gefunden hat** (beide vor dem ersten Render behoben):

1. `font_family_without_font_face: cascadia mono` — ein Schriftname außerhalb der
   gebündelten Liste wäre still auf eine Ersatzschrift zurückgefallen.
2. `text_box_overflow … 23px` — die zitierte Frage lief in der Terminal-Karte
   rechts heraus.

**Ein Fehler, den erst das Ansehen der Einzelbilder gefunden hat:** Der
gesprochene Satz lautete *„Seven people were **asked**"* — Vera wurde nie
gefragt, sie hatte keine Nummer. Das ist genau die Ungenauigkeit, die der Film
anprangert, im Film selbst. Korrigiert zu *„…were invited"*, neu vertont
(zufällig exakt gleich lang, die Zeitachse blieb stehen), neu gerendert.

Alle Learnings dieses Laufs: `_calle-videos/ringedingeding/LEARNINGS.md`.

---

## 8. Die Entscheidungen — getroffen, nicht vorgelegt

Fünf Fragen standen offen; nach der Freigabe „alle Gates bis Phase 6 sind weiche
Gates, es geht um Präferenzen" sind sie hier entschieden. Grundlage ist der
belegte Entscheidungs-Korpus (`tom-lm`), dessen häufigste Korrektur überhaupt
lautet: **Overclaims sind die härteste, nicht verhandelbare Grenze.** Diese eine
Regel entscheidet vier der fünf Fragen.

| # | Entscheidung | Warum | Konfidenz |
|---|---|---|---|
| **D1** | **Hook bleibt** die eine Zeile echter Programmausgabe: `=> Works for all 3 who answered: Sat 09-13`, dann *„Seven people were asked."* | Er nimmt dem Zuschauer eine Gewissheit weg, die er sich gerade selbst gegeben hat — genau der Overclaim, den das Werkzeug verhindert. Und er ist **echte Ausgabe**, muss also nichts behaupten. | hoch |
| **D2** | **Herzensszene ist Vera** (Nummer nachgetragen, ein Anruf, Ergebnis kippt) — nicht der Bestätigungsschritt vor dem Wählen. | Sicherheit ist Hygiene und wird in S3 ohnehin gezeigt; Ehrlichkeit ist die Aussage. Die Alternative liegt als **Variante B** unten. | hoch |
| **D3** | **Abgrenzung zur Anbieter-App bleibt drin** (S5, 14 s von 89). | `_analysis/abgrenzung-zur-anbieter-app.md` sagt es wörtlich: *„Diese Frage wird die Jury stellen. Sie gehört beantwortet, bevor sie gestellt wird — in jedem README und im Video."* | hoch |
| **D4** | **Musik geduckt** (`data-volume="0.17"` auf der Score-Spur) als Hauptfassung. | Der `music-composer` sagt es selbst: Bett, nicht Melodie. Bei 238 gesprochenen Wörtern in 89 s trägt die Stimme. Die präsentere Fassung ist **eine Zahl in einer Zeile** — als Variante dokumentiert, nicht als zweiter Render. | hoch |
| **D5** | **Weboberfläche bleibt draußen.** | `EVIDENCE.md` §14: sie hat nie ein Mensch im Browser angesehen. Sie zu zeigen hieße, etwas Ungeprüftes zu behaupten. Sie kommt in den Einreichungsschnitt, **nachdem** jemand sie aufgemacht hat. | hoch |

**Was hier NICHT entschieden wurde:** Guthaben aufladen für den Feldversuch
(kostet Geld, irreversibel) und alles jenseits von Phase 6 — Veröffentlichung,
Upload, Einreichung. Das bleiben harte Gates.

### Variante B — der Sicherheits-Schnitt

Ernsthaft im Rennen, deshalb ausformuliert statt weggeworfen. Sie tauscht die
Kernbotschaft: nicht *„das Ergebnis kann falsch sein, wenn jemand fehlt"*,
sondern *„niemand wird angerufen, den du nicht freigegeben hast"*.

- **S3 wird die Herzensszene** und wächst auf ~22 s: der vollständige
  Auftragstext, wie er das Haus verlässt, Zeile für Zeile — dann Anzahl,
  Kosten und die getippte Bestätigung `CALL THEM`.
- **S4 schrumpft auf ~16 s**: das Board bleibt, die Vera-Wendung wird zu einer
  Zeile im Nachsatz statt zur Szene.
- **S1 und S6 bleiben unverändert** — der Hook trägt beide Fassungen.
- **Was sie kostet:** Die Wendung ist das einzige Bild im Film, das den
  Zuschauer überrascht. Ohne sie ist es eine gute Werkzeugvorstellung statt
  eines Arguments.
- **Wann sie besser wäre:** wenn die Jury Sicherheitsfragen priorisiert, oder
  wenn der Feldversuch mit echten Anrufen stattgefunden hat — dann wird der
  Bestätigungsschritt zur belegten Aussage statt zur Behauptung.

### Variante Ton — Bett oder präsent

Eine Zeile in `index.html`, kein zweiter Entwurf:

```
<audio id="bgm" ... data-volume="0.17">   <- Hauptfassung (Bett)
<audio id="bgm" ... data-volume="0.30">   <- Variante (Musik präsent)
```

Der Score ist in beiden Fällen identisch und deterministisch (`seed: 1908`);
die Variante ändert nur die Lautstärkeregel.

---

## 9. Wo der Entwurf liegt

Gebaut in `C:\_Local_DEV\_calle-videos\ringedingeding` (HyperFrames-Projekt,
CLI auf `0.7.88` gepinnt):

```
BRIEF.md                 Auftrag (workflow: general-video, flow: automation)
index.html               die Komposition — sechs Szenen, 21 Untertitel-Cues
scripts/make_vo.py       Vertonung, edge-tts + ffprobe-Ratenanpassung
scripts/make_subs.py     Untertitel-Cues aus den gemessenen Sprechzeiten
scripts/storyline.json   Musik-Storyline (sechs Sektionen, drei Ereignisse)
audio/s1..s6.mp3         die Sprachspuren
audio/score.mp3|wav|mid  der Score + Arrangement-Log
audio/vo_report.json     gemessene Dauern, Raten, Zeitachse
renders/                 das gerenderte Video
snapshots/               Einzelbilder zur Sichtprüfung
```

Reproduzierbar: `python scripts/make_vo.py`, `python scripts/make_subs.py`,
`python <ai-media-editor>/tools/compose_music.py scripts/storyline.json -o audio/score`,
dann `hyperframes check` und `hyperframes render`.
