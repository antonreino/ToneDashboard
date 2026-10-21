// Calendar links carry a separate, revocable read-only token; no dashboard credentials.
(()=>{
 const status=document.getElementById('animeCalendarStatus');
 const addForm=document.getElementById('animeAddForm'),addToggle=document.getElementById('animeCalendarAdd'),addTitle=document.getElementById('animeAddTitle'),addStatus=document.getElementById('animeAddStatus');
 const showAdd=show=>{addForm.hidden=!show;addToggle.setAttribute('aria-expanded',String(show));if(show)addTitle.focus();};
 addToggle.addEventListener('click',()=>showAdd(addForm.hidden));
 document.getElementById('animeAddCancel').addEventListener('click',()=>showAdd(false));
 const manage=body=>window.ToneAPI.json('/api/anime-calendar/series',body,{timeoutMs:60000});
 addForm.addEventListener('submit',async e=>{e.preventDefault();const button=addForm.querySelector('[type=submit]');button.disabled=true;addStatus.textContent='Buscando anime y descargando portada…';try{await manage({action:'add',title:addTitle.value});addForm.reset();addStatus.textContent='';showAdd(false);document.getElementById('animeCalendarLoad').click();}catch(err){addStatus.textContent=err.message;}finally{button.disabled=false;}});
 document.getElementById('animeCalendarLoad').addEventListener('click',async()=>{
  try{
   const d=await window.ToneAPI.json('/api/anime-calendar');
   const container=document.getElementById('animeCalendarEvents');container.replaceChildren();
   for(const s of d.series){
    const card=document.createElement('article');card.className='anime-card';
    const header=document.createElement('div');header.className='anime-card__header';
    const poster=document.createElement('div');poster.className='anime-card__poster';
    if(s.cover?.startsWith('https://')||/^\/api\/anime-calendar\/covers\/[a-z0-9-]+\.jpg$/.test(s.cover||'')){const img=document.createElement('img');img.src=s.cover;img.alt='Portada de '+s.title;img.loading='lazy';img.referrerPolicy='no-referrer';img.addEventListener('error',()=>{img.hidden=true;const notice=document.createElement('span');notice.className='anime-card__placeholder';notice.textContent='No se pudo cargar la portada';poster.append(notice);},{once:true});poster.append(img);}else{const placeholder=document.createElement('span');placeholder.className='anime-card__placeholder';placeholder.textContent='Portada pendiente';poster.append(placeholder);}
    const heading=document.createElement('div');heading.className='anime-card__heading';
    const state=document.createElement('span');state.className='anime-card__badge'+(s.status==='archived'?' is-waiting':'');state.textContent=s.status==='archived'?'Esperando temporada':'En emisión';
    const title=document.createElement('h3');title.textContent=s.title;
    const note=document.createElement('p');note.className='anime-card__note';note.textContent=s.season_note||(s.status==='archived'?'Seguimos buscando noticias y fecha de la próxima temporada.':'Estreno japonés y doblaje castellano por separado.');
    heading.append(state,title,note);header.append(poster,heading);card.append(header);
    const content=document.createElement('div');content.className='anime-card__body';const eventList=document.createElement('div');eventList.className='anime-card__events';content.append(eventList);
    const events=d.events.filter(e=>e.series===s.id);
    for(const e of events){
     const line=document.createElement('div');line.className='anime-card__event';
     const type=document.createElement('span');type.className='anime-card__label';type.textContent=e.version==='dub-es'?'DOBLAJE CASTELLANO':e.version==='jp-original'?'ESTRENO EN JAPÓN · JST':'SUBTITULADO · ESPAÑA';
     const day=document.createElement('strong');day.textContent=new Date(e.date+'T12:00:00').toLocaleDateString('es-ES',{weekday:'long',day:'numeric',month:'long'});
     const episode=document.createElement('span');episode.textContent='Temporada '+e.season+' · Episodio '+e.episode;
     line.append(type,day,episode);eventList.append(line);
    }
    if(!events.length){const line=document.createElement('div');line.className='anime-card__event';const label=document.createElement('span');label.className='anime-card__label';label.textContent='PRÓXIMO ESTRENO';const text=document.createElement('strong');text.textContent='Fecha por confirmar';line.append(label,text);eventList.append(line);}
    const dub=document.createElement('p');dub.className='anime-card__dub';dub.textContent=s.dub_status||'Castellano: pendiente de confirmación';content.append(dub);card.append(content);
    const actions=document.createElement('div');actions.className='anime-card__actions';
    for(const [label,next] of [[s.status==='archived'?'Marcar en emisión':'Esperar próxima temporada',s.status==='archived'?'active':'archived'],['Historia finalizada','finished']]){
     const button=document.createElement('button');button.className='button '+(next==='finished'?'anime-card__finish':'anime-card__archive');button.textContent=label;
     button.addEventListener('click',async()=>{if(next==='finished'&&!confirm('¿Confirmas que la historia terminó definitivamente? Si solo terminó la temporada, usa Esperar próxima temporada: seguiremos buscando su continuación.'))return;button.disabled=true;try{await window.ToneAPI.json('/api/anime-calendar/status',{id:s.id,status:next,confirmed:next==='finished'});document.getElementById('animeCalendarLoad').click();}catch(e){status.textContent=e.message;}finally{button.disabled=false;}});actions.append(button);
    }
    const remove=document.createElement('button');remove.className='button anime-card__remove';remove.textContent='Quitar del seguimiento';remove.setAttribute('aria-label','Quitar '+s.title+' del seguimiento');
    remove.addEventListener('click',async()=>{if(!confirm('¿Quitar '+s.title+' del seguimiento? Dejarás de recibir sus avisos y desaparecerá del calendario. Podrás añadirlo de nuevo.'))return;remove.disabled=true;try{await manage({action:'remove',id:s.id});document.getElementById('animeCalendarLoad').click();}catch(err){status.textContent=err.message;}finally{remove.disabled=false;}});
    actions.append(remove);card.append(actions);container.append(card);
   }
   status.textContent='Revisado: '+d.checked_at+(d.events.length?'':' · Sin fechas futuras confirmadas.');
  }catch(e){status.textContent=e.message;}
 });
 document.getElementById('animeCalendarSubscribe').addEventListener('click',async()=>{
  try{const d=await window.ToneAPI.json('/api/anime-calendar/subscribe',{});const url=new URL(d.path,location.origin);const field=document.getElementById('animeCalendarURL');field.value=url.href;field.hidden=false;field.focus();field.select();status.textContent='Copia este enlace privado y añádelo como suscripción. Quien lo tenga podrá leer solo este calendario.';}catch(e){status.textContent=e.message;}
 });
})();
