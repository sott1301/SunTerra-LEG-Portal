# ADR 0002: Mutationsbindung und Entry-Freigabe

## Status

Akzeptiert

## Kontext

Das Portal unterstützt mehrere Mutationstypen. Frühere Formulierungen haben
verwischt, ob alle Mutationen eine LEG-Freigabe brauchen oder ob die
Teilnehmererklärung schon bei Einreichung verbindlich ist. Die Go-live-
Entscheidung trennt `entry` von allen anderen Mutationstypen.

## Entscheidung

`entry` ist der einzige Mutationstyp mit konstitutiver LEG-Freigabe. Ein
Eintritt wird erst durch LEG-Freigabe zur verbindlichen Teilnahmeabsicht.

Alle Nicht-`entry`-Mutationen sind bei Einreichung verbindliche
Teilnehmererklärungen, ausser sie sind fehlerhaft oder unvollständig. Vor der
Paketierung führt die LEG einen Paketbereit-Check auf Vollständigkeit und
Plausibilität durch. Dieser Check ist keine fachliche Wirksamkeitsfreigabe.

Fehlerhafte oder unvollständige Mutationen gehen mit Begründung auf Klärung oder
Stopp. Teilnehmer reichen korrigierte Informationen als neue oder aktualisierte
Erklärung ein.

Partnerstatus aus der Gemeinde/EW-Bearbeitung erzeugt Folgearbeit, ändert
Mutation oder Mitgliedschaft aber nicht automatisch.

## Konsequenzen

- Tests und UI-Wording dürfen den Paketbereit-Check für Nicht-`entry`-Mutationen
  nicht als Freigabe beschreiben.
- Entry-Freigabe und Paketbereitschaft für Nicht-`entry` bleiben getrennte
  Workflow-Seams.
- Partnerfeedback wird als Folgeaufgabe oder Statushistorie geführt, nicht als
  automatische Domain-State-Änderung.
