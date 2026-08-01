# AGENTS.md — verbindliche Regeln für dieses Repo

> Beitrag zum **CALL-E-Hackathon** („Your Code Is Calling"), Frist **2026-09-14**.
> Operator: Claude Code. Diese Datei gilt für **jeden** Agenten, der hier arbeitet.
> Der konkrete Bauauftrag steht in `SPEC.md`.

## Die wichtigste Regel zuerst

**Standardverhalten ist der Trockenlauf. Ohne ausdrückliches Flag wird NIE telefoniert.**

Das Ziel-Repo schließt Beiträge aus, die „depend on private services without a local
fake-server or dry-run path". Ein Fixture-/Fake-Modus, der die komplette Logik ohne Konto
und ohne Netz durchlaufen lässt, ist deshalb **Pflichtbestandteil**, nicht Kür.

Praktisch: Die gesamte Entwicklung läuft **ohne CALL-E-Konto**. Es existiert noch keins.
Wer „ich bräuchte Zugangsdaten" schreibt, hat den Auftrag missverstanden.

## Was CALL-E kann — nicht dagegen anbauen

- Werkzeuge: **`plan_call` → `run_call` → `get_call_run`**. Mehr gibt es nicht.
- API: `POST /v1/calls`, `GET /v1/calls/{id}`, `GET /v1/calls/{id}/events`,
  `POST /calle/webhook` (terminal).
- **Kein Eingriff ins laufende Gespräch.** Kein Live-Kanal, kein Inject, kein Mithören.
- Gesprächsführung wird **nur über den `goal`/`task`-Freitext** gesteuert — es gibt kein
  Feld für Tonfall, Persona oder Skript.
- **Der stärkere Hebel ist das Ergebnis-Schema** (`result_schema` /
  `recipient_result_schema`): Was der Agent ausfüllen muss, bestimmt, was er im Gespräch
  herausfinden muss. Schema-Entwurf ist Kernarbeit.
- Rückgabe: `status`, `taskCompleted`, `completionConfidence`, `structuredResult`,
  `evidence`, `transcript`.
- Endstatus differenziert: `COMPLETED`, `FAILED`, `NO_ANSWER`, `DECLINED`, `CANCELED`,
  `VOICEMAIL`, `BUSY`, `EXPIRED` — **diese Unterscheidung nicht wegwerfen.**
- Fortschritt nur per **Polling**: erste Abfrage ~60 s nach Start, dann alle 5–10 s;
  liefert `activity` mit Zeitstempel.
- Kosten: **0,05 USD pro Anruf**, nicht pro Minute. Freikontingent: 20.
- Deutschland wird unterstützt, Sprachen Englisch **und Deutsch**.

**Zwei Dinge sind ungeprüft — im Code offenhalten, nicht annehmen:**
1. ob mehrere Anrufe **parallel** laufen („concurrency controls" sind dokumentiert, die
   Grenze nicht),
2. ob das **Transkript schon während** des Gesprächs wächst oder erst am Ende erscheint.

## Safety-Pflichten (aus dem CONTRIBUTING des Ziel-Repos)

- ausdrückliche Nutzerabsicht vor jedem Anruf
- **E.164**-Rufnummern (`+49…`), Validierung **vor** dem Wählen
- **Rufnummern in allen Ausgaben maskieren** — Logs, Zusammenfassungen, Berichte
- keine Zugangsdaten in Code, Logs oder Commits; nur Umgebungsvariablen
- **keine versteckten wiederkehrenden Zeitpläne**: kein Daemon, keine Endlosschleife.
  Wiederholung stößt der Host an (Aufgabenplanung/cron/n8n)
- keine Doppelanrufe → `Idempotency-Key`
- sauberes Abbruchverhalten (Strg-C beendet ordentlich, Zustand bleibt konsistent)
- Grenzen bei medizinischen, rechtlichen, finanziellen und Notfall-Inhalten
- Beispiele **nur mit fiktiven/maskierten Nummern**

## Datensparsamkeit

Der Sprach-Agent läuft **nicht lokal**, sondern bei CALL-E/AiRudder in Singapur
(`https://seleven-mcp-sg.airudder.com`). Alles, was in einen Auftrag geschrieben wird,
verlässt das Haus.

- Nur übergeben, was für **diesen einen Anruf** nötig ist. Keine Vorgeschichte,
  keine Zusatzmerkmale „für den Fall".
- Im README **offenlegen**, wohin die Daten gehen.
- Im lokalen Zustand Personenbezug minimieren (IDs statt Klarnamen, wo möglich).

## Technischer Rahmen

- **Python 3.11+**, SDK `pip install calle-ai` (alternativ MCP über den `calle`-CLI)
- Arbeitsort ist **ausschließlich dieses Repo**. Nicht nach OneDrive schreiben.
- Repo ist **privat**. Veröffentlichung entscheidet der Nutzer, nicht der Bau-Agent.
- Repo-Sprache **Englisch** (README, Code, Kommentare) — das Ziel-Repo verlangt Englisch.
  Absprachen mit dem Operator laufen auf Deutsch.

## Definition of Done

1. Läuft vollständig im **Trockenlauf**, ohne Konto, ohne Netz (Fixtures).
2. `README.md` (Englisch): Setup, Nutzung, Nebenwirkungen, Abbruch, **Datenfluss-Offenlegung**.
3. Tests decken den Kern ab und laufen im Trockenlauf grün.
4. Alle Safety-Punkte oben umgesetzt **und im README benannt**.
5. `EVIDENCE.md` hält fest, **was tatsächlich ausgeführt wurde** — wörtlich, ohne
   Glättung. Was nicht lief, steht als „nicht ausgeführt" drin. **Keine erfundenen Zahlen.**
6. Sauberer Git-Verlauf; `.gitignore` liegt bereits vor und wird nicht aufgeweicht.

## Ausdrücklich NICHT Teil des Bauauftrags

Echte Anrufe · Konto-Registrierung · Veröffentlichung des Repos · Pull Request ans
Ziel-Repo · Video. Das sind Operator- und Nutzer-Schritte. Wer daran rührt, überschreitet
seinen Auftrag.

## Wenn etwas unklar ist

Annahme **schriftlich in `EVIDENCE.md` festhalten** und weiterbauen — nicht blockieren,
aber auch nicht so tun, als sei die Frage geklärt. Erfundene Fakten sind der einzige
Fehler, der hier wirklich zählt.
