const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const LANG_NAME = {en: 'English', hi: 'Hindi', mr: 'Marathi'};
const audio = $('#audio');

/* ---------- waveform bars ---------- */
(function(){const eq=$('#eq');for(let i=0;i<44;i++){const b=document.createElement('i');
  b.style.animationDelay=((i*37)%10)/10+'s';b.style.animationDuration=(0.7+((i*13)%7)/10)+'s';eq.append(b);}})();

/* ---------- state ---------- */
const S = {lang: 'en', playText: '', segs: [], idx: 0, speed: 1, token: 0,
           cache: new Map(), trans: new Map(), bookmarks: []};
try { S.bookmarks = JSON.parse(localStorage.getItem('ab_bookmarks') || '[]'); } catch (e) {}

function status(msg, err = false) { const s = $('#status'); s.textContent = msg || ''; s.className = 'status' + (err ? ' err' : ''); }
async function api(url, opts) {
  const r = await fetch(url, opts);
  if (!r.ok) { let m = 'Request failed'; try { m = (await r.json()).error || m; } catch (e) {} throw new Error(m); }
  return r;
}

/* ---------- upload ---------- */
const drop = $('#drop');
['dragenter', 'dragover'].forEach(t => drop.addEventListener(t, e => { e.preventDefault(); drop.classList.add('over'); }));
['dragleave', 'drop'].forEach(t => drop.addEventListener(t, e => { e.preventDefault(); drop.classList.remove('over'); }));
drop.addEventListener('drop', e => { if (e.dataTransfer.files[0]) upload(e.dataTransfer.files[0]); });
$('#file').addEventListener('change', e => { if (e.target.files[0]) upload(e.target.files[0]); e.target.value = ''; });

async function upload(file) {
  $('#dropTitle').textContent = 'Reading ' + file.name + ' ...';
  status('Extracting text ...');
  const fd = new FormData(); fd.append('file', file);
  try {
    const r = await api('/api/extract', {method: 'POST', body: fd});
    $('#text').value = (await r.json()).text;
    onTextChanged();
    $('#dropTitle').textContent = file.name;
    status('Text extracted. Pick a language to listen.');
  } catch (e) { $('#dropTitle').textContent = 'Drag & drop your file'; status(e.message, true); }
}

/* ---------- text / language ---------- */
$('#text').addEventListener('input', onTextChanged);
function onTextChanged() { resetPlayer(); S.trans.clear(); $('#trans').hidden = true; S.playText = ''; render(); }

$$('.lang').forEach(b => b.addEventListener('click', () => selectLang(b.dataset.lang, {play: true})));

async function selectLang(lang, {play}) {
  const src = $('#text').value.trim();
  if (!src) { status('Upload a file or type some text first.', true); return false; }
  $$('.lang').forEach(b => b.classList.toggle('on', b.dataset.lang === lang));
  if (S.lang === lang && S.playText && S.segs.length) { if (play) startPlay(); return true; }
  resetPlayer(); S.lang = lang; $('#playLang').textContent = LANG_NAME[lang];
  try {
    if (lang === 'en') { S.playText = src; $('#trans').hidden = true; }
    else {
      if (!S.trans.has(lang)) {
        status('Translating to ' + LANG_NAME[lang] + ' ...');
        const r = await api('/api/translate', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({text: src, lang})});
        S.trans.set(lang, (await r.json()).text);
      }
      S.playText = S.trans.get(lang);
      $('#transText').textContent = S.playText; $('#trans').hidden = false;
    }
    S.segs = buildSegs(S.playText); S.idx = 0; status(''); render();
    if (play) startPlay();
    return true;
  } catch (e) { status(e.message, true); return false; }
}

function buildSegs(text, max = 900) {
  const parts = text.match(/[^.!?।\n]+[.!?।]*\s*/g) || [text], segs = [];
  let cur = '', start = 0, pos = 0;
  for (const p of parts) {
    if (cur && cur.length + p.length > max) { segs.push({start, len: cur.length, text: cur}); start = pos; cur = ''; }
    cur += p; pos += p.length;
    while (cur.length > max * 2) { segs.push({start, len: max, text: cur.slice(0, max)}); cur = cur.slice(max); start += max; }
  }
  if (cur.trim()) segs.push({start, len: cur.length, text: cur});
  return segs;
}

