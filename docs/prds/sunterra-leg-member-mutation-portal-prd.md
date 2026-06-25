# PRD: SunTerra LEG Mitglieder- und Mutationsportal

## Problem Statement

Die SunTerra LEG braucht ein eigenständiges Portal, in dem Teilnehmer ihre Mitgliedschaft, Dokumente, Einwilligungen und meldepflichtigen Änderungen nachvollziehbar verwalten können. LEG-Vertreter müssen Eintritte, Mutationen, Paketbereit-Prüfungen und Meldungen an Gemeinde und Elektrizitätswerk sicher bearbeiten können. Die kombinierte Gemeinde/EW-Rolle braucht ein minimales, datensparsames Mitgliederregister und eine klare Inbox für MutationPackages.

Das Portal soll nicht nur als technischer Prototyp funktionieren, sondern in einem verbindlichen Pilot mit echten Nutzern, echten Einwilligungen, echten MutationPackages und echten Gemeinde/EW-Rückmeldungen belastbar sein. Danach soll der Zugang öffentlich für Bürgerinnen und Bürger im SunTerra-LEG-Gebiet geöffnet werden.

Heute ist der fachliche Bedarf klar, aber mehrere Go-live-Fragen sind rechtlich, betrieblich und domänensprachlich entscheidend: produktive Authentifizierung ohne Dev-Zugänge, belastbare Datenpersistenz, nachvollziehbare Dokumentannahme, verbindliche Mutationssemantik, Netzwerktopologie-Prüfung, produktive Mailzustellung, Backup/Restore, Monitoring sowie Legal-, Datenschutz- und Partnerfreigabe.

## Solution

Das Portal wird als eigenständige Webanwendung für Teilnehmer, LEG-Vertreter, Gemeinde/EW-Administratoren und Plattform-Administratoren gebaut. Es unterstützt Einladung, kontrollierten Self-Service, E-Mail-Verifikation, risikobasierte Identitätsprüfung, versionierte Dokumente, Clickwrap-Einwilligungen, direkte Kontaktänderungen und meldepflichtige Mutationen.

Der Go-live erfolgt zweistufig. Phase 1 ist ein verbindlicher, kontrollierter Pilot mit flexibler Testgruppe und allen Kernrollen. Pilotnutzer können echte Daten verwenden und echte Prozesse auslösen, aber der Zugang bleibt per Allowlist oder Einladung begrenzt. Nicht freigegebene E-Mail-Adressen werden als Interessensmeldungen vorgemerkt. Phase 2 öffnet den Self-Service öffentlich für Bürgerinnen und Bürger im SunTerra-LEG-Gebiet.

Der produktive Markenauftritt lautet SunTerra LEG. Basadingen-Schlattingen und Gemeinde/EW werden dort genannt, wo Gebiet, Zuständigkeit, Netzwerktopologie oder Partnerverantwortung konkret werden.

Der öffentliche Teilnahme-Start fragt nur die E-Mail-Adresse ab. Erst nach E-Mail-Verifikation ergänzt der Teilnehmer im geschützten Onboarding seinen Anzeigenamen und setzt ein Passwort. Für verbindliche Teilnahme braucht es eine LEG-Prüfung der Teilnahmeberechtigung. Diese Prüfung berücksichtigt insbesondere die Netzwerktopologie: Der Messpunkt muss im abgedeckten angeschlossenen Raum liegen. Im Pilot erfolgt diese Prüfung manuell ausserhalb des Portals und wird im Portal dokumentiert. Vor dem öffentlichen Rollout soll eine importierbare Messpunkt-/Adressliste eine Vorprüfung ermöglichen; manuelle Ausnahmebestätigung bleibt bei Listenunvollständigkeit möglich.

Teilnehmer akzeptieren vor verbindlicher Nutzung versionierte Dokumente: Datenschutzhinweis, Portal-Nutzungsbedingungen und LEG-Vertrag. ConsentEvidence speichert Hash, Zeitpunkt, Dokumentversion und Kontext.

Die Mutationssemantik wird geschärft. Ein `entry` braucht konstitutive LEG-Freigabe. Alle anderen Mutationstypen gelten bei Einreichung als gültige Teilnehmererklärung, sofern sie nicht fehlerhaft oder unvollständig sind. Vor Paketierung führt die LEG für Nicht-`entry`-Mutationen einen formalen Paketbereit-Check durch. Das ist keine fachliche Wirksamkeitsfreigabe, sondern eine Vollständigkeits- und Plausibilitätsprüfung. Fehlerhafte oder unvollständige Mutationen gehen auf Klärung oder Stopp mit Begründung; Teilnehmer reichen korrigiert neu ein. Gemeinde/EW-Status wie Rückfrage oder technisch nicht möglich erzeugt Folgeaufgaben, ändert Mutation oder Mitgliedschaft aber nicht automatisch.

