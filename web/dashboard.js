const esc=s=>String(s??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]));
function size(n){if(n==null)return "—";let v=Number(n),u=["B","KB","MB","GB","TB"],i=0;while(v>=1000&&i<u.length-1){v/=1000;i++}return `${v.toFixed(i?1:0)} ${u[i]}`}
function serviceLabel(k){return {organizer:"Organizer",telegram:"Telegram bot",viewer:"Dashboard",alerts:"Alertas"}[k]||k}
function serviceTone(running,state){if(running)return "ok";const s=String(state||"").toLowerCase();if(s.includes("loaded")||s.includes("cargado")||s.includes("exited"))return "warn";return "bad"}
function statusTone(status){const s=String(status||"").toLowerCase();if(["completed","success","done","ok"].includes(s))return "ok";if(["queued","pending","active","running","processing","quarantined"].includes(s))return "warn";return "bad"}
function categoryLabel(category){
  const labels={anime:"Anime",series:"Series",movies:"Películas"};
  return labels[String(category||"").toLowerCase()]||category||"Sin categoría";
}
function statusLabel(status){
  const s=String(status||"").toLowerCase();
  const labels={
    queued:"En cola",
    active:"Descargando",
    completed:"Completada",
    failed:"Fallida",
    success:"Correcto",
    error:"Error",
    pending:"Pendiente",
    running:"En curso",
    processing:"Procesando",
    done:"Completada",
    ok:"Correcto",
    cancelled:"Cancelada",
    canceled:"Cancelada",
    paused:"Pausada",
    quarantined:"Cuarentena",
  };
  return labels[s]||status||"—";
}
function duration(seconds){
  if(seconds==null||!isFinite(Number(seconds))||Number(seconds)<0)return "—";
  let s=Math.round(Number(seconds)),h=Math.floor(s/3600);s%=3600;let m=Math.floor(s/60);s%=60;
  if(h)return `${h} h ${m} min`;
  if(m)return `${m} min ${s} s`;
  return `${s} s`;
}
function progress(r){
  if(r.progress_percent==null)return '<span class="muted">—</span>';
  const p=Math.max(0,Math.min(100,Number(r.progress_percent)));
  const active=String(r.status).toLowerCase()==='active';
  const speed=r.speed_bps!=null&&active?` · ${size(r.speed_bps)}/s`:'';
  const eta=r.eta_seconds!=null&&active?` · quedan ~${duration(r.eta_seconds)}`:'';
  return `<div class="progress"><div class="progress-track"><div class="progress-fill" style="width:${p}%"></div></div><div class="progress-label">${p.toFixed(1)}% · ${size(r.downloaded_bytes)} / ${size(r.size_bytes)}${speed}${eta}</div></div>`;
}
function table(rows, cols){
  if(!rows.length)return '<div class="empty">Sin datos todavía.</div>';
  const head=`<thead><tr>${cols.map(c=>`<th>${esc(c[0])}</th>`).join("")}</tr></thead>`;
  const body=`<tbody>${rows.map(r=>`<tr>${cols.map(c=>`<td data-label="${esc(c[0])}">${c[1](r)}</td>`).join("")}</tr>`).join("")}</tbody>`;
  return `<table>${head}${body}</table>`;
}
function embyStorageMeta(emby){
  if(!emby.updated_at)return 'Sin fecha de lectura';
  const d=new Date(emby.updated_at);
  const when=isNaN(d)?String(emby.updated_at):d.toLocaleString('es-ES');
  return `${emby.stale?'Último dato válido':'Última lectura'} · ${when}`;
}
function formatHistoryDate(value){
  if(!value)return "—";
  const d=new Date(value);
  if(isNaN(d))return esc(String(value).replace("T"," ").replace("+00:00"," UTC"));
  return esc(d.toLocaleString("es-ES"));
}
async function loadDashboard(){
  const r=await fetch('/api/dashboard',{cache:'no-store'});
  const d=await r.json();

  document.getElementById('services').innerHTML=Object.entries(d.services).map(([k,v])=>{
    const tone=serviceTone(v.running,v.state);
    const label=v.running?'Operativo':(v.state||'parado');
    return `<div class="service-card">
      <div class="service-card__name">${esc(serviceLabel(k))}</div>
      <div class="service-card__state ${tone}"><span class="dot"></span>${esc(label)}</div>
      <div class="muted" style="margin-top:10px;font-size:12px">${v.running?'Servicio en ejecución':'Estado detectado: '+esc(v.state||'desconocido')}</div>
    </div>`;
  }).join('');

  const h=d.summary.history_24h;
  document.getElementById('hcount').textContent=h.count;
  document.getElementById('hsuccess').textContent=h.success;
  document.getElementById('herrors').textContent=h.errors;
  document.getElementById('hdownloadbytes').textContent=size(h.downloaded_bytes);document.getElementById('hmovedbytes').textContent=size(h.moved_bytes);

  document.getElementById('downloads').innerHTML=table(d.downloads,[
    ['ID',r=>'<span class="mono">#'+r.id+'</span>'],
    ['Nombre',r=>esc(r.name)],
    ['Estado',r=>`<span class="pill ${statusTone(r.status)}">${esc(statusLabel(r.status))}</span>`],
    ['Progreso',r=>progress(r)],
    ['Tamaño',r=>size(r.size_bytes)],
    ['Intento',r=>esc(r.attempt||0)]
  ]);

  document.getElementById('history').innerHTML=table(d.history,[
    ['Fecha',r=>formatHistoryDate(r.created_at)],
    ['Tipo',r=>esc(r.kind)],
    ['Estado',r=>`<span class="pill ${statusTone(r.status)}">${esc(statusLabel(r.status))}</span>`],
    ['Título',r=>esc(r.title||'—')],
    ['Categoría',r=>esc(r.category||'—')],
    ['Detalle',r=>esc(r.details||'—')]
  ]);

  const total=Number(d.disk.total||0), free=Number(d.disk.free||0), used=Math.max(0,total-free);
  const usedPct=total>0 ? Math.min(100,(used*100/total)) : 0;
  const internal=d.internal_disk||{};
  const iTotal=Number(internal.total||0),iFree=Number(internal.free||0),iUsed=Math.max(0,iTotal-iFree);
  const iPct=iTotal>0?Math.min(100,iUsed*100/iTotal):0;
  const sys=d.system||{};
  document.getElementById('sysCpu').textContent=sys.cpu_percent!=null?`${Number(sys.cpu_percent).toFixed(1)}%`:'—';
  document.getElementById('sysGpu').textContent=sys.gpu_percent!=null?`${Number(sys.gpu_percent).toFixed(1)}%`:'N/D';
  document.getElementById('sysGpuHint').textContent=sys.gpu_percent!=null?'Residencia activa GPU':(sys.powermetrics_note||'GPU no accesible');
  document.getElementById('sysRam').textContent=sys.ram_percent!=null?`${Number(sys.ram_percent).toFixed(1)}%`:'—';
  const pressure=sys.memory_free_percent!=null?` · ${Number(sys.memory_free_percent).toFixed(0)}% libre por memory_pressure`:'';
  const swap=sys.swap_used?` · swap ${size(sys.swap_used)}`:'';
  document.getElementById('sysRamHint').textContent=sys.ram_used!=null?`${size(sys.ram_used)} de ${size(sys.ram_total)}${pressure}${swap}`:'Memoria unificada';
  document.getElementById('sysTemp').textContent=sys.temperature_c!=null?`${Number(sys.temperature_c).toFixed(1)} °C`:(sys.thermal_state||'N/D');
  document.getElementById('sysTempHint').textContent=
    sys.cpu_temperature_c!=null||sys.gpu_temperature_c!=null
      ? `CPU ${sys.cpu_temperature_c!=null?Number(sys.cpu_temperature_c).toFixed(1)+' °C':'—'} · GPU ${sys.gpu_temperature_c!=null?Number(sys.gpu_temperature_c).toFixed(1)+' °C':'—'}`
      : (sys.thermal_state?`Presión térmica: ${sys.thermal_state}`:(sys.powermetrics_note||'Sensor no accesible'));
  document.getElementById('sysNet').textContent=`↓ ${size(sys.net_rx_bps||0)}/s · ↑ ${size(sys.net_tx_bps||0)}/s`;
  document.getElementById('memoryNote').textContent=sys.memory_free_percent!=null
    ? `macOS utiliza RAM libre como caché. Que el porcentaje ocupado sea alto no implica por sí solo falta de memoria; fíjate también en memory_pressure y en el uso de swap.`
    : `macOS utiliza RAM libre como caché, por lo que un porcentaje ocupado alto no implica necesariamente falta de memoria.`;
  const embySystem=d.emby_system||{};
  document.getElementById('embyCpu').textContent=embySystem.cpu_percent!=null?`${Number(embySystem.cpu_percent).toFixed(1)}%`:'—';
  document.getElementById('embyRam').textContent=embySystem.ram_percent!=null?`${Number(embySystem.ram_percent).toFixed(1)}%`:'—';
  document.getElementById('embyRamHint').textContent=embySystem.ram_used!=null?`${size(embySystem.ram_used)} de ${size(embySystem.ram_total)}`:(embySystem.error||'Sin lectura');
  document.getElementById('embyLoad').textContent=embySystem.load_1!=null?`${Number(embySystem.load_1).toFixed(2)} · ${Number(embySystem.load_5).toFixed(2)} · ${Number(embySystem.load_15).toFixed(2)}`:'—';
  document.getElementById('embySystemHint').textContent=embySystem.updated_at?`${embySystem.stale?'Último dato válido':'Última lectura'} · ${new Date(embySystem.updated_at).toLocaleString('es-ES')}`:(embySystem.error||'1 · 5 · 15 minutos');
  const emby=d.emby_disk||{};
  let embyHtml='';
  if(emby.available){
    const eTotal=Number(emby.total||0),eFree=Number(emby.free||0),eUsed=Number(emby.used||0);
    const ePct=eTotal>0?Math.min(100,eUsed*100/eTotal):0;
    embyHtml=`<div class="storage-chip">
      <strong>Servidor Emby</strong>
      <div>${size(eFree)} libres de ${size(eTotal)}</div>
      <div class="storage-bar"><div class="storage-bar__fill" style="width:${ePct}%"></div></div>
      <div class="muted" style="margin-top:10px;font-size:12px">${ePct.toFixed(1)}% usado · ${size(eUsed)} ocupados</div>
      <div class="muted" style="margin-top:6px;font-size:12px">${esc(embyStorageMeta(emby))}</div>
      ${emby.stale&&emby.last_error?`<div class="warn" style="margin-top:6px;font-size:12px">Última actualización fallida: ${esc(emby.last_error)}</div>`:''}
    </div>`;
  }else{
    embyHtml=`<div class="storage-chip">
      <strong>Servidor Emby</strong>
      <div class="warn">No se pudo consultar el espacio remoto</div>
      <div class="muted" style="margin-top:8px;font-size:12px">${esc(emby.error||'Sin información')}</div>
    </div>`;
  }
  document.getElementById('macStorage').innerHTML=`
    <div class="storage-chip">
      <strong>Disco interno · macOS</strong>
      <div class="mono">${esc(internal.path||'/')}</div>
      <div style="margin-top:8px">${size(iFree)} libres de ${size(iTotal)}</div>
      <div class="storage-bar"><div class="storage-bar__fill" style="width:${iPct}%"></div></div>
      <div class="muted" style="margin-top:10px;font-size:12px">${iPct.toFixed(1)}% usado · ${size(iUsed)} ocupados</div>
    </div>
    <div class="storage-chip">
      <strong>Disco Datos · descargas</strong>
      <div class="mono">${esc(d.disk.path)}</div>
      <div style="margin-top:8px">${size(free)} libres de ${size(total)}</div>
      <div class="storage-bar"><div class="storage-bar__fill" style="width:${usedPct}%"></div></div>
      <div class="muted" style="margin-top:10px;font-size:12px">${usedPct.toFixed(1)}% usado · ${size(used)} ocupados</div>
    </div>`;

  document.getElementById('serverStorage').innerHTML=embyHtml;


  const st=d.statistics||{};
  document.getElementById('statDownloaded').textContent=size(st.downloaded_bytes||0);
  document.getElementById('statMoved').textContent=size(st.moved_bytes||0);
  document.getElementById('statTotal').textContent=size(st.total_bytes||0);
  document.getElementById('statDownloadCount').textContent=`${st.download_count||0} descargas completadas`;
  document.getElementById('statMovedCount').textContent=`${st.moved_count||0} archivos enviados`;
  document.getElementById('statSince').textContent=st.first_event?new Date(st.first_event).toLocaleDateString('es-ES'):'—';

  document.getElementById('periodStats').innerHTML=table(st.periods||[],[
    ['Periodo',r=>esc(r.label)],
    ['Descargado',r=>size(r.downloaded_bytes)],
    ['Movido a Emby',r=>size(r.moved_bytes)],
    ['Descargas',r=>esc(r.download_count)],
    ['Archivos Emby',r=>esc(r.moved_count)]
  ]);

  document.getElementById('categoryStats').innerHTML=table(st.categories||[],[
    ['Biblioteca',r=>esc(categoryLabel(r.category))],
    ['Datos',r=>size(r.bytes)],
    ['Archivos',r=>esc(r.count)]
  ]);
  document.getElementById('updated').textContent='Actualizado · '+new Date().toLocaleTimeString('es-ES');
}

