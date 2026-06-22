# SunTerra LEG Mitglieder- Und Mutationsportal

Stand: 2026-06-22

## Summary

Neubau als separates Repository: ein eigenständiges Portal für Teilnehmer, LEG-Vertreter und kombinierte Gemeinde/EW-Rolle. Keine Abrechnung, kein Inkasso, kein Settlement, keine Bankdaten, keine 15-Minuten-Messwerte.

Stack: FastAPI + SQLModel/Alembic + Postgres, React/Vite/TypeScript mit modularen Screens, OpenAPI-generierten Types und eigener Deployment-/Config-Schicht. Der bestehende SunTerra-LEG-Code dient nur als Musterquelle, nicht als Runtime-Abhängigkeit.

Rechtsbasis für den Mutationskern: VSE-Branchenempfehlung LEG mit Art. 19g StromVV-Referenz: Bildung/Auflösung, Teilnehmerkreisänderungen, Aussenvertretung, technische Erzeugungsdaten und Mindestverhältnis-Meldung.

Quellen:

- VSE Branchenempfehlung LEG: <https://www.strom.ch/de/media/15458/download>
- Fedlex AS 2025 139: <https://www.fedlex.admin.ch/eli/oc/2025/139/de>

## Key Changes

Rollen: `participant`, `leg_admin`, `partner_admin`, `platform_admin`. `partner_admin` ist die kombinierte Gemeinde/EW-Rolle für Basadingen, mit minimalem Mitgliederregister plus Mutationspaketen.

Kernobjekte: LEG, Participant, Membership, MeterPoint, GenerationAsset, DocumentVersion, ConsentEvidence, IdentityVerification, MutationRequest, MutationPackage, PartnerTask, FileEvidence, AuditEvent.

Onboarding: Einladung plus öffentlicher Self-Service, E-Mail-Verifikation, risikobasierte Identitätsprüfung, versionierte Dokumente, Clickwrap-Evidenz mit Hash, Zeitpunkt, Dokumentversion und Kontext. E-ID/SwissID nur als spätere Provider-Schnittstelle.

Teilnehmer dürfen Kontaktkanäle direkt ändern. Meldepflichtige Daten wie Adresse, Messpunkt, Rolle, Erzeugungsanlage, Eintritt/Austritt laufen als Mutation.

Fristenmodell: Q1 Jan-Mar, Q2 Apr-Jun, Q3 Jul-Sep, Q4 Okt-Dez. Teilnehmer beantragen reguläre Eintritte, Austritte und Mutationen mit 3 Monaten Frist zum Quartalsende. LEG-Vertreter meldet Gemeinde/EW mit 2 Monaten Frist. Eintritte und Mutationen gelten ab dem ersten Tag nach Quartalsende, Austritte am Quartalsende. Auszug, Todesfall, Eigentümer-/Mieterwechsel, Messpunktfehler und Gemeinde/EW-Korrektur sind begründete Sondermutationen.

Mutationpakete: freigegebene Mutationen werden gesammelt, dann als unveränderliches Paket mit CSV, PDF, JSON, Hash, Stichtag, Frist, Actor und Statushistorie erzeugt. Gemeinde/EW kann Status setzen: empfangen, in Prüfung, verarbeitet, Rückfrage, technisch nicht möglich; immer mit Referenz oder Begründung. LEG entscheidet Mitgliedschaft allein.

Dateien: kontrollierte Dateiablage für definierte Dokumenttypen, keine freie Ablage. Alles mit Zweck, Version, Hash, Zugriffsschutz und Aufbewahrungsstatus.

Kommunikation: Portal-first. Keine Status-/Frist-E-Mails in v1; nur notwendige Auth-/Verifikationskommunikation. Teilnehmer sehen Mitgliedschaft, Dokumente, Einwilligungen, eigene Mutationen und Zuständigkeit der Gemeinde für Abrechnung/Inkasso, aber keine Rechnungen.

## Interfaces

Backend REST-API mit klar getrennten Bereichen:

- `/auth`
- `/me`
- `/documents`
- `/participants/me`
- `/participants/me/mutations`
- `/admin/participants`
- `/admin/mutations`
- `/admin/packages`
- `/partner/member-register`
- `/partner/packages`
- `/partner/tasks`

Public DTOs bleiben minimal und rollenbasiert: Partner-DTOs enthalten nur meldepflichtige Registerdaten und Paketstatus; interne DTOs enthalten Prüfung, Belege und Auditverweise; Teilnehmer-DTOs enthalten nur eigene Daten und eigene Historie.

Exports sind versionierte Artefakte, nicht Live-Views. Jeder Export enthält Schema-Version, Paket-ID, LEG-ID, Quartal, Wirksamkeitsdatum, Datensätze, Hash und Erzeugungszeitpunkt.

## Test Plan

Backend-Tests: Fristenrechner für Quartale und Sonderfälle, Consent-Evidence, IdentityVerification-Level, Mutationsfreigabe, Paket-Immutability, Partnerstatus, RBAC/Redaction, Audit-Hashing, Datei-Zugriffsschutz, Export-Golden-Files.

Frontend-Smokes: Teilnehmer-Onboarding, Kontaktänderung direkt, meldepflichtige Mutation, LEG-Freigabe, Paketbildung, Partner-Inbox, Partner-Mitgliederregister, Deutsch-only UI.

Migration/Deployment-Tests: frische Postgres-Migration, Backup/Restore-Smoke, Secret-Konfigurationschecks, produktionsnahe Startguards.

## Assumptions

Basadingen zuerst, aber Datenmodell mit LEG/Gemeinde-ID. Deutsch only in v1. Managed Webbetrieb ist Zielannahme. Keine automatische Gemeinde-/EW-Schnittstelle in v1. Datenumfang bleibt minimal: keine Bankdaten, keine Rechnungen, keine Energiedaten. Legal/Datenschutz sollte die VSE/StromVV-Auslegung vor produktiver Nutzung bestätigen.
