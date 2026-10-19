// Operational controls are shared by web and both native containers.
window.ToneOperations=(()=>{
  let diagnostic=null,busy=false;
  const dirtyReviews=new Set();
  const node=id=>document.getElementById(id);
  const message=text=>{node('operationStatus').textContent=text;const el=node('operationsDialogStatus');if(el)el.textContent=text;};
  async function api(path,body){
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),20000);
    try{
      const response=await fetch(path,{cache:'no-store',signal:controller.signal,...(body?{method:'POST',headers:{'Content-Type':'application/json','X-Dashboard-Action':'write'},body:JSON.stringify(body)}:{})});
      const data=await response.json();if(!response.ok)throw new Error(data.error||'No se pudo completar la operación');return data;
    }finally{clearTimeout(timer);}
  }
  function downloadButtons(r){
    if(['pending','processing'].includes(r.command?.status))return '<span class="muted">Acción pendiente de confirmar</span>';
    const actions={active:['pause','cancel'],queued:['pause','cancel'],paused:['resume','cancel'],failed:['retry'],cancelled:['retry']}[r.status]||[];
    return actions.map(action=>`<button class="button" data-job-action="${action}" data-job-id="${Number(r.id)}">${{pause:'Pausar',resume:'Reanudar',cancel:'Cancelar',retry:'Reintentar'}[action]}</button>`).join(' ');
  }
  function amuleButtons(r){return ['pause','resume','stop'].map(action=>`<button class="button" data-amule-control="${action}" data-hash="${esc(r.hash)}">${{pause:'Pausar',resume:'Reanudar',stop:'Detener'}[action]}</button>`).join(' ');}
  function reviewCard(r){
    const d=r.decision?JSON.parse(r.decision):{};
    return `<section class="panel"><div class="panel__head"><h2 class="section-title">${esc(r.name)} <small>${esc(r.status==='approved'?'Aprobado, esperando a Organizer':r.reason)}</small></h2></div><form class="operations-form" data-review-id="${Number(r.id)}"><label>Título<input name="title" value="${esc(d.title||'')}" required maxlength="180"></label><label>Categoría<select name="category"><option value="movies" ${d.category==='movies'?'selected':''}>Película</option><option value="series" ${d.category==='series'?'selected':''}>Serie</option><option value="anime" ${d.category==='anime'?'selected':''}>Anime</option></select></label>${[['year','Año'],['season','Temporada'],['episode','Episodio']].map(([name,label])=>`<label>${label}<input type="number" name="${name}" min="${name==='year'?1880:0}" max="${name==='year'?2200:99999}" value="${esc(d[name]??'')}"></label>`).join('')}<label>Recordar para nombres que contengan (opcional)<input name="pattern" maxlength="160" placeholder="Fragmento distintivo del nombre"></label><button class="button" ${r.status==='approved'?'disabled':''}>Aprobar y volver a procesar</button></form></section>`;
  }
  async function refresh(force=false){
    if(busy)return;const view=document.querySelector('.view.active')?.id;
    if(!['view-organizer','view-diagnostico','view-historial'].includes(view))return;
    busy=true;
    try{
      if(view==='view-organizer'){
        // Do not overwrite a decision while the user is editing it.
        if(!force&&(dirtyReviews.size||node('organizerReviews').contains(document.activeElement)))return;
        const d=await api('/api/organizer/reviews');node('organizerReviews').innerHTML=d.items.map(reviewCard).join('')||'<div class="empty">No hay archivos pendientes de revisión.</div>';
        const rules=await api('/api/organizer/rules');node('organizerReviews').insertAdjacentHTML('beforeend','<h2>Reglas recordadas</h2>'+table(rules.items,[['Nombre',r=>esc(r.pattern)],['Título',r=>esc(JSON.parse(r.decision).title)],['Acción',r=>`<button class="button" data-rule-remove="${Number(r.id)}">Eliminar regla</button>`]]));
      }else if(view==='view-diagnostico'){
        diagnostic=await api('/api/diagnostics');
        node('diagnosticResults').innerHTML=table([
          ...Object.entries(diagnostic.services||{}).map(([name,v])=>({name:serviceLabel(name),state:v.running?'Proceso en ejecución':'Proceso detenido'})),
          {name:'aMule',state:diagnostic.amule.available?`${diagnostic.amule.kad_nodes} nodos Kad · ${diagnostic.amule.downloads} archivos`:'Sin respuesta EC'},
          {name:'Orbit',state:diagnostic.orbit.running?'Proceso en ejecución':'Detenido'},
          ...['emby_system','emby_storage'].map(key=>({name:key==='emby_system'?'Métricas Emby':'Almacenamiento Emby',state:diagnostic[key].available?`${diagnostic[key].stale?'Último dato válido':'Lectura disponible'} · ${diagnostic[key].updated_at||'Sin fecha'}`:'Sin lectura'})),
          {name:'Copias SQLite',state:diagnostic.backups?.ok?`Verificadas · ${diagnostic.backups.checked_at}`:'Todavía no hay una copia correcta registrada'}
        ],[['Servicio',r=>esc(r.name)],['Estado',r=>esc(r.state)]]);
      }else{
        const d=await api('/api/activity');node('fileActivity').innerHTML=activityTable(d.items);
      }
    }catch(e){message(e.message);}finally{busy=false;}
  }
  function activityTable(items){return table(items,[['Fecha',r=>formatHistoryDate(new Date(r.created*1000).toISOString())],['Archivo',r=>esc(r.name)],['Estado',r=>esc(({queued:'En cola',downloading:'Descargando',downloaded:'Descargado',classifying:'Clasificando',review:'Por revisar',transferring:'Transfiriendo',incorporated:'Enviado a biblioteca Emby',failed:'Fallido',paused:'Pausado',cancelled:'Cancelado'})[r.stage]||r.stage)],['Detalle',r=>esc(r.detail)],['Acción',r=>`<button class="button" data-file-activity="${Number(r.id)}">Ver recorrido</button>`]]);}
  async function page(kind,before){
    const d=await api(`/api/${kind}${before?'?before='+encodeURIComponent(before):''}`);
    const rows=kind==='downloads'?d.history:d.items;
    node('operationsDialogBody').innerHTML=`<h2>${kind==='downloads'?'Descargas anteriores':'Historial'}</h2>`+table(rows,[['Fecha',r=>formatHistoryDate(r.created_at)],['Nombre',r=>esc(r.name||r.title||'—')],['Estado',r=>esc(statusLabel(r.status))],['Detalle',r=>esc(r.details||r.error||'')]])+(d.next_cursor?`<button class="button" data-ops-page="${kind}" data-before="${d.next_cursor}">Página anterior</button>`:'');
    if(!node('operationsDialog').open)node('operationsDialog').showModal();
  }
  async function preferences(product){
    const d=await api('/api/deals/preferences');
    node('operationsDialogBody').innerHTML=`<h2>Alertas de ${esc(({ps5:'PlayStation 5',switch2:'Nintendo Switch 2'})[product]||product)}</h2><form id="alertPreferencesForm" class="operations-form"><input type="hidden" name="product" value="${esc(product)}"><label>Destinatario<select name="chat"><option value="">Todos (regla general)</option>${d.recipients.map(chat=>`<option value="${esc(chat)}">${esc(chat)}</option>`).join('')}</select></label><label>Precio máximo (€), vacío para cualquiera<input name="target" type="number" min="0.01" step="0.01"></label><label>Bajada mínima (%)<input name="min_drop" type="number" min="0" max="100" step="0.1" value="0"></label><label><input name="restock" type="checkbox" checked> Avisar cuando vuelva el stock</label><label>Silenciar durante (horas; 0 desactiva silencio)<input name="mute_hours" type="number" min="0" max="8760" value="0"></label><p class="muted">La regla individual sustituye a la general. Los filtros de precio, bajada y stock se combinan. Guardar no reenvía ofertas anteriores.</p><button class="button">Guardar alertas</button></form>`;
    const form=node('alertPreferencesForm');
    function fill(){const p=d.preferences.find(p=>p.product===product&&p.chat===form.elements.chat.value);form.elements.target.value=p?.target_cents!=null?p.target_cents/100:'';form.elements.min_drop.value=p?.min_drop||0;form.elements.restock.checked=p?!!p.restock:true;form.elements.mute_hours.value=p?Math.max(0,Math.ceil((p.muted_until-Date.now()/1000)/3600)):0;}
    form.elements.chat.addEventListener('change',fill);fill();
    form.addEventListener('submit',async e=>{e.preventDefault();try{const f=form.elements;await api('/api/deals/preferences',{product,chat:f.chat.value,target_cents:f.target.value?Math.round(Number(f.target.value)*100):null,min_drop:Number(f.min_drop.value),restock:f.restock.checked,mute_hours:Number(f.mute_hours.value)});message('Preferencias guardadas');node('operationsDialog').close();}catch(err){message(err.message);}});
    node('operationsDialog').showModal();
  }
  document.addEventListener('input',e=>{const form=e.target.closest('[data-review-id]');if(form)dirtyReviews.add(form.dataset.reviewId);});
  document.addEventListener('submit',async e=>{
    const form=e.target.closest('[data-review-id]');if(!form)return;e.preventDefault();
    try{const f=new FormData(form),body={id:Number(form.dataset.reviewId),title:f.get('title'),category:f.get('category'),pattern:f.get('pattern')};for(const key of ['year','season','episode'])if(f.get(key))body[key]=Number(f.get(key));await api('/api/organizer/review',body);dirtyReviews.delete(form.dataset.reviewId);message('Revisión aprobada. Organizer la procesará en su siguiente ciclo.');await refresh(true);}catch(err){message(err.message);}
  });
  document.addEventListener('click',async e=>{
    const button=e.target.closest('[data-job-action],[data-amule-control],[data-ops-page],[data-alert-preferences],[data-file-activity],[data-rule-remove]');if(!button||button.disabled)return;
    const {jobAction,jobId,amuleControl,hash,opsPage,before,alertPreferences,fileActivity,ruleRemove}=button.dataset;
    if((jobAction==='cancel'||amuleControl==='stop')&&!confirm('Se detendrá esta descarga. Los archivos parciales se conservan. ¿Continuar?'))return;
    button.disabled=true;
    try{
      if(fileActivity){const d=await api('/api/activity?file='+encodeURIComponent(fileActivity));node('operationsDialogBody').innerHTML='<h2>Recorrido del archivo</h2>'+activityTable(d.items);if(!node('operationsDialog').open)node('operationsDialog').showModal();}
      else if(ruleRemove){await api('/api/organizer/rules/remove',{id:Number(ruleRemove)});message('Regla eliminada');await refresh();}
      else if(opsPage)await page(opsPage,before);
      else if(alertPreferences)await preferences(alertPreferences);
      else if(amuleControl){await api('/api/amule/control',{hash,action:amuleControl});message('aMule ha aceptado la acción. Actualizando el estado observado…');await loadAmule();}
      else{await api('/api/downloads/control',{id:Number(jobId),action:jobAction});message('Orden guardada; el estado cambiará cuando el motor la ejecute.');}
    }catch(err){message(err.message);}finally{button.disabled=false;}
  });
  node('exportDiagnostic').addEventListener('click',()=>{
    if(!diagnostic){message('Espera a que termine el diagnóstico');return;}
    const link=document.createElement('a'),url=URL.createObjectURL(new Blob([JSON.stringify(diagnostic,null,2)],{type:'application/json'}));link.href=url;link.download='tone-diagnostic.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  return Object.freeze({refresh,downloadButtons,amuleButtons});
})();

