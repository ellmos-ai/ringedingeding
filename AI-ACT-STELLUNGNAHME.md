# Ersteinschätzung zum EU AI Act: RingeDingeDing

**Stand:** 2. August 2026
**Gegenstand:** KI-gestützte Anrufe bei mehreren Privatpersonen zur Sammlung und Zusammenführung von Terminen oder Meinungen
**Hinweis:** Diese technische und redaktionelle Ersteinschätzung ist keine Rechtsberatung. Der konkrete Betreiber muss Zweck, Empfängerkreis, Datenquelle, Verträge und Rechtsordnung vor Live-Anrufen rechtlich prüfen lassen.

## Kurzurteil

RingeDingeDing ist nach seinem dokumentierten Zweck kein Hochrisiko-System nach Anhang III des AI Act. Art. 50 Abs. 1 und 5 greift dennoch: Die angerufene Person muss spätestens bei der ersten Interaktion klar und unterscheidbar erfahren, dass sie mit einem KI-System spricht. Die Pflicht gilt seit dem 2. August 2026.

Von den drei geprüften Projekten hat RingeDingeDing die stärkste technische Reihenfolge: Der erste Satz ist verpflichtend, wortwörtlich zitiert und steht vor benutzerdefinierten Begrüßungen. Er sagt jedoch nur „automatischer Assistent“ beziehungsweise „automated assistant“, nicht „KI“ oder „AI“. Außerdem prüft der Ergebnisweg das Transkript nicht auf eine tatsächlich zuerst gesprochene Offenlegung. Damit ist Art. 50 **teilweise umgesetzt, aber nicht nachgewiesen erfüllt**.

Besonders gewichtig ist hier die vorgelagerte Kontaktfrage: Mehrere Privatpersonen werden anhand vom Organisator eingetragener Nummern angerufen. Weder die Live-Bestätigung des Organisators noch die Frage „Passt es gerade?“ beweist eine Rechtsgrundlage für die bereits erfolgte Anwahl.

## 1. Welche Pflichten greifen?

| Thema | Ersteinschätzung | Begründung |
| --- | --- | --- |
| Art. 50 Abs. 1 und 5 AI Act | **Greift.** | Das System ist für direkte Sprachinteraktion mit natürlichen Personen bestimmt. Die Information muss spätestens bei der ersten Interaktion klar, unterscheidbar und barrierefrei erfolgen. |
| Art. 4 AI Act | **Greift rollenbezogen.** | Anbieter und Betreiber müssen Maßnahmen zur Förderung der KI-Kompetenz der mit dem System arbeitenden Personen treffen, insbesondere zu Zweckgrenzen, Freigabe, Ablehnung, Datenschutz und Eskalation. |
| Art. 6 und Anhang III AI Act | **Nach aktuellem Zweck kein Hochrisiko-System.** | Terminabfrage und einfache Meinungsaggregation sind keine der aufgezählten Entscheidungen über Bildung, Beschäftigung, wesentliche Dienste, Strafverfolgung, Migration, Justiz oder demokratische Prozesse. |
| Art. 53 / GPAI-Verhaltenskodex | **Keine unmittelbare Projektpflicht belegt.** | Das Repository stellt kein eigenes General-Purpose-AI-Modell bereit. Es ist eine nachgelagerte Anwendung eines Anrufdienstes. |
| DSGVO | **Greift.** | Telefonnummern, Namen, Verfügbarkeit, Meinungen, Freitext und Transkripte können personenbezogen sein; politische, religiöse, gesundheitliche oder gewerkschaftliche Meinungen können Art. 9 berühren. |

