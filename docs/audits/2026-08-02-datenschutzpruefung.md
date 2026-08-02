# Prüfbericht: Datenschutz und Hosting — 2026-08-02

> **Ein Beleg, kein aktueller Stand.** Dies ist der Bericht einer Prüfung vom
> **2. August 2026**. Er beschreibt die Anwendungen, wie sie an diesem Tag
> waren — vor dem Umbau, den er ausgelöst hat. Er wird hier aufbewahrt, weil
> eine Prüfung, die stattgefunden hat, mehr wert ist als ein makelloses
> Dokument ohne Vorgeschichte.
>
> **Was aus den Befunden wurde, steht im Schutzkonzept:** [`SCHUTZKONZEPT.de.md`](../../SCHUTZKONZEPT.de.md)
> — dort erscheint jeder Befund mit seiner Antwort. Der heutige Datenfluss steht
> in [`DATA-FLOW.md`](../../DATA-FLOW.md).
>
> Bereinigt für die Veröffentlichung: lokale Dateipfade des Prüfrechners wurden
> durch eine Umschreibung ersetzt. Inhaltlich unverändert.
>
> Englische Fassung: [`2026-08-02-privacy-audit.md`](2026-08-02-privacy-audit.md)

---

Stand: 2. August 2026<br>
Prüfgegenstand: `hungrycall`, `ringedingeding`, `researchcall`

> **Rechtliche Ersteinschätzung mit Fundstellen — keine Rechtsberatung.** Dies ist eine KI-gestützte Erstorientierung und kein Ersatz für die individuelle Prüfung durch eine zugelassene Rechtsanwältin oder einen zugelassenen Rechtsanwalt. Der konkrete Verantwortliche, Einsatzzweck, Personenkreis, Anbieter-Vertrag, Hostingort und Fragebogen können das Ergebnis ändern. Keine Fristüberwachung; bei Behördenpost, Abmahnung oder sonstigen Fristen sofort qualifizierte Rechtsberatung einholen.

## Ergebnis in einem Satz

Die Nutzerüberlegung ist nur teilweise richtig: Eine ausschließlich persönliche oder familiäre Nutzung durch eine natürliche Person **kann** unter die Haushaltsausnahme fallen, aber nicht weil die Datei auf dem eigenen PC liegt. Auch bei einem gehosteten Dienst kann die Tätigkeit des privaten Endnutzers im Einzelfall darunterfallen; Betreiber und Hoster bleiben für ihre eigene Verarbeitung jedoch erfasst. Keine der drei Apps ist technisch host-ready.

## Kurzbefund

| Projekt | Lokale Privatnutzung | Daten verlassen den Rechner? | Mehrbenutzerfähig? | Hosting-Befund |
| --- | --- | --- | --- | --- |
| HungryCall | Ein rein privater Bestell-/Reservierungsvorgang kann grundsätzlich in die Haushaltsausnahme fallen. Zweck und tatsächliche Nutzung entscheiden. | Bei Remote-Hosting immer Browser→App-Host. Darüber hinaus nutzt schon die normale Nicht-Test-Suche Nominatim/Overpass; Karten laden OSM-Tiles. Live zusätzlich CALL-E und Restaurant. | Nein: gemeinsamer Prozesszustand, eine SQLite-Datei, keine Konten/Autorisierung, ein CALL-E-Schlüssel | **Nicht veröffentlichen; Risiko hoch.** Verlauf, Ergebnis und Transkript wären besucherübergreifend. |
| Ringedingeding | Rein private Familien-/Freundeskoordination kann grundsätzlich erfasst sein. Vereins-, Organisations-, berufliche oder wirtschaftliche Nutzung ist gesondert zu prüfen und regelmäßig nicht „ausschließlich“ privat/familiär. | Bei rein lokaler Fixture-Ausführung kein Providertransfer; bei Remote-Hosting immer Browser→App-Host. Live zusätzlich Telefonnummer, Name/Task, Referenz und Antworten/Transkript an CALL-E und Angerufene. | Nein: gemeinsame Kontakte, Fotos, Projekte, Transkripte, Jobs, SQLite-Datei und ein über die ungeschützte Einstellungsroute änderbarer Schlüssel | **Nicht veröffentlichen; Risiko hoch.** |
| ResearchCall | Eine planmäßige Befragung für wissenschaftliche, institutionelle, berufliche oder veröffentlichungsbezogene Zwecke ist regelmäßig keine ausschließlich persönliche/familiäre Tätigkeit. | Bei rein lokaler Workbench-Ausführung kein Providertransfer; bei Remote-Hosting immer Browser→App-Host. Live-CLI zusätzlich Rufnummer, Fragebogen-Task, Schema, Sprache und Sample-ID an CALL-E. | Nein: ein gemeinsamer Workspace und eine gemeinsame Workbench-Datenbank; Web ohne Login. Live nur separat per CLI mit einem Prozessschlüssel | **Nicht veröffentlichen; Risiko hoch, bei umfangreichen Art.-9-Daten ggf. höher.** Studienrecht/Ethik und ggf. DSFA zusätzlich prüfen. |

