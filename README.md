# Sistema B · Apuestas EC

Comparador público de cuotas pre-partido para LigaPro Ecuador y partidos de la selección de Ecuador. Este sistema complementa al Sistema A académico y mantiene el mismo stack: FastAPI, Keycloak, Vault, SQLAlchemy async, Alembic, HTMX, Alpine y Tailwind CDN.

## Arquitectura

- `app/routers/public.py`: home pública, detalle de partido, healthcheck y sitemap.
- `app/routers/admin.py`: dashboard protegido con rol `admin`, scrapers, partidos, cuotas crudas y contenido destacado.
- `app/routers/api_internal.py`: `POST /api/internal/featured-content`, protegido por API key compartida con Sistema A.
- `app/scrapers/`: scrapers Playwright para Ecuabet, Betcris, Bet593 y Betano. Si `SCRAPERS_USE_MOCK=true`, generan datos demo realistas sin abrir Chromium.
- `app/services/vault_service.py`: descifrado con Vault Transit usando `VAULT_TOKEN` y `VAULT_TRANSIT_KEY`.
- `alembic/versions/202605030001_initial_schema.py`: crea usuarios, partidos, odds, logs y featured content.

## Correr localmente

```bash
cd /Users/lyriom/Documents/Goszyl/sistema-b
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
# ajusta DATABASE_URL, Keycloak, Vault y secretos
alembic upgrade head
uvicorn app.main:app --reload
```

Con `SCRAPERS_USE_MOCK=true`, el scheduler inserta datos demo si la base está vacía y luego ejecuta los jobs cada 6 horas con stagger de 90 minutos.

## Endpoint A -> B

```bash
curl -X POST https://apuestas.gozsyl.cloud/api/internal/featured-content \
  -H "Authorization: Bearer $SISTEMA_A_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"post_id":1,"ciphertext":"vault:v1:..."}'
```

El plaintext descifrado debe ser JSON con `title`, `excerpt`, `content_html` y `slug`. El HTML se sanitiza antes de guardarse.

## Deploy en EasyPanel

1. Sube la carpeta `sistema-b` al repositorio `https://github.com/Lyriom/Apuestas-Goszyl.git` o al repo separado que usarás para este sistema.
2. Crea un servicio Docker apuntando al `Dockerfile`.
3. Configura las variables de `.env.example` en EasyPanel.
4. Asocia el dominio `https://apuestas.gozsyl.cloud`.
5. Ejecuta `alembic upgrade head` una vez contra la base PostgreSQL.
6. Arranca el servicio. No hay `HEALTHCHECK` en el Dockerfile para evitar el problema de SIGTERM visto en Sistema A.

## Operación

- Público: `/` y `/partido/{id}`.
- Admin: `/admin`, requiere login Keycloak y rol `admin`.
- Manual scraping: `/admin/scrapers`, botón `Ejecutar ahora`.
- API interna: `POST /api/internal/featured-content`.

## Nota responsable

Apostar puede ser adictivo. Juega con responsabilidad. +18.
