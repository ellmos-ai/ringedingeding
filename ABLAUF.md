# Ringedingeding — der Prozess in Worten

> Formalisierung des Produktkonzepts (`konzept-ringedingeding-ui.md`) in Abfragen,
> Entscheidungen und Ablaufbäume. **Grundlage für beides**: den `SKILL.md`-Ablauf, den ein
> fremder Agent im Gespräch führt, und die Oberfläche, die dieselben Entscheidungen
> sichtbar macht.
>
> Leitsatz des Nutzers: *„Das LLM könnte mich virtuell durch das Menü führen als
> Audiosystem."* Was hier steht, muss also **ohne Bildschirm funktionieren** — und deshalb
> passt es hinterher zwangsläufig zur Oberfläche.

---

## 0. Grundprinzip

**Ein Ablauf, drei Zugänge.** Jede Entscheidung existiert genau einmal — als Knoten in
diesem Baum. Die Oberfläche zeigt sie als Feld, der Skill stellt sie als Frage, die CLI
nimmt sie als Argument.

**Drei Arten von Knoten:**

| Art | Bedeutung | Verhalten des Agenten |
|---|---|---|
| **PFLICHT** | ohne das geht es nicht weiter | fragt nach, bis beantwortet |
| **ABLEITBAR** | kann aus Kontext oder Bestand kommen | **selbst herausfinden, dann bestätigen lassen** |
| **OPTIONAL** | verbessert das Ergebnis | nur fragen, wenn es sich anbietet — nie abarbeiten |

**Der Agent darf proaktiv sein.** Der Nutzer hat es vorgemacht:
*„Bitte such doch mal in meinen Mails nach ihren Telefonnummern oder im Kontaktbuch."*
Was aus Kontakten, Mail oder Kalender beschaffbar ist, wird beschafft — und dann
**vorgelegt, nicht angenommen**.

---

## 1. Der Einstieg — welche Art von Runde?

```
Was möchtest du tun?
├── Termin finden        → Zweig A: TERMINKONZIL
└── Meinungen einholen   → Zweig B: RUNDER TISCH
```

**Erkennbar auch ohne Frage:** Enthält die Eingabe ein Datum, einen Wochentag oder Wörter
wie „wann", „Termin", „treffen" → Zweig A. Enthält sie „was haltet ihr von", „fragen ob",
„Meinung" → Zweig B. **Bei Unklarheit fragen, nicht raten.**

---

## Zweig B — Runder Tisch (der kürzere, deshalb zuerst)

Der Nutzer hat den Idealfall selbst durchgespielt. Als Referenzdialog:

> **Nutzer:** „Ich möchte bitte mit meinen Freunden — die nenne ich immer *die
> Kokosritter*, bitte merk dir das als Gruppe. Das sind der Thomas, der Simon und der
> Bastian. Such doch mal in meinen Mails nach ihren Telefonnummern oder im Kontaktbuch.
> Von denen möchte ich unbedingt wissen, was sie von der neuen Switch-Konsole halten und
> ob sie sie schon ausprobiert haben. Das ist wirklich dringend."
>
> **Agent:** *(sucht die Nummern, legt die Gruppe an, legt den Auftrag vor)* → abschicken.

**Das ist das Maß.** Ein Satz des Nutzers, ein Rückfragepunkt, fertig.

### Der Baum

```
B1  WEN fragen?                                        [PFLICHT]
    ├── bestehende Gruppe nennen ("die Kokosritter")   → laden
    ├── Personen aufzählen                             → B1a
    └── "meine Familie" o. Ä. ohne Gruppe              → nachfragen, wer dazugehört

    B1a  Telefonnummern beschaffen                     [ABLEITBAR]
         ├── im Kontaktbuch vorhanden          → übernehmen
         ├── in Mail/Kalender findbar          → suchen, dann VORLEGEN
         └── nicht auffindbar                  → B1b

    B1b  Kontakt ohne Nummer                           [SONDERFALL]
         → nicht stillschweigend weglassen. Melden:
           "Für Bastian finde ich keine Nummer. Nachtragen oder ohne ihn starten?"
         → Er bleibt in der Runde, als "nicht anrufbar" markiert, und kann
           nachträglich ergänzt werden — dann wird sein Anruf NACHGEHOLT.

    B1c  Gruppe merken?                                [OPTIONAL]
         → wenn der Nutzer einen Namen genannt hat: als Gruppe speichern.
           Nicht fragen, ob er speichern will — er hat den Namen ja genannt.

B2  WAS willst du wissen?                              [PFLICHT]
    → Freitext. Wird wörtlich zur Frage.
    ⚠ Was in Anführungszeichen steht, wird zitiert; alles andere formuliert der
      Telefon-Agent um. Bei präzisen Fragen also zitieren.

    B2a  Antwortform                                   [ABLEITBAR]
         ├── Ja/Nein erkennbar          → binäres Schema
         ├── Auswahl genannt            → enum-Schema aus den Optionen
         └── offen                      → Freitext + Zusammenfassung

B3  Dringlichkeit / Zeitrahmen                         [OPTIONAL]
    → "wirklich dringend" ändert nichts am Ablauf, aber am Ton des Anrufs
      und ggf. an der Reihenfolge.

B4  Begrüßung, Schlussformel, Policy                   [OPTIONAL]
    → nur anbieten, wenn der Nutzer selbst in diese Richtung spricht,
      oder wenn für die Gruppe eine Policy gespeichert ist → dann anwenden
      und einmal erwähnen.

B5  VORLEGEN                                           [PFLICHT-GATE]
    → "Ich rufe Thomas, Simon und Bastian an und frage: <Frage>.
       Drei Anrufe, etwa 15 Cent. Soll ich?"
    → erst nach Bestätigung wählen.
```