Das sind Risikoeinschätzungen für die erwogene Veröffentlichung im **jetzigen** Zustand, keine Feststellung eines bereits eingetretenen Datenschutzverstoßes.

## Prüfung der Nutzerüberlegung

Ausgangsthese, sprachlich normalisiert:

> „Wenn die Apps die Daten privat nutzen, speichert der Nutzer sie auf seinem PC — da muss man keine Datenschutzerklärung machen. Aber wenn es jemand hosten würde, dann müsste dieser das dann machen.“

### Was daran stimmt

Art. 2 Abs. 2 lit. c DSGVO nimmt die Verarbeitung durch natürliche Personen zur Ausübung **ausschließlich persönlicher oder familiärer Tätigkeiten** aus. Erwägungsgrund 18 nennt als mögliche Beispiele privaten Schriftverkehr, Anschriftenverzeichnisse, soziale Netze und Online-Tätigkeiten in diesem privaten/familiären Rahmen. Fällt ein konkreter Nutzer tatsächlich vollständig unter diese Ausnahme, treffen ihn die DSGVO-Pflichten für diese konkrete Verarbeitung nicht.

### Was daran nicht stimmt

1. **Der Speicherort entscheidet nicht.** Lokale automatisierte Speicherung ist grundsätzlich Verarbeitung im Sinn von Art. 2 Abs. 1 und Art. 4 Nr. 2 DSGVO. Die Ausnahme hängt am Zweck und Kontext der Tätigkeit, nicht an „PC statt Cloud“.
2. **Das Anrufen eines Dritten beendet die Ausnahme nicht automatisch.** Nach dem EuGH beziehen sich „persönlich oder familiär“ auf die Tätigkeit der verarbeitenden Person, nicht auf die Person, deren Daten verarbeitet werden. Ein privater Terminabgleich mit Familienmitgliedern kann daher trotz fremder Telefonnummern privat bleiben.
3. **Der Außenbezug ist trotzdem wichtig.** Organisierte Forschung, berufliche/wirtschaftliche Nutzung, Vereins-/Organisationsbetrieb oder Veröffentlichung für einen unbestimmten Personenkreis überschreiten die ausschließlich private/familiäre Sphäre regelmäßig. Der EuGH legt die Ausnahme eng aus.
4. **Externe Anbieter bleiben nicht automatisch ausgenommen.** Erwägungsgrund 18 sagt ausdrücklich, dass die DSGVO für Verantwortliche oder Auftragsverarbeiter gilt, die die Verarbeitungsmittel für private/familiäre Tätigkeiten bereitstellen. CALL-E, ein SaaS-Betreiber oder ein Hostinganbieter muss seine eigene Rolle prüfen, auch wenn ein Endnutzer persönlich handelt.
5. **„Der Hoster macht die Datenschutzerklärung“ ist zu pauschal.** Die Stelle, die Zwecke und Mittel bestimmt, ist Verantwortlicher (Art. 4 Nr. 7). Ein reiner Infrastrukturhost ist typischerweise Auftragsverarbeiter (Art. 4 Nr. 8, Art. 28); der App-/Dienstbetreiber ist häufig Verantwortlicher. Je nach Produktgestaltung können Betreiber und Nutzer getrennte oder gemeinsame Verantwortlichkeiten haben. Diese Rollen müssen anhand der tatsächlichen Entscheidungen und Verträge festgelegt werden.

