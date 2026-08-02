"""Small UI translation extension for the CALL-E settings surface."""

from __future__ import annotations

from .translator import TranslationSystem as BaseTranslationSystem

CALLE_TRANSLATIONS = {
    "CALL-E-Einstellungen": {"en": "CALL-E settings"},
    "Der API-Schlüssel wurde in der lokalen Projekt-Config gespeichert.": {"en": "The API key was saved in the local project config."},
    "Aktiver Zugang": {"en": "Active access"},
    "Quelle": {"en": "Source"},
    "Angezeigt werden ausschließlich die letzten vier Zeichen.": {"en": "Only the final four characters are displayed."},
    "Noch kein API-Schlüssel eingerichtet.": {"en": "No API key has been configured yet."},
    "Schlüssel lokal speichern": {"en": "Save key locally"},
    "Neuer API-Schlüssel": {"en": "New API key"},
    "Der Wert wird in der ignorierten Projekt-Config gespeichert. Er erscheint weder im HTML noch in Protokollen oder Fehlermeldungen.": {"en": "The value is saved in the ignored project config. It never appears in HTML, logs, or error messages."},
    "Sicher speichern": {"en": "Save securely"},
    "Priorität": {"en": "Priority"},
    "in der Umgebung": {"en": "in the environment"},
    "in der Projektdatei": {"en": "in the project file"},
    "kann den Pfad ändern": {"en": "can change the path"},
    "in der Projekt-Config": {"en": "in the project config"},
    "Die zuerst gefundene Quelle gewinnt. Trockenläufe funktionieren ohne Schlüssel.": {"en": "The first source found wins. Dry runs work without a key."},
    "Echte Anrufe kosten Geld und starten nur nach der ausdrücklichen Live-Bestätigung.": {"en": "Real calls cost money and start only after explicit live confirmation."},
    "Kein API-Schlüssel eingerichtet.": {"en": "No API key is configured."},
    "Jetzt in den Einstellungen hinterlegen": {"en": "Open settings now"},
}


class TranslationSystem(BaseTranslationSystem):
    """The standard catalog plus strings owned by the settings feature."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.translations.update(CALLE_TRANSLATIONS)
