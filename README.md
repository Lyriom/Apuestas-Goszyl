# Sistema B · Apuestas EC

Comparador público de cuotas pre-partido para LigaPro Ecuador y partidos de la selección de Ecuador. Este sistema complementa al Sistema A académico y mantiene el mismo stack: FastAPI, Keycloak, Vault, SQLAlchemy async, Alembic, HTMX, Alpine y Tailwind CDN.

## Arquitectura

- `app/routers/public.py`: home pública, detalle de partido, healthcheck y sitemap.
- `app/routers/admin.py`: dashboard protegido con rol `admin`, scrapers, partidos, cuotas crudas y contenido destacado.
- `app/routers/api_internal.py`: `POST /api/internal/featured-content`, protegido por API key compartida con Sistema A.
- `app/scrapers/`: scrapers JSON reales basados en `httpx` (sin Playwright). `altenar.py` define un adaptador genérico para casas que corren sobre el backend B2B de Altenar (`sb2frontend-altenar2.biahosted.com`) y expone subclases para **Ecuabet**, **Doradobet** y **Bet593** con sus propios márgenes. `pinnacle.py` añade una casa "sharp" desde la API pública de Pinnacle. `espn.py` enriquece con calendario oficial y escudos de equipos cuando alguna casa aún no abrió el mercado. La filtración por categoría 852 (Ecuador) garantiza que solo entran partidos de LigaPro/Serie B y los internacionales con clubes ecuatorianos (Libertadores, Sudamericana, eliminatorias, Mundial).
- `app/services/vault_service.py`: descifrado con Vault Transit usando `VAULT_TOKEN` y `VAULT_TRANSIT_KEY`.
- `alembic/versions/202605030001_initial_schema.py`: crea usuarios, partidos, odds, logs y featured content.

## Correr localmente

```bash
cd /Users/lyriom/Documents/Goszyl/sistema-b
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# ajusta DATABASE_URL, Keycloak, Vault y secretos
alembic upgrade head
uvicorn app.main:app --reload
```

El scheduler ejecuta cada scraper cada `SCRAPERS_INTERVAL_HOURS` horas (default 6h) con stagger de 20 minutos. La primera corrida arranca a los `SCRAPERS_INITIAL_RUN_DELAY_SECONDS` segundos del inicio. No hay modo mock: si la fuente bloquea o cambia, el log marca `error` y no se inserta nada.

## Acceso admin

Solo entran a `/admin` los usuarios cuyo email esté en `ADMIN_EMAILS` (separados por comas) **o** que tengan el rol `admin` (o sus alias) en el JWT de Keycloak. Cualquier otra cuenta autenticada es redirigida a `/auth/no-access` y ve un 403 si intenta acceder directo.

## Endpoint A -> B

```bash
curl -X POST https://apuestas.gozsyl.cloud/api/internal/featured-content \
  -H "Authorization: Bearer $SISTEMA_A_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"post_id":"<uuid-del-post>","ciphertext":"vault:v1:..."}'
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
- Admin: `/admin`, requiere login Keycloak + email en `ADMIN_EMAILS` o rol `admin`.
- Manual scraping: `/admin/scrapers`, botón `Ejecutar ahora`.
- API interna: `POST /api/internal/featured-content`.

## Nota responsable

Apostar puede ser adictivo. Juega con responsabilidad. +18.