## Was sich ändert, sobald Dritte angerufen werden

Telefonnummer, Name, Gesprächsinhalte, Antworten, Rückrufwunsch und Transkript können personenbezogene Daten der angerufenen Person sein. In ResearchCall können die frei gestaltbaren Fragen zudem besondere Kategorien nach Art. 9 Abs. 1 DSGVO betreffen.

Wenn die Haushaltsausnahme nicht greift:

- Vor jeder Verarbeitung ist eine tragfähige Rechtsgrundlage nach Art. 6 zu bestimmen; bei besonderen Kategorien zusätzlich eine Ausnahme nach Art. 9 Abs. 2 und gegebenenfalls nationales Forschungsrecht.
- Stammt die Telefonnummer aus einem Adressbuch, vom Organisator, aus OSM oder einer Stichprobendatei, ist Art. 14 zu prüfen. Bei Verwendung zur Kontaktaufnahme ist die Information grundsätzlich spätestens bei der ersten Mitteilung zu erteilen (Art. 14 Abs. 3 lit. b), soweit keine Ausnahme greift.
- Antworten, die die Person im Gespräch selbst gibt, werden bei ihr erhoben; dafür ist Art. 13 maßgeblich und die Information grundsätzlich zum Erhebungszeitpunkt bereitzustellen.
- Eine kurze verständliche Erstinformation im Gespräch plus erreichbarer Volltext ist technisch naheliegend, muss aber für Zweck, Zielgruppe und Rechtsgrundlage juristisch/ethisch bestätigt werden.
- Ob automatisierte Anrufe, Gesprächsaufzeichnung/Transkription, Werbung, Forschungseinwilligung oder berufs-/sektorspezifische Regeln zulässig sind, ist eine zusätzliche Prüfung. Diese Unterlagen entscheiden das nicht.

## Normtext und Subsumtion

Verwendeter lokaler Normtext: law-checker `_data/gesetze/DSGVO.txt`, amtliche EUR-Lex-Quelle, konsolidierte Fassung `02016R0679-20160504`, abgerufen am 19.07.2026.

Wörtliche Kernfundstellen aus den verifizierten amtlichen Texten:

- Art. 2 Abs. 2 lit. c DSGVO: „durch natürliche Personen zur Ausübung ausschließlich persönlicher oder familiärer Tätigkeiten“.
- Erwägungsgrund 18 DSGVO: „ausschließlich persönlicher oder familiärer Tätigkeiten und somit ohne Bezug zu einer beruflichen oder wirtschaftlichen Tätigkeit“; der folgende Satz erfasst Anbieter der Verarbeitungsmittel ausdrücklich weiter.
- Art. 8 Abs. 1 GRCh: „Jede Person hat das Recht auf Schutz der sie betreffenden personenbezogenen Daten.“ Lokaler law-checker-Text: amtliche EUR-Lex-Fassung 2012/C 326/02, abgerufen am 19.07.2026.

