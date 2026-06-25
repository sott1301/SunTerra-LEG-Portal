# ADR 0001: Verbindlicher Pilot, privates Hosting und Public-Rollout-Gate

## Status

Akzeptiert

## Kontext

Das SunTerra-LEG-Portal muss echte Mitgliedschafts-, Einwilligungs-,
MutationPackage- und Gemeinde/EW-Rückmeldeprozesse beweisen, bevor der
öffentliche Zugang geöffnet wird. Der Pilot ist verbindlich: Pilotnutzer können
echte Daten verwenden und echte Prozesse auslösen, aber der Zugang bleibt über
Einladung oder Allowlist kontrolliert.

Privates Hosting ist für den Pilot akzeptabel, wenn die Betriebsgrundlagen
stehen: TLS/Domain, Postgres, SMTP, Secret-Handling, tägliche verschlüsselte
Offsite-Backups, Restore-Test, Health/Readiness-Checks und Alerts.

## Entscheidung

Vor dem öffentlichen Rollout läuft ein verbindlicher Pilot. Pilotzugang bleibt
per Einladung oder Allowlist begrenzt; nicht freigegebene E-Mail-Adressen werden
zu Interessensmeldungen.

Für den Pilot darf privates Hosting genutzt werden. Vor dem öffentlichen Rollout
muss ein Public-Rollout-Gate entscheiden, ob privates Hosting weiter genügt oder
Managed Hosting erforderlich ist.

Das Public-Rollout-Gate verlangt mindestens ein echtes verarbeitetes
MutationPackage, danach 14 stabile Tage ohne kritische offene Befunde, einen
bestandenen Restore-Test, aktive Alerts sowie schriftliche Legal-, Datenschutz-
und Gemeinde/EW-Prozessfreigabe.

## Konsequenzen

- Der Pilot ist keine Wegwerf-Demo; Nachweise und Entscheidungen sind
  verbindlich.
- Betriebschecks werden Release-Kriterien vor öffentlichem Zugang.
- Öffentlicher Self-Service öffnet erst nach bestandenem Betriebsgate.