Das Portal bleibt in v1 bewusst fokussiert: keine Abrechnung, kein Inkasso, kein Settlement, keine Bankdaten, keine 15-Minuten-Messwerte, keine freie Dateiablage und keine automatisierte Gemeinde-/EW-Schnittstelle.

Für den verbindlichen Pilot sind produktive Betriebsgrundlagen erforderlich: DB-backed Runtime ohne produktive Abhängigkeit von globalem In-Memory-State, Dev-Auth in Production gesperrt, produktive CORS-Konfiguration, produktive SMTP-Mailzustellung für Auth-/Verifikationskommunikation, Bootstrap-CLI für erste Admins, TOTP-MFA für Admin-Rollen, tägliche verschlüsselte Offsite-Backups mit Restore-Test, Health/Readiness und Alerts. Privates Hosting ist für den Pilot erlaubt; vor öffentlichem Rollout entscheidet ein Betriebsgate, ob privat weiterbetrieben oder auf Managed Hosting gewechselt wird.

## User Stories

1. Als Besucher möchte ich zuerst eine öffentliche SunTerra-LEG-Seite sehen, damit ich verstehe, was die SunTerra LEG ist und wie Teilnahme grundsätzlich funktioniert.
2. Als interessierter Bürger möchte ich die Teilnahme mit meiner E-Mail-Adresse starten können, damit ich ohne Vorabkontakt Interesse anmelden kann.
3. Als Pilotinteressent ausserhalb der Allowlist möchte ich als Interessent vorgemerkt werden, damit ich später kontaktiert oder freigegeben werden kann.
4. Als Pilotteilnehmer möchte ich über Einladung oder Allowlist registrieren können, damit der verbindliche Pilot kontrolliert bleibt.
5. Als Teilnehmer möchte ich meine E-Mail-Adresse produktiv verifizieren können, damit Authentifizierungs- und Verifikationsnachrichten mich erreichen.
6. Als Teilnehmer möchte ich nach E-Mail-Verifikation Anzeigename und Passwort setzen, damit ich mein geschütztes Konto abschliessen kann.
7. Als Teilnehmer möchte ich mich über einen gemeinsamen Login anmelden, damit ich nicht zwischen Rollenportalen unterscheiden muss.
8. Als Teilnehmer möchte ich meine aktuelle Mitgliedschaft sehen, damit ich weiss, wie ich in der SunTerra LEG geführt werde.
9. Als Teilnehmer möchte ich erkennen, ob meine Teilnahmeberechtigung noch geprüft wird, damit ich den Prozessstatus verstehe.
10. Als Teilnehmer möchte ich sehen, dass die LEG meine Teilnahmeberechtigung anhand der Netzwerktopologie prüft, damit klar ist, warum Messpunktdaten erforderlich sind.
11. Als LEG-Vertreter möchte ich eine Teilnahmeberechtigung manuell prüfen und begründen können, damit der Pilot ohne importierte Topologieliste starten kann.
12. Als LEG-Vertreter möchte ich später eine Messpunkt-/Adressliste importieren können, damit öffentliche Registrierungen automatisch vorgeprüft werden.
13. Als LEG-Vertreter möchte ich bei Listenunvollständigkeit manuell eine Ausnahme bestätigen können, damit berechtigte Teilnehmer nicht blockiert werden.
14. Als Teilnehmer möchte ich den Datenschutzhinweis akzeptieren, damit meine Personendatenverarbeitung transparent nachgewiesen wird.
15. Als Teilnehmer möchte ich die Portal-Nutzungsbedingungen akzeptieren, damit die Regeln des digitalen Kanals klar sind.
16. Als Teilnehmer möchte ich den LEG-Vertrag akzeptieren, damit fachliche Teilnahme- und Mutationsregeln verbindlich dokumentiert sind.
17. Als Prüfer möchte ich ConsentEvidence mit Dokumentversion, Hash, Zeitpunkt und Kontext sehen können, damit Einwilligungen beweisbar sind.
18. Als Teilnehmer möchte ich Kontaktkanäle direkt ändern können, damit alltägliche Erreichbarkeitsdaten ohne Mutationsprozess aktuell bleiben.
19. Als Teilnehmer möchte ich meldepflichtige Adressänderungen einreichen können, damit Gemeinde und EW korrekt informiert werden.
20. Als Teilnehmer möchte ich Messpunktänderungen einreichen können, damit der relevante Bezugspunkt geprüft und gemeldet wird.
21. Als Teilnehmer möchte ich Rollenänderungen einreichen können, damit Eigentümer-, Mieter- oder andere relevante Rollenwechsel nachvollziehbar verarbeitet werden.
22. Als Teilnehmer möchte ich Änderungen an Erzeugungsanlagen einreichen können, damit technische Erzeugungsdaten aktuell bleiben.
23. Als Teilnehmer möchte ich Eintritte beantragen können, damit neue Teilnahme kontrolliert durch die LEG freigegeben wird.
24. Als Teilnehmer möchte ich Austritte einreichen können, damit mein Austritt mit Frist und Wirksamkeitsdatum sauber geplant wird.
25. Als Teilnehmer möchte ich Sondermutationen für Auszug, Todesfall, Eigentümer-/Mieterwechsel, Messpunktfehler und Gemeinde/EW-Korrektur einreichen können, damit Ausnahmefälle dokumentiert werden.
26. Als Teilnehmer möchte ich Wirksamkeitsdaten anhand des LEG-Vertrags sehen, damit ich verstehe, ab wann eine eingereichte Änderung für Abrechnung oder Register relevant wird.
27. Als Teilnehmer möchte ich bei Fehlern oder Unvollständigkeit eine Klärung mit Begründung sehen, damit ich korrigiert neu einreichen kann.
28. Als Teilnehmer möchte ich den Status meiner eigenen Mutationen sehen, damit ich weiss, ob sie eingereicht, paketbereit, in Klärung, gestoppt oder paketiert sind.
29. Als LEG-Vertreter möchte ich Eintritte konstitutiv freigeben oder stoppen können, damit neue Teilnahme fachlich kontrolliert wird.
30. Als LEG-Vertreter möchte ich Nicht-`entry`-Mutationen formal auf Paketbereitschaft prüfen, damit gültige Teilnehmererklärungen vollständig und plausibel gemeldet werden.
31. Als LEG-Vertreter möchte ich fehlerhafte oder unvollständige Mutationen mit Grund auf Klärung oder Stopp setzen, damit der Nachweis vollständig bleibt.
32. Als LEG-Vertreter möchte ich paketbereite Mutationen für ein kommendes Quartal sehen, damit die Meldung an Gemeinde/EW vollständig erfolgt.
33. Als LEG-Vertreter möchte ich ein unveränderliches MutationPackage erzeugen, damit gemeldete Daten später nicht stillschweigend verändert werden.
34. Als LEG-Vertreter möchte ich Paketartefakte als CSV, PDF und JSON erhalten, damit unterschiedliche Prüf- und Ablagebedürfnisse abgedeckt sind.
35. Als LEG-Vertreter möchte ich den Hash eines Pakets sehen, damit Integrität und Nachvollziehbarkeit gesichert sind.
36. Als LEG-Vertreter möchte ich eine Statushistorie des Pakets sehen, damit Reaktionen der Partner nachvollziehbar bleiben.
37. Als LEG-Vertreter möchte ich Rückfragen von Gemeinde/EW als Folgeaufgaben sehen, damit ich fehlende oder unklare Informationen gezielt klären kann.
38. Als LEG-Vertreter möchte ich erkennen, wenn eine Meldung technisch nicht möglich ist, damit ich den Fall mit Teilnehmern und Partnern weiterbehandeln kann.
39. Als Gemeinde/EW-Administrator möchte ich ein minimales Mitgliederregister sehen, damit Gemeinde/EW nur die meldepflichtigen Registerdaten erhalten.
40. Als Gemeinde/EW-Administrator möchte ich neue MutationPackages in einer Inbox sehen, damit eingehende Meldungen nicht in E-Mails oder manuellen Ablagen verloren gehen.
41. Als Gemeinde/EW-Administrator möchte ich ein Paket als empfangen, in Prüfung oder verarbeitet markieren, damit die LEG den Bearbeitungsstand sieht.
42. Als Gemeinde/EW-Administrator möchte ich Rückfragen mit Begründung erfassen, damit die LEG gezielt nacharbeiten kann.
43. Als Gemeinde/EW-Administrator möchte ich technische Nicht-Möglichkeit mit Begründung erfassen, damit Ablehnungen auditierbar und nicht informell bleiben.
44. Als Gemeinde/EW-Administrator möchte ich keine internen Prüfnotizen, Einwilligungen oder nicht meldepflichtigen Daten sehen, damit Datensparsamkeit eingehalten wird.
45. Als Plattform-Administrator möchte ich den ersten produktiven Adminzugang über einen Bootstrap-Prozess erzeugen können, damit keine Default-Accounts in Production nötig sind.
46. Als Plattform-Administrator möchte ich interne LEG- und Plattform-Nutzer anlegen und sperren können, damit administrative Zugänge kontrolliert entstehen.
47. Als LEG-Vertreter möchte ich Gemeinde/EW-Admins über einen expliziten Partnerzugangs-Flow anlegen, damit Partnerzugriff bewusst vergeben wird.
48. Als Admin-Nutzer möchte ich TOTP-MFA einrichten und beim Login verwenden, damit administrative Zugänge vor dem Pilot stärker geschützt sind.
49. Als Nutzer möchte ich mein Passwort vor dem öffentlichen Rollout per E-Mail zurücksetzen können, damit Support nicht alle Resets manuell bearbeiten muss.
50. Als Betreiber möchte ich Dev-Token in Production gesperrt wissen, damit keine Entwicklungszugänge produktiv funktionieren.
51. Als Betreiber möchte ich CORS aus `SUNTERRA_ALLOWED_ORIGINS` konfigurieren, damit nur erlaubte Frontend-Ursprünge produktiv zugreifen.
52. Als Betreiber möchte ich produktive SMTP-Mailzustellung konfigurieren, damit Einladungen, Verifikation und Passwortreset nicht über Dev-Hilfen laufen.
53. Als Betreiber möchte ich die Runtime vollständig DB-backed betreiben, damit verbindliche Daten App-Neustarts überleben und nicht aus globalem Runtime-State stammen.
54. Als Betreiber möchte ich tägliche verschlüsselte Offsite-Backups mit Restore-Test haben, damit Datenverlustszenarien vor Pilotstart geübt sind.
55. Als Betreiber möchte ich Health/Readiness und Alerts haben, damit Ausfälle oder kritische Fehler im Pilot sichtbar werden.
56. Als Betreiber möchte ich In-App-Feedback aus dem Pilot sammeln, damit Go/No-Go-Bewertungen nachvollziehbar sind.
57. Als Betreiber möchte ich den öffentlichen Rollout erst nach einem verarbeiteten echten MutationPackage und 14 stabilen Tagen öffnen, damit der Prozess belastbar erprobt ist.
58. Als Betreiber möchte ich vor öffentlichem Rollout entscheiden, ob privates Hosting genügt oder Managed Hosting nötig ist, damit Betriebsrisiken bewusst getragen werden.
59. Als Betreiber möchte ich keine Status- oder Frist-E-Mails in v1 versenden, damit Kommunikation portal-first bleibt.
60. Als Teilnehmer möchte ich erkennen, dass Gemeinde oder EW für Abrechnung und Inkasso zuständig sind, damit ich das Portal nicht als Rechnungsportal missverstehe.
61. Als Teilnehmer möchte ich keine fremden Teilnehmerdaten sehen können, damit Datenschutz und Rollenabgrenzung gewahrt bleiben.
62. Als Entwickler möchte ich öffentliche DTOs rollenbasiert minimal halten, damit API und UI Datenschutz und Zuständigkeit ausdrücken.
63. Als Entwickler möchte ich OpenAPI-generierte Types im Frontend verwenden, damit Backend- und Frontend-Verträge nicht auseinanderlaufen.
64. Als Prüfer möchte ich AuditEvents für relevante Aktionen sehen, damit Änderungen und Entscheidungen nachvollziehbar bleiben.
65. Als Nutzer möchte ich die SunTerra-Oberfläche als ruhige, präzise Infrastrukturplattform erleben, damit öffentliche und geschützte Bereiche als ein kohärentes Produkt wirken.