function euroPrice(cents){if(cents==null)return "—";return new Intl.NumberFormat("es-ES",{style:"currency",currency:"EUR"}).format(Number(cents)/100)}
function familyLabel(family){return family==="ean"?"Producto EAN":family==="switch2"?"Switch 2 Zelda":"PS5"}
function availabilityLabel(v){return {in_stock:"En stock",preorder:"Preventa / reserva",out_of_stock:"Agotado",unknown:"Stock por confirmar"}[v]||v||"—"}
function kindLabel(v){return {retailer:"Tienda",comparison:"Comparador",deal:"Chollo"}[v]||v||"—"}
function safeDealURL(raw){
  try{const url=new URL(raw);return ['http:','https:'].includes(url.protocol)?url.href:'#';}
  catch{return '#';}
}
function renderActiveDeals(rows,emptyText="No hay ofertas activas disponibles."){
  if(!rows.length)return `<div class="empty" style="grid-column:1/-1">${esc(emptyText)}</div>`;
  return [...rows].sort((a,b)=>Number(a.price)-Number(b.price)).map(o=>`<article class="deal-card">
    <div class="deal-card__top"><div><div class="deal-card__family">${esc(familyLabel(o.family))} · ${esc(kindLabel(o.kind))}</div><div class="deal-card__price">${esc(euroPrice(o.price))}</div></div><span class="pill ${o.availability==='unknown'?'warn':'ok'}">${esc(availabilityLabel(o.availability))}</span></div>
    <div class="deal-card__title">${esc(o.title||'Sin título')}</div>
    <div class="deal-card__meta">${esc(o.source||'—')}${o.seller?' · '+esc(o.seller):''}<br>${o.shipping!=null?'Envío: '+esc(euroPrice(o.shipping)):'Envío por confirmar'}<br>Última lectura: ${formatHistoryDate(o.seen_iso)}</div>
    <a class="deal-card__link" href="${esc(safeDealURL(o.url))}" target="_blank" rel="noopener noreferrer">Abrir oferta ↗</a>
  </article>`).join('');
}
document.getElementById('eanProductForm').addEventListener('submit',async event=>{
  event.preventDefault(); const form=event.currentTarget,button=form.querySelector('button'),message=document.getElementById('eanProductMessage');
  button.disabled=true;
  try {
    const r=await fetch('/api/deals/products',{method:'POST',headers:{'Content-Type':'application/json','X-Dashboard-Action':'write'},body:JSON.stringify({ean:document.getElementById('eanProductInput').value.trim()})});
    const d=await r.json(); if(!r.ok)throw new Error(d.error||'No se pudo guardar el producto');
    document.getElementById('eanProductInput').value='';message.textContent='Producto guardado. El seguimiento se incorpora automáticamente; la primera lectura puede tardar unos minutos.';await loadDeals();
  } catch(e){message.textContent=e.message} finally {button.disabled=false}
});
document.getElementById('eanProductCards').addEventListener('click',async event=>{
  const button=event.target.closest('[data-remove-tracking]');if(!button)return;
  const id=button.dataset.removeTracking;if(!confirm('¿Dejar de seguir '+id+'? Se conservará el historial.'))return;
  button.disabled=true;
  try {
    const r=await fetch('/api/deals/products/remove',{method:'POST',headers:{'Content-Type':'application/json','X-Dashboard-Action':'write'},body:JSON.stringify({id})});
    const d=await r.json();if(!r.ok)throw new Error(d.error||'No se pudo eliminar el producto');await loadDeals();
  }catch(e){document.getElementById('eanProductMessage').textContent=e.message;button.disabled=false}
});
document.getElementById('inactiveProducts').addEventListener('click',async event=>{
  const button=event.target.closest('[data-restore-tracking]');if(!button)return;button.disabled=true;
  try{
    const r=await fetch('/api/deals/products/restore',{method:'POST',headers:{'Content-Type':'application/json','X-Dashboard-Action':'write'},body:JSON.stringify({id:button.dataset.restoreTracking})});
    const d=await r.json();if(!r.ok)throw new Error(d.error||'No se pudo recuperar el seguimiento');await loadDeals();
  }catch(e){document.getElementById('eanProductMessage').textContent=e.message;button.disabled=false}
});
async function loadDeals(){
  const r=await fetch(`/api/deals?lines=${linesEl.value}`,{cache:'no-store'}),d=await r.json();
  const status=document.getElementById('dealStatus'),ps5=document.getElementById('activeDealsPs5'),sw=document.getElementById('activeDealsSwitch'),history=document.getElementById('dealHistory'),events=document.getElementById('dealEvents'),log=document.getElementById('dealLog');
  if(!d.available){
    status.textContent='Bot no disponible';
    const msg=`<div class="empty" style="grid-column:1/-1">${esc(d.error||'No se encuentra el bot de precios.')}</div>`;
    ps5.innerHTML=msg;
    sw.innerHTML=msg;
    history.innerHTML='<div class="empty">Sin datos.</div>';
    events.innerHTML='<div class="empty">Sin datos.</div>';
    log.textContent=d.log||'(sin log)';
    return;
  }
  const ps5Offers=d.active_offers.filter(o=>o.family==='ps5');
  const switchOffers=d.active_offers.filter(o=>o.family==='switch2');
  document.getElementById('eanProductCards').innerHTML=(d.products||[]).map(p=>`<section class="panel product-group"><div class="panel__head"><h2 class="section-title">${esc(p.name)} <small>${p.family==='ean'?'EAN '+esc(p.ean):'Seguimiento'}</small></h2><button type="button" class="button" data-remove-tracking="${esc(p.id||p.ean)}" aria-label="Dejar de seguir ${esc(p.name)}">Eliminar</button></div><div class="panel__body pad"><div class="deal-grid">${renderActiveDeals(d.active_offers.filter(o=>p.family&&p.family!=='ean'?o.family===p.family:o.ean===p.ean),'Todavía no hay ofertas verificadas para este seguimiento.')}</div></div></section>`).join('');
  document.getElementById('inactiveProducts').innerHTML=(d.inactive_products||[]).map(p=>`<button class="button" type="button" data-restore-tracking="${esc(p.id)}">Volver a seguir ${esc(p.name)}</button>`).join(' ');
  status.textContent=`${ps5Offers.length} PS5 · ${switchOffers.length} Switch Zelda`;
  ps5.innerHTML=renderActiveDeals(ps5Offers,'No hay ofertas activas de PS5.');
  sw.innerHTML=renderActiveDeals(switchOffers,'No hay ofertas activas de Switch Zelda.');
  history.innerHTML=table(d.history,[['Fecha',r=>formatHistoryDate(r.created_iso)],['Aviso',r=>esc(r.body)]]);
  events.innerHTML=table(d.events,[['Fecha',r=>formatHistoryDate(r.created_iso)],['Fuente',r=>esc(r.name)],['Estado',r=>`<span class="pill ${r.level==='error'?'bad':'ok'}">${esc(r.level==='error'?'Error':'Recuperada')}</span>`],['Detalle',r=>esc(r.detail)]]);
  const near=log.scrollHeight-log.scrollTop-log.clientHeight<80;log.textContent=d.log||'(vacío)';if(near)log.scrollTop=log.scrollHeight;
}