// Calendar links carry a separate, revocable read-only token; no dashboard credentials.
(()=>{
 const status=document.getElementById('animeCalendarStatus');
 document.getElementById('animeCalendarOpen').addEventListener('click',()=>{document.getElementById('animeCalendarPanel').open=true;document.getElementById('animeCalendarLoad').click();});
 document.getElementById('animeCalendarLoad').addEventListener('click',async()=>{
  try{
   const r=await fetch('/api/anime-calendar',{cache:'no-store'});if(!r.ok)throw Error('No se pudo consultar el calendario');const d=await r.json();
   const container=document.getElementById('animeCalendarEvents');container.replaceChildren();
   for(const s of d.series){
    const card=document.createElement('article');card.className='anime-card';
    const header=document.createElement('div');header.className='anime-card__header';
    const poster=document.createElement('div');poster.className='anime-card__poster';
    if(s.cover?.startsWith('https://')){const img=document.createElement('img');img.src=s.cover;img.alt='Portada de '+s.title;img.loading='lazy';img.referrerPolicy='no-referrer';poster.append(img);}
    const heading=document.createElement('div');heading.className='anime-card__heading';
    const state=document.createElement('span');state.className='anime-card__badge'+(s.status==='archived'?' is-waiting':'');state.textContent=s.status==='archived'?'Esperando temporada':'En emisión';
    const title=document.createElement('h3');title.textContent=s.title;
    const note=document.createElement('p');note.className='anime-card__note';note.textContent=s.status==='archived'?'Seguimos buscando noticias y fecha de la próxima temporada.':'Subtítulos y castellano con fechas independientes.';
    heading.append(state,title,note);header.append(poster,heading);card.append(header);
    const content=document.createElement('div');content.className='anime-card__body';
    const events=d.events.filter(e=>e.series===s.id);
    for(const e of events){
     const line=document.createElement('div');line.className='anime-card__event';
     const type=document.createElement('span');type.className='anime-card__label';type.textContent=e.version==='dub-es'?'DOBLAJE CASTELLANO':'SUBTITULADO · ESPAÑA';
     const day=document.createElement('strong');day.textContent=new Date(e.date+'T12:00:00').toLocaleDateString('es-ES',{weekday:'long',day:'numeric',month:'long'});
     const episode=document.createElement('span');episode.textContent='Temporada '+e.season+' · Episodio '+e.episode;
     line.append(type,day,episode);content.append(line);
    }
    if(!events.length){const line=document.createElement('div');line.className='anime-card__event';const label=document.createElement('span');label.className='anime-card__label';label.textContent='PRÓXIMO ESTRENO';const text=document.createElement('strong');text.textContent='Fecha por confirmar';line.append(label,text);content.append(line);}
    const dub=document.createElement('p');dub.className='anime-card__dub';dub.textContent=s.dub_status||'Castellano: pendiente de confirmación';content.append(dub);card.append(content);
    const actions=document.createElement('div');actions.className='anime-card__actions';
    for(const [label,next] of [[s.status==='archived'?'Marcar en emisión':'Esperar próxima temporada',s.status==='archived'?'active':'archived'],['Historia finalizada','finished']]){
     const button=document.createElement('button');button.className='button '+(next==='finished'?'anime-card__finish':'anime-card__archive');button.textContent=label;
     button.addEventListener('click',async()=>{if(next==='finished'&&!confirm('¿Confirmas que la historia terminó definitivamente? Si solo terminó la temporada, usa Esperar próxima temporada: seguiremos buscando su continuación.'))return;button.disabled=true;try{const response=await fetch('/api/anime-calendar/status',{method:'POST',headers:{'Content-Type':'application/json','X-Dashboard-Action':'write'},body:JSON.stringify({id:s.id,status:next,confirmed:next==='finished'})});if(!response.ok)throw Error('No se pudo guardar el estado');document.getElementById('animeCalendarLoad').click();}catch(e){status.textContent=e.message;}finally{button.disabled=false;}});actions.append(button);
    }
    card.append(actions);container.append(card);
   }
   status.textContent='Revisado: '+d.checked_at+(d.events.length?'':' · Sin fechas futuras confirmadas.');
  }catch(e){status.textContent=e.message;}
 });
 document.getElementById('animeCalendarSubscribe').addEventListener('click',async()=>{
  try{const r=await fetch('/api/anime-calendar/subscribe',{method:'POST',headers:{'X-Dashboard-Action':'write'},cache:'no-store'});if(!r.ok)throw Error('No se pudo crear la suscripción');const d=await r.json();const url=new URL(d.path,location.origin);const field=document.getElementById('animeCalendarURL');field.value=url.href;field.hidden=false;field.focus();field.select();status.textContent='Copia este enlace privado y añádelo como suscripción. Quien lo tenga podrá leer solo este calendario.';}catch(e){status.textContent=e.message;}
 });
})();
