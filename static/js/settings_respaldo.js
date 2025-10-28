// === Util ===
function csrftoken(){ const m=document.cookie.match(/csrftoken=([^;]+)/); return m?m[1]:''; }
// Cache simple para tipos de sensor
let SENSOR_TYPES_CACHE = null;

async function fetchSensorTypes(){
  if (SENSOR_TYPES_CACHE) return SENSOR_TYPES_CACHE;

  // Ruta principal que ya tienes en backend:
  const tryUrls = ['/api/settings/sensor-types/'];
  let lastErr = null;

  for (const u of tryUrls){
    try{
      const resp = await api(u);
      SENSOR_TYPES_CACHE = resp.results || resp;
      return SENSOR_TYPES_CACHE;
    }catch(e){
      lastErr = e;
    }
  }
  // Si fallara todo, lanza el último error
  throw lastErr || new Error('No se pudieron cargar tipos de sensor');
}

async function api(url, method='GET', body=null){
  const headers={'X-Requested-With':'XMLHttpRequest'};
  if(method!=='GET'){ headers['Content-Type']='application/json'; headers['X-CSRFToken']=csrftoken(); }
  const resp=await fetch(url,{method,headers,body:body?JSON.stringify(body):null});
  if(!resp.ok){ throw new Error(await resp.text()||`${resp.status} ${resp.statusText}`); }
  return await resp.json();
}
function el(tag, attrs={}, children=[]){
  const e=document.createElement(tag);
  Object.entries(attrs).forEach(([k,v])=>{
    if(k==='class') e.className=v; else if(k==='style') e.setAttribute('style',v); else e.setAttribute(k,v);
  });
  (Array.isArray(children)?children:[children]).forEach(c=>{ if(c==null)return; if(typeof c==='string') e.appendChild(document.createTextNode(c)); else e.appendChild(c); });
  return e;
}

// === Tabs ===
(function initTabs(){
  const tabs=document.querySelectorAll('#settings-tabs a');
  tabs.forEach(a=>{
    a.addEventListener('click',(ev)=>{
      ev.preventDefault();
      tabs.forEach(x=>x.parentElement.classList.remove('active'));
      a.parentElement.classList.add('active');
      const name=a.dataset.tab;
      document.querySelectorAll('.tab-pane').forEach(p=>p.style.display='none');
      document.getElementById('tab-'+name).style.display='block';
      if(name==='stations') loadStations();
      if(name==='sensors')  initSensorsTab();
      if(name==='policies') initPoliciesTab();
    });
  });
})();

// === Stations ===
async function loadStations(){
  const wrap=document.getElementById('stations-table');
  wrap.textContent='Cargando...';
  try{
    const data=await api('/api/settings/stations/');
    const rows=data.results||[];
    const table=el('table',{class:'table table-striped table-condensed'});
    const thead=el('thead',{},el('tr',{},[
      el('th',{},'Nombre'), el('th',{},'Empresa'), el('th',{},'Ubicación'),
      el('th',{},'Lat'), el('th',{},'Lon'), el('th',{},'Acciones')
    ]));
    const tbody=el('tbody');
    rows.forEach(r=>{
      const actions=[];
      if(window.SETTINGS_CTX.isAdmin){
        const ebtn=el('button',{class:'btn btn-xs btn-default'},'Editar');
        ebtn.onclick=()=>openStationModal(r.id);
        actions.push(ebtn);
      }else{
        actions.push(el('span',{style:'color:#6c757d'},'Solo lectura'));
      }
      const tr=el('tr',{},[
        el('td',{},r.name),
        el('td',{},r.company_name||''),
        el('td',{},r.location||''),
        el('td',{},r.latitude==null?'':String(r.latitude)),
        el('td',{},r.longitude==null?'':String(r.longitude)),
        el('td',{},actions)
      ]);
      tbody.appendChild(tr);
    });
    table.appendChild(thead); table.appendChild(tbody);
    wrap.innerHTML=''; wrap.appendChild(table);
  }catch(err){ wrap.textContent='Error: '+err.message; }
}
document.getElementById('btn-new-station')?.addEventListener('click',()=>openStationModal(null));