Eine reine Meinungsumfrage ist nicht allein deshalb „demokratischer Prozess“ im Sinne von Anhang III. Wird das System später aber dazu bestimmt, Wahlergebnisse oder das Wahlverhalten natürlicher Personen zu beeinflussen, Personen für Beschäftigung oder Bildung zu bewerten oder Anhang-III-Entscheidungen vorzubereiten, ist neu zu klassifizieren. Profiling in einem einschlägigen Anhang-III-Anwendungsfall verschärft die Einstufung nach Art. 6 Abs. 3. Die einschlägigen Hochrisiko-Pflichten nach Anhang III gelten infolge der Verordnung (EU) 2026/1744 ab dem 2. Dezember 2027; Art. 50 gilt bereits jetzt.

## 2. Was erfüllt der aktuelle Code – und was nicht?

### Vorhandene Kontrollen

- Die deutschen Regeln schreiben als ersten, unaufgeforderten und wortwörtlichen Satz vor: „Guten Tag, hier ist ein automatischer Assistent im Auftrag von … Ich habe eine kurze Frage.“ (`ringedingeding/schemas.py:307-327`).
- Die englische Fassung verlangt entsprechend „automated assistant“ (`ringedingeding/schemas.py:285-305`).
- Benutzerdefinierte Begrüßungen folgen ausdrücklich **nach** dieser Pflichtformel (`ringedingeding/schemas.py:330-353`).
- Ein Nein wird ohne Überredung akzeptiert; bei einem unpassenden Zeitpunkt wird kein automatischer Rückruf versprochen (`ringedingeding/schemas.py:316-326`).
- Der Live-Transport kann ohne explizite Bestätigung nicht gebaut werden (`ringedingeding/transports/calle.py:105-125`); der zentrale Service verlangt zusätzlich die exakte Live-Bestätigungsphrase (`ringedingeding/service.py:573-614`).
- Das Ergebnis enthält ein maskiertes Transkript (`ringedingeding/transports/calle.py:393-407`), das für einen Offenlegungsnachweis genutzt werden könnte.

### Offene Lücke nach Art. 50

Die Formulierung „automatischer Assistent“ beschreibt Automatisierung, identifiziert das Gegenüber aber nicht ausdrücklich als KI-System. Ob der Ausdruck in jedem Kontext rechtlich genügt, ist nicht durch Repository-Evidenz geklärt; auf die Offensichtlichkeitsausnahme sollte nicht vertraut werden. Der Code prüft auch nicht, ob die Pflichtformel in der tatsächlichen ersten Bot-Äußerung enthalten war.

Der Status lautet deshalb **gute technische Grundlage, rechtlicher Nachweis offen**. Die Pflichtformel sollte ausdrücklich lauten:

> „Guten Tag, hier spricht ein KI-Assistent im Auftrag von [Organisator]. Ich habe eine kurze Frage.“

beziehungsweise:

> “Hello, this is an AI assistant calling on behalf of [organiser]. I have one short question.”

Ein Regressionstest muss für beide Sprachen und alle Projektarten die Position vor jeder anderen Äußerung sichern. Die Ergebnisprüfung muss das erste BOT-Segment validieren und fehlende oder verspätete Offenlegung als nicht konform ausweisen. Diese Lücken stehen in `AUFGABEN.txt`.

## 3. Die angerufene Person hat vorher nicht eingewilligt

Der Organisator kann eine Nummer eintragen und einen Live-Lauf bestätigen. Der Code belegt damit weder, dass die betroffene Person ihre Nummer für diesen Zweck überlassen hat, noch dass sie mit dem Anruf, der Transkription oder der Zusammenführung ihrer Antwort einverstanden war.

Die Frage, ob es „gerade passt“, ist eine gute Respektregel. Sie kommt aber nach Nummernverarbeitung, Weitergabe und Anwahl. Auch die Zustimmung zur kurzen Frage heilt diese Schritte nicht rückwirkend. Vor Live-Betrieb braucht jedes Projekt daher einen dokumentierten Kontaktpfad:

