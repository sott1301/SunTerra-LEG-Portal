# PRD: SunTerra LEG Mitglieder- und Mutationsportal

## Problem Statement

Die SunTerra LEG Basadingen braucht ein eigenständiges Portal, in dem Teilnehmer ihre Mitgliedschaft, Dokumente, Einwilligungen und meldepflichtigen Änderungen nachvollziehbar verwalten können. LEG-Vertreter müssen Mutationen prüfen, freigeben und fristgerecht als unveränderliche Pakete an Gemeinde und Elektrizitätswerk melden können. Die kombinierte Gemeinde/EW-Rolle braucht ein minimales, datensparsames Mitgliederregister und eine klare Inbox für Mutationspakete.

Heute ist der fachliche Bedarf klar, aber das Portal soll bewusst als Neubau entstehen und nicht als Laufzeitabhängigkeit des bestehenden SunTerra-LEG-Pilotprojekts. Das neue System muss daher die rechtlich relevanten Mutationsprozesse, Fristen, Nachweise, Rollen und Datenbegrenzungen von Anfang an sauber abbilden.

## Solution

Das Portal wird als eigenständige Webanwendung für Teilnehmer, LEG-Vertreter, Partner-Administratoren und Plattform-Administratoren gebaut. Es unterstützt Einladung und Self-Service-Onboarding, E-Mail-Verifikation, risikobasierte Identitätsprüfung, versionierte Dokumente, Clickwrap-Einwilligungen, direkte Kontaktänderungen und meldepflichtige Mutationen.

Meldepflichtige Änderungen werden als MutationRequests erfasst, durch LEG-Vertreter geprüft und freigegeben und danach zu unveränderlichen MutationPackages zusammengefasst. Diese Pakete enthalten CSV-, PDF- und JSON-Artefakte mit Schema-Version, Paket-ID, LEG-ID, Quartal, Wirksamkeitsdatum, Hash und Erzeugungszeitpunkt. Partner-Administratoren können Pakete empfangen, prüfen, verarbeiten, Rückfragen stellen oder technische Nicht-Möglichkeit begründen, ohne Zugriff auf nicht notwendige interne Daten zu erhalten.

Das Portal bleibt in v1 bewusst fokussiert: keine Abrechnung, kein Inkasso, kein Settlement, keine Bankdaten, keine 15-Minuten-Messwerte, keine freie Dateiablage und keine automatisierte Gemeinde-/EW-Schnittstelle.

Die Portaloberfläche wird in einen öffentlichen und einen geschützten Teil getrennt. Alle Besucher landen zuerst auf einer schlanken öffentlichen SunTerra-LEG-Seite, die kurz erklärt, was eine LEG ist, wie Teilnahme grundsätzlich funktioniert und wie der Teilnahmeprozess startet. Bereits registrierte Teilnehmer, LEG-Vertreter, Gemeinde/EW-Administratoren und Plattform-Administratoren melden sich über einen gemeinsamen Login an und werden danach direkt in ihren jeweiligen Rollenbereich geführt.

Der öffentliche Teilnahme-Start fragt nur die E-Mail-Adresse ab. Erst nach E-Mail-Verifikation ergänzt der Teilnehmer im geschützten Onboarding seinen Anzeigenamen und setzt ein Passwort. Das Portal nutzt damit ein echtes E-Mail-/Passwort-Login mit signierten JWT-Zugriffstokens. Öffentliche Einladungscodes bleiben ein optionales Admin-/Deep-Link-Werkzeug, werden aber nicht als primärer öffentlicher Onboarding-Weg präsentiert.

Die visuelle Richtung folgt dem etablierten SunTerra-LEG-Design `Swiss Energy Infrastructure` / `Operator`: neutraler Near-White-Hintergrund, SunTerra-Grün als Primärfarbe, Solar-Gold nur als gezielter Akzent, IBM-Plex-Typografie, flache Panels mit Hairline-Rahmen und sichtbare Trust-/Sicherheits-/Statusmuster. Die öffentliche Seite darf einladender und luftiger wirken als die Arbeitsbereiche, bleibt aber Teil derselben SunTerra-Produktfamilie. Logo und großes Hero-Visual werden in diesem Slice bewusst noch nicht final entschieden.

## User Stories