- **Art. 2 Abs. 1 DSGVO:** Erfasst ganz oder teilweise automatisierte Verarbeitung personenbezogener Daten. Die drei Apps speichern strukturiert in SQLite/JSON; lokale Verarbeitung ist daher nicht schon wegen des Speicherorts ausgenommen.
- **Art. 2 Abs. 2 lit. c DSGVO:** Ausnahme nur bei Verarbeitung „durch natürliche Personen zur Ausübung ausschließlich persönlicher oder familiärer Tätigkeiten“. „Ausschließlich“ ist die entscheidende Grenze.
- **Erwägungsgrund 18:** Kein Bezug zu beruflicher/wirtschaftlicher Tätigkeit; private Anschriftenverzeichnisse/Online-Aktivitäten können erfasst sein; Anbieter der Verarbeitungsmittel bleiben erfasst.
- **Art. 4 Nr. 1, 2, 7 und 8 DSGVO:** Telefonnummern, Namen, Freitext und Transkripte können personenbezogene Daten sein; Speichern, Auslesen und Übermitteln sind Verarbeitung; Verantwortlicher und Auftragsverarbeiter sind nach tatsächlicher Entscheidungs-/Auftragslage zu bestimmen.
- **Art. 5 Abs. 1 lit. c, e, f und Abs. 2 DSGVO:** Datenminimierung, Speicherbegrenzung, Vertraulichkeit und Rechenschaft. In allen drei Apps fehlen allgemeine automatische Löschfristen; gemeinsame, ungeschützte Datenräume widersprechen dem Ziel der Vertraulichkeit eines Hostbetriebs.
- **Art. 6 DSGVO:** Mindestens eine passende Rechtsgrundlage ist nötig; die Vorlagen lassen sie deshalb bewusst offen und erfinden keine.
- **Art. 9 DSGVO:** ResearchCall kann je nach Fragebogen besondere Datenkategorien verarbeiten; Art. 6 allein genügt dann nicht.
- **Art. 12 bis 14 DSGVO:** Transparenz und Information für App-Nutzer und Angerufene. Art. 14 verlangt unter anderem Datenkategorien und Quelle; bei Kontaktaufnahme gilt grundsätzlich spätestens die erste Mitteilung.
- **Art. 24, 25 und 32 DSGVO:** Nachweisbare, risikogerechte Maßnahmen, Datenschutz durch Technikgestaltung/Voreinstellungen und Sicherheit. Art. 25 Abs. 2 verlangt insbesondere, Daten nicht ohne Eingreifen einer unbestimmten Zahl von Personen zugänglich zu machen.
- **Art. 28 DSGVO:** Bei Verarbeitung im Auftrag sind Auswahlprüfung und Vertrag mit dem Auftragsverarbeiter nötig.
- **Art. 35 DSGVO:** Vor voraussichtlich hohem Risiko ist eine Datenschutz-Folgenabschätzung nötig; das ist bei ResearchCall studien- und umfangsabhängig vorab zu entscheiden.
- **Art. 44 ff. DSGVO:** Eine Übermittlung in Drittländer verlangt die Voraussetzungen des Kapitels V. Ein Quellcode-Endpunkt oder eine README-Angabe belegt weder tatsächliche Länder noch Garantien.
- **Art. 7 und 8 GRCh:** Privat-/Familienleben und personenbezogene Daten sind grundrechtlich geschützt; diese Gewährleistungen tragen die enge Auslegung der Ausnahme und die risikoorientierte Abwägung.

