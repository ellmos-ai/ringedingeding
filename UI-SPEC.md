# Ringedingeding — Produktkonzept

> Diktiert vom Nutzer am 2026-08-01, aufgenommen vom Operator.
> **Seine Vorstellung**; Ergänzungen und Bedenken des Operators sind markiert.

## Grundhaltung

Gleiche Bauart wie „I am hungry": **Web-App, sehr clean, weiß, kein Schnickschnack.**
Browser auf, Auswahl treffen, los.

> *„Von der Art würde ich die wirklich alle gleich bauen. Die werden trotzdem sehr
> unterschiedlich sein — nur das Backend ist dann halt ziemlich ähnlich. Es kommt auf die
> Funktion an."*

## Die Grundentscheidung: eigene Kontakte

**Das Werkzeug ergibt nur Sinn mit den eigenen Kontakten.** Daraus folgt der ganze
Unterbau:

- **Kontaktbuch-Modul** aus dem Bestand als Grundlage — der Nutzer legt Profil und
  Kontakte an, vor allem mit **Telefonnummern**. Das Kontaktbuch ist auch anderweitig
  nutzbar.
- **Kalendermodul** anbinden — die gefundenen Termine müssen ja irgendwo hin.
- **Konnektoren** (Mail u. a.), über die Kontakte hereinkommen.
- **Die eigene lokale KI soll Kontakte suchen dürfen** — aus den verbundenen Konnektoren.
- **Export zu fremden Kalendern**, priorisiert: Google und Microsoft, dazu der
  Android-Standardkalender bzw. der iOS-Kalender.

Zunächst aber: **eigene Kalender- und Kontaktdatenbank.** Der Nutzer muss sie befüllen,
sonst ergibt das Werkzeug keinen Sinn. Zielgruppe eher privat, beruflich aber genauso
möglich.

## Die zwei Modi brauchen Namen und Bilder

Zwei Begriffe, die gut dargestellt werden müssen — und im Englischen ebenfalls gute
Entsprechungen brauchen.

1. **Terminkonzil** — Termin finden
2. **Runder Tisch** / **meine Berater** / **meine Ritterrunde** — Meinungen einholen

> **Bild des Nutzers:** die Versammlung in Bruchtal bei Herr der Ringe, wo beschlossen
> wird, was mit dem Ring geschieht, und sich die Gefährten bilden. Passt zum Projektnamen.

**Wichtig: Der Nutzer darf umbenennen.** Es gibt einen Standard, aber wer will, nennt es
„meine Ritterrunde".

---

## Modus 1 — Terminkonzil

### Anlage

**Anlass:** *„Um was geht's?"* / *„Wozu möchtest du einladen?"*

### Terminarten (die Auswahl davor)

| Art | Ablauf |
|---|---|
| **Tagestermin** (zeitlich begrenzt) | Kalenderansicht → Tage anklicken → **Standardzeit für alle Tage** festlegen: ein Slot, zwei Slots, drei Slots, je mit Start/Ende/Dauer → „auf alle Tage anwenden" → dann **Abweichungen je Tag**: Slots verschieben, neue hinzufügen, bestehende löschen → fertig |
| **Ganzer Tag** | Tage anklicken, gilt für den ganzen Tag, keine Uhrzeit nötig |
| **Woche anbieten** | gleiches Vorgehen, gröbere Einheit |
| **Monat anbieten** | ebenso |
| **Mehrere Tage** (zusammenhängend) | Zeitraum auswählen — alles dazwischen zählt als ein Slot; Startzeit am ersten und Endzeit am letzten Tag |
| **Regelmäßiger Wochentermin** | einfach Montag, Dienstag, Mittwoch … auswählen |

> **Nutzer-Hinweis:** Mit **TerminPilot** vergleichen — Abfragen, Felder und Abläufe lassen
> sich übernehmen, auch wenn man nicht das ganze Modul verwendet.

### Kontakte

Überschrift passend zum gewählten Begriff: *„Wen möchtest du einladen?"* / *„Dein Team"*

- **+ neuer Kontakt** — Telefonnummer ist Pflicht, sonst funktioniert der Kontakt nicht
- **E-Mail** als spätere Ausbaustufe, aber schon eingebbar
- **Bilder zu den Kontakten** — „weil wir Menschen nicht so heißen", und es sieht besser aus
- **Kontakte ohne Telefonnummer werden ausgegraut**: hinzufügbar, aber nicht berücksichtigt;
  das wird sichtbar symbolisiert

### Gesprächssteuerung

- **Begrüßungsformel und Schlussformel** — eigene Sätze, beliebig viele hinzufügbar
- **Eigene Policy speichern** = eigene Hintergrund-Prompts, Bedingungen und Regeln
- **PromptBoard-Backend wiederverwenden** — die gespeicherten Sätze und Regeln werden
  später zu einem Gesamt-Prompt zusammengefügt
