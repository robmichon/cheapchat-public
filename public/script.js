// --- ELEMENTY ---
let threadId = "";
const threadsDiv = document.getElementById('threads');
const renameInp = document.getElementById('renameInp');
const renameBtn = document.getElementById('renameBtn');
const newBtn = document.getElementById('newBtn');

const chat = document.getElementById('chat');
const inp  = document.getElementById('inp');
const sendBtn = document.getElementById('sendBtn');
const webChk = document.getElementById('webChk');
const memChk = document.getElementById('memChk');
const micBtn  = document.getElementById('micBtn');
const speakBtn= document.getElementById('speakBtn');
const voiceSel= document.getElementById('voiceSel');
const imgBtn  = document.getElementById('imgBtn');
const themeSel= document.getElementById('themeSel');
const toc = document.getElementById('toc');
const statusEl = document.getElementById('status');

const memModal = document.getElementById('memModal');
const memClose = document.getElementById('memClose');
const memPanelBtn = document.getElementById('memPanelBtn');
const memKey = document.getElementById('memKey');
const memValue = document.getElementById('memValue');
const memScope = document.getElementById('memScope');
const memAdd = document.getElementById('memAdd');
const memRefresh = document.getElementById('memRefresh');
const memList = document.getElementById('memList');

const fileInp = document.getElementById('fileInp');
const filesBtn = document.getElementById('filesBtn');
const filesModal = document.getElementById('filesModal');
const filesClose = document.getElementById('filesClose');
const filesList = document.getElementById('filesList');
const filesUpload = document.getElementById('filesUpload');

function el(tag, cls){ const x = document.createElement(tag); if(cls) x.className=cls; return x; }
function renderMarkdown(md) {
  marked.setOptions({ gfm: true, breaks: false });
  const html = marked.parse(md || "");
  const safe = DOMPurify.sanitize(html, {ALLOWED_ATTR: ['class','href','src','alt','title','target','rel']});
  const tmp = document.createElement('div');
  tmp.innerHTML = safe;
  tmp.querySelectorAll('pre code').forEach((block) => { try { hljs.highlightElement(block); } catch(e) {} });
  enhanceCodeBlocks(tmp);
  return tmp.innerHTML;
}
function enhanceCodeBlocks(container){
  container.querySelectorAll('pre').forEach(pre=>{
    if (pre.querySelector('.copybtn')) return;
    const btn = document.createElement('button');
    btn.textContent = 'Copy'; btn.className = 'copybtn';
    pre.appendChild(btn);
    btn.onclick = async ()=>{
      const code = pre.querySelector('code')?.innerText || pre.innerText;
      try { await navigator.clipboard.writeText(code); btn.textContent='Copied!'; setTimeout(()=>btn.textContent='Copy', 1200); } catch(e){}
    };
  });
}
function setStatus(txt){ statusEl.textContent = txt; }

function addTextMsg(role, text, turnIndex=null){
  const b = el('div','msg ' + (role==='user'?'user':'assistant'));
  const meta = el('div','meta'); meta.textContent = role==='user' ? (turnIndex ? `Ty (#${turnIndex})` : 'Ty') : 'Asystent';
  const body = el('div');
  if (role === 'assistant') body.innerHTML = renderMarkdown(text);
  else body.textContent = text;
  if (turnIndex) b.id = `turn-${turnIndex}`;
  b.appendChild(meta); b.appendChild(body); chat.appendChild(b);
  chat.scrollTop = chat.scrollHeight;
  return {container:b, body};
}
function addTypingBubble(){
  const {container, body} = addTextMsg('assistant', '');
  container.classList.add('typing-bubble');
  const t = el('div','typing');
  t.innerHTML = '<span class="dot"></span><span class="dot"></span><span class="dot"></span>';
  body.appendChild(t);
  return container;
}
function replaceTypingBubble(bubble, md){
  if(!bubble) return addTextMsg('assistant', md);
  bubble.classList.remove('typing-bubble');
  const meta = bubble.querySelector('.meta'); if(meta) meta.textContent = 'Asystent';
  const body = bubble.querySelector('div:not(.meta)'); if(body) body.innerHTML = renderMarkdown(md);
  chat.scrollTop = chat.scrollHeight;
}

function addImageMsg(url, alt="Wygenerowany obraz"){
  const b = el('div','msg assistant');
  const meta = el('div','meta'); meta.textContent = 'Asystent (obraz)';
  const img = el('img','chatimg'); img.src=url; img.alt=alt;
  b.appendChild(meta); b.appendChild(img); chat.appendChild(b);
  chat.scrollTop = chat.scrollHeight;
}