async function openStationModal(id){
  const isNew=(id==null);
  const modal=buildModal(isNew?'Nueva estación':'Editar estación');
  
  // ==================================================================
  // SOLUCIÓN APLICADA AQUÍ
  // La caja del modal (box) se añade DENTRO del fondo (backdrop).
  // Luego, el backdrop (que ya contiene la caja) se añade al body.
  // Esto asegura que el modal se centre correctamente.
  modal.backdrop.appendChild(modal.box);
  document.body.appendChild(modal.backdrop);
  // ==================================================================

  let companies=[];
  try{ const c=await api('/api/settings/companies/'); companies=c.results||[]; }catch(e){}

  let data={name:'',description:'',company_id:null,location:'',latitude:'',longitude:''};
  if(!isNew){ data=await api(`/api/settings/stations/${id}/`); }

  const form=el('div',{},[
    inputGroup('Nombre','name',data.name),
    inputGroup('Descripción','description',data.description),
    inputGroup('Ubicación','location',data.location),
    selectGroup('Empresa','company_id',companies.map(x=>({value:String(x.id),label:x.name})), String(data.company_id||'')),
    inputGroup('Latitud','latitude',data.latitude??'','number','step="0.000001"'),
    inputGroup('Longitud','longitude',data.longitude??'','number','step="0.000001"'),
  ]);
  modal.body.appendChild(form);

  const btn=el('button',{class:'btn btn-primary'},'Guardar');
  btn.onclick=async ()=>{
    const p=readForm(form);
    p.latitude= p.latitude===''?null:Number(p.latitude);
    p.longitude=p.longitude===''?null:Number(p.longitude);
    p.company_id=p.company_id?Number(p.company_id):null;
    try{
      if(isNew) await api('/api/settings/stations/','POST',p);
      else await api(`/api/settings/stations/${id}/`,'PUT',p);
      closeModal(modal); loadStations();
    }catch(err){ alert(err.message); }
  };
  modal.footer.appendChild(btn);
}

// === Sensores ===
async function initSensorsTab(){
  const sel=document.getElementById('sel-station-sensors');
  sel.innerHTML='';
  const data=await api('/api/settings/stations/');
  (data.results||[]).forEach(s=>{
    sel.appendChild(el('option',{value:String(s.id)}, `${s.name} — ${s.company_name||''}`));
  });
  sel.onchange=()=>loadSensorsForStation(sel.value);
  if(sel.options.length){ sel.selectedIndex=0; loadSensorsForStation(sel.value); }

  document.getElementById('btn-new-sensor')?.addEventListener('click',()=>{
    const st=sel.value; if(!st){alert('Selecciona estación');return;}
    openSensorModal(null, Number(st));
  });
}

async function loadSensorsForStation(stationId){
  const wrap=document.getElementById('sensors-table');
  wrap.textContent='Cargando...';
  try{
    const data=await api(`/api/settings/sensors/?station_id=${stationId}`);
    const rows=data.results||[];

    const table=el('table',{class:'table table-striped table-condensed'});
    const thead=el('thead',{},el('tr',{},[
      el('th',{},'Nombre'),
      el('th',{},'Unidad'),
      el('th',{},'Color'),
      el('th',{},'Site'),
      el('th',{},'Mín'),
      el('th',{},'Máx'),
      el('th',{},'Activo'),
      el('th',{},'Acciones')
    ]));
    const tbody=el('tbody');

    rows.forEach(r=>{
      const tr=el('tr');
      let tdName;
      if (window.SETTINGS_CTX.isAdmin){
        tdName = editableCell('name', r.name || '', r.id, 'text');
      } else {
        tdName = el('td',{}, r.name);
      }
      tr.appendChild(tdName);
      tr.appendChild(el('td',{}, r.unit || ''));
      const tdColor = editableCell('color', r.color || '#3b82f6', r.id, 'color');
      const tdSite  = editableCell('site',  r.site  || '',        r.id, 'text');
      const tdMin   = editableCell('min_value', r.min_value ?? '', r.id, 'number', 'step="0.0001"');
      const tdMax   = editableCell('max_value', r.max_value ?? '', r.id, 'number', 'step="0.0001"');
      const tdAct   = toggleCell('is_active', !!r.is_active, r.id);
      tr.appendChild(tdColor);
      tr.appendChild(tdSite);
      tr.appendChild(tdMin);
      tr.appendChild(tdMax);
      tr.appendChild(tdAct);
      const actions=[];
      if (window.SETTINGS_CTX.isAdmin){
        const ebtn=el('button',{class:'btn btn-xs btn-default'},'Editar');
        ebtn.onclick=()=>openSensorModal(r.id, Number(stationId));
        actions.push(ebtn);
      } else {
        actions.push(el('span',{style:'color:#6c757d'},'Editar limit.'));
      }
      tr.appendChild(el('td',{}, actions));
      tbody.appendChild(tr);
    });

    table.appendChild(thead);
    table.appendChild(tbody);
    wrap.innerHTML='';
    wrap.appendChild(table);
  }catch(err){
    wrap.textContent='Error: '+err.message;
  }
}