- Gedacht als **„Gesprächspolicy"** bzw. mitgelieferte Skills: was im Gespräch wichtig ist

Dann: **Start.**

### Während der Anrufe

- Telefonsymbol bei dem, der gerade angerufen wird
- **nicht erreicht** → rot, durchgestrichen (X)
- **hat geantwortet** → grün
- die Daten füllen sich sichtbar

> **Offene Frage des Nutzers:** *„Muss man das Fenster immer offen haben? Oder kann man es
> später wieder öffnen? Läuft es ohne einen weiter?"* — siehe Antwort unten bei den
> Operator-Anmerkungen.

### Auswertung: die Kalenderansicht des Projekts

**Jedes Terminprojekt hat seinen eigenen Kalender in der Datenbank.** Ein Projekt ist wie
ein Projekt in einer Software — eine Interaktion, eine Tabelle.

- Man sieht die angebotenen Zeiträume
- Wer geantwortet hat, erscheint mit **Bild/Symbol und Namen** beim passenden Zeitraum
- In der Kalenderübersicht steht zunächst nur **die Zahl**, wie viele können
- **Klick auf einen Zeitraum** → Detailansicht mit den Symbolen der Personen
- **wer gar nicht kann** → rot dargestellt
- **wer nicht erreicht wurde** → Fragezeichen und ausgegraut *(bewusst unterschieden!)*
- **wer gar nicht anrufbar war** → als Liste darunter:
  *„Folgende Kontakte haben keine Telefonnummer und keine E-Mail-Adresse und konnten nicht
  kontaktiert werden."*
  → Kontaktdaten lassen sich **nachtragen**, dann werden diese Anrufe **nachgeholt**

### Präferenzen und Entscheidung

Der Einladende setzt **drei Kriterien**:

1. ein **Lieblingstermin**
2. **Kontakte, die unbedingt dabei sein sollen**
3. **die Anzahl** (fließt ein, wird aber nicht extra genannt)

Daraus werden die passendsten Termine **hervorgehoben** — „3 von 3 Kriterien passen",
„1 von 3". Ein solches Kriterienprofil gilt je Projekt.

