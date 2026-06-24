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

Wenn `SUNTERRA_DATABASE_URL` gesetzt ist, speichert das Portal den V1-Portalzustand datenbankgestützt und lädt ihn bei neuen Requests wieder. Für lokale Persistenz:

```powershell
$env:SUNTERRA_DATABASE_URL = "sqlite:///./sunterra-leg-portal.db"
.\.venv\Scripts\python -m alembic upgrade head
```

`SUNTERRA_DATABASE_URL` ist eine SQLAlchemy/SQLModel-Datenbank-URL. Lokale Tests und Entwicklung können SQLite-Dateien wie oben verwenden; eine Postgres-kompatible Umgebung kann denselben Pfad mit einer URL wie `postgresql+psycopg://user:password@host:5432/database` betreiben, sofern der passende Treiber in der Laufzeitumgebung installiert ist.

### OpenAPI-Typen

Frontend-Vertragstypen werden aus der FastAPI-OpenAPI-Spezifikation generiert:

```powershell
npm run api:types
npm run api:types:check
```

Die generierten Dateien liegen unter `frontend/src/generated/` und werden eingecheckt, damit Contract-Drift sichtbar bleibt.

### Production Readiness

Die ersten produktionsnahen Smoke Checks fuer Konfiguration, frische Migrationen und Backup/Restore sind in `docs/ops/production-readiness.md` dokumentiert.