function editableCell(field, value, id, type='text', extra=''){
  const td=el('td');
  const inp=el('input',{class:'form-control input-sm',type,value:value==null?'':value});
  if(type==='color' && !value) inp.value='#3b82f6';
  const allowedNonAdmin=['color','site','min_value','max_value'];
  if(!window.SETTINGS_CTX.isAdmin && !allowedNonAdmin.includes(field)) inp.disabled=true;

  inp.addEventListener('change', async ()=>{
    const payload={};
    if(type==='number') payload[field]=(inp.value==='')?null:Number(inp.value);
    else payload[field]=(field==='site')? String(inp.value): inp.value;
    try{ await api(`/api/settings/sensors/${id}/`,'PUT',payload); }
    catch(err){ alert(err.message); }
  });
  td.appendChild(inp); return td;
}
function toggleCell(field, value, id){
  const td=el('td');
  const inp=el('input',{type:'checkbox'}); inp.checked=!!value;
  if(!window.SETTINGS_CTX.isAdmin) inp.disabled=true;
  inp.addEventListener('change', async ()=>{
    const payload={}; payload[field]=inp.checked;
    try{ await api(`/api/settings/sensors/${id}/`,'PUT',payload); }
    catch(err){ alert(err.message); }
  });
  td.appendChild(inp); return td;
}
async function openSensorModal(id, stationId){
  const isNew = (id == null);
  const modal = buildModal(isNew ? 'Nuevo sensor' : 'Editar sensor');

  // ==================================================================
  // SOLUCIÓN APLICADA AQUÍ TAMBIÉN
  // Mismo principio que en el modal de estaciones.
  modal.backdrop.appendChild(modal.box);
  document.body.appendChild(modal.backdrop);
  // ==================================================================

  if (!isNew){
    modal.body.appendChild(
      el('div',{class:'alert alert-info',style:'margin:0;'},
        'Usa la edición inline de la tabla para modificar.')
    );
    return;
  }

  if (!stationId){ alert('Selecciona estación primero.'); return; }

  let types = [];
  try{
    types = await fetchSensorTypes();
  }catch(e){
    console.warn('No pude cargar tipos de sensor', e);
    types = [];
  }

  const options = [{ value:'', label:'Seleccione un tipo...' }]
    .concat(types.map(t => ({
      value: String(t.id),
      label: t.unit ? `${t.name} (${t.unit})` : t.name
    })));

  const form = el('div',{},[
    inputGroup('Nombre','name',''),
    selectGroup('Tipo de sensor','sensor_type_id', options, ''),
    colorGroup('Color','color','#3b82f6'),
    inputGroup('Site','site','', 'text'),
    inputGroup('Mín','min_value','', 'number','step="0.0001"'),
    inputGroup('Máx','max_value','', 'number','step="0.0001"'),
    checkboxGroup('Activo','is_active', true),
  ]);
  modal.body.appendChild(form);

  const btn = el('button',{class:'btn btn-primary'},'Crear');
  btn.onclick = async () => {
    const p = readForm(form);
    p.station_id     = Number(stationId);
    p.sensor_type_id = p.sensor_type_id ? Number(p.sensor_type_id) : null;
    p.site           = (p.site || '').trim() || null;
    p.min_value      = (p.min_value === '' ? null : Number(p.min_value));
    p.max_value      = (p.max_value === '' ? null : Number(p.max_value));
    p.is_active      = !!p.is_active;

    if (!p.name) return alert('El nombre es obligatorio');
    if (!p.sensor_type_id) return alert('Selecciona el tipo de sensor');

    try{
      await api('/api/settings/sensors/','POST', p);
      closeModal(modal);
      await loadSensorsForStation(String(stationId));
    }catch(err){
      alert(err.message);
    }
  };
  modal.footer.appendChild(btn);
}