## Implementation Decisions

- Das Portal wird als eigenständiges Neubau-Projekt umgesetzt. Der bestehende SunTerra-LEG-Code darf als fachliche und technische Musterquelle dienen, wird aber keine Runtime-Abhängigkeit.
- Der technische Zielstack bleibt FastAPI, SQLModel, Alembic und Postgres im Backend sowie React, Vite und TypeScript im Frontend.
- Die produktive Marke ist SunTerra LEG. Basadingen-Schlattingen wird dort genannt, wo Gebiet, Zuständigkeit, Netzwerktopologie oder Gemeinde/EW-Rolle konkret werden.
- Die Rollen bleiben `participant`, `leg_admin`, `partner_admin` und `platform_admin`. `partner_admin` ist die kombinierte Gemeinde/EW-Rolle.
- Der Pilot ist verbindlich und umfasst alle Kernrollen. Die Pilotgruppe ist flexibel gross; entscheidend ist ein vollständiger End-to-End-Fall.
- Pilotzugang wird über Allowlist oder Einladung begrenzt. Nicht freigegebene E-Mails werden als Interessensmeldungen gespeichert, aber nicht zu verbindlichen Konten.
- Es gibt keinen initialen Mitgliederimport. Teilnehmer entstehen über Registrierung und LEG-Prüfung.
- Öffentliche Registrierung braucht eine Teilnahmeberechtigungsprüfung durch die LEG. Die Prüfung bewertet insbesondere, ob der Messpunkt gemäss Netzwerktopologie im abgedeckten angeschlossenen Raum liegt.
- Im Pilot erfolgt die Netzwerktopologie-Prüfung manuell und wird im Portal mit Ergebnis und Begründung dokumentiert.
- Vor öffentlichem Rollout unterstützt das Portal eine importierte Messpunkt-/Adressliste zur Vorprüfung. Manuelle Ausnahmebestätigung bleibt möglich.
- Vor verbindlicher Nutzung akzeptieren Teilnehmer drei Dokumentversionen: Datenschutzhinweis, Portal-Nutzungsbedingungen und LEG-Vertrag.
- E-Mail-Verifikation und Auth-Kommunikation laufen produktiv über konfigurierbare SMTP-Zustellung.
- Das Login nutzt E-Mail und Passwort mit signierten JWT-Zugriffstokens. Refresh-Tokens bleiben ausserhalb von v1.
- Passwort-zurücksetzen per E-Mail ist vor öffentlichem Rollout in scope.
- Admin-Rollen müssen TOTP-MFA schon vor dem verbindlichen Pilot einrichten und verwenden. Teilnehmer-MFA bleibt ausserhalb von v1.
- Dev-Token und Demo-Rollen bleiben nur Entwicklungswerkzeug und sind in Production hard-disabled.
- Der erste produktive Admin wird über eine Bootstrap-CLI erzeugt. Es gibt keine produktiven Default-Accounts.
- `SUNTERRA_ALLOWED_ORIGINS` steuert produktive CORS-Origin-Konfiguration.
- Alle verbindlichen Daten werden DB-backed betrieben. Produktive Requests dürfen nicht von globalem In-Memory-State oder Full-State-Snapshot-Reloads als Source of Truth abhängen.
- `entry` ist die einzige Mutation mit konstitutiver LEG-Freigabe.
- Alle anderen Mutationstypen gelten bei Einreichung als gültige Teilnehmererklärung, sofern sie nicht fehlerhaft oder unvollständig sind.
- Nicht-`entry`-Mutationen brauchen vor Paketierung einen formalen Paketbereit-Check durch die LEG. Dieser Check bestätigt Vollständigkeit und Plausibilität, nicht fachliche Wirksamkeit.
- Fehlerhafte oder unvollständige Mutationen gehen auf Klärung oder Stopp mit Begründung; Teilnehmer reichen korrigiert neu ein.
- Wirksamkeitsdaten folgen den im LEG-Vertrag definierten Fristen.
- Partnerstatus ändert Mutation oder Mitgliedschaft nicht automatisch. Rückfrage und technische Nicht-Möglichkeit erzeugen Folgeaufgaben.
- MutationPackages bleiben unveränderliche Artefakte mit CSV, PDF, JSON, Hash, Quartal, Wirksamkeitsdaten, Actor und Statushistorie.
- Privates Hosting ist für den Pilot erlaubt. Vor öffentlichem Rollout entscheidet ein Betriebsgate, ob privat weiterbetrieben oder auf Managed Hosting gewechselt wird.
- Pilotbetrieb braucht TLS/Domain, Postgres, SMTP, Secret-Handling, tägliche verschlüsselte Offsite-Backups, Restore-Test, Health/Readiness und Alerts.
- Der öffentliche Rollout ist erst erlaubt, wenn mindestens ein echtes MutationPackage verarbeitet wurde und danach 14 Tage stabiler Betrieb ohne kritische offene Befunde verstrichen sind.
- In-App-Feedback wird im Pilot strukturiert gesammelt und in eine Reviewliste für Go/No-Go überführt.
- Legal-, Datenschutz- und Gemeinde/EW-Prozessfreigabe müssen vor dem verbindlichen Pilot schriftlich vorliegen.
- Kommunikation bleibt portal-first. v1 versendet keine Status- oder Frist-E-Mails, sondern nur notwendige Auth- und Verifikationskommunikation.
- Es gibt weiterhin keine automatische Gemeinde-/EW-Schnittstelle in v1.
- Es gibt keine Abrechnung, kein Inkasso, kein Settlement, keine Bankdaten, keine Rechnungen im Portal und keine 15-Minuten-Messwerte.

