# Codex-Ausbau-Report — Nutzer-Feedback vom 2026-08-02

## Ergebnis

Ringedingeding ist jetzt sichtbar in zwei Produkte geteilt:

1. **Terminfinden** fragt „Wann kannst du?“, führt Verfügbarkeiten zusammen,
   lässt einen Termin entscheiden und kann anschließend einladen.
2. **Ask Your Advisor** fragt „Was meinst du?“ und zeigt Tendenz,
   Gegenstimmen, Begründungen und Bedenken. Offene Antworten werden nicht wie
   Termine geschnitten und Mehrheiten werden nicht als Einigkeit ausgegeben.

Beide Wege nutzen dieselben Sicherheits-, Kontakt-, Trockenlauf- und
Anrufmechanismen. Die Auswahl im ersten Klick bestimmt den Produktweg. Eine
Advisor-Frage ohne Optionen sammelt freie Ratschläge; mindestens zwei
verschiedene Optionen ergeben eine begründete Abstimmung.

## Was gebaut wurde

### 1. Ask Your Advisor

- eigener Modus `roundtable` in Service, Weboberfläche und CLI;
- persistierte Frage mit freier oder `choice`-Antwortform;
- erweitertes Ergebnisschema für Richtung, Gründe und Bedenken;
- getrennte Aggregation mit `primary_tendency`, `countervoices` und
  unveränderten Einzelantworten;
- eigener Wizard-Schritt und eigenes Ergebnisboard;
- Probelauf erzeugt deterministische, ausdrücklich als erfunden markierte
  Advisor-Antworten;
- Konsolen- und Markdown-Berichte führen Gründe und Gegenargumente mit.

### 2. Beliebige Gruppen

- frei benennbare, wiederverwendbare Gruppen mit Notiz und Kontaktmitgliedern;
- Auswahl der Zielgruppe direkt beim Projektanlegen;
- Gruppenverwaltung im Web sowie `group add` und `group list` in der CLI;
- die aktuelle Gruppenmitgliedschaft wird beim Anlegen in das Projekt kopiert.
  Das ist absichtlich ein Schnappschuss: eine spätere Gruppenänderung verändert
  keinen bereits freigegebenen Anrufauftrag unbemerkt.

### 3. Kalender und Filter

- globale Kalenderansicht über alle datierten Terminprojekte;
- Projekte lassen sich per Checkbox ein- und ausblenden;
- Advisor-Projekte erscheinen nicht als Schein-Termine;
- laufende Kandidaten sind als Vorschlag, entschiedene Slots als entschieden
  gekennzeichnet.

Anzeige und Export bekommen dasselbe `CalendarEntry`-Tupel. Der Projektfilter
ist dadurch tatsächlich die Exportauswahl und nicht nur Oberflächenkomfort.

### 4. Export

- RFC-5545-ICS mit stabilen lokalen UIDs, `TENTATIVE` für Vorschläge und
  `CONFIRMED` für Entscheidungen;
- echtes `.xlsx` als standardkonformes ZIP/XML-Arbeitsbuch, vollständig mit
  Python-Standardbibliothek erzeugt;
- beide Downloads enthalten exakt die in der Kalenderansicht angehakten
  Projekte.

Google Calendar und Microsoft Calendar können die ICS-Datei importieren. Eine
direkte OAuth-Kontoverknüpfung blieb offen: Sie ist im Feedback nur optional,
würde neue Zugangsdaten- und Netzpfade schaffen und ist für den vollständigen
Offline-Weg nicht nötig.

### 5. Deutsch und Englisch

Verwendet wurde das vorhandene System aus Editor-PythonBox:

- `TranslationSystem` aus `translator.py` mit deutschem Ausgangstext als
  Schlüssel, UTF-8-JSON-Katalog, Sprach-Fallback und atomarem Speichern;
- `manage_translations.py` mit den Befehlen `list`, `add` und `missing`;
- derselbe Katalogpfad `locales/translations.json`.

Die einzige notwendige Anpassung ist der Scanner: PythonBox sucht Qt-Aufrufe;
Ringedingeding ist Jinja/HTML und sucht deshalb zusätzlich `t('…')` in Python-
und Template-Dateien. Das Übersetzungssystem selbst wurde nicht neu erfunden.
Der Katalog enthält 300 Einträge; der echte Lauf von `missing` gab nichts aus.
Der Sprachwechsel setzt nur ein lokales Cookie und lädt keinen Übersetzungsdienst.

