# SunTerra LEG Portal

Eigenständiges Neubau-Projekt für das Mitglieder- und Mutationsportal der SunTerra LEG Basadingen.

Dieses Projekt ist bewusst vom grossen SunTerra-LEG Pilotprojekt getrennt. Das alte Projekt dient nur als fachliche und technische Referenz, nicht als Runtime-Abhängigkeit.

Startpunkt:

- `docs/plans/sunterra-leg-member-mutation-portal.md`

## Lokale Entwicklung

### Voraussetzungen

- Python 3.12
- Node.js 24 oder kompatibel
- npm 11 oder kompatibel

### Backend einrichten und testen

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m pytest
```

Backend starten:

```powershell
.\.venv\Scripts\python -m uvicorn sunterra_leg_portal.main:app --reload
```

Der Health-Endpunkt ist danach unter `http://127.0.0.1:8000/api/health` erreichbar.

Für die lokale Entwicklung gibt es eine einfache Demo-Authentifizierung:

```http
Authorization: Bearer dev:participant
Authorization: Bearer dev:leg_admin
Authorization: Bearer dev:partner_admin
Authorization: Bearer dev:platform_admin
```

`GET /api/me` liefert damit die aktuelle Demo-Identität und Rolle. Diese Development-Auth ist nur ein austauschbarer Einstieg für die ersten Portal-Slices.

### Frontend einrichten und testen

```powershell
npm install
npm run test
npm run build
```

Frontend starten:

```powershell
npm run dev
```

Das Frontend läuft standardmässig unter `http://127.0.0.1:5173` und leitet `/api` im Entwicklungsmodus an das lokale Backend weiter.

### Datenbank-Migrationen

Die Backend-Struktur ist für SQLModel und Alembic vorbereitet. Lokale Migrationen verwenden standardmässig `sqlite:///./sunterra-leg-portal.db`; produktionsnahe Umgebungen setzen `SUNTERRA_DATABASE_URL`.

### Production Readiness

Die ersten produktionsnahen Smoke Checks fuer Konfiguration, frische Migrationen und Backup/Restore sind in `docs/ops/production-readiness.md` dokumentiert.