## Testing Decisions

- Tests sollen externes Verhalten prüfen und nicht Implementierungsdetails festnageln.
- Der höchste sinnvolle Test-Seam bleibt der API-/Workflow-Seam: Registrierung, Verifikation, Dokumentannahme, Teilnahmeberechtigungsprüfung, Mutation, LEG-Prüfung, Paketbildung, Partnerstatus und Feedback werden als Rollenflüsse getestet.
- Bestehende Backend- und Frontend-Workflowtests bleiben Prior Art. Neue Tests orientieren sich an den vorhandenen Auth-, Onboarding-, Mutation-, Partner-, Persistent-State- und Production-Readiness-Tests.
- Backend-Tests prüfen Dev-Auth-Sperre in Production, produktive CORS-Konfiguration, SMTP-Zustellung, Bootstrap-Admin, TOTP-MFA, Passwortreset, Allowlist, Interessensmeldung, Netzwerktopologie-Prüfung, Listen-Vorprüfung, manuelle Ausnahme, Mutationsstatus, Paketbereit-Check, Partner-Folgeaufgaben und DB-backed Persistenz über App-Neustart.
- Frontend-Smokes prüfen Pilotmodus, öffentliche Registrierung, Interessensmeldung, Admin-MFA, Dokumentannahme, Teilnahmeberechtigungsprüfung, Mutationseinreichung, Paketbereit-Check, Partner-Inbox, In-App-Feedback und deutschsprachige UI.
- Migration- und Deployment-Tests umfassen frische Migration, Backup/Restore-Smoke, Secret-Konfigurationschecks, produktionsnahe Startguards, Health/Readiness und Alert-Probe.
- API-Type-Checks bleiben Gate, damit Backend- und Frontend-Verträge nicht auseinanderlaufen.
- Public Rollout Gate wird als Checkliste testbar gemacht: ein echtes verarbeitetes MutationPackage, 14 stabile Tage, keine kritischen offenen Befunde, bestandener Restore-Test, aktive Alerts, schriftliche Freigaben.

