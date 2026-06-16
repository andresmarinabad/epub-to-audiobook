/* ── State ─────────────────────────────────────────────────────────────── */
const state = {
  apiKey: localStorage.getItem('apiKey') || '',
  txtContent: '',
  bookTitle: '',
  bookAuthor: '',
  voices: [],
  coverPath: null,
  jobId: null,
  eventSource: null,
  mergeStart: null,
  mergeTimer: null,
};

/* ── DOM refs ───────────────────────────────────────────────────────────── */
const $ = id => document.getElementById(id);

const steps = {
  upload:   $('step-upload'),
  edit:     $('step-edit'),
  config:   $('step-config'),
  progress: $('step-progress'),
};

/* ── Navigation ─────────────────────────────────────────────────────────── */
function showStep(name) {
  Object.values(steps).forEach(el => el.classList.add('hidden'));
  steps[name].classList.remove('hidden');
}

/* ── API helper ─────────────────────────────────────────────────────────── */
async function api(path, opts = {}) {
  const key = $('api-key').value.trim() || state.apiKey;
  const res = await fetch(path, {
    ...opts,
    headers: { 'X-API-Key': key, ...(opts.headers || {}) },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res;
}

/* ── Toast ──────────────────────────────────────────────────────────────── */
function toast(msg, isError = false) {
  const el = $('toast');
  el.textContent = msg;
  el.className = 'toast' + (isError ? ' error' : '');
  el.classList.remove('hidden');
  setTimeout(() => el.classList.add('hidden'), 4000);
}

/* ── Step 1: Upload ─────────────────────────────────────────────────────── */
const dropZone  = $('drop-zone');
const epubInput = $('epub-input');

dropZone.addEventListener('click', () => epubInput.click());
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) handleEpub(file);
});
epubInput.addEventListener('change', () => {
  if (epubInput.files[0]) handleEpub(epubInput.files[0]);
});

async function handleEpub(file) {
  const key = $('api-key').value.trim();
  if (!key) { toast('Introduce la API Key primero', true); return; }

  localStorage.setItem('apiKey', key);
  state.apiKey = key;

  dropZone.classList.add('loading');
  dropZone.querySelector('p').textContent = 'Procesando EPUB…';

  try {
    const form = new FormData();
    form.append('file', file);
    const res = await api('/api/epub/parse', { method: 'POST', body: form });
    const data = await res.json();

    state.txtContent = data.txt_content;
    state.bookTitle  = data.book_title;
    state.bookAuthor = data.book_author;
    state.coverPath  = data.cover_path || null;

    $('txt-editor').value = data.txt_content;
    $('meta-title').textContent  = data.book_title;
    $('meta-author').textContent = data.book_author;

    showStep('edit');
    renderPartsPanel();
    loadVoices();
  } catch (err) {
    toast(err.message, true);
  } finally {
    dropZone.classList.remove('loading');
    dropZone.querySelector('p').innerHTML = 'Arrastra un <strong>.epub</strong> aquí o haz clic';
  }
}

/* ── Step 2: Parts panel ─────────────────────────────────────────────────── */
function scanParts(text) {
  const matches = [];
  const re = /^# Part (\d+)$/gm;
  let m;
  while ((m = re.exec(text)) !== null) {
    matches.push(Number(m[1]));
  }
  return matches;
}

function renderPartsPanel() {
  const text   = $('txt-editor').value;
  const parts  = scanParts(text);
  const list   = $('parts-list');
  const badge  = $('parts-badge');

  // Preserve values already typed by the user
  const saved = {};
  list.querySelectorAll('.part-row').forEach(row => {
    const n = row.dataset.part;
    const inp = row.querySelector('.part-input');
    if (inp && inp.value.trim()) saved[n] = inp.value;
  });

  list.innerHTML = '';
  badge.textContent = parts.length;
  badge.classList.toggle('ok', parts.length === 0);

  if (parts.length === 0) {
    list.innerHTML = '<p class="parts-empty">No hay marcadores <code># Part N</code> en el texto.</p>';
    return;
  }

  parts.forEach(n => {
    const row = document.createElement('div');
    row.className = 'part-row';
    row.dataset.part = n;

    const lbl = document.createElement('span');
    lbl.className = 'part-label';
    lbl.textContent = `# Part ${n}`;

    const inp = document.createElement('input');
    inp.type = 'text';
    inp.className = 'part-input';
    inp.placeholder = `Título para Part ${n}`;
    inp.value = saved[n] || '';

    row.appendChild(lbl);
    row.appendChild(inp);
    list.appendChild(row);
  });
}

function applyParts() {
  const list = $('parts-list');
  const editor = $('txt-editor');
  let text = editor.value;

  list.querySelectorAll('.part-row').forEach(row => {
    const n   = row.dataset.part;
    const val = row.querySelector('.part-input').value.trim();
    if (!val) return;
    const re = new RegExp(`^# Part ${n}$`, 'gm');
    text = text.replace(re, `# ${val}`);
  });

  editor.value = text;
  renderPartsPanel(); // re-scan after replacements
}