// === Políticas ===
async function initPoliciesTab(){
  const selSt=document.getElementById('sel-station-policies');
  selSt.innerHTML='';
  const stData=await api('/api/settings/stations/');
  (stData.results||[]).forEach(s=>{
    selSt.appendChild(el('option',{value:String(s.id)}, s.name));
  });
  selSt.onchange=()=>reloadSensorsForPolicy(selSt.value);
  if(selSt.options.length){ selSt.selectedIndex=0; reloadSensorsForPolicy(selSt.value); }

  document.getElementById('sel-sensor-policy').onchange=()=>loadPolicyForm();
}

async function reloadSensorsForPolicy(stationId){
  const sel=document.getElementById('sel-sensor-policy');
  sel.innerHTML='';
  if(!stationId) return;
  const data=await api(`/api/settings/sensors/?station_id=${stationId}`);
  (data.results||[]).forEach(s=>{
    const opt=el('option',{
      value:String(s.id),
      'data-unit': s.unit||'',
      'data-min': s.min_value==null?'':String(s.min_value),
      'data-max': s.max_value==null?'':String(s.max_value),
      'data-color': s.color||'#3b82f6'
    }, s.name);
    sel.appendChild(opt);
  });
  const wrap=document.getElementById('policy-form-wrap');
  if(sel.options.length){ sel.selectedIndex=0; await loadPolicyForm(); wrap.style.display='block'; }
  else wrap.style.display='none';
}

let gaugeChart=null;
function ensureGauge(){
  if(!gaugeChart) gaugeChart = echarts.init(document.getElementById('policy-gauge'));
  return gaugeChart;
}
function val(n){ return (n===null||n===undefined||n==='')?null:Number(n); }