// Wątki
async function refreshThreads(){
  const r = await fetch('/api/threads'); const data = await r.json();
  renderThreadList(data);
  if (threadId){
    const me = data.find(t => t.id === threadId);
    if (me){ renameInp.value = me.title || ''; memChk.checked = !!me.use_memory; }
  }
}
function renderThreadList(items){
  threadsDiv.innerHTML = "";
  for(const t of items){
    const d = el('div','th' + (t.id===threadId?' active':'')); d.textContent = t.title || t.id;
    const del = el('button','del'); del.innerHTML = '🗑️'; del.title='Usuń wątek';
    del.onclick = async (ev)=>{ ev.stopPropagation(); if(!confirm('Na pewno usunąć ten wątek?')) return;
      const r = await fetch('/api/thread/'+t.id, {method:'DELETE'});
      if(r.ok){ if(threadId===t.id){ threadId=""; chat.innerHTML=""; toc.innerHTML=""; renameInp.value=""; } refreshThreads(); }
    };
    d.appendChild(del);
    d.onclick = ()=>{ loadThread(t.id); };
    threadsDiv.appendChild(d);
  }
}
async function newThread(){
  const r = await fetch('/api/new_thread', {method:'POST'}); const js = await r.json();
  await loadThread(js.thread_id);
  addTextMsg('assistant','Utworzono nowy wątek.');
}
async function loadThread(id){
  threadId = id;
  const r = await fetch('/api/thread/'+id); const data = await r.json();
  chat.innerHTML = "";
  let ti = 0;
  for(const m of data){
    if(m.kind==='image' && typeof m.content === 'string'){ try{ m.content = JSON.parse(m.content);}catch(e){} }
    if(m.role==='user' && m.kind==='text'){ ti += 1; addTextMsg('user', m.content, ti); }
    else if(m.kind==='image' && m.content && m.content.url){ addImageMsg(m.content.url, m.content.prompt||'Obraz'); }
    else{ addTextMsg(m.role, m.content); }
  }
  await refreshThreads(); await refreshToc();
}
newBtn.onclick = newThread;

// rename
renameBtn.onclick = async ()=>{ if(!threadId) return alert("Brak bieżącego wątku.");
  const title = renameInp.value.trim();
  const r = await fetch('/api/rename_thread', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({thread_id: threadId, title})});
  if(r.ok) refreshThreads();
};
renameInp.addEventListener('keydown', (ev)=>{ if(ev.key==='Enter'){ ev.preventDefault(); renameBtn.click(); } });

// toggle memory
memChk.onchange = async ()=>{ if(!threadId) return;
  await fetch('/api/thread/use_memory', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({thread_id: threadId, use_memory: memChk.checked})});
};

// TOC / anchors
async function refreshToc(){
  toc.innerHTML = "";
  if(!threadId) return;
  const anchors = await (await fetch('/api/anchors/'+threadId)).json();
  const turns = [...chat.querySelectorAll('.msg.user')].map((_,i)=>i+1);
  for(const i of turns){
    const row = el('div','th');
    const label = anchors.find(x => x.turn_index===i)?.label || ""
    const a = el('span'); a.textContent = label ? `#${i} — ${label}` : `#${i}`;
    const edit = el('button','del'); edit.innerHTML='✏️'; edit.title='Etykieta';
    edit.onclick = async (ev)=>{ ev.stopPropagation();
      const cur = label || "";
      const val = prompt("Etykieta dla #" + i, cur);
      if(val===null) return;
      if(val.trim()===""){
        await fetch('/api/anchors', {method:'DELETE', headers:{'Content-Type':'application/json'}, body: JSON.stringify({thread_id: threadId, turn_index: i})});
      }else{
        await fetch('/api/anchors', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({thread_id: threadId, turn_index: i, label: val.trim().slice(0,120)})});
      }
      refreshToc();
    };
    row.appendChild(a); row.appendChild(edit);
    row.onclick = ()=>{ document.getElementById('turn-'+i)?.scrollIntoView({behavior:'smooth', block:'start'}); };
    toc.appendChild(row);
  }
}

// MOTYWY
function loadTheme(){ const t = localStorage.getItem('theme') || 'theme-dark'; themeSel.value = t; document.body.className = t; }
themeSel.onchange = ()=>{ localStorage.setItem('theme', themeSel.value); document.body.className = themeSel.value; };

// Głosy
async function loadVoices(){
  try{
    const r = await fetch('/api/voices'); const data = await r.json();
    const voices = data.voices || [];
    voiceSel.innerHTML = "";
    for(const v of voices){
      const opt = el('option'); opt.value=v; opt.textContent=v;
      if(v===data.default) opt.selected = true;
      voiceSel.appendChild(opt);
    }
  }catch(e){}
}