$('btn-apply-parts').addEventListener('click', applyParts);

$('btn-back-upload').addEventListener('click', () => showStep('upload'));
$('btn-go-config').addEventListener('click', () => {
  state.txtContent = $('txt-editor').value;
  showStep('config');
});

/* ── Step 3: Config → voices ─────────────────────────────────────────────── */
$('btn-back-edit').addEventListener('click', () => { showStep('edit'); renderPartsPanel(); });

async function loadVoices() {
  try {
    const res = await api('/api/voices');
    state.voices = await res.json();
    buildVoiceSelectors(state.voices);
  } catch {
    // Non-fatal — user can still type a voice name
  }
}

function buildVoiceSelectors(voices) {
  const localeSet = new Set(voices.map(v => v.locale));
  const localeFilter = $('locale-filter');
  localeFilter.innerHTML = '<option value="">Todos los idiomas</option>';
  [...localeSet].sort().forEach(loc => {
    const opt = document.createElement('option');
    opt.value = loc;
    opt.textContent = loc;
    localeFilter.appendChild(opt);
  });

  function renderVoices(filter) {
    const filtered = filter ? voices.filter(v => v.locale === filter) : voices;
    const sel = $('voice-select');
    sel.innerHTML = '';
    filtered.forEach(v => {
      const opt = document.createElement('option');
      opt.value = v.short_name;
      opt.textContent = `${v.short_name} — ${v.gender}`;
      // Default to Spanish Spain male voice if available
      if (v.short_name === 'es-ES-AlvaroNeural') opt.selected = true;
      sel.appendChild(opt);
    });
  }

  localeFilter.addEventListener('change', () => renderVoices(localeFilter.value));
  renderVoices('');
}

/* ── Step 3: Start conversion ────────────────────────────────────────────── */
$('btn-start').addEventListener('click', startConversion);

async function startConversion() {
  const btn = $('btn-start');
  btn.disabled = true;
  btn.textContent = 'Verificando…';

  // Enforce one job at a time
  const existingId = localStorage.getItem('activeJobId');
  if (existingId) {
    try {
      const check = await api(`/api/jobs/${existingId}`);
      const checkData = await check.json();
      if (checkData.status !== 'done' && checkData.status !== 'error') {
        toast('Ya hay una conversión en progreso. Espera a que termine.', true);
        btn.disabled = false;
        btn.textContent = 'Convertir a audiolibro';
        return;
      }
    } catch { /* job expired — safe to proceed */ }
    localStorage.removeItem('activeJobId');
  }

  btn.textContent = 'Enviando…';

  try {
    const res = await api('/api/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        txt_content:       $('txt-editor').value,
        voice:             $('voice-select').value || 'en-US-AndrewNeural',
        sentence_pause_ms: Number($('pause-sentence').value),
        paragraph_pause_ms:Number($('pause-paragraph').value),
        chapter_pause_ms:  Number($('pause-chapter').value),
        cover_path:        state.coverPath,
      }),
    });
    const job = await res.json();
    state.jobId = job.job_id;
    localStorage.setItem('activeJobId', job.job_id);

    initProgressUI(job.total_chapters);
    showStep('progress');
    startSSE(job.job_id);
  } catch (err) {
    toast(err.message, true);
    btn.disabled = false;
    btn.textContent = 'Convertir a audiolibro';
  }
}

/* ── Step 4: Progress UI ─────────────────────────────────────────────────── */
function initProgressUI(totalChapters) {
  _stopMergeIndicator();
  $('overall-bar').style.width = '0%';
  $('overall-pct').textContent = '0%';
  $('status-text').textContent = 'Procesando capítulos…';
  $('status-text').style.color = '';
  $('download-section').classList.add('hidden');

  const grid = $('chapters-grid');
  grid.innerHTML = '';
  for (let i = 0; i < totalChapters; i++) {
    const card = document.createElement('div');
    card.className = 'chapter-card';
    card.id = `ch-${i}`;
    card.innerHTML = `
      <div class="ch-title">Capítulo ${i + 1}</div>
      <div class="ch-status">pendiente</div>
      <div class="ch-bar-track"><div class="ch-bar-fill"></div></div>
    `;
    grid.appendChild(card);
  }
}

function updateChapterCard(ch) {
  const card = $(`ch-${ch.index}`);
  if (!card) return;
  card.className = `chapter-card ${ch.status}`;
  card.querySelector('.ch-title').textContent = ch.title && ch.title !== 'blank'
    ? ch.title
    : `Capítulo ${ch.index + 1}`;
  card.querySelector('.ch-status').textContent = statusLabel(ch.status);
  card.querySelector('.ch-bar-fill').style.width = `${Math.round(ch.progress * 100)}%`;
}

function statusLabel(s) {
  return { pending: 'pendiente', processing: 'convirtiendo…', done: 'listo', merging: 'uniendo…', error: 'error' }[s] || s;
}