async function loadPolicyForm(){
  const wrap=document.getElementById('policy-form-wrap');
  const cont=document.getElementById('policy-form');
  const sel=document.getElementById('sel-sensor-policy');
  const sensorId=Number(sel.value); if(!sensorId){ wrap.style.display='none'; return; }

  const policy=await api(`/api/settings/policy/${sensorId}/`);
  const exists=!!policy.exists;

  cont.innerHTML='';
  const isAdmin=window.SETTINGS_CTX.isAdmin;

  const allowed = isAdmin
    ? ['alert_mode','warn_low','alert_low','warn_high','alert_high','enable_low_thresholds','hysteresis','persistence_seconds','bands_active','color_warn','color_alert']
    : ['warn_low','alert_low','warn_high','alert_high'];

  const initial = exists ? policy : {
    alert_mode: 'ABS',
    warn_low:null, alert_low:null, warn_high:null, alert_high:null,
    enable_low_thresholds:true, hysteresis:null, persistence_seconds:null,
    bands_active:true, color_warn:'#f59e0b', color_alert:'#ef4444'
  };

  allowed.forEach(f=>{
    if(f==='alert_mode'){
      cont.appendChild(selectGroup('Modo alerta','alert_mode',[
        {value:'ABS', label:'Absoluto'},
        {value:'REL', label:'Relativo (%)'}
      ], initial.alert_mode));
    }else if(f==='enable_low_thresholds'){
      cont.appendChild(checkboxGroup('Habilitar umbrales bajos','enable_low_thresholds', !!initial.enable_low_thresholds));
    }else if(f==='bands_active'){
      cont.appendChild(checkboxGroup('Activar bandas (gauge)','bands_active', !!initial.bands_active));
    }else if(f==='color_warn'){
      cont.appendChild(colorGroup('Color WARN','color_warn', initial.color_warn||'#f59e0b'));
    }else if(f==='color_alert'){
      cont.appendChild(colorGroup('Color ALERT','color_alert', initial.color_alert||'#ef4444'));
    }else{
      cont.appendChild(inputGroup(f.replaceAll('_',' ').toUpperCase(), f, initial[f]??'', 'number', 'step="0.0001"'));
    }
  });

  const btn=el('button',{class:'btn btn-primary',style:'margin-top:10px;'}, exists?'Guardar cambios':'Crear política');
  btn.onclick=async ()=>{
    const p=readForm(cont);
    ['warn_low','alert_low','warn_high','alert_high','hysteresis','persistence_seconds'].forEach(k=>{
      if(k in p && p[k] !== '' && p[k] !== null) p[k]=Number(p[k]); else if(k in p) p[k]=null;
    });
    if('enable_low_thresholds' in p) p.enable_low_thresholds=!!p.enable_low_thresholds;
    if('bands_active' in p) p.bands_active=!!p.bands_active;

    try{
      if(exists) await api(`/api/settings/policy/${sensorId}/`,'PUT',p);
      else await api(`/api/settings/policy/${sensorId}/`,'POST',p);
      renderGaugePreview();
      alert('Guardado');
    }catch(err){ alert(err.message); }
  };
  cont.appendChild(btn);

  wrap.style.display='block';
  renderGaugePreview();
}

function renderGaugePreview(){
  const g=ensureGauge();
  const sel=document.getElementById('sel-sensor-policy');
  const opt=sel.options[sel.selectedIndex];
  const unit=opt.getAttribute('data-unit') || '';
  const smin=val(opt.getAttribute('data-min'));
  const smax=val(opt.getAttribute('data-max'));
  const form=document.getElementById('policy-form');
  const f = readForm(form);
  const warn_low=val(f.warn_low), alert_low=val(f.alert_low),
        warn_high=val(f.warn_high), alert_high=val(f.alert_high);
  const color_warn = f.color_warn || '#f59e0b';
  const color_alert= f.color_alert|| '#ef4444';
  let gmin=smin, gmax=smax;
  const candidates=[warn_low,alert_low,warn_high,alert_high].filter(v=>v!=null);
  if(gmin==null) gmin = candidates.length ? Math.min(...candidates) : 0;
  if(gmax==null) gmax = candidates.length ? Math.max(...candidates) : 100;
  if(gmax<=gmin){ gmax=gmin+1; }
  function ratio(v){ return Math.min(1, Math.max(0, (v - gmin)/(gmax - gmin))); }
  const stops=[];
  stops.push([0, '#d1d5db']);
  if(f.enable_low_thresholds && warn_low!=null && alert_low!=null && warn_low < alert_low){
    stops.push([ratio(warn_low), '#d1d5db']);
    stops.push([ratio(alert_low), color_warn]);
    stops.push([ratio(alert_low*0.9999), color_warn]);
    stops.push([ratio(alert_low), color_alert]);
  }
  stops.push([ratio(warn_high ?? alert_high ?? gmax), '#d1d5db']);
  if(warn_high!=null && alert_high!=null && warn_high < alert_high){
    stops.push([ratio(warn_high), color_warn]);
    stops.push([ratio(alert_high), color_alert]);
    stops.push([1, color_alert]);
  }else{
    stops.push([1, '#d1d5db']);
  }
  const option={
    series:[{
      type:'gauge',
      startAngle:210, endAngle:-30,
      min:gmin, max:gmax,
      splitNumber:5,
      progress:{show:true,width:10},
      axisLine:{ lineStyle:{ width:10, color:stops } },
      axisTick:{ show:false }, splitLine:{ show:false },
      axisLabel:{ show:true, color:'#6b7280' },
      pointer:{ show:false },
      detail:{
        formatter:()=>{
          return `WARN: ${warn_low??'—'} / ${warn_high??'—'}\nALERT: ${alert_low??'—'} / ${alert_high??'—'} ${unit}`;
        },
        color:'#111827', fontSize:12, offsetCenter:[0,'65%']
      }
    }]
  };
  g.setOption(option,true);
}