// Wyślij
async function sendText(text){
  const turn = chat.querySelectorAll('.msg.user').length+1;
  addTextMsg('user', text, turn);
  const bubble = addTypingBubble();
  setStatus('myślę…');
  sendBtn.disabled = true;
  try{
    const payload = {thread_id: threadId || null, text, web: webChk.checked, use_memory: memChk.checked};
    const r = await fetch('/api/send', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
    const raw = await r.text(); let data; try { data = JSON.parse(raw); } catch(_){ throw new Error(`HTTP ${r.status} — nie-JSON:\n${raw}`); }
    if(!r.ok) throw new Error(data?.detail || `HTTP ${r.status}`);
    if(!threadId) threadId = data.thread_id;
    replaceTypingBubble(bubble, data.reply);
    window._lastReply = data.reply;
    refreshThreads(); refreshToc();
    setStatus('gotowy');
  }catch(e){
    bubble.remove();
    addTextMsg('assistant', `**Błąd:** ${e.message}`);
    setStatus('błąd');
  } finally {
    sendBtn.disabled=false;
  }
}
sendBtn.onclick = () => { const t = inp.value.trim(); if(!t) return; inp.value=""; sendText(t); };
inp.addEventListener('keydown', (ev)=>{ if(ev.key==='Enter' && !ev.shiftKey){ ev.preventDefault(); sendBtn.click(); } });

// Obrazy
imgBtn.onclick = async ()=>{
  const prompt = inp.value.trim();
  if(!prompt){ alert("Podaj prompt do obrazu."); return; }
  setStatus('generuję obraz…');
  imgBtn.disabled = true;
  try{
    const r = await fetch('/api/image', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({thread_id: threadId || null, prompt})});
    const raw = await r.text(); let data; try { data = JSON.parse(raw); } catch(_){ throw new Error(`HTTP ${r.status} — nie-JSON:\n${raw}`); }
    if(!r.ok) throw new Error(data?.detail || `HTTP ${r.status}`);
    if(!threadId) threadId = data.thread_id;
    addImageMsg(data.url, data.prompt);
    window._lastReply = `Obraz: ${data.url}`; inp.value = "";
    refreshThreads(); refreshToc();
    setStatus('gotowy');
  }catch(e){ alert('Błąd obrazu: '+e.message); setStatus('błąd'); }
  finally{ imgBtn.disabled = false; }
};

// Nagrywanie
let mediaRecorder, chunks=[];
async function startRec(){
  const stream = await navigator.mediaDevices.getUserMedia({ audio:true });
  chunks=[]; mediaRecorder = new MediaRecorder(stream, {mimeType:'audio/webm'});
  mediaRecorder.ondataavailable = e => chunks.push(e.data);
  mediaRecorder.onstop = async ()=>{
    setStatus('transkrybuję…');
    const blob = new Blob(chunks, {type:'audio/webm'});
    const fd = new FormData(); fd.append('file', blob, 'audio.webm');
    const r = await fetch('/api/transcribe', {method:'POST', body:fd});
    const js = await r.json();
    const text = (js && js.text) ? js.text : '';
    if(text){ inp.value = text; sendText(text); } else { setStatus('gotowy'); }
  };
  mediaRecorder.start(); micBtn.classList.add('rec');
}
function stopRec(){ if(mediaRecorder){ mediaRecorder.stop(); micBtn.classList.remove('rec'); } }
micBtn.onmousedown = startRec; micBtn.onmouseup = stopRec; micBtn.onmouseleave= ()=>{ if(mediaRecorder && mediaRecorder.state==='recording') stopRec(); };

// TTS
speakBtn.onclick = async ()=>{
  const text = window._lastReply || '';
  if(!text){ alert("Brak odpowiedzi do przeczytania."); return; }
  const voice = voiceSel.value || 'alloy';
  setStatus('syntezuję…');
  const r = await fetch('/api/tts', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({text, voice})});
  const buf = await r.arrayBuffer();
  const url = URL.createObjectURL(new Blob([buf], {type:'audio/mpeg'}));
  const audio = new Audio(url); audio.play();
  setStatus('gotowy');
};