## Out of Scope

- Abrechnung
- Inkasso
- Settlement
- Bankdaten
- Rechnungen im Portal
- 15-Minuten-Messwerte
- Energiedatenverarbeitung über den Mutationsbedarf hinaus
- Automatische Gemeinde-/EW-Schnittstelle in v1
- E-ID- oder SwissID-Produktintegration in v1
- Status- oder Frist-E-Mails in v1
- Refresh-Token in v1
- Teilnehmer-MFA in v1
- Finale Logo-Entscheidung oder finale Hero-Visualisierung für die öffentliche Landing-Page
- Konkrete Spar-, Ertrags- oder Preisversprechen auf der öffentlichen Landing-Page
- Freie Dateiablage
- Mehrsprachigkeit in v1
- Mobile App
- Vollständige Multi-LEG-Betriebsoberfläche über den ersten SunTerra-LEG-Kontext hinaus
- Automatischer initialer Mitgliederimport

## Further Notes

- Quellen aus dem bestehenden Plan:
  - VSE Branchenempfehlung LEG: https://www.strom.ch/de/media/15458/download
  - Fedlex AS 2025 139: https://www.fedlex.admin.ch/eli/oc/2025/139/de
- `CONTEXT.md` hält die kanonischen Begriffe SunTerra LEG, LEG-Vertrag, Mutation, Eintritt, Paketbereit-Check, Netzwerktopologie, Interessensmeldung und Partnerstatus fest.
- ADRs dokumentieren die überraschenden Entscheidungen: verbindlicher Pilot mit privatem Hosting und Public-Rollout-Gate, sowie Mutationsbindung bei Einreichung ausser `entry`.
