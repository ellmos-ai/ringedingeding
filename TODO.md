# TODO — Ringedingeding

## Datenschutz und Hosting [Prüfung 2026-08-02]

- [x] Belegten Datenschaltplan erstellt: `DATA-FLOW.md`.
- [x] Anpassbare Muster-Datenschutzerklärung mit Hoster-Platzhaltern erstellt:
      `PRIVACY-TEMPLATE.md`.
- [x] Host-Readiness belegt: `HOST-READINESS.md`.
- [ ] **Hosting-Sperre:** Die App ist derzeit nicht mehrbenutzerfähig. Vor
      Veröffentlichung müssen insbesondere Authentifizierung, Mandantentrennung,
      objektbezogene Autorisierung, nutzerbezogene Secret-Verwaltung,
      Löschfristen und eine deployment-spezifische Rechts-/Anbieterprüfung gebaut
      und getestet werden.
- [x] **Löschdefekt repariert (2026-08-05):** Projektlöschung entfernt
      `phrase`-/`project_question`-Zeilen und den zugehörigen
      Poll-/Teilnehmer-/Antwortbaum einschließlich Rohnummern und Transkripten.
      Kontaktlöschung entfernt duplizierte Teilnehmer- und Interviewdaten.
      Regressionstests decken simulierte und nicht simulierte Ergebnisdaten ab.
- [x] Bei der Prüfung keinen echten Anruf ausgelöst und keine echten Rufnummern
      dokumentiert.