### Gruppenprofile

Eine Gruppe trägt: **Name** (frei, „die Kokosritter"), **Mitglieder**, optional eine
eigene **Policy** und **eigene Fragetexte**. Der Nutzer darf die Überschriften selbst
benennen — *„Was möchtest du von deinen Knappen wissen?"*, *„Um welche Schlacht geht es?"*
Das ist keine Spielerei, sondern der Grund, warum Leute so ein Werkzeug wiederbenutzen.

---

## Zweig A — Terminkonzil

Aufwendiger, weil die **Terminart** den weiteren Verlauf bestimmt.

```
A1  Worum geht es? (Anlass)                            [PFLICHT]
    → wird im Anruf genannt: "es geht um <Anlass>"

A2  WEN einladen?                                      [PFLICHT]
    → identisch zu B1 samt Sonderfällen (keine Nummer → nachtragbar, wird nachgeholt)

A3  Welche ART von Termin?                             [PFLICHT]
    Der Agent fragt nicht die sechs Arten ab, sondern:
    "Geht es um einzelne Stunden an bestimmten Tagen, um ganze Tage,
     um eine Woche, um mehrere zusammenhängende Tage — oder um etwas
     Regelmäßiges?"

    ├── A3-a  TAGESTERMIN (Stunden an Tagen)     → A4a
    ├── A3-b  GANZER TAG                          → A4b
    ├── A3-c  WOCHE                               → A4b (Einheit = Woche)
    ├── A3-d  MONAT                               → A4b (Einheit = Monat)
    ├── A3-e  MEHRERE TAGE (zusammenhängend)      → A4c
    └── A3-f  REGELMÄSSIG (Wochentag)             → A4d

A4a TAGESTERMIN
    1. Welche Tage?                    → Liste von Daten
    2. Standardzeiten für alle Tage    → 1..n Slots, je Start/Ende (oder Start+Dauer)
    3. "auf alle Tage anwenden"
    4. Abweichungen je Tag             [OPTIONAL]
       → Slot verschieben / hinzufügen / löschen, tagweise
    Ergebnis: Liste konkreter Slots, jeder mit Datum + Zeitraum

A4b GANZER TAG / WOCHE / MONAT
    1. Welche Tage bzw. Wochen bzw. Monate?
    Ergebnis: Liste von Zeiträumen ohne Uhrzeit

A4c MEHRERE TAGE
    1. Von wann bis wann? (mehrere solche Blöcke möglich)
    2. Startzeit am ersten Tag, Endzeit am letzten Tag   [OPTIONAL]
    Ergebnis: je Block ein Zeitraum; alles dazwischen gehört dazu

A4d REGELMÄSSIG
    1. Welche Wochentage?
    2. Uhrzeit                          [OPTIONAL]
    Ergebnis: Wochentagsmuster

A5  Begrüßung, Schlussformel, Policy                   [OPTIONAL]  (wie B4)

A6  VORLEGEN                                           [PFLICHT-GATE]
    → "Ich frage sechs Personen nach diesen drei Zeitfenstern: … Sechs Anrufe,
       etwa 30 Cent. Soll ich?"
```

### Was im Anruf gefragt wird

**Zu jedem Slot einzeln**, nicht als offene Frage:

> „Können Sie am Samstag zwischen 14 und 18 Uhr?"

**Regel, die ins Schema gehört:** *Nicht erwähnt heißt nicht zugesagt.* Wer zu einem Slot
nichts sagt, gilt als **unklar** — nicht als „kann". Das Ergebnisschema trennt deshalb
`kann`, `kann_nicht` und lässt alles übrige leer.

---

## 2. Während der Anrufe

```
je Teilnehmer:  wartet → klingelt → spricht → Endzustand

Endzustände (aus dem Dienst, NICHT zusammenwerfen):
  COMPLETED  → hat geantwortet                    grün
  NO_ANSWER  → niemand da                         Fragezeichen, ausgegraut
  DECLINED   → weggedrückt                        rot
  BUSY       → besetzt                            Fragezeichen, ausgegraut
  VOICEMAIL  → Anrufbeantworter                   Fragezeichen, ausgegraut
  FAILED / EXPIRED / CANCELED → Fehler            rot, mit Grund

zusätzlich, ohne Anruf:
  KEINE_NUMMER → gar nicht anrufbar               eigene Liste darunter
```

**Der Agent im Sprachmodus** meldet das gerafft: *„Vier haben geantwortet, Erik ging nicht
ran, bei Frida war besetzt."* — die Unterscheidung bleibt erhalten, die Aufzählung nicht.

---

## 3. Auswertung

### Zweig A — Terminkonzil

```
je Slot:  Anzahl "kann"  +  wer kann  +  wer kann nicht  +  wer unklar
```

**Nichterreichte werden nie als Zustimmung gewertet.** Jede Aussage trägt ihren Nenner:
„4 von 6 haben geantwortet."

**Kriterien setzen** [OPTIONAL, verändert nur die Sortierung]:
1. Lieblingstermin des Einladenden
2. Personen, die unbedingt dabei sein müssen
3. Anzahl der Zusagen (immer implizit)

→ Slots werden bewertet: „3 von 3 Kriterien erfüllt".

**Terminieren** → ein Slot wird verbindlich.

### Zweig B — Runder Tisch

```
je Person:  Rohantwort  +  Deutung des Telefon-Agenten
```

**Beides aufheben.** Die Deutung ist bequem, die Rohantwort ist der Beleg — der Dienst
kategorisiert eigenständig (gemessen), das muss überprüfbar bleiben.

Ansichten: chatartig je Person · oder Zusammenfassung durch ein eigenes LLM
(*„Was hat die Ritterrunde zu meinem Vorschlag gesagt?"*) · oder Bericht als Markdown/PDF.

---

## 4. Nachlauf (Zweig A)

```
A7  Wie sollen die anderen erfahren, was herauskam?
    ├── per Telefon
    ├── per E-Mail
    ├── Telefon, sonst E-Mail
    └── gar nicht / ich mache das selbst

A8  Einladungstext                                     [ABLEITBAR]
    → Default aus dem Projekt vorausgefüllt:
      "Wir haben einen Termin gefunden. Alle konnten wir nicht unter einen Hut
       bringen, aber am besten passte <Slot>. Deshalb lade ich dich ein zu <Anlass>."
    → anpassbar; Sätze, Skills, Policies wie bei A5

A9  Auch informieren:                                  [OPTIONAL]
    → Personen, die gar nicht eingeladen waren, können nachträglich dazu
    → nachgetragene Kontaktdaten lösen den nachgeholten Anruf aus

A10 Übersicht: wer wurde erreicht, wo lief der Anrufbeantworter,
    wer bekam eine Mail — mit Symbol für den Kanal
```

---

## 5. Was der Agent NIE tut

- **wählen ohne Vorlage** — jeder Lauf hat ein Bestätigungs-Gate mit Anzahl und Kosten
- **Nummern raten** — keine Nummer heißt „nicht anrufbar", nicht „vielleicht diese hier"
- **Nichterreichte als Zustimmung werten**
- **Schweigen zu einem Slot als Zusage werten**
- **die Rohantwort verwerfen** und nur die Deutung behalten
- **überreden**, wenn jemand nicht antworten will — Verweigerung ist ein gültiges Ergebnis
- **Rufnummern unmaskiert ausgeben**

---

## 6. Warum das automatisch zur Oberfläche passt

Jeder **PFLICHT**-Knoten wird ein Feld, das man ausfüllen muss.
Jeder **ABLEITBAR**-Knoten wird ein vorausgefülltes Feld mit Korrekturmöglichkeit.
Jeder **OPTIONAL**-Knoten wird ein aufklappbarer Bereich, der zugeklappt bleibt.
Jedes **GATE** wird ein Bestätigungsschritt.

Der Unterschied zwischen Skill und Oberfläche ist damit nur die Darstellung —
die Entscheidungen sind dieselben, und keine kann in einem Zugang fehlen, ohne im anderen
aufzufallen.
