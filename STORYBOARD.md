# STORYBOARD — Ringedingeding (Demo-Video, Entwurf)

> **Arbeitsdokument des Operators.** Auf Deutsch, weil hier entschieden wird;
> **alles Gesprochene und alles im Bild ist Englisch** — Zielpublikum ist die Jury
> des CALL-E-Hackathons.
>
> **Status: ENTWURF. Kein Video gerendert.** Dieses Dokument ist das Gate: der
> Nutzer entscheidet über die Story, bevor irgendein Frame entsteht.
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

| # | Zeitfenster (Ziel) | Wörter | Gesprochener Text (wortgenau) |
|---|---|---|---|
| **S1** | 0:00–0:08 | 14 | *"‚Works for all three who answered.' So — Saturday, then?* **(Pause)** *Seven people were asked."* |
| **S2** | 0:08–0:24 | 44 | *"Four are missing, and each for a different reason. A poll link won't fix that: the people who ignore links are the people whose answer you need. So you call them one by one, and work out the overlap in your head."* |
| **S3** | 0:24–0:40 | 40 | *"Ringedingeding takes one brief and makes the calls. Before it dials, it shows who gets called, what they'll be asked, how many calls that is, and what it costs. Nothing rings until you say so."* |
| **S4** | 0:40–1:08 | 72 | *"Then it merges the answers, and keeps apart what a person in a hurry runs together. Can. Cannot. Said nothing about that one — which is not a no. Didn't pick up. Line busy. Declined.* **(Pause)** *And Vera, who was never in the round, because the address book has no number for her.* **(Pause)** *Add her number: the same round places exactly one call. Her answer overturns the result."* |
| **S5** | 1:08–1:22 | 44 | *"The CALL-E app already handles one call better than anything I could build. This is the other case: many calls from one brief, answers as data instead of seven transcripts, and a result that says out loud what it rests on."* |
| **S6** | 1:22–1:32 | 24 | *"Dry run by default. Numbers masked everywhere. Nobody unreached is ever counted as a yes.* **(Pause)** *Ask everyone, get one answer — and know who didn't answer."* |

**238 Wörter.** Bei ~155 Wörtern pro Minute ergibt das rund 92 Sekunden.
**Das ist eine Rechnung, keine Messung** — die echte Länge steht erst fest, wenn
die Spuren synthetisiert sind, und wird dann hier eingetragen. `make_vo.py` aus
dem Roshambo-Bestand misst jede Spur mit `ffprobe` und synthetisiert schrittweise
mit erhöhter Sprechrate neu, wenn ein Abschnitt sein Fenster sprengt — der
Wortlaut bleibt unangetastet, nur das Tempo zieht an.

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
| **S5** | Zweispaltige Karte, gesetzt, keine Aufnahme: links *CALL-E app — one call, one transcript*, rechts *Ringedingeding — one brief, N calls, one result with a denominator*. Darunter drei Wörter, die den Musterwert zeigen: *family · club · survey*. | gesetzte Grafik | **Platzhalter** — Text steht, Layout wird gebaut |
| **S6** | Drei kurze Karten hintereinander: `dry run by default` · `numbers masked` · `not reached ≠ yes`. Schluss: Wortmarke **Ringedingeding**, darunter *ask everyone · get one answer*, daneben Repo-Adresse. | gesetzte Grafik | **Platzhalter** — Repo-Adresse trägt **nur** der Einreichungsschnitt, siehe §5 |

**Zwei Platzhalter, beide mit Notiz — das ist die Bedingung dafür, dass sie
Platzhalter und keine Lücken sind:**

1. **S5-Vergleichskarte.** Der Text steht (oben), das Layout nicht. Wenn sie
   gebaut wird: keine Abwertung der Anbieter-App, nur zwei Spalten nebeneinander.
2. **S6-Schlusskarte.** Die Repo-Adresse steht dort erst, **wenn der Nutzer das
   Repo öffentlich geschaltet hat**. Bis dahin bleibt das Feld leer — eine
   erfundene Repository-Adresse ist genau der Fehler, den `AGENTS.md` verbietet.

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

## 7. Produktion — Reihenfolge und Prüfliste

**Reihenfolge, nicht verhandelbar:** Story (dieses Dokument) → Freigabe des
Nutzers → Vertonung → Bilder → Rohschnitt → Prüfung → Render.

1. **Aufnahmen (alle offline, kein Konto):**
   - `python -m ringedingeding proof` — die Szenen S1, S2, S3, S4a–c am Stück.
     Ein einziger Durchlauf liefert alles; Terminal 1920×1080, dunkles Thema,
     Monospace groß genug zum Lesen auf dem Telefon.
   - `python -m pytest` — nur falls eine Testzahl eingeblendet wird, und dann
     frisch.
2. **Vertonung:** sechs Spuren S1–S6, `edge-tts`, `en-US-ChristopherNeural`,
   danach `ffprobe`-Messung je Spur und Ratenanpassung nach `make_vo.py`.
   **Jede Spur bekommt eine `id`.**
3. **Gemessene Längen hier eintragen** und die Zeitfenster in §2 durch die
   Ist-Werte ersetzen. Ab dann sind es Messungen und keine Rechnung mehr.
4. **Vor dem Render:** `npx hyperframes check` — **Fehler beheben, nicht zählen.**
   Im ersten Entwurf ging ein `media_missing_id` zwischen acht Warnungen unter
   und das Video war stumm.
5. **Version prüfen:** `npx hyperframes@latest upgrade --project . --check`.
6. **Renderdauer einplanen:** der erste Entwurf brauchte für 2:18 min bei
   1920×1080 elf Minuten. Ein Durchlauf ist kein Zwischenschritt.
7. **Nach dem Render:** ansehen — und zurück in die Entwicklung. Ein fertiger
   Entwurf ist der erste Moment, in dem auffällt, was dem *Produkt* noch fehlt.
   Was auffällt, kommt in `LEARNINGS.md` neben dem Video, nicht in den Kopf.

---

## 8. Was der Nutzer entscheiden muss (GATE)

Bevor ein Frame entsteht:

1. **Trägt der Hook?** *„Works for all three who answered" — so, Saturday then?*
   Wenn dieser Satz nicht sitzt, ist alles Weitere verfrüht.
2. **Ist S4c die richtige Herzensszene** — Vera bekommt eine Nummer und kippt das
   Ergebnis? Die Alternative wäre, den Bestätigungsschritt vor dem Wählen zur
   Hauptszene zu machen (Sicherheit statt Ehrlichkeit als Kernbotschaft).
3. **Soll S5 (Abgrenzung zur Anbieter-App) drin bleiben?** Sie kostet 14
   Sekunden von 90. Dafür beantwortet sie die Frage, die die Jury ohnehin stellt.
4. **Ton:** eine Fassung mit geduckter Musik und eine ohne — welche?
5. **Weboberfläche:** soll sie in den Einreichungsschnitt? Dann muss sie vorher
   jemand im Browser aufmachen und ansehen (§3).

**Erst nach dieser Freigabe wird vertont und gerendert.**
