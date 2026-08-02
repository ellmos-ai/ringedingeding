# Codex Cockpit Report

**Datum:** 2026-08-02  
**Umfang:** Startseite als eigenständiges Ringedingeding-Cockpit, ohne echten Anruf, Push oder Veröffentlichung

## Hauptwahl für neue Anrufketten

Die Startseite zeigt die beiden bereits vorhandenen Anwendungsfälle als gleichwertige, prominente Einstiege:

1. **Termin finden – „Wann kannst du?“**  
   Ziel: `/?mode=schedule#new-chain`  
   Wirkung: Öffnet das vorhandene Formular und wählt den Modus `schedule` vor.
2. **Ask Your Advisor – „Was meinst du?“**  
   Ziel: `/?mode=roundtable#new-chain`  
   Wirkung: Öffnet dasselbe vorhandene Formular und wählt den Modus `roundtable` vor.

Ein unbekannter `mode`-Wert fällt sicher auf „Termin finden“ zurück. Es wurde kein neuer Call-Typ erfunden.

## Kacheln und erschlossene Bereiche

| Kachel | Ziel | Vorhandener Bereich |
|---|---|---|
| Kalender | `/calendar` | Kalenderansicht |
| Kontakte | `/contacts` | Kontaktverwaltung |
| Gruppen | `/groups` | Gruppenverwaltung |
| Laufende Ketten | `#chains` | Bestehende Ketten auf der Startseite |
| Ergebnisse & Export | `/calendar#export` | Vorhandene ICS-/XLSX-Exporte im Kalender |

Es gibt exakt fünf Bereichskacheln. Alle Ziele sind vorhandene GET-Routen oder vorhandene Seitenanker; es wurde keine leere Zielseite ergänzt.

## Gestaltung

- Das Ringedingeding-Logo aus dem Repo-Root ist prominent im Cockpit-Hero eingebunden. Die verwendete Static-Kopie ist laut SHA-256-Prüfung bytegleich mit `logo.svg` im Root.
- Die Oberfläche erhielt eine eigene technische Cockpit-Handschrift: tiefes Navy, Cockpit-Blau, Cobalt, Signal-Gold, Radar-/Ringmotiv und dezente Rasterflächen.
- Die zwei Hauptaktionen besitzen große, klar getrennte Startkarten. Die übrigen Bereiche folgen als kompakteres Kachelraster.
- Abstände, Typografie, Statuszeile, Icons, Hoverzustände und Kartenhierarchie wurden ausgebaut.
- Das Raster reagiert über vier Layoutstufen von fünf über drei und zwei auf eine Spalte.
- `prefers-reduced-motion` wird berücksichtigt.
- Fokusrahmen und Sekundärtext wurden nach einem unabhängigen Re-Test nachgebessert. Gemessene Kontraste: Fokus auf Weiß 8,53:1, Weiß auf Navy 17,53:1, Weiß auf Termin-Blau 8,02:1 und Sekundärtext auf Seitenhintergrund 5,14:1.
- Es werden keine entfernten Design-Assets geladen; die Gestaltung bleibt lokal und unterscheidet sich bewusst von Papier-Optik oder hellem/buntem Schwesterprojekt-Design.

## Zweisprachigkeit

Alle neuen sichtbaren Texte laufen über den vorhandenen `t(...)`-Mechanismus. Der Katalog ist gültiges JSON und enthält nach der Erweiterung 322 Einträge. Der frische Katalogabgleich fand für 288 in 34 Templates verwendete Literale keinen fehlenden Schlüssel und keinen leeren englischen Wert. Deutsche Texte verwenden echte Umlaute.

## Tests und tatsächliche Verifikation

Neu hinzugefügt wurden drei Dashboard-Regressionstests für:

- die zwei prominenten Einstiege samt Logo,
- exakt fünf Kacheln und ihre realen Ziele,
- die Modusvorwahl einschließlich sicherem Fallback.

Der frische `pytest --collect-only`-Lauf sammelte **321 Tests** aus 18 Dateien; vor dem Cockpit lag der letzte vollständig ausgeführte Lauf bei **318 bestandenen Tests**. Zwei isolierte statische Regressionen und ein schreibfreier Jinja-Smoke für `schedule`, `roundtable` und einen ungültigen Modus bestanden.

Eine frische vollständige Ausführung konnte in dieser Sandbox nicht bis zu den Testkörpern starten: Pytest erhielt beim Anlegen von `C:\Users\User\AppData\Local\Temp\pytest-of-User` `PermissionError [WinError 5]`; auch ein Basistemp unter `C:\tmp` scheiterte an `EPERM`. Deshalb wird **kein neuer „321 bestanden“-Wert behauptet**.

Zusätzlich wurde die laufende lokale Oberfläche per HTTP gemessen: Startseite `200`, exakt fünf Bereichskacheln, erreichbare Hauptlinks sowie korrekte Vorwahl für `schedule`, `roundtable` und ungültigen Modus. Diese Prüfung ersetzt keinen vollständigen Pytest-Lauf.

## Harte Grenzen

- Kein echter Anruf und kein Live-Flag.
- Kein CALL-E-Netzwerkzugriff.
- Kein Git-Push.
- Keine Veröffentlichung.

## Lokaler Commit

Der geforderte lokale Commit konnte in dieser Ausführungsumgebung nicht erzeugt werden. `git status --short`, das ausschließlich auf die oben genannten Cockpit-Dateien begrenzte `git add -- ...` und `git commit -m "Build bilingual dashboard cockpit"` scheiterten jeweils bereits vor dem Start von Git: Die Windows-Sandbox konnte PowerShell wegen `CreateProcessAsUserW failed: 5 (Zugriff verweigert)` nicht starten. Deshalb wurde nichts gestaget und kein Commit behauptet. Die bekannten fremden Dateien `banner.png` und `README_de.md` blieben unangetastet.