1. Als Teilnehmer möchte ich mich über eine Einladung registrieren, damit ich sicher dem richtigen LEG-Kontext zugeordnet werde.
2. Als Teilnehmer möchte ich mich auch über einen öffentlichen Self-Service-Prozess melden können, damit ich ohne manuelle Vorab-Einladung starten kann.
3. Als Teilnehmer möchte ich meine E-Mail-Adresse verifizieren, damit das Portal sicherstellen kann, dass Authentifizierungs- und Verifikationsnachrichten mich erreichen.
4. Als Teilnehmer möchte ich meine Identität risikobasiert bestätigen, damit meldepflichtige Änderungen verlässlich einer Person zugeordnet werden können.
5. Als Teilnehmer möchte ich sehen, welche Identitätsprüfung für meinen aktuellen Vorgang erforderlich ist, damit ich verstehe, warum ein Schritt nötig ist.
6. Als Teilnehmer möchte ich die jeweils gültigen Dokumentversionen sehen, damit ich weiss, welchen Bedingungen ich zustimme.
7. Als Teilnehmer möchte ich Einwilligungen per Clickwrap abgeben, damit meine Zustimmung mit Zeitpunkt, Dokumentversion, Hash und Kontext nachweisbar ist.
8. Als Teilnehmer möchte ich meine abgegebenen Einwilligungen einsehen, damit ich nachvollziehen kann, was ich bestätigt habe.
9. Als Teilnehmer möchte ich meine aktuellen Mitgliedschaftsdaten sehen, damit ich weiss, wie ich in der LEG geführt werde.
10. Als Teilnehmer möchte ich meine Kontaktkanäle direkt ändern können, damit alltägliche Erreichbarkeitsdaten ohne Mutationsprozess aktuell bleiben.
11. Als Teilnehmer möchte ich meldepflichtige Adressänderungen als Mutation beantragen, damit Gemeinde und EW korrekt informiert werden können.
12. Als Teilnehmer möchte ich Messpunktänderungen als Mutation beantragen, damit der fachlich relevante Bezugspunkt geprüft und gemeldet wird.
13. Als Teilnehmer möchte ich Rollenänderungen als Mutation beantragen, damit Eigentümer-, Mieter- oder andere relevante Rollenwechsel nachvollziehbar verarbeitet werden.
14. Als Teilnehmer möchte ich Änderungen an Erzeugungsanlagen als Mutation beantragen, damit technische Erzeugungsdaten aktuell bleiben.
15. Als Teilnehmer möchte ich reguläre Eintritte mit der passenden Frist zum Quartalsende beantragen, damit mein Beitritt rechtzeitig geprüft werden kann.
16. Als Teilnehmer möchte ich reguläre Austritte mit der passenden Frist zum Quartalsende beantragen, damit mein Austritt sauber geplant wird.
17. Als Teilnehmer möchte ich Sondermutationen für Auszug beantragen können, damit dringende fachliche Fälle nicht künstlich bis zum regulären Quartalsprozess warten müssen.
18. Als Teilnehmer möchte ich Sondermutationen für Todesfall melden können, damit die Mitgliedschaft in einem Ausnahmefall korrekt behandelt wird.
19. Als Teilnehmer möchte ich Sondermutationen für Eigentümer- oder Mieterwechsel beantragen können, damit reale Nutzungs- und Verantwortlichkeitswechsel abgebildet werden.
20. Als Teilnehmer möchte ich Sondermutationen für Messpunktfehler beantragen können, damit technische Korrekturen nachvollziehbar möglich sind.
21. Als Teilnehmer möchte ich den Status meiner eigenen Mutationen sehen, damit ich weiss, ob sie eingereicht, in Prüfung, freigegeben, paketiert oder beantwortet sind.
22. Als Teilnehmer möchte ich die Wirksamkeitsdaten meiner Mutationen sehen, damit ich verstehe, ab wann eine Änderung gilt.
23. Als Teilnehmer möchte ich erkennen, dass Gemeinde oder EW für Abrechnung und Inkasso zuständig sind, damit ich das Portal nicht als Rechnungsportal missverstehe.
24. Als Teilnehmer möchte ich keine fremden Teilnehmerdaten sehen können, damit Datenschutz und Rollenabgrenzung gewahrt bleiben.
25. Als LEG-Vertreter möchte ich Teilnehmer und Mitgliedschaften verwalten, damit das Mitgliederregister fachlich korrekt bleibt.
26. Als LEG-Vertreter möchte ich eingereichte MutationRequests prüfen, damit nur fachlich plausible und vollständige Änderungen weiterlaufen.
27. Als LEG-Vertreter möchte ich Mutationen freigeben oder zurückweisen, damit die LEG die Mitgliedschaft weiterhin selbst entscheidet.
28. Als LEG-Vertreter möchte ich Fristen automatisch berechnen lassen, damit reguläre Eintritte, Austritte und Mutationen zum richtigen Quartal verarbeitet werden.
29. Als LEG-Vertreter möchte ich Sondermutationen mit Begründung behandeln, damit Ausnahmefälle dokumentiert und prüfbar bleiben.
30. Als LEG-Vertreter möchte ich sehen, welche Mutationen für ein kommendes Quartal paketiert werden können, damit die Meldung an Gemeinde/EW vollständig erfolgt.
31. Als LEG-Vertreter möchte ich ein unveränderliches MutationPackage erzeugen, damit gemeldete Daten später nicht stillschweigend verändert werden.
32. Als LEG-Vertreter möchte ich Paketartefakte als CSV, PDF und JSON erhalten, damit unterschiedliche Prüf- und Ablagebedürfnisse abgedeckt sind.
33. Als LEG-Vertreter möchte ich den Hash eines Pakets sehen, damit Integrität und Nachvollziehbarkeit gesichert sind.
34. Als LEG-Vertreter möchte ich eine Statushistorie des Pakets sehen, damit Reaktionen der Partner nachvollziehbar bleiben.
35. Als LEG-Vertreter möchte ich Rückfragen von Gemeinde/EW sehen, damit ich fehlende oder unklare Informationen gezielt klären kann.
36. Als LEG-Vertreter möchte ich erkennen, wenn eine Mutation technisch nicht möglich ist, damit ich den Fall mit Teilnehmern und Partnern weiterbehandeln kann.
37. Als Partner-Administrator möchte ich ein minimales Mitgliederregister sehen, damit Gemeinde/EW nur die meldepflichtigen Registerdaten erhalten.
38. Als Partner-Administrator möchte ich neue MutationPackages in einer Inbox sehen, damit eingehende Meldungen nicht in E-Mails oder manuellen Ablagen verloren gehen.
39. Als Partner-Administrator möchte ich ein Paket als empfangen markieren, damit die LEG weiss, dass die Meldung angekommen ist.
40. Als Partner-Administrator möchte ich ein Paket als in Prüfung markieren, damit der Bearbeitungsstand sichtbar ist.
41. Als Partner-Administrator möchte ich ein Paket als verarbeitet markieren, damit der Mutationsprozess abgeschlossen werden kann.
42. Als Partner-Administrator möchte ich eine Rückfrage mit Begründung erfassen, damit die LEG gezielt nacharbeiten kann.
43. Als Partner-Administrator möchte ich technische Nicht-Möglichkeit mit Begründung erfassen, damit Ablehnungen auditierbar und nicht informell bleiben.
44. Als Partner-Administrator möchte ich keine internen Prüfnotizen, Einwilligungen oder nicht meldepflichtigen Daten sehen, damit Datensparsamkeit eingehalten wird.
45. Als Plattform-Administrator möchte ich LEG-Stammdaten und Gemeindezuordnung verwalten, damit Basadingen zuerst unterstützt wird und das Modell später erweiterbar bleibt.
46. Als Plattform-Administrator möchte ich Dokumentversionen veröffentlichen können, damit neue Bedingungen oder Hinweise kontrolliert ausgerollt werden.
47. Als Plattform-Administrator möchte ich Zugriffsschutz und Aufbewahrungsstatus von Dateien kontrollieren, damit Dokumente zweckgebunden und regelkonform gespeichert werden.
48. Als Plattform-Administrator möchte ich AuditEvents für relevante Aktionen haben, damit Änderungen und Entscheidungen nachvollziehbar bleiben.
49. Als Prüfer möchte ich ConsentEvidence mit Hash, Zeitpunkt, Dokumentversion und Kontext sehen können, damit Einwilligungen beweisbar sind.
50. Als Prüfer möchte ich IdentityVerification-Level nachvollziehen können, damit risikobasierte Freigaben erklärbar sind.
51. Als Betreiber möchte ich das Portal deutschsprachig betreiben, damit die v1 klar auf Basadingen und die Zielnutzer fokussiert bleibt.
52. Als Betreiber möchte ich keine Status- oder Frist-E-Mails in v1 versenden, damit Kommunikation portal-first bleibt und nur notwendige Auth-/Verifikationskommunikation ausgelöst wird.
53. Als Betreiber möchte ich eine produktionsnahe Konfiguration mit Startguards, damit Fehlkonfigurationen früh erkannt werden.
54. Als Betreiber möchte ich Backup/Restore-Smokes haben, damit ein Datenverlustszenario vor Produktivbetrieb geübt ist.
55. Als Entwickler möchte ich öffentliche DTOs rollenbasiert minimal halten, damit die API Datenschutz und Zuständigkeit ausdrückt.
56. Als Entwickler möchte ich OpenAPI-generierte Types im Frontend verwenden, damit Backend- und Frontend-Verträge nicht auseinanderlaufen.
57. Als Besucher möchte ich zuerst eine öffentliche SunTerra-LEG-Landing-Page sehen, damit ich verstehe, was eine LEG ist und wie ich teilnehmen kann.
58. Als interessierter Teilnehmer möchte ich die Teilnahme mit meiner E-Mail-Adresse starten können, damit ich ohne Einladung beginnen kann und keine unnötigen Personendaten vor der Verifikation angeben muss.
59. Als interessierter Teilnehmer möchte ich nach der E-Mail-Verifikation meinen Anzeigenamen und mein Passwort setzen können, damit ich mein geschütztes Portal-Konto abschliessen kann.
60. Als registrierter Nutzer möchte ich mich über einen gemeinsamen Login anmelden, damit ich nicht zwischen Teilnehmer-, LEG-, Gemeinde/EW- oder Plattform-Login unterscheiden muss.
61. Als angemeldeter Teilnehmer möchte ich direkt in `Mein Portal` landen, damit ich meine Mitgliedschaft, Dokumente, Einwilligungen und Mutationen ohne Umweg verwalten kann.
62. Als angemeldeter LEG-Vertreter möchte ich direkt in `LEG-Verwaltung` landen, damit ich Mutationen, Freigaben, Dokumentversionen und Partnerzugänge bearbeiten kann.
63. Als angemeldeter Gemeinde/EW-Administrator möchte ich direkt in `Gemeinde/EW` landen, damit ich Aufgaben, Pakete und das minimale Mitgliederregister bearbeiten kann.
64. Als angemeldeter Plattform-Administrator möchte ich direkt in `Benutzerverwaltung` landen, damit ich Login-Konten und Zugriff steuern kann.
65. Als Plattform-Administrator möchte ich alle bestehenden Login-Konten sehen können, damit ich Zugriff und Rollen überprüfen kann.
66. Als Plattform-Administrator möchte ich interne LEG- und Plattform-Nutzer anlegen können, damit administrative Zugänge kontrolliert entstehen.
67. Als Plattform-Administrator möchte ich Anzeigenamen, Rollen, Aktivstatus und Startpasswörter verwalten können, damit Zugriffe korrigiert oder gesperrt werden können.
68. Als Plattform-Administrator möchte ich bestehende Teilnehmer- und Gemeinde/EW-Konten verwalten, ohne neue Teilnehmermitgliedschaften anzulegen, damit fachliche Mitgliedschaftsprozesse nicht umgangen werden.
69. Als LEG-Vertreter möchte ich einen Gemeinde/EW-Admin über einen expliziten Partnerzugangs-Flow anlegen, damit ein besonders sensibler Partnerzugriff bewusst und nachvollziehbar vergeben wird.
70. Als LEG-Vertreter möchte ich beim Erstellen eines Gemeinde/EW-Zugangs E-Mail, Anzeigename, Organisation/Zuständigkeit und Startpasswort erfassen, damit der Zugang fachlich eindeutig ist.
71. Als LEG-Vertreter möchte ich vor dem Erstellen eines Gemeinde/EW-Zugangs sehen, welche Daten diese Rolle sehen darf, damit Fehlvergabe vermieden wird.
72. Als LEG-Vertreter möchte ich Dokumentversionen veröffentlichen können, damit fachliche Bedingungen und Hinweise bei der LEG-Zuständigkeit bleiben.
73. Als Plattform-Administrator möchte ich Dokumentversionen einsehen, aber nicht veröffentlichen können, damit technische Administration nicht mit fachlicher LEG-Verantwortung vermischt wird.
74. Als Betreiber möchte ich Demo-Rollen nur als klar markiertes Entwicklungswerkzeug sehen, damit die öffentliche Seite produktnah wirkt.
75. Als Besucher möchte ich ein sanftes Nutzenversprechen sehen, ohne konkrete Spar- oder Ertragsversprechen, damit die LEG verständlich wirkt, ohne falsche Erwartungen zu setzen.
76. Als Nutzer möchte ich die SunTerra-Oberfläche als ruhige, präzise Infrastrukturplattform erleben, damit öffentliche und geschützte Bereiche als ein kohärentes Produkt wirken.