// === UI Helpers ===
function buildModal(title){
  if (!document.body.dataset.prevOverflow) {
    document.body.dataset.prevOverflow = document.body.style.overflow || '';
  }
  document.body.style.overflow = 'hidden';
  const bd = el('div',{
    style: [
      'position:fixed','inset:0','z-index:200000',
      'background:rgba(0,0,0,.45)',
      'display:flex','align-items:center','justify-content:center',
      'padding:4vh 16px'
    ].join(';')
  });
  const bx = el('div',{
    style: [
      'z-index:200001',
      'background:#fff','border:1px solid #e5e7eb','border-radius:10px',
      'width:780px','max-width:96vw',
      'max-height:92vh',
      'display:flex','flex-direction:column',
      'box-shadow:0 10px 30px rgba(0,0,0,.2)'
    ].join(';')
  });
  const hd = el('div',{
    style:'padding:12px 14px;border-bottom:1px solid #e5e7eb;display:flex;justify-content:space-between;align-items:center;'
  },[
    el('strong',{},title),
    el('button',{class:'btn btn-xs btn-default','aria-label':'Cerrar'},'×')
  ]);
  const body = el('div',{style:'padding:14px; overflow:auto; flex:1;'});
  const ft = el('div',{
    style:'padding:12px 14px;border-top:1px solid #e5e7eb;display:flex;justify-content:flex-end;gap:8px;background:#f9fafb;'
  });
  hd.lastChild.onclick = () => closeModal({backdrop: bd, box: bx});
  bx.appendChild(hd);
  bx.appendChild(body);
  bx.appendChild(ft);
  return {backdrop:bd, box:bx, body, footer:ft};
}

function closeModal(m){
  if (document.body.dataset.prevOverflow !== undefined) {
    document.body.style.overflow = document.body.dataset.prevOverflow;
    delete document.body.dataset.prevOverflow;
  }
  if (m && m.backdrop) m.backdrop.remove();
}

function inputGroup(label,name,value,type='text',extra=''){
  const g=el('div',{class:'form-group'}); g.appendChild(el('label',{},label));
  const i=el('input',{class:'form-control',name,type});
  if(extra && extra.includes('step')){ const step=extra.match(/step="([^"]+)"/); if(step) i.setAttribute('step',step[1]); }
  if(value!==undefined && value!==null) i.value=value;
  g.appendChild(i); return g;
}
function selectGroup(label,name,options,selected){
  const g=el('div',{class:'form-group'}); g.appendChild(el('label',{},label));
  const s=el('select',{class:'form-control',name});
  options.forEach(o=>{ const op=el('option',{value:o.value},o.label); if(String(o.value)===String(selected)) op.selected=true; s.appendChild(op); });
  g.appendChild(s); return g;
}
function colorGroup(label,name,value){
  const g=el('div',{class:'form-group'}); g.appendChild(el('label',{},label));
  const i=el('input',{class:'form-control',name,type:'color'}); i.value=value||'#3b82f6'; g.appendChild(i); return g;
}
function checkboxGroup(label,name,checked){
  const g=el('div',{class:'form-group'});
  const l=el('label',{},[el('input',{type:'checkbox',name,checked:checked?'checked':null}), ' '+label]);
  g.appendChild(l); return g;
}
function readForm(w){
  const out={}; w.querySelectorAll('input,select,textarea').forEach(el=>{
    if(el.type==='checkbox') out[el.name]=el.checked; else out[el.name]=el.value;
  }); return out;
}

// Inicial
loadStations();