Amtlicher Volltext: [EUR-Lex, Verordnung (EU) 2016/679](https://eur-lex.europa.eu/legal-content/DE/TXT/?uri=CELEX:32016R0679).

## Rechtsprechung zur Haushaltsausnahme

1. **EuGH, Urteil vom 10.07.2018, C-25/17, Tietosuojavaltuutettu/Jehovan todistajat, ECLI:EU:C:2018:551, Rn. 40–42.** Die vergleichbare Haushaltsausnahme der Datenschutzrichtlinie ist eng; entscheidend ist die Tätigkeit des Verarbeitenden, nicht die Identität der betroffenen Person. Eine nach außen gerichtete Tür-zu-Tür-Datenerhebung war nicht ausschließlich persönlich/familiär. [Amtliche EuGH-Fundstelle](https://curia.europa.eu/juris/document/document.jsf?docid=203822&doclang=DE).
2. **EuGH, Urteil vom 11.12.2014, C-212/13, Ryneš, ECLI:EU:C:2014:2428, insbesondere Rn. 29–33.** Eine private Kamera, die auch öffentlichen Raum erfasste, fiel nicht unter die vergleichbare Ausnahme; die Ausnahme ist grundrechtsorientiert eng auszulegen. [Amtliche EuGH-Fundstelle](https://curia.europa.eu/juris/document/document.jsf?docid=160561&doclang=DE).

Beide Entscheidungen betreffen die Vorgängerrichtlinie, nicht unmittelbar Art. 2 Abs. 2 lit. c DSGVO. Ihre Auslegung der inhaltlich vergleichbaren Haushaltsausnahme und der EuGH-Verweis in C-25/17 sind für die Grenzziehung aussagekräftig; die konkrete heutige Anwendung bleibt einzelfallabhängig.

## Technische Belege je Repo

### HungryCall

- `hungrycall/db.py`: eine SQLite-Datei mit Namen, Anfrage, Lieferadresse, unmaskierter Rückrufnummer und telefonnummernmaskiertem Transkripttext; keine automatische Löschung.
- `hungrycall/web.py`: modulweite `ACTIVE_ORDERS`/`CANCELED_ORDERS`, ungeschützte Verlaufs-/Ergebnisrouten, keine Nutzeridentität.
- `hungrycall/location.py` und `hungrycall/static/app.js`: Nominatim/Overpass außerhalb des ausdrücklichen Testmodus; browserseitige OSM-Tile-Verbindungen auch bei gerenderter Testmodus-Karte.
- `hungrycall/call_client.py`/`engine.py`: ein Prozessschlüssel; live gehen Zielrufnummer und auftragsbezogene Daten an CALL-E.

Liefergegenstände: `hungrycall/DATA-FLOW.md`, `hungrycall/PRIVACY-TEMPLATE.md`, `hungrycall/HOST-READINESS.md` und Eintrag in `hungrycall/AUFGABEN.txt`.

### Ringedingeding

- `ringedingeding/store.py`/`projects.py`: eine SQLite-Datei mit Kontakten, Kanälen, Fotos, Projekten, Rohnummern, Antworten und Transkripten.
- `ringedingeding/web/app.py`: keine Anmeldung; alle Projekt-/Kontakt-/Foto-/Export-/Run-Routen teilen denselben Zustand. Projektlöschung lässt Phrase-/Fragezeilen und den separaten Poll-/Teilnehmer-/Antwortbaum zurück; Live-Transkripte können verwaist bleiben.
- `ringedingeding/calle_credentials.py`: ein Prozess-/Projekt-Schlüssel; die aktuelle ungeschützte Einstellungsroute kann ihn in `config.local.json` ersetzen.
- `ringedingeding/transports/base.py`/`runner.py`: live gehen Rohnummer, standardmäßig Vorname, Task und Metadaten an CALL-E.

Liefergegenstände: `ringedingeding/DATA-FLOW.md`, `ringedingeding/PRIVACY-TEMPLATE.md`, `ringedingeding/HOST-READINESS.md` und Eintrag in `ringedingeding/TODO.md` (die vorhandene `AUFGABEN.txt` war beim Bearbeiten schreibgesperrt).

### ResearchCall

- `src/researchcall/web/workspace.py`/`web/app.py`: ein gemeinsames `workspace.json`, ungeschützte Stationen, Tasks, Berichte und Exporte; Web ausschließlich Fixtures.
- `src/researchcall/database.py`/`sampling.py`: externe Referenz und Rohnummer in SQLite; Stichprobe, Versuche und strukturierte Antworten.
- `src/researchcall/calls.py`/`cli.py`: live nur über das ausdrückliche CLI-Gate; ein Prozessschlüssel; Rohnummer und Fragebogen-Task an CALL-E.
- `src/researchcall/runner.py`: Volltranskript wird geprüft, aber nicht lokal gespeichert; gezielter Withdrawal-Purge entfernt Nummer, Antwort und Provider-Run-ID, lässt jedoch Sample-/Versuchsmetadaten und Idempotenzschlüssel zurück und löscht nicht beim Provider.
- `src/researchcall/export.py`: Export ohne Rufnummer/externe Referenz und ohne zurückgezogene Datensätze; Freitext kann trotzdem identifizieren.

Liefergegenstände: `researchcall/DATA-FLOW.md`, `researchcall/PRIVACY-TEMPLATE.md`, `researchcall/HOST-READINESS.md` und `researchcall/AUFGABEN.txt`.

## Mindestanforderungen vor Hosting

1. Veröffentlichung bis zur Umsetzung von Anmeldung, sicheren Sitzungen, Mandantentrennung und objektbezogener Autorisierung sperren.
2. Jede Tabelle, jeder Workspace, Job, Export und Stream braucht einen belegten Eigentümer/Tenant und serverseitige Zugriffsprüfung.
3. Nutzerbezogene API-Schlüssel nur verschlüsselt in einem Secret Store, mit Rotation, Löschung, Quoten und Abrechnungsgrenzen; alternativ Live-Telefonie nur operatorseitig anbieten.
4. Lösch-/Aufbewahrungsplan in Code, Backups, Logs und Anbieter-Verträgen umsetzen und testen.
5. Verantwortlichen-/Auftragsverarbeiterrollen, Rechtsgrundlagen, Art.-13/14-Informationen, AV-Verträge und Drittlandmechanismen dokumentieren.
6. CALL-E-Rechtsträger, tatsächliche Verarbeitungsländer, Unterauftragsverarbeiter, Logs und Speicherfristen vertraglich belegen. Gleiches gilt bei HungryCall für die konkret betriebenen Nominatim-/Overpass-/Tile-Endpunkte.
7. TLS, CSRF-Schutz, sichere Cookies, Rate Limits, Auditierung, Uploadschutz und unabhängige Sicherheitsprüfung ergänzen.
8. Für ResearchCall zusätzlich Fragebogen, Art.-9-Daten, nationales Forschungsrecht, Ethik, Widerruf/Withdrawal und DSFA-Schwelle studienspezifisch prüfen.

Eine ausgefüllte Datenschutzerklärung ist nur Transparenzdokumentation. Sie ersetzt weder Rechtsgrundlage noch Verträge, Sicherheit, Mandantentrennung oder Löschung.

## law-checker-Protokoll

Verwendet wurde eine lokale Installation des Werkzeugs `law-checker` (Pfad hier ausgelassen; es handelt sich um eine Arbeitskopie auf dem Prüfrechner). Registry: `config.json`, Version 5; lokaler DSGVO-Text mit Quellenkopf und Abrufdatum 19.07.2026. Ergänzend wurde der Skill `rechtsabteilung` für Norm-/Rechtsprechungsfundstellen angewandt.

Aktive Registergesetze wurden gesichtet: GG, BGB, SGB V, UrhG, RDG, MarkenG, StBerG, UWG, DSGVO, EHDS-VO und GRCh. Für diesen eng begrenzten Datenschutz-/Hostingbefund wurden **DSGVO** und grundrechtlich **GRCh** ausgewählt. UWG wurde als möglicher Randbereich für Werbung geprüft, aber mangels belegter Werbeanrufe nicht subsumiert. GG, BGB, SGB V, UrhG, RDG, MarkenG, StBerG und EHDS-VO waren für die konkreten Fragen nicht entscheidungserheblich. Die im Register deaktivierten StGB und MStV wurden nicht aktiviert; insbesondere Gesprächsaufzeichnung/Transkription und Telefonwerberecht bleiben gesonderte Prüffelder.

## Offene Tatsachen für die anwaltliche/deployment-spezifische Prüfung

- Wer betreibt welches Repo zu welchem Zweck und für welchen Personenkreis?
- Ist ein App-Betreiber, jeder nutzende Organisator oder sind beide Verantwortliche?
- Welche CALL-E-Vertragsgesellschaft, Serverregionen, Unterauftragsverarbeiter, Speicherfristen und Übermittlungsgrundlagen gelten tatsächlich?
- Welche konkreten Nominatim-/Overpass-/Tile-Instanzen und Nutzungsbedingungen werden im Betrieb verwendet?
- Werden Gespräche aufgezeichnet oder nur maschinell transkribiert; wie und wann werden Angerufene darüber informiert?
- Welche Rechtsgrundlage gilt je Zweck, und enthält ein ResearchCall-Fragebogen besondere Kategorien?
- Welche Infrastruktur-, Proxy-, Sicherheits-, Support- und Backup-Logs existieren im realen Hosting?