## Implementation Decisions

- Das Portal wird als eigenständiges Neubau-Projekt umgesetzt. Der bestehende SunTerra-LEG-Code darf als fachliche und technische Musterquelle dienen, wird aber keine Runtime-Abhängigkeit.
- Der technische Zielstack ist FastAPI, SQLModel, Alembic und Postgres im Backend sowie React, Vite und TypeScript im Frontend.
- Die Rollen sind `participant`, `leg_admin`, `partner_admin` und `platform_admin`.
- `partner_admin` ist die kombinierte Gemeinde/EW-Rolle für Basadingen und erhält nur ein minimales Mitgliederregister plus Mutationspakete.
- Die Kernobjekte sind LEG, Participant, Membership, MeterPoint, GenerationAsset, DocumentVersion, ConsentEvidence, IdentityVerification, MutationRequest, MutationPackage, PartnerTask, FileEvidence und AuditEvent.
- Die Rechtsbasis für den Mutationskern orientiert sich an der VSE-Branchenempfehlung LEG und der Art. 19g StromVV-Referenz, insbesondere Bildung/Auflösung, Teilnehmerkreisänderungen, Aussenvertretung, technische Erzeugungsdaten und Mindestverhältnis-Meldung.
- Onboarding unterstützt Einladung und öffentlichen Self-Service.
- Die Portalrouten sind produktseitig getrennt: `/` für die öffentliche Landing-Page, `/registrieren` für den E-Mail-Start, `/login` für den gemeinsamen Login und `/app` für den geschützten Rollenbereich.
- Der öffentliche Self-Service-Start erfasst nur eine E-Mail-Adresse. Anzeigename und Passwort werden erst nach E-Mail-Verifikation im geschützten Teilnehmer-Setup gesetzt.
- Das Login nutzt E-Mail und Passwort mit signierten JWT-Zugriffstokens. Tokens werden mit `SUNTERRA_SECRET_KEY` signiert, laufen nach 8 Stunden ab und haben in diesem Slice keine Refresh-Token.
- Nutzerkonten enthalten mindestens ID, E-Mail, Anzeigename, Rolle, Aktivstatus, Passwort-Hash, Passwort-Salt und optional Organisation/Zuständigkeit für Gemeinde/EW-Administratoren.
- Passwörter werden nie im Klartext gespeichert. Startpasswörter werden nur zum Setzen oder Zurücksetzen verwendet und danach gehasht.
- Plattform-Administratoren verwalten alle bestehenden Login-Konten, dürfen aber keine neuen Teilnehmermitgliedschaften anlegen.
- Plattform-Administratoren können interne LEG- und Plattform-Nutzer anlegen, Anzeigenamen und Rollen anpassen, Konten aktivieren/deaktivieren und Startpasswörter zurücksetzen.
- Gemeinde/EW-Administratoren werden durch LEG-Vertreter über einen expliziten Partnerzugangs-Flow angelegt, weil die LEG die Partnerbeziehung verantwortet.
- Dokumentversionen werden durch LEG-Vertreter veröffentlicht. Plattform-Administratoren dürfen Dokumentversionen einsehen, aber nicht veröffentlichen.
- Demo-Rollen und Development-Token bleiben nur als klar markiertes lokales Entwicklungswerkzeug und erscheinen nicht auf der öffentlichen Landing-Page.
- Die visuelle Richtung ist `Swiss Energy Infrastructure` / `Operator`; die Landing-Page ist etwas einladender, aber nutzt dieselben SunTerra-Tokens und denselben ruhigen Infrastruktur-Charakter.
- E-Mail-Verifikation ist Teil des Authentifizierungs- und Onboarding-Flusses.
- Identitätsprüfung ist risikobasiert. E-ID oder SwissID werden in v1 nicht fest eingebaut, aber als spätere Provider-Schnittstelle berücksichtigt.
- Dokumente sind versioniert. Einwilligungen werden als ConsentEvidence mit Hash, Zeitpunkt, Dokumentversion und Kontext gespeichert.
- Teilnehmer dürfen Kontaktkanäle direkt ändern.
- Meldepflichtige Daten wie Adresse, Messpunkt, Rolle, Erzeugungsanlage, Eintritt und Austritt laufen über MutationRequests.
- Das Fristenmodell nutzt Quartale: Q1 Januar bis März, Q2 April bis Juni, Q3 Juli bis September, Q4 Oktober bis Dezember.
- Teilnehmer beantragen reguläre Eintritte, Austritte und Mutationen mit 3 Monaten Frist zum Quartalsende.
- LEG-Vertreter melden Gemeinde/EW mit 2 Monaten Frist.
- Eintritte und Mutationen gelten ab dem ersten Tag nach Quartalsende.
- Austritte gelten am Quartalsende.
- Auszug, Todesfall, Eigentümer-/Mieterwechsel, Messpunktfehler und Gemeinde/EW-Korrektur sind begründete Sondermutationen.
- Freigegebene Mutationen werden in immutable MutationPackages gesammelt.
- Ein MutationPackage enthält CSV-, PDF- und JSON-Artefakte, Hash, Stichtag, Frist, Actor und Statushistorie.
- Partner-Administratoren können Paketstatus setzen: empfangen, in Prüfung, verarbeitet, Rückfrage und technisch nicht möglich.
- Partnerstatus braucht immer eine Referenz oder Begründung, wenn der Status fachlich erklärungsbedürftig ist.
- Die LEG entscheidet Mitgliedschaft allein. Partnerstatus darf die Mitgliedschaft nicht automatisch ändern.
- Dateien werden kontrolliert nach definierten Dokumenttypen gespeichert. Es gibt keine freie Dateiablage.
- Jede Datei hat Zweck, Version, Hash, Zugriffsschutz und Aufbewahrungsstatus.
- Kommunikation ist portal-first. v1 versendet keine Status- oder Frist-E-Mails, sondern nur notwendige Auth- und Verifikationskommunikation.
- Teilnehmer sehen Mitgliedschaft, Dokumente, Einwilligungen, eigene Mutationen und die Zuständigkeit der Gemeinde für Abrechnung/Inkasso.
- Teilnehmer sehen keine Rechnungen, Bankdaten, Settlement-Daten oder Messwertverläufe.
- Backend-REST-API-Bereiche werden fachlich getrennt: Authentifizierung, eigene Daten, Dokumente, Teilnehmer-Mutationen, Admin-Teilnehmer, Admin-Mutationen, Admin-Pakete, Partner-Mitgliederregister, Partner-Pakete und Partner-Aufgaben.
- Public DTOs bleiben minimal und rollenbasiert. Partner-DTOs enthalten nur meldepflichtige Registerdaten und Paketstatus. Interne DTOs enthalten Prüfung, Belege und Auditverweise. Teilnehmer-DTOs enthalten nur eigene Daten und eigene Historie.
- Exports sind versionierte Artefakte und keine Live-Views.
- Jeder Export enthält Schema-Version, Paket-ID, LEG-ID, Quartal, Wirksamkeitsdatum, Datensätze, Hash und Erzeugungszeitpunkt.
- Basadingen ist der erste Zielkontext, aber das Datenmodell enthält LEG- und Gemeinde-ID.
- v1 ist deutschsprachig.
- Managed Webbetrieb ist die Zielannahme.

