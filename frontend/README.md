# Frontend — epub2audiobook

Interfaz web estática servida por **nginx**. Sin framework, sin build step — HTML + CSS + JS vanilla puro.

## Estructura

```
frontend/
├── Dockerfile          # nginx:alpine — copia src/ y la config
├── nginx.conf          # Sirve /  y proxifica /api/ → backend:8000 (SSE ready)
└── src/
    ├── index.html      # Página única con 4 secciones (pasos del flujo)
    ├── style.css       # Dark theme, design tokens CSS, responsive
    └── app.js          # Lógica: upload, SSE, barras de progreso, descarga
```

## Flujo de usuario

```
Paso 1 — Upload
  Arrastra o selecciona un .epub
  Introduce la API Key (se guarda en localStorage)
  → POST /api/epub/parse

Paso 2 — Editar texto
  Textarea con el TXT generado (formato epub2tts-edge)
  Edita capítulos, elimina prefacios, etc.

Paso 3 — Configurar
  Selector de idioma → filtro de voces
  Selector de voz (322 voces Edge TTS)
  Pausa por frase / párrafo / capítulo (ms)
  → POST /api/jobs

Paso 4 — Progreso y descarga
  Barra general de progreso
  Grid de cards por capítulo (estado + barra individual)
  Stream de actualizaciones vía SSE (fetch + ReadableStream)
  Fallback: polling cada 3s si SSE falla
  Botón descarga M4B (fetch + blob + URL.createObjectURL)
```

## SSE con autenticación

`EventSource` nativo no soporta headers personalizados, por eso el frontend usa `fetch()` con `ReadableStream` para leer el SSE autenticado:

```js
fetch('/api/jobs/{id}/stream', { headers: { 'X-API-Key': key } })
  .then(res => res.body.getReader())  // ReadableStream
  .then(...)  // parse 'data: {...}\n\n'
```

## Desarrollo local

Sirve los archivos de `src/` directamente:

```bash
cd frontend/src
python3 -m http.server 3000
# o cualquier servidor estático
```

El API debe estar en `http://localhost:8000` — ajusta el proxy en nginx.conf si es necesario, o usa CORS del backend en desarrollo.

## Personalización

- Colores: variables CSS en `:root` en `style.css`
- Voz por defecto: `es-ES-AlvaroNeural` (línea ~105 de `app.js`)
- Pausas por defecto: editables en los inputs del paso 3
