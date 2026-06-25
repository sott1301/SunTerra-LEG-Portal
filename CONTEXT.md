# SunTerra LEG Domain Context

Dieses Repository implementiert das Mitglieder- und Mutationsportal der
SunTerra LEG. Die folgende Sprache ist kanonisch für Issues, Tests,
API-Bezeichnungen und sichtbare Workflow-Namen.

## Kanonische Begriffe

- **SunTerra LEG**: Die produktive Marke der lokalen Elektrizitätsgemeinschaft
  und des Portals. Die Marke steht eigenständig; Gebiets- oder Partnerbezüge
  werden nur genannt, wenn Teilnahmeberechtigung, Netzwerktopologie oder
  Gemeinde/EW-Zuständigkeit erklärt werden.
- **Basadingen-Schlattingen**: Das Gebiet und der Partnerkontext des ersten
  SunTerra-LEG-Rollouts. Der Begriff beschreibt den lokalen Raum und die
  Gemeinde/EW-Verantwortung, nicht die Produktmarke.
- **Teilnehmer**: Eine Person, die im Portal Mitgliedschaft, Dokumente,
  ConsentEvidence, Kontaktkanäle und meldepflichtige Änderungen verwaltet.
- **LEG-Vertrag**: Der verbindliche Vertrag der lokalen Elektrizitätsgemeinschaft,
  den Teilnehmer vor verbindlicher Portalnutzung akzeptieren.
- **Mutation**: Eine Teilnehmererklärung zu einer meldepflichtigen Änderung,
  etwa Adresse, Messpunkt, Rolle, Erzeugungsanlage, Eintritt, Austritt oder
  Sonderfall.
- **Eintritt**: Die Mutation `entry`. Sie ist die einzige Mutation, die eine
  konstitutive LEG-Freigabe braucht, bevor sie als verbindliche Teilnahmeabsicht
  gilt.
- **Paketbereit-Check**: Eine formale LEG-Prüfung für Nicht-`entry`-Mutationen
  vor der Paketierung. Sie bestätigt Vollständigkeit und Plausibilität, aber
  keine fachliche Wirksamkeitsfreigabe.
- **Netzwerktopologie**: Der Teilnahmeberechtigungskontext, der bestimmt, ob ein
  Messpunkt im abgedeckten angeschlossenen Raum liegt. Im Pilot wird dies
  manuell geprüft und im Portal dokumentiert.
- **Interessensmeldung**: Eine gespeicherte Interessensbekundung einer
  E-Mail-Adresse, die noch nicht für den kontrollierten Pilot freigegeben ist.
  Sie ist kein Konto und keine verbindliche Teilnehmerbeziehung.
- **Partnerstatus**: Der Bearbeitungsstand der Gemeinde/EW-Rolle für ein
  MutationPackage, etwa empfangen, in Prüfung, verarbeitet, Rückfrage oder
  technisch nicht möglich. Partnerstatus erzeugt Folgearbeit, ändert aber
  Mutation oder Mitgliedschaft nicht automatisch.
- **MutationPackage**: Ein unveränderliches Paket paketbereiter Mutationen für
  den Gemeinde/EW-Partnerkontext mit CSV, PDF, JSON, Hash, Quartal,
  Wirksamkeitsdaten, Actor und Statushistorie.

## Sprachregeln

- Nutze **SunTerra LEG** für Produkt- und Gemeinschaftsmarke.
- Nutze **Basadingen-Schlattingen** nur für Gebiet, Teilnahmeberechtigung,
  Netzwerktopologie oder Gemeinde/EW-Partnerkontext.
- Nutze **LEG-Vertrag** für den verbindlichen Teilnehmervertrag.
- Behandle Nicht-`entry`-Mutationen bei Einreichung als verbindlich, ausser sie
  sind fehlerhaft oder unvollständig; vor Paketbildung laufen sie durch den
  Paketbereit-Check.