/* ---------- player ---------- */
function resetPlayer() { S.token++; audio.pause(); audio.removeAttribute('src'); S.cache.forEach(p => p.then(u => URL.revokeObjectURL(u)).catch(() => {})); S.cache.clear(); S.segs = []; S.idx = 0; setPlaying(false); progress(0); }
function setPlaying(on) { $('#eq').classList.toggle('on', on); $('#playBtn').classList.toggle('playing-now', on); $('#playIcon').setAttribute('href', on ? '#i-pause' : '#i-play'); }
function getUrl(i) {
  if (!S.cache.has(i)) S.cache.set(i, api('/api/tts', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({text: S.segs[i].text, lang: S.lang})}).then(r => r.blob()).then(b => URL.createObjectURL(b)));
  return S.cache.get(i);
}
async function loadSeg(i, frac = 0, play = true) {
  const tok = ++S.token; S.idx = i; status('Preparing audio ...');
  try {
    const url = await getUrl(i);
    if (tok !== S.token) return;
    audio.src = url; audio.playbackRate = S.speed;
    await new Promise(res => { audio.onloadedmetadata = res; audio.onerror = res; });
    if (tok !== S.token) return;
    if (frac) audio.currentTime = frac * audio.duration;
    status('');
    if (play) { await audio.play(); setPlaying(true); }
    if (i + 1 < S.segs.length) getUrl(i + 1).catch(() => {});
  } catch (e) { if (tok === S.token) { status(e.message, true); setPlaying(false); } S.cache.delete(i); }
}
function startPlay() { if (S.segs.length) loadSeg(S.idx, 0, true); }
audio.addEventListener('ended', () => {
  if (S.idx + 1 < S.segs.length) loadSeg(S.idx + 1);
  else { setPlaying(false); S.idx = 0; progress(S.playText.length); }
});
audio.addEventListener('timeupdate', () => progress(curPos()));
function curPos() {
  const s = S.segs[S.idx]; if (!s) return 0;
  const f = audio.duration ? Math.min(audio.currentTime / audio.duration, 1) : 0;
  return Math.round(s.start + s.len * f);
}
function progress(pos) {
  const t = S.playText.length;
  $('#fill').style.width = (t ? pos / t * 100 : 0) + '%';
  $('#posL').textContent = pos + ' chars'; $('#posR').textContent = t + ' chars';
  $('#addBm').disabled = !t;
  const n = $('#nowRead'); n.textContent = '';
  const d = document.createElement('span'), x = document.createElement('span');
  d.className = 'done'; x.className = 'next';
  if (t) { d.textContent = S.playText.slice(Math.max(0, pos - 120), pos); x.textContent = S.playText.slice(pos, pos + 260); }
  else x.textContent = 'Your text appears here as it is read.';
  n.append(d, x);
}
function render() { progress(0); renderBookmarks(); }

$('#playBtn').addEventListener('click', async () => {
  if (audio.src && !audio.paused) { audio.pause(); setPlaying(false); return; }
  if (S.segs.length && audio.src && audio.currentSrc && !audio.ended) { await audio.play(); setPlaying(true); return; }
  if (S.segs.length) return startPlay();
  selectLang(S.lang, {play: true});
});
$('#stopBtn').addEventListener('click', () => { S.token++; audio.pause(); audio.removeAttribute('src'); S.idx = 0; setPlaying(false); progress(0); });
$$('.sp').forEach(b => b.addEventListener('click', () => {
  S.speed = +b.dataset.speed; audio.playbackRate = S.speed;
  $$('.sp').forEach(x => x.classList.toggle('on', x === b));
}));
$('#vol').addEventListener('input', e => audio.volume = +e.target.value);
$('#bar').addEventListener('click', e => {
  if (!S.segs.length) return;
  const r = e.currentTarget.getBoundingClientRect();
  seekChar(Math.floor((e.clientX - r.left) / r.width * S.playText.length), !audio.paused);
});
function seekChar(pos, play = true) {
  let i = S.segs.findIndex(s => pos < s.start + s.len); if (i < 0) i = S.segs.length - 1;
  const s = S.segs[i];
  loadSeg(i, Math.max(0, Math.min((pos - s.start) / s.len, .98)), play);
}

/* ---------- bookmarks ---------- */
function saveBm() { try { localStorage.setItem('ab_bookmarks', JSON.stringify(S.bookmarks)); } catch (e) {} }
$('#addBm').addEventListener('click', () => {
  const pos = curPos();
  S.bookmarks.push({id: Date.now(), pos, lang: S.lang, snippet: S.playText.slice(pos, pos + 60).replace(/\s+/g, ' ')});
  saveBm(); renderBookmarks();
});
$('#bmToggle').addEventListener('click', e => { const h = $('#bmBox').hidden = !$('#bmBox').hidden; e.currentTarget.setAttribute('aria-expanded', !h); });
function renderBookmarks() {
  $('#bmCount').textContent = S.bookmarks.length;
  $('#bmEmpty').hidden = S.bookmarks.length > 0;
  const ul = $('#bmList'); ul.innerHTML = '';
  S.bookmarks.forEach(b => {
    const li = document.createElement('li');
    const go = document.createElement('button'); go.className = 'go';
    go.innerHTML = '<b></b><span></span>';
    go.firstChild.textContent = `${LANG_NAME[b.lang]} · char ${b.pos}`; go.lastChild.textContent = b.snippet ? '“' + b.snippet + '…”' : '';
    go.onclick = async () => { if (await selectLang(b.lang, {play: false})) seekChar(b.pos, true); };
    const del = document.createElement('button'); del.className = 'del'; del.setAttribute('aria-label', 'Delete bookmark');
    del.innerHTML = '<svg><use href="#i-trash"/></svg>';
    del.onclick = () => { S.bookmarks = S.bookmarks.filter(x => x.id !== b.id); saveBm(); renderBookmarks(); };
    li.append(go, del); ul.append(li);
  });
}
render();