1. **Quelle und Erwartung:** Woher stammen Name und Nummer? Wurde die Person vorab eingeladen, oder worauf stützt sich die Kontaktaufnahme? Öffentliche Auffindbarkeit oder die Adressliste eines Organisators genügt nicht automatisch.
2. **Rechtsgrundlage je Phase:** Art. 6 DSGVO ist für Listenimport, Anwahl, Gespräch, Zusammenführung und Aufbewahrung getrennt zu dokumentieren. Bei Art. 6 Abs. 1 Buchst. f sind Zweck, Erforderlichkeit, vernünftige Erwartungen, Schutzmaßnahmen und Widerspruchsfolgen konkret abzuwägen.
3. **Art. 13/14-Information:** Stammt die Nummer vom Organisator oder einer anderen Quelle, ist Art. 14 regelmäßig spätestens bei der ersten Kommunikation relevant. Direkt erfragte Angaben fallen unter Art. 13. Der mündliche Ersthinweis sollte Betreiber, Zweck, Nummernquelle, Transkription beziehungsweise Aufzeichnung, Freiwilligkeit und einen Vollhinweis nennen.
4. **Ablehnung, Widerspruch und Nicht-anrufen-Liste:** Der vorhandene Gesprächsabbruch muss in eine belastbare Sperrlogik übergehen. Eine Person darf nicht in einem neuen Aggregationslauf unbeabsichtigt wieder kontaktiert werden, soweit eine zweckgebundene Sperrung rechtlich zulässig und erforderlich ist.
5. **Sensible Themen:** Projektfragen müssen vorab auf besondere Kategorien nach Art. 9 geprüft werden. Eine beiläufige politische, gesundheitliche oder religiöse Antwort darf nicht ohne passende Rechtsgrundlage und Schutzmaßnahmen gespeichert oder weitergegeben werden.
6. **Werbung und Aufzeichnung:** Nur wenn der konkrete Anruf Werbung ist, kommt zusätzlich § 7 UWG zur Anwendung; dann gelten strenge vorherige Einwilligungsvoraussetzungen, insbesondere bei automatischen Anrufmaschinen. Ob CALL-E Audio aufzeichnet, ist im Repository nicht belegt. Falls ja, ist § 201 StGB separat vor der Aufnahme zu prüfen.

„Freiwillig antworten“ und „rechtmäßig angerufen werden“ sind zwei verschiedene Prüfungen. Für Privatpersonen ist ein dokumentierter vorheriger Einladungs- oder Opt-in-Pfad die belastbarste Produktvorgabe, sofern keine andere tragfähige Rechtsgrundlage festgestellt wurde.

## 4. Pflichten des Hosters in den Servermodi

Die tatsächlichen Zwecke, Mittel, Verträge und Marken bestimmen die Rollen. Ein Hoster kann je nach Ausgestaltung AI-Act-Anbieter, Betreiber, datenschutzrechtlich Verantwortlicher, gemeinsam Verantwortlicher oder Auftragsverarbeiter sein. Ein Nutzerschlüssel oder Browserstorage entscheidet das nicht allein.

| Modus aus `../huckepack/KONZEPT.md` | Betreiberanforderung |
| --- | --- |
| `local` | Eine gemeinsame Adress- und Projektdatenbank ohne Konten ist nicht für nicht vertrauenswürdige Mehrnutzer geeignet (`HOST-READINESS.md:3-30`). Vor Hosting sind Authentifizierung, Mandantentrennung, Objektberechtigungen, Fristen, Rechte und Schlüsselgrenzen umzusetzen. |
| `huckepack-gift` | Der Hoster stellt Schlüssel und Anrufausführung. Browserpersistenz ändert nicht, dass Nummer, Aufgabe und Antwort durch Host und CALL-E verarbeitet werden. Er braucht Art.-50-Sicherung, Rechtsgrundlagen, Anbieterprüfung, Quoten, Missbrauchsschutz und einen Rechtekanal. |
| `huckepack-only-host` | Der Besucher zahlt über einen eigenen Schlüssel; der Host vermittelt trotzdem Oberfläche und Anruf. Transitdaten, Schlüsselhandhabung, Rollen, Vertragskette und Sicherheit müssen transparent und technisch abgesichert sein. |
| `pay-membership` | Nur Stub. Vor Freigabe braucht es Konten, Abrechnung, Mandanten- und Datentrennung, Secret-Management, Rechte, Löschung, Export und Incident-Prozesse. |