async function loadLogs(){
  const lines=linesEl.value;
  const r=await fetch(`/api/logs?lines=${lines}`,{cache:'no-store'});
  const d=await r.json();
  for(const [k,v] of Object.entries(d.logs)){
    const el=document.getElementById(k);
    if(!el)continue;
    const near=el.scrollHeight-el.scrollTop-el.clientHeight<80;
    el.textContent=v||'(vacío)';
    if(near)el.scrollTop=el.scrollHeight;
  }
}
const downloadForm=document.getElementById('downloadForm');
downloadForm.addEventListener('submit',async e=>{
  e.preventDefault();
  const input=document.getElementById('downloadUrl');
  const status=document.getElementById('downloadFormStatus');
  const url=input.value.trim();
  if(!url)return;
  status.textContent='Enviando solicitud al bot…';
  try{
    const r=await fetch('/api/download',{
      method:'POST',
      headers:{'Content-Type':'application/json','X-Dashboard-Action':'write'},
      body:JSON.stringify({url})
    });
    const d=await r.json();
    if(!r.ok)throw new Error(d.error||`HTTP ${r.status}`);
    status.textContent=`Solicitud #${d.request_id} enviada. El bot la procesará y notificará por Telegram.`;
    input.value='';
    setTimeout(loadDashboard,1200);
  }catch(err){
    status.textContent='Error: '+err.message;
  }
});

