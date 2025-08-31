const webChk = document.getElementById('webChk');
const memChk = document.getElementById('memChk');
const modelSel = document.getElementById('modelSel');
const voiceSel = document.getElementById('voiceSel');
const themeSel = document.getElementById('themeSel');
const memPanelBtn = document.getElementById('memPanelBtn');
const backBtn = document.getElementById('backBtn');
const memModal = document.getElementById('memModal');
const memClose = document.getElementById('memClose');
const memKey = document.getElementById('memKey');
const memValue = document.getElementById('memValue');
const memScope = document.getElementById('memScope');
const memAdd = document.getElementById('memAdd');
const memRefresh = document.getElementById('memRefresh');
const memList = document.getElementById('memList');

function loadTheme(){
  const t = localStorage.getItem('theme') || 'theme-dark';
  themeSel.value = t;
  document.body.className = t;
}
themeSel.onchange = ()=>{
  localStorage.setItem('theme', themeSel.value);
  document.body.className = themeSel.value;
};

async function loadModels(){
  try{
    const r = await fetch('/api/models');
    const data = await r.json();
    modelSel.innerHTML='';
    for(const m of data.models || []){
      const opt=document.createElement('option');
      opt.value=m; opt.textContent=m;
      modelSel.appendChild(opt);
    }
    const saved = localStorage.getItem('model');
    if(saved) modelSel.value = saved;
  }catch(e){}
}
modelSel.onchange = ()=> localStorage.setItem('model', modelSel.value);

async function loadVoices(){
  try{
    const r = await fetch('/api/voices');
    const data = await r.json();
    voiceSel.innerHTML='';
    for(const v of data.voices || []){
      const opt=document.createElement('option');
      opt.value=v; opt.textContent=v;
      voiceSel.appendChild(opt);
    }
    const saved = localStorage.getItem('voice');
    if(saved) voiceSel.value = saved;
    else if(data.default) voiceSel.value = data.default;
  }catch(e){}
}
voiceSel.onchange = ()=> localStorage.setItem('voice', voiceSel.value);

webChk.checked = localStorage.getItem('web') === '1';
webChk.onchange = ()=> localStorage.setItem('web', webChk.checked ? '1' : '0');

memChk.checked = localStorage.getItem('use_mem') !== '0';
memChk.onchange = async ()=>{
  localStorage.setItem('use_mem', memChk.checked ? '1' : '0');
  const tid = localStorage.getItem('threadId');
  if(tid){
    await fetch('/api/thread/use_memory', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({thread_id: tid, use_memory: memChk.checked})
    });
  }
};

function toggleMem(open){
  memModal.hidden = !open;
  if(open) loadMemList();
}
memPanelBtn.onclick = ()=>{ toggleMem(true); };
memClose.onclick = ()=> toggleMem(false);
memRefresh.onclick = ()=> loadMemList();
memAdd.onclick = async ()=>{
  const value = memValue.value.trim(); if(!value) return;
  const key = memKey.value.trim() || null;
  const scope = memScope.value || 'other';
  await fetch('/api/memory/add', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({key, value, scope})
  });
  memValue.value='';
  loadMemList();
};
async function loadMemList(){
  const active = await (await fetch('/api/memory/list?active=1')).json();
  const inactive = await (await fetch('/api/memory/list?active=0')).json();
  memList.innerHTML = '';
  const section = (title, items, isActive)=>{
    const h = document.createElement('h4');
    h.textContent = title; memList.appendChild(h);
    if(items.length===0){
      const p=document.createElement('div'); p.className='memitem'; p.textContent='(pusto)';
      memList.appendChild(p); return;
    }
    for(const m of items){
      const it=document.createElement('div'); it.className='memitem';
      it.innerHTML=`<div><b>${m.key||'(brak klucza)'}</b> — <i>${m.scope}</i></div><div>${m.value}</div><div class="muted">#${m.id} • ${m.created_at}</div>`;
      const act=document.createElement('div'); act.className='actions';
      const btn=document.createElement('button'); btn.textContent=isActive?'Zapomnij':'Przywróć';
      btn.onclick=async()=>{
        await fetch(isActive?'/api/memory/forget':'/api/memory/restore',{
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({id:m.id})
        });
        loadMemList();
      };
      act.appendChild(btn); it.appendChild(act); memList.appendChild(it);
    }
  };
  section('Aktywne', active, true);
  section('Wyłączone', inactive, false);
}

backBtn.onclick = ()=>{ window.location = '/'; };

function init(){
  loadTheme();
  loadModels();
  loadVoices();
}
window.addEventListener('DOMContentLoaded', init);