### 6. Designakzente

- klar unterscheidbare Moduskarten für Terminfinden und Advisor;
- lokales Ring-Logo, Farbverläufe, dezente Hintergrundakzente und stärkere
  Kartenhierarchie;
- eigene Akzentfarben für Termin-, Gruppen- und Advisor-Bereiche;
- hervorgehobene Advisor-Tendenz, Gegenstimmenkarten und Kalenderstatus;
- responsive Anpassung für schmale Ansichten.

Ich habe lokale CSS-Akzente statt eines generierten Bildes gewählt. Sie
verbessern Wiedererkennung und Hierarchie, bleiben offline, skalieren sauber,
benötigen keine zusätzliche Asset-Lizenz und führen weder CDN noch Upload ein.

## Übersetzungsweg

Quellweg, der vor der Umsetzung gelesen und übertragen wurde:

`C:\Users\User\OneDrive\.TOPICS\.SOFTWARE\CODING\REL_Editor_PythonBox\`

Übernommen wurden das Verfahren und die Verträge aus `translator.py`,
`manage_translations.py` und `locales/translations.json`. Die lokale Umsetzung
liegt in `ringedingeding/translator.py`, `manage_translations.py` und
`ringedingeding/locales/translations.json`.

## Verifikation

Ausgeführter Abschlusslauf:

```text
$ python -X utf8 -m pytest --basetemp out/pytest-evidence-codex-20260802-d
........................................................................ [ 22%]
........................................................................ [ 45%]
........................................................................ [ 67%]
........................................................................ [ 90%]
..............................                                           [100%]
318 passed, 2 warnings in 49.56s
```

Ausgangspunkt waren 308 grüne Tests. Hinzugekommen sind 10 Regressionen für
Gruppenschnappschuss, offene Advisor-Tendenz, begründete Abstimmung,
Kalenderfilter, leere Auswahl, ICS, XLSX, vollständigen Katalog, englische
Weboberfläche, Offline-Advisor-Ablauf und lokale Designakzente (ein Test deckt
mehrere eng gekoppelte Exportaspekte ab).

Die zwei Warnungen sind:

- Starlettes Hinweis, dass sein `TestClient` künftig `httpx2` erwartet;
- Pytests Cache-Warnung wegen fehlender Schreibrechte auf `.pytest_cache`.

Beide beeinflussen die 318 bestandenen Tests nicht. Für temporäre Testdaten
wurde deshalb ein expliziter Pfad unter `out/` benutzt.

Zusätzlich ausgeführt:

```text
$ python -X utf8 manage_translations.py missing
[keine Ausgabe]
EXIT=0
```

Außerdem wurde lokal und ohne Build-Isolation ein Wheel erzeugt. Der Inhalt
enthielt nachweislich `ringedingeding/locales/translations.json` sowie die neuen
Advisor- und Kalendertemplates. Der Sprachkatalog geht bei einer Installation
also nicht verloren.

## Offen geblieben

- der gewünschte lokale Commit: `git add -A` scheiterte beim Anlegen von
  `.git/index.lock` mit `Permission denied`. Es wurde nichts gestaged. Ein
  zweiter Versuch wurde ohne wiederhergestellten Git-Schreibzugriff nicht
  erzwungen;
- direkte Google-Calendar- und Microsoft-Calendar-Kontoverknüpfung; ICS-Import
  ist vorhanden und dokumentiert;
- kein visueller Geräte- oder Browser-Screenshot-Lauf; Templates, Routen und
  responsive CSS sind automatisiert geprüft, aber nicht als Gerätefreigabe zu
  verstehen;
- keine echte CALL-E-Antwort für die neuen Advisor-Schemata gemessen. Der
  vollständige Fixture-/Probelauf ist grün; reale Dienstreaktion bleibt offen;
- Parallelität und wachsendes Live-Transkript bleiben wie zuvor ungeprüfte
  CALL-E-Eigenschaften.

## Grenzen eingehalten

Es wurde kein echter Anruf ausgelöst, nichts gepusht, veröffentlicht,
hochgeladen oder an die Schwesterprojekte angeglichen. Alle Änderungen liegen
in diesem Repository. Rufnummern bleiben maskiert und der Standardweg bleibt
der vollständige Offline-Trockenlauf.

Während der Arbeit neu erschienene ungetrackte Dateien `banner.png` und
`README_de.md` wurden als fremde Änderungen behandelt, nicht verändert und
nicht in die Ausbauleistung eingerechnet.