const torrentForm=document.getElementById('torrentForm');
torrentForm.addEventListener('submit',async e=>{
  e.preventDefault();
  const input=document.getElementById('torrentFile');
  const status=document.getElementById('torrentFormStatus');
  const file=input.files&&input.files[0];
  if(!file){status.textContent='Selecciona un archivo .torrent.';return;}
  status.textContent='Subiendo torrent…';
  try{
    const r=await fetch('/api/torrent',{
      method:'POST',
      headers:{'X-Dashboard-Action':'write','Content-Type':'application/x-bittorrent','X-Torrent-Filename':encodeURIComponent(file.name)},
      body:file
    });
    const d=await r.json();
    if(!r.ok)throw new Error(d.error||`HTTP ${r.status}`);
    status.textContent=`✅ Torrent añadido: ${d.name}`;
    input.value='';
    setTimeout(loadDashboard,800);
  }catch(err){
    status.textContent='❌ '+(err.message||err);
  }
});


// orbit-catalog-proxy v2: proxy mismo origen para Safari/iPhone, sin direcciones LAN en el cliente.
// Orbit Zero v3: cargar solo en la pestaña, sin comprobaciones HEAD.
let orbitCodeTimer,orbitCodeRequest;
function clearOrbitCode(){
 clearTimeout(orbitCodeTimer);orbitCodeRequest?.abort();
 document.getElementById('orbitPairPassword').value='';
 document.getElementById('orbitPairResult').textContent='';
}
document.getElementById('orbitReveal').addEventListener('click',()=>{
 clearOrbitCode();document.getElementById('orbitPairDialog').showModal();
 document.getElementById('orbitPairPassword').focus();
});
document.getElementById('orbitPairClose').addEventListener('click',()=>document.getElementById('orbitPairDialog').close());
document.getElementById('orbitPairDialog').addEventListener('close',clearOrbitCode);
document.addEventListener('visibilitychange',()=>{if(document.hidden){clearOrbitCode();document.getElementById('orbitPairDialog').close();}});
document.getElementById('orbitPairForm').addEventListener('submit',async e=>{
 e.preventDefault();clearTimeout(orbitCodeTimer);orbitCodeRequest?.abort();
 const secret=document.getElementById('orbitPairPassword');const password=secret.value;secret.value='';
 const output=document.getElementById('orbitPairResult');output.textContent='Consultando el Mac…';
 const request=new AbortController();orbitCodeRequest=request;
 try{
  const response=await fetch('/api/orbit/pair-code',{method:'POST',cache:'no-store',signal:request.signal,
   headers:{'Content-Type':'application/json','X-Dashboard-Action':'write','X-Orbit-Action':'reveal-code','X-Orbit-Pair-Password':password},body:'{}'});
  const data=await response.json();if(!response.ok)throw new Error(data.error||'No se pudo consultar Orbit');
  if(request.signal.aborted)return;
  output.textContent='Código vigente: '+data.code+'\nSe ocultará en 60 segundos.';
  orbitCodeTimer=setTimeout(()=>{clearOrbitCode();document.getElementById('orbitPairDialog').close();},60000);
 }catch(error){if(!request.signal.aborted)output.textContent=error.message;}
});
let orbitLoaded=false,orbitRefreshing=false;
async function orbitRefreshStatus(loadFrame=false){
 const status=document.getElementById('orbitStatus');
 const start=document.getElementById('orbitStart');
 try{
  const r=await fetch('/api/orbit/status',{cache:'no-store'});
  if(!r.ok)throw new Error('HTTP '+r.status);
  const d=await r.json();
  start.hidden=Boolean(d.running)||!d.can_start;
  if(d.running){
    status.textContent='Orbit Zero disponible en el Mac mini.';
    if(loadFrame&&!orbitLoaded){document.getElementById('orbitFrame').src='/orbit-bridge/zero/';orbitLoaded=true;}
  }else{
    status.textContent=d.can_start?'Orbit Zero no está iniciado. Pulsa «Iniciar Orbit» para abrirlo en el Mac mini.':'Orbit Zero no responde. Comprueba que está instalado y que el control de inicio está configurado.';
    if(loadFrame){document.getElementById('orbitFrame').src='about:blank';orbitLoaded=false;}
  }
 }catch(err){status.textContent='No se pudo comprobar Orbit: '+err.message;start.hidden=true;}
}
function orbitEnsureLoaded(){
 if(!orbitRefreshing){orbitRefreshing=true;orbitRefreshStatus(true).finally(()=>orbitRefreshing=false);}
}
document.getElementById('orbitRetry').addEventListener('click',()=>{orbitLoaded=false;orbitEnsureLoaded();});
document.getElementById('orbitStart').addEventListener('click',()=>{
 const dialog=document.getElementById('orbitControlDialog');
 dialog.showModal();document.getElementById('orbitControlPassword').focus();
});
document.getElementById('orbitCancelStart').addEventListener('click',()=>document.getElementById('orbitControlDialog').close());
document.getElementById('orbitControlForm').addEventListener('submit',async e=>{
 e.preventDefault();
 const secret=document.getElementById('orbitControlPassword');
 const password=secret.value; secret.value='';
 document.getElementById('orbitControlDialog').close();
 const status=document.getElementById('orbitStatus');status.textContent='Solicitando inicio de Orbit Zero…';
 try{
   const r=await fetch('/api/orbit/start',{method:'POST',headers:{'Content-Type':'application/json','X-Orbit-Control-Password':password,'X-Orbit-Action':'start'},body:'{}',credentials:'same-origin'});
   const data=await r.json();if(!r.ok)throw new Error(data.error||'HTTP '+r.status);
   status.textContent=data.running?'Orbit ya está disponible.':'Solicitud de inicio enviada. Espera unos segundos y pulsa Reconectar.';
   orbitLoaded=false;await orbitRefreshStatus(true);
 }catch(err){status.textContent='No se pudo iniciar Orbit: '+err.message;}
});