function _tickMergeTimer() {
  const elapsed = Math.floor((Date.now() - state.mergeStart) / 1000);
  const mm = String(Math.floor(elapsed / 60)).padStart(2, '0');
  const ss = String(elapsed % 60).padStart(2, '0');
  $('status-text').textContent = `Creando M4B… ${mm}:${ss}`;
}

function _startMergeIndicator() {
  if (state.mergeStart) return; // already running
  state.mergeStart = Date.now();
  $('overall-bar').classList.add('indeterminate');
  $('overall-pct').textContent = '…';
  _tickMergeTimer();
  state.mergeTimer = setInterval(_tickMergeTimer, 1000);
}

function _stopMergeIndicator() {
  if (!state.mergeTimer) return;
  clearInterval(state.mergeTimer);
  state.mergeTimer = null;
  state.mergeStart = null;
  $('overall-bar').classList.remove('indeterminate');
}

function updateOverall(data) {
  if (data.status === 'merging') {
    _startMergeIndicator();
  } else {
    _stopMergeIndicator();
    const pct = Math.round((data.overall_progress || 0) * 100);
    $('overall-bar').style.width = `${pct}%`;
    $('overall-pct').textContent = `${pct}%`;
    $('status-text').textContent = statusLabel(data.status);
  }

  if (data.chapters) {
    data.chapters.forEach(updateChapterCard);
  }

  if (data.status === 'done' && data.m4b_ready) {
    showDownload();
  }
  if (data.status === 'error') {
    localStorage.removeItem('activeJobId');
    $('new-conversion-row').classList.remove('hidden');
    $('status-text').textContent = `Error: ${data.error || 'desconocido'}`;
    $('status-text').style.color = 'var(--error)';
  }
}

function showDownload() {
  localStorage.removeItem('activeJobId');
  $('new-conversion-row').classList.remove('hidden');
  const sec = $('download-section');
  sec.classList.remove('hidden');
  const link = $('download-link');
  link.href = `/api/jobs/${state.jobId}/download`;
  link.setAttribute('download', '');
  // Add API key as query param isn't possible for FileResponse auth; use fetch+blob
  link.addEventListener('click', async e => {
    e.preventDefault();
    try {
      const res = await api(`/api/jobs/${state.jobId}/download`);
      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href = url;
      a.download = `audiobook-${state.jobId}.m4b`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      toast(err.message, true);
    }
  }, { once: false });
  $('overall-bar').style.width = '100%';
  $('overall-pct').textContent = '100%';
}

/* ── SSE ─────────────────────────────────────────────────────────────────── */
function startSSE(jobId) {
  // We can't set headers on EventSource, so we use a custom fetch-based reader
  const key = state.apiKey;
  const url  = `/api/jobs/${jobId}/stream`;

  const controller = new AbortController();
  state.eventSource = controller;

  fetch(url, { headers: { 'X-API-Key': key }, signal: controller.signal })
    .then(async res => {
      if (!res.ok) { toast('Error al conectar con el stream', true); return; }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop(); // keep incomplete chunk
        for (const part of parts) {
          if (part.startsWith('data: ')) {
            try {
              const data = JSON.parse(part.slice(6));
              updateOverall(data);
              if (data.status === 'done' || data.status === 'error') {
                controller.abort();
                return;
              }
            } catch {}
          }
        }
      }
    })
    .catch(err => {
      if (err.name !== 'AbortError') {
        // Fallback: poll every 3 seconds
        pollFallback(jobId);
      }
    });
}

function pollFallback(jobId) {
  const interval = setInterval(async () => {
    try {
      const res  = await api(`/api/jobs/${jobId}`);
      const data = await res.json();
      updateOverall(data);
      if (data.status === 'done' || data.status === 'error') {
        clearInterval(interval);
      }
    } catch {}
  }, 3000);
}

/* ── Session restore ─────────────────────────────────────────────────────── */
async function restoreJob(jobId) {
  try {
    const res  = await api(`/api/jobs/${jobId}`);
    const data = await res.json();
    state.jobId = jobId;
    initProgressUI(data.chapters.length);
    updateOverall(data); // fills chapter cards + overall bar
    showStep('progress');
    if (data.status !== 'done' && data.status !== 'error') {
      startSSE(jobId);
    }
  } catch {
    // Job expired or bad API key — clear so it doesn't block future jobs
    localStorage.removeItem('activeJobId');
  }
}

function startNewConversion() {
  if (state.eventSource) { state.eventSource.abort(); state.eventSource = null; }
  _stopMergeIndicator();
  state.jobId = null;
  localStorage.removeItem('activeJobId');
  $('new-conversion-row').classList.add('hidden');
  $('download-section').classList.add('hidden');
  showStep('upload');
}

$('btn-new-conversion').addEventListener('click', startNewConversion);

// Auto-restore on page load if a job was active
(async () => {
  const savedJobId = localStorage.getItem('activeJobId');
  if (savedJobId && state.apiKey) {
    await restoreJob(savedJobId);
  }
})();
