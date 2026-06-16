# Backend — epub2audiobook

API FastAPI + workers Celery en Python, gestionados con **uv**.

## Arquitectura hexagonal

```
src/audiobook/
├── domain/               # Núcleo — sin dependencias externas
│   ├── models.py         # Job, Chapter, ConversionOptions (dataclasses puras)
│   └── ports.py          # Interfaces abstractas: IJobStore, ITTSEngine, IAudioMerger, IEpubReader, IProgressBus
│
├── application/          # Casos de uso — sólo depende del dominio
│   └── services.py       # ParseEpubService, ConvertChapterService, MergeAudiobookService
│
└── infrastructure/       # Adaptadores — dependen de librerías externas
    ├── adapters/
    │   ├── epub_reader.py    # IEpubReader  → ebooklib + BeautifulSoup + NLTK
    │   ├── tts_engine.py     # ITTSEngine   → edge-tts (async, semáforo 10, reintentos)
    │   ├── audio_merger.py   # IAudioMerger → pydub + ffmpeg (FLAC → M4B)
    │   └── redis_store.py    # IJobStore (sync/Celery) + IProgressBus (async/SSE)
    ├── celery/
    │   ├── app.py            # Configuración Celery (broker: Redis)
    │   └── tasks.py          # convert_chapter (por capítulo) + merge_audiobook (chord callback)
    └── api/
        ├── main.py           # FastAPI app, CORS, NLTK init
        ├── auth.py           # API key (X-API-Key header)
        ├── deps.py           # Inyección de dependencias (fábricas)
        ├── schemas.py        # Pydantic request/response models
        └── routes/
            ├── epub.py       # POST /api/epub/parse
            ├── jobs.py       # POST/GET /api/jobs + SSE + download
            └── voices.py     # GET /api/voices
```

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/epub/parse` | Sube EPUB → devuelve TXT editable |
| `GET` | `/api/voices` | Lista de voces Edge TTS disponibles |
| `POST` | `/api/jobs` | Inicia conversión → devuelve `job_id` |
| `GET` | `/api/jobs/{id}` | Estado del job (polling) |
| `GET` | `/api/jobs/{id}/stream` | SSE — progreso en tiempo real |
| `GET` | `/api/jobs/{id}/download` | Descarga el M4B (cuando `status=done`) |
| `GET` | `/api/health` | Health check |

Todas las rutas requieren `X-API-Key` header.

## Ejecución local

```bash
cd backend
uv sync                    # crea .venv e instala todo

# Terminal 1 — API
uv run uvicorn audiobook.infrastructure.api.main:app --reload --port 8000

# Terminal 2 — Redis (necesitas Docker o redis-server)
docker run -p 6379:6379 redis:7-alpine

# Terminal 3 — Worker Celery
REDIS_URL=redis://localhost:6379/0 \
API_KEY=dev \
uv run celery -A audiobook.infrastructure.celery.app:celery_app worker \
  --concurrency=2 --loglevel=info -Q chapters,celery

# Terminal 4 — Flower (opcional, monitoring)
REDIS_URL=redis://localhost:6379/0 \
uv run celery -A audiobook.infrastructure.celery.app:celery_app flower --port=5555
```

## Paralelismo de capítulos

```
Nº workers = max(1, nproc - 2)
  → en un sistema de 8 cores: 6 capítulos en paralelo
  → configurable via WORKER_CONCURRENCY en .env

Dentro de cada capítulo (en el worker):
  → asyncio + Semaphore(10) para sintetizar frases concurrentemente vía edge-tts
```

## Estructura Redis

```
job:{id}            → JSON con estado completo del job (TTL 24h)
job:{id}:updates    → canal pub/sub para SSE
```

## Dependencias (pyproject.toml)

Gestión con `uv`. Para añadir una dependencia:
```bash
uv add <paquete>
uv sync
```