document.querySelectorAll('.tab').forEach(tab=>{
  tab.addEventListener('click',()=>{
    document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active',t===tab));
    document.querySelectorAll('.view').forEach(v=>v.classList.remove('active'));
    const target=document.getElementById(`view-${tab.dataset.view}`);
    if(target)target.classList.add('active');
    if(tab.dataset.view==='orbitzero')orbitEnsureLoaded();
    else refreshAll();
  });
});
const linesEl=document.getElementById('lines');
linesEl.addEventListener('change',()=>{loadLogs();loadDeals();});
let refreshingWeb=false;
async function refreshAll(){
  if(refreshingWeb)return;
  refreshingWeb=true;
  try{
    if(document.hidden||document.getElementById('view-orbitzero').classList.contains('active'))return;
    const tasks=[loadDashboard()];
    if(document.getElementById('view-logs').classList.contains('active'))tasks.push(loadLogs());
    if(document.getElementById('view-chollos').classList.contains('active'))tasks.push(loadDeals());
    await Promise.all(tasks);
  }catch(e){
    document.getElementById('updated').textContent='Error de actualización';
    console.error(e);
  }finally{refreshingWeb=false;}
}
refreshAll();
setInterval(refreshAll, 12000);

// Native containers call the same cleanup used when the page leaves the foreground.
window.ToneDashboard = Object.freeze({
  version: document.documentElement.dataset.version || 'unknown',
  clearSensitiveState(){
    clearOrbitCode();
    ['orbitPairDialog','orbitControlDialog'].forEach(id=>{const dialog=document.getElementById(id);if(dialog?.open)dialog.close();});
    ['orbitPairPassword','orbitControlPassword'].forEach(id=>{const input=document.getElementById(id);if(input)input.value='';});
  }
});