// Panel pamięci
function toggleMem(open){ memModal.classList.toggle('hidden', !open); if(open) loadMemList(); }
memPanelBtn.onclick = ()=> toggleMem(true);
memClose.onclick = ()=> toggleMem(false);
memRefresh.onclick = ()=> loadMemList();
memAdd.onclick = async ()=>{
  const value = memValue.value.trim(); if(!value) return;
  const key = memKey.value.trim() || null;
  const scope = memScope.value || 'other';
  await fetch('/api/memory/add', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key, value, scope})});
  memValue.value = ""; loadMemList();
};
async function loadMemList(){
  const active = await (await fetch('/api/memory/list?active=1')).json();
  const inactive = await (await fetch('/api/memory/list?active=0')).json();
  memList.innerHTML = "";
  const section = (title, items, isActive)=> {
    const h = document.createElement('h4'); h.textContent = title; memList.appendChild(h);
    if(items.length===0){ const p=document.createElement('div'); p.className='memitem'; p.textContent="(pusto)"; memList.appendChild(p); return; }
    for(const m of items){
      const it = document.createElement('div'); it.className='memitem';
      it.innerHTML = `<div><b>${m.key||'(brak klucza)'}</b> — <i>${m.scope}</i></div><div>${m.value}</div><div class="muted">#${m.id} • ${m.created_at}</div>`;
      const act = document.createElement('div'); act.className='actions';
      const btn = document.createElement('button'); btn.textContent = isActive ? 'Zapomnij' : 'Przywróć';
      btn.onclick = async ()=>{
        await fetch(isActive?'/api/memory/forget':'/api/memory/restore', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({id: m.id})});
        loadMemList();
      };
      act.appendChild(btn); it.appendChild(act); memList.appendChild(it);
    }
  };
  section('Aktywne', active, true);
  section('Wyłączone', inactive, false);
}

// Pliki
function showFilesModal(open){ filesModal.classList.toggle('hidden', !open); if(open) loadFilesList(); }
filesBtn.onclick = ()=> showFilesModal(true);
filesClose.onclick = ()=> showFilesModal(false);
filesUpload.onclick = ()=> fileInp.click();
fileInp.onchange = ()=>{ if(fileInp.files.length){ uploadFiles(fileInp.files); fileInp.value=""; } };

async function uploadFiles(files){
  const fd = new FormData();
  for(const f of files) fd.append('files', f);
  setStatus('upload pliku…');
  const r = await fetch('/api/files/upload', {method:'POST', body: fd});
  const js = await r.json();
  if(r.ok){
    for(const it of js.files || []){
      if(it.mime && it.mime.startsWith('image/')) addImageMsg(it.url);
      else addTextMsg('assistant', `[${it.name}](${it.url})`);
    }
    loadFilesList();
  } else {
    alert('Błąd uploadu: ' + (js.detail || r.status));
  }
  setStatus('gotowy');
}

async function loadFilesList(){
  const r = await fetch('/api/files/list'); const list = await r.json();
  filesList.innerHTML = "";
  for(const f of list){
    const row = document.createElement('div'); row.className='fileitem';
    row.innerHTML = `<div><b>${f.name}</b> <span class="muted">${(f.size/1024).toFixed(1)}kB</span></div>`;
    const act = document.createElement('div'); act.className='actions';
    const openBtn = document.createElement('button'); openBtn.textContent='Otwórz'; openBtn.onclick=()=>window.open(f.url,'_blank');
    const textBtn = document.createElement('button'); textBtn.textContent='Tekst'; textBtn.onclick=async()=>{ setStatus('parsuję…'); const rr = await fetch(`/api/files/${f.id}/text`); const jj = await rr.json(); addTextMsg('assistant', "### Tekst z pliku\n\n```\n" + (jj.text||"") + "\n```"); setStatus('gotowy'); };
    const ocrBtn = document.createElement('button'); ocrBtn.textContent='OCR'; ocrBtn.onclick=async()=>{ const lang = prompt('Języki OCR (np. pol+eng):','pol+eng') || 'pol+eng'; setStatus('OCR…'); const rr = await fetch(`/api/files/${f.id}/ocr?lang=${encodeURIComponent(lang)}`); const jj = await rr.json(); addTextMsg('assistant', "### OCR ("+lang+")\n\n```\n" + (jj.text||"") + "\n```"); setStatus('gotowy'); };
    const delBtn = document.createElement('button'); delBtn.textContent='Usuń'; delBtn.onclick=async()=>{ if(confirm('Usunąć?')){ await fetch(`/api/files/${f.id}`, {method:'DELETE'}); loadFilesList(); } };
    act.append(openBtn, textBtn, ocrBtn, delBtn); row.appendChild(act); filesList.appendChild(row);
  }
}

// Drag & drop + paste
['dragenter','dragover','dragleave','drop'].forEach(ev=> window.addEventListener(ev, e=>{ e.preventDefault(); }));
window.addEventListener('drop', e=>{ const fs = e.dataTransfer?.files; if(fs && fs.length) uploadFiles(fs); });
window.addEventListener('paste', e=>{ const items = e.clipboardData?.items || []; const arr=[]; for(const it of items){ if(it.kind==='file'){ const f=it.getAsFile(); if(f) arr.push(f); } } if(arr.length) uploadFiles(arr); });

// INIT
function init(){ const t = localStorage.getItem('theme') || 'theme-dark'; themeSel.value = t; document.body.className = t; loadVoices(); refreshThreads().then(newThread); setStatus('gotowy'); }
window.addEventListener('DOMContentLoaded', init);