Dann: **den Termin festlegen** („terminieren").

### Einladung verschicken

*Wie sollen die anderen informiert werden?*

- nur per **E-Mail**
- nur per **Telefon**
- **Telefon, sonst E-Mail**
- **„ich informiere selbst"** / keine automatische Information

Fehlende Kontaktdaten können nachgetragen werden — die Information wird dann nachgeholt.
Auch **bisher nicht Eingeladene** können nachträglich hinzugefügt und benachrichtigt werden.

Beim Verschicken: neue Maske mit **Sätzen, Skills, Policies** — oder der Default, aus dem
Projekt vorausgefüllt und anpassbar. Der Standardtext sinngemäß:

> *„Wir haben einen Termin gefunden. Alle kann man nie unter einen Hut bekommen, aber am
> besten passte der Termin am … Deswegen lade ich euch ein zu …"*

Danach dieselbe Übersicht wie bei den Anrufen: **wer wurde informiert, wer erreicht, wo lief
der Anrufbeantworter** — mit Symbol dafür, ob per E-Mail oder Telefon.

---

## Modus 2 — Runder Tisch (Meinungen einholen)

### Gruppenprofile

Der Nutzer legt **Profile** an, die gleich bleiben und wiederverwendet werden:
„meine Freunde", „meine Familie", „meine Ritterrunde". Braucht eine eigene Tabelle.

Profil anklicken → Maske mit **Sätzen, Skills, Policies**.

### Die Fragen darf der Nutzer selbst benennen

Standard: *„Was möchtest du von den anderen wissen?"*, *„Was müssen die anderen dazu
wissen?"* — dazu ein paar Standardvorschläge und ein **Plus-Symbol** für eigene.

**Pro Profil individuell:** Wer sich als Ritterrunde versteht, fragt
*„Was möchtest du von deinen Knappen wissen?"* oder *„Um welche Schlacht geht es?"*

Dann: absenden, Anrufe laufen, Antworten werden gesammelt.

### Antworten ansehen

- **Chat-artige Ansicht:** jeder mit seinem Symbol, daneben was er gesagt hat
- oder: auf die Person klicken, dann erscheint ihre Antwort
- **Mit eigenem LLM** (lokal oder Anbieter) per Skill abfragbar:
  *„Was hat die Ritterrunde zu meinem Vorschlag gesagt, auf Schatzsuche zu gehen?"*
  → *„Bisher hat nur Arthur geantwortet. Er ist wie immer mit dabei."*
- **Bericht erzeugen** als PDF oder Markdown — Zusammenfassung aller Antworten

> **Nutzer-Hinweis:** Für Zusammenfassung und Synthese gibt es bereits Skills im Bestand,
> die sich wiederverwenden lassen.

---

## ★ Der wichtigste Gedanke: Skill-First

> *„Das soll man auch einfach per CLI bedienen können — alles, ohne dass man das Tool
> selbst benutzt. Man soll das auch einfach durch seinen eigenen Agenten benutzen können.
> Ich glaube, das ist sogar wichtiger: wenn wir diese Konzepte erst mal als Skills und als
> Anweisungen und Abläufe weiter ausarbeiten — was, wenn das nur ein Skill-Prozess wäre?
> Was würde das LLM dann tun? Was würde es fragen? Und da wir jetzt das Frontend
> beschrieben haben, müsste es ja dann auch ganz gut zusammenpassen."*

**Das ist die strategisch beste Idee des Abends** — aus drei Gründen:

1. **Es passt zur Bewertung.** „Quality of Idea" belohnt ausdrücklich, was *„reusable by
   the community"* ist. Ein Skill ist genau das; eine Web-App ist es nur für den, der sie
   installiert.
2. **Es passt zum Einreichungsweg.** Die `skills/`-Area des Ziel-Repos verlangt
   `SKILL.md` — dasselbe Format, das die eigene Skill-Bibliothek seit Langem pflegt.
3. **Es ist der bessere Entwurfsweg.** Wer zuerst formuliert, *welche Fragen ein Agent
   stellen müsste*, hat damit automatisch die Feldliste der Oberfläche — und merkt sofort,
   wo eine Frage überflüssig ist. Ein Formular, das aus einem Gesprächsablauf entsteht,
   ist fast immer schlanker als eines, das am Reißbrett wächst.

**Konsequenz für die Bauweise:** Kern ist ein Ablauf, der **drei Zugänge** hat —
CLI, Skill (für den eigenen Agenten), Web-Oberfläche. Alle drei bedienen dieselbe Logik.
Die Oberfläche ist eine Sicht darauf, nicht das Werkzeug selbst.

---

## Operator-Anmerkungen

### Antwort auf die offene Frage „muss das Fenster offen bleiben?"

**Nein — solange der Server läuft.** Der Anruf findet ohnehin bei CALL-E statt; unser
Werkzeug fragt nur den Fortschritt ab. Läuft das Abfragen im Server (nicht im Browser),
kann man den Browser jederzeit schließen und später wieder öffnen — der Stand steht in der
Datenbank.

Das ist eine **Architekturentscheidung, die früh fallen muss**: Der Browser darf nur
*anzeigen*, nicht *treiben*. Sonst bricht ein geschlossenes Fenster die Runde ab. Für
Ringedingeding mit sechs Anrufen à ~1,5 Minuten ist das keine Feinheit, sondern der
Unterschied zwischen brauchbar und ärgerlich.

### Der Umfang ist erneut das Hauptrisiko

Das hier ist eine vollständige Terminplanungs-Suite mit Kontaktbuch, Kalender,
Konnektoren, Fremdkalender-Export, zwei Modi, Kriterienbewertung und Einladungsversand.
Realistisch in 44 Tagen **neben zwei weiteren Werkzeugen**: nein.

**Vorschlag für den Schnitt:**

**Kern (trägt das Video und die Bewertung):**
Anlass → Terminart **„Tagestermin" und „ganzer Tag"** (die zwei häufigsten) →
Kontakte aus einer einfachen eigenen Liste (mit Bild, ohne Konnektoren) →
Begrüßungs-/Schlussformel → Anrufe mit Live-Ansicht →
**Projekt-Kalenderansicht mit Zahl je Slot, Detail bei Klick, drei getrennte Zustände
(kann / kann nicht / nicht erreicht / gar nicht anrufbar)** → Kriterien setzen →
Termin festlegen → Einladung per Telefon verschicken.

**Kür (in dieser Reihenfolge):**
Runder-Tisch-Modus · Gruppenprofile mit eigenen Fragen · restliche Terminarten
(Woche, Monat, mehrere Tage, regelmäßig) · Kontakt-Import über Konnektoren ·
Fremdkalender-Export · LLM-Zusammenfassung und Berichte · E-Mail-Weg ·
PromptBoard-Anbindung für Policies

**Begründung:** Der Kern zeigt das Alleinstellungsmerkmal — mehrere Menschen anrufen und
daraus **einen** Termin machen, mit ehrlicher Behandlung der Nichterreichten. Alles andere
macht das Produkt besser, aber nicht den Wettbewerbsbeitrag.

### Wiederverwendung — erlaubt, aber mit Vorsicht

Kontaktbuch, Kalendermodul, PromptBoard, Mail-Konnektor dürfen einfließen (siehe
`konzept-hungrycall-ui.md`, Abschnitt Wiederverwendung). **Aber:** Jedes eingebundene
Modul bringt eigene Abhängigkeiten und eigene Fehlerquellen mit. Für einen Beitrag, der
in vier Wochen fertig sein muss, ist eine schlanke eigene Kontakttabelle oft schneller als
die Integration eines gewachsenen Moduls. Das ist von Fall zu Fall zu entscheiden —
nicht pauschal „alles wiederverwenden".