`DATA-FLOW.md:17-32, 37-66` dokumentiert Telefonnummern, Antworten und Transkripte sowie verbleibende Transit- und Exportgrenzen der Huckepack-Modi. `PRIVACY-TEMPLATE.md:20-75` verlangt bewusst eine konkrete Rechtsgrundlage, Informationen bei der ersten Kommunikation und verifizierte Dienstleisterdaten; Platzhalter sind kein Freigabenachweis.

### Freigabekriterien vor Live-Hosting

- Explizite KI-Offenlegung als erster wortwörtlicher Satz, plus automatischer Nachweis aus dem ersten Bot-Segment.
- Projektbezogener Kontaktbeleg: Nummernquelle, vorherige Einladung oder andere Rechtsgrundlage, Zweck, Empfängerkreis und Interessenabwägung.
- Art.-13/14-Erstinformation, Vollhinweis, Widerspruchs- und Nicht-anrufen-Prozess.
- Inhaltsprüfung auf Art.-9-Daten sowie Grenzen gegen Profiling, Überredung und zweckfremde Weitergabe.
- Verifizierte CALL-E-Rollen, Vertragspartei, Unterauftragsverarbeiter, Länder, Aufbewahrung, Löschung, Art. 28 und gegebenenfalls Kapitel V.
- Modusgerechte Sicherheit, Raten- und Kostenlimits, Mandantentrennung sowie Export-/Löschwege.
- Art.-4-KI-Kompetenz und dokumentierte Anhang-III-Neubewertung bei jeder Zweckänderung.

## 5. Quellen und Evidenzgrenzen

Eigene Um:bruch-Analysen, auf die diese Einschätzung aufbaut, ohne sie zu kopieren:

- `C:\Users\User\OneDrive\.TOPICS\.UMBRUCH\website\src\content\blog\ai-act-transparenzpflichten-ab-august-2026.md` – wichtigste Ausgangsanalyse.
- `...\ki-reviews\eu-ai-act-transparenz-code-of-practice.md` mit englischer Fassung `eu-ai-act-transparency-code-of-practice.md`.
- `...\ki-reviews\eu-ai-act-haftungsluecke.md` mit englischer Fassung `eu-ai-act-liability-gap.md`.
- `C:\Users\User\OneDrive\.TOPICS\.UMBRUCH\_editorial\entwuerfe\2026-07-03_eu-ai-act_leitartikel_synthese.md` – als Entwurf behandelt.

Primär- und Behördenquellen: [Verordnung (EU) 2024/1689](https://eur-lex.europa.eu/eli/reg/2024/1689/oj), [Verordnung (EU) 2026/1744](https://eur-lex.europa.eu/eli/reg/2026/1744/oj), [Art. 50](https://ai-act-service-desk.ec.europa.eu/de/ai-act/article-50), [Anhang III](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-3), [Umsetzungszeitplan](https://ai-act-service-desk.ec.europa.eu/en/ai-act/timeline/timeline-implementation-eu-ai-act), [DSGVO](https://eur-lex.europa.eu/eli/reg/2016/679/2016-05-04/eng), [§ 7 UWG](https://www.gesetze-im-internet.de/uwg_2004/__7.html) und [§ 201 StGB](https://www.gesetze-im-internet.de/stgb/__201.html).

Nicht belegt und offen sind vorherige Einwilligungen oder Einladungen der konkreten Kontakte, CALL-E-Audioverhalten und Vertragsdaten, Anbieteraufbewahrung, Verarbeitungsländer, Unterauftragsverarbeiter und die Rechtsgrundlage eines konkreten Projekts.