## Testing Decisions

- Tests sollen externes Verhalten prüfen und nicht Implementierungsdetails festnageln.
- Der höchste sinnvolle Test-Seam ist der API-/Workflow-Seam: Onboarding, Mutation beantragen, LEG-Freigabe, Paketbildung und Partnerstatus werden als komplette Rollenflüsse getestet.
- Fachlogik wird an einem Domain-Seam separat getestet: Fristenrechner, Quartalswirksamkeit, Sondermutationen, ConsentEvidence, IdentityVerification-Level und Paketregeln.
- RBAC und Redaction werden explizit getestet, damit `participant`, `leg_admin`, `partner_admin` und `platform_admin` nur die jeweils erlaubten Daten sehen.
- MutationPackage-Immutability wird über Verhaltenstests geprüft: Ein erzeugtes Paket darf nicht stillschweigend geändert werden.
- Export-Artefakte werden mit Golden Files oder stabilen Snapshot-Prüfungen getestet: CSV, PDF und JSON müssen Schema-Version, Paket-ID, LEG-ID, Quartal, Wirksamkeitsdatum, Hash und Erzeugungszeitpunkt korrekt enthalten.
- Datei-Zugriffsschutz wird getestet, inklusive Zweck, Version, Hash, Zugriffsschutz und Aufbewahrungsstatus.
- AuditEvent-Erzeugung und Audit-Hashing werden an relevanten Aktionen getestet.
- Frontend-Smokes prüfen die wichtigsten Nutzerwege: Teilnehmer-Onboarding, direkte Kontaktänderung, meldepflichtige Mutation, LEG-Freigabe, Paketbildung, Partner-Inbox, Partner-Mitgliederregister und deutschsprachige UI.
- Backend-Workflowtests prüfen Login-Erfolg und -Fehler, inaktive Nutzer, JWT-basierte `/api/me`-Auflösung, E-Mail-first-Registrierung, verifiziertes Teilnehmer-Setup, Plattform-Benutzerverwaltung, LEG-Erstellung von Gemeinde/EW-Administratoren und neue Dokument-RBAC-Regeln.
- Frontend-Tests prüfen, dass die öffentliche Landing-Page der erste Screen ist, `Teilnahme starten` nach `/registrieren` führt, `Einloggen` den gemeinsamen Login öffnet, Rollen nach Login direkt in ihre Startfunktion gelangen und Demo-Rollen nicht auf der Landing-Page sichtbar sind.
- Frontend-Tests sollen Nutzerinteraktion und sichtbares Verhalten prüfen, nicht interne React-Komponentenstruktur.
- Migration- und Deployment-Tests umfassen frische Postgres-Migration, Backup/Restore-Smoke, Secret-Konfigurationschecks und produktionsnahe Startguards.
- Da das Projekt ein Neubau ist, gibt es noch keine vorhandene Testsuite als Prior Art. Die ersten Tests sollen deshalb die oben genannten Systemgrenzen etablieren und danach als Muster für weitere Issues dienen.

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
- Refresh-Token, MFA, Passwort-zurücksetzen-per-E-Mail und produktive Mailzustellung
- Finale Logo-Entscheidung oder finale Hero-Visualisierung für die öffentliche Landing-Page
- Konkrete Spar-, Ertrags- oder Preisversprechen auf der öffentlichen Landing-Page
- Freie Dateiablage
- Mehrsprachigkeit in v1
- Mobile App
- Vollständige Multi-LEG-Betriebsoberfläche über Basadingen hinaus
- Legal- oder Datenschutzfreigabe selbst. Die VSE/StromVV-Auslegung soll vor produktiver Nutzung durch Legal/Datenschutz bestätigt werden.

## Further Notes

- Quellen aus dem bestehenden Plan:
  - VSE Branchenempfehlung LEG: https://www.strom.ch/de/media/15458/download
  - Fedlex AS 2025 139: https://www.fedlex.admin.ch/eli/oc/2025/139/de
- Das PRD ist als `ready-for-agent` gedacht, sobald das initiale Projektgerüst und die GitHub-Issue-Veröffentlichung vorhanden sind.
- Spätere Umsetzung sollte aus diesem PRD in kleinere, unabhängig bearbeitbare Issues zerlegt werden.
