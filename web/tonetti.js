(() => {
  const $=id=>document.getElementById(id),list=$('tonettiMessages'),form=$('tonettiForm'),status=$('tonettiStatus'),send=$('tonettiSend'),input=$('tonettiInput'),error=$('tonettiError'),files=$('tonettiFiles'),chips=$('tonettiAttachments'),threads=$('tonettiThreads');
  let timer=null,reading=false,rerun=false,posting=false,uploading=false,signature='',conversation=1,staged=[],allMessages=[],hasMore=false,generation=0;
  if(matchMedia('(max-width: 767px)').matches)$('tonettiHistory').open=false;
  const drafts=new Map();let elapsedTimer=null;
  function duration(seconds){return Math.max(0,Math.floor(seconds))+' s';}
  function tickElapsed(){for(const node of list.querySelectorAll('[data-started]')){const seconds=(Date.now()-Number(node.dataset.started))/1000;node.textContent='Trabajando · '+duration(seconds);}}
  elapsedTimer=setInterval(tickElapsed,1000);
  function showError(message){error.textContent=message;error.hidden=!message;}
  function attachmentNode(item,removable=false){
    const chip=document.createElement('div');chip.className='tonetti-attachment';
    if(item.kind==='image'){const img=document.createElement('img');img.src='/api/tonetti/attachment/'+item.id+'?preview=1';img.alt='Vista previa de '+item.name;img.loading='lazy';chip.append(img);}
    const label=document.createElement(removable?'span':'a');label.textContent=item.name;if(!removable){label.href='/api/tonetti/attachment/'+item.id;label.download=item.name;label.setAttribute('aria-label','Guardar '+item.name);}chip.append(label);
    if(removable){const button=document.createElement('button');button.type='button';button.textContent='×';button.setAttribute('aria-label','Quitar '+item.name);button.addEventListener('click',()=>{staged=staged.filter(x=>x.id!==item.id);renderChips();});chip.append(button);}
    return chip;
  }
  function renderChips(){chips.replaceChildren(...staged.map(item=>attachmentNode(item,true)));}
  function renderMessages(){
    const nearBottom=list.scrollHeight-list.scrollTop-list.clientHeight<120;list.replaceChildren();
    $('tonettiOlder').hidden=!hasMore;
    for(const item of allMessages){
      const article=document.createElement('article');article.className='tonetti-message '+item.role;
      const label=document.createElement('div');label.className='tonetti-message__label';label.textContent=(item.role==='user'?'Tú':'Tonetti')+(item.at?' · '+new Date(item.at).toLocaleTimeString('es-ES',{hour:'2-digit',minute:'2-digit'}):'');article.append(label);
      if(item.attachments?.length){const row=document.createElement('div');row.className='tonetti-attachment-row';for(const file of item.attachments)row.append(attachmentNode(file));article.append(row);}
      if(item.role==='assistant'){
        const timing=document.createElement('div');timing.className='tonetti-elapsed';
        if(item.state==='pending'){const started=Date.parse(item.at);if(Number.isFinite(started))timing.dataset.started=started;timing.textContent='Trabajando…';}
        else if(Number.isFinite(item.timing?.elapsed_seconds))timing.textContent=(item.state==='done'?'Trabajó durante ':'Interrumpido tras ')+duration(item.timing.elapsed_seconds);
        if(timing.textContent)article.append(timing);
      }
      const text=item.state==='pending'?(item.content||'Preparando respuesta…'):item.content;
      if(item.role==='assistant'&&item.state==='done')article.append(window.ToneMarkdown.render(text));
      else{const p=document.createElement('p');p.textContent=text;article.append(p);}
      if(item.state==='error'||item.state==='interrupted')article.classList.add('tonetti-message--error');
      if(item.sources?.length){const details=document.createElement('details'),summary=document.createElement('summary'),refs=document.createElement('p');summary.textContent='Fuentes y memoria utilizadas';refs.textContent=[...new Set(item.sources.map(s=>s.reference))].join(' · ');details.append(summary,refs);article.append(details);}
      list.append(article);
    }
    if(!allMessages.length){const welcome=document.createElement('div');welcome.className='tonetti-welcome';const title=document.createElement('h3'),p=document.createElement('p');title.textContent='¿Qué revisamos, Tone?';p.textContent='Continúa una conversación o empieza otra. El historial se conserva y la memoria relevante puede recuperarse entre conversaciones.';welcome.append(title,p);list.append(welcome);}
    tickElapsed();if(nearBottom)list.scrollTop=list.scrollHeight;
  }
  function renderThreads(data){
    threads.replaceChildren();for(const item of data.conversations||[{id:1,title:'Historial anterior'}]){const button=document.createElement('button');button.type='button';button.className='tonetti-thread';button.classList.toggle('selected',item.id===conversation);button.setAttribute('aria-current',item.id===conversation?'true':'false');button.textContent=item.title;button.title=item.title;button.addEventListener('click',()=>select(item.id));threads.append(button);}
    const current=data.conversations?.find(x=>x.id===conversation);$('tonettiTitle').textContent=current?.title||'Conversación';
  }
  function select(id){if(posting||uploading)return;drafts.set(conversation,{text:input.value,files:staged.slice()});conversation=id;const draft=drafts.get(id);input.value=draft?.text||'';staged=draft?.files?.slice()||[];generation++;allMessages=[];signature='';renderChips();showError('');if(matchMedia('(max-width: 767px)').matches)$('tonettiHistory').open=false;refresh();}
  async function refresh(){
    if(reading){rerun=true;return;}reading=true;const epoch=generation;
    try{
      const data=await window.ToneAPI.json('/api/tonetti?conversation='+conversation);if(epoch!==generation){rerun=true;return;}
      renderThreads(data);const next=JSON.stringify(data.messages);
      if(next!==signature){signature=next;const older=allMessages.filter(x=>data.messages.length&&x.id<data.messages[0].id);allMessages=older.concat(data.messages);hasMore=older.length?hasMore:!!data.has_more;renderMessages();}
      send.disabled=data.busy||posting||uploading;status.textContent=data.busy?'Respondiendo…':'Tonetti · Local';
      $('tonettiMemory').textContent=(data.memory?.total_messages||0)+' mensajes conservados · Contexto recuperado según la pregunta, no memoria ilimitada en cada respuesta.';
      clearTimeout(timer);if(data.busy||$('view-tonetti').classList.contains('active'))timer=setTimeout(refresh,data.busy?750:15000);
    }catch(e){status.textContent=e.message;}finally{reading=false;if(rerun){rerun=false;clearTimeout(timer);timer=setTimeout(refresh,0);}}
  }
  // Operations are explicit structured controls, never parsed from model text.
  let taskToken=null,taskPosting=false,taskTimer=null;
  const taskPanel=$('tonettiTaskPanel'),taskSelect=$('tonettiTaskSelect'),taskStatus=$('tonettiTaskStatus'),taskPlan=$('tonettiTaskPlan');
  taskPanel.addEventListener('toggle',async()=>{
    if(!taskPanel.open)return;
    try{const data=await window.ToneAPI.json('/api/scheduled-tasks');const selected=taskSelect.value;taskSelect.replaceChildren();
      for(const task of data.tasks||[]){const option=document.createElement('option');option.value=task.id;option.textContent=task.name+(task.enabled?'':' · Pausada');option.disabled=!task.can_run;taskSelect.append(option);}if(selected)taskSelect.value=selected;
    }catch(e){taskStatus.textContent=e.message;}
  });
  async function pollTask(){
    if(!taskToken)return;
    try{const data=await window.ToneAPI.json('/api/tonetti/task-plans/status',{token:taskToken});const result=data.result||{};const labels={ok:'Completado',partial:'Parcial',error:'Error',running:'En ejecución',unknown:'Sin confirmar',interrupted:'Interrumpido',prepared:'Preparado',not_confirmed:'Lanzamiento no confirmado',dispatching:'Sin confirmar'};taskStatus.textContent=(labels[result.state||data.plan_state]||'Sin confirmar')+' · '+(result.message||result.error||'Plan preparado; pendiente de confirmación.');
      if(result.state==='running'){clearTimeout(taskTimer);taskTimer=setTimeout(pollTask,5000);}
    }catch(e){taskStatus.textContent=e.message+' Consulta los registros antes de repetir.';}
  }
  $('tonettiTaskForm').addEventListener('submit',async e=>{
    e.preventDefault();if(taskPosting)return;taskPosting=true;clearTimeout(taskTimer);taskStatus.textContent='Preparando plan…';taskPlan.replaceChildren();taskToken=null;
    try{const plan=await window.ToneAPI.json('/api/tonetti/task-plans',{id:taskSelect.value});taskToken=plan.token;
      const title=document.createElement('h3'),description=document.createElement('p'),requirements=document.createElement('p'),checks=document.createElement('ul'),notice=document.createElement('p'),execute=document.createElement('button');
      title.textContent=plan.name;description.textContent=plan.description;requirements.textContent='Requisitos: '+plan.requirements.join(' · ');
      for(const text of plan.checks){const li=document.createElement('li');li.textContent=text;checks.append(li);}notice.textContent=plan.notice+' Ejecutor: '+plan.executor+'. Plan válido durante 10 minutos.';
      execute.type='button';execute.className='button';execute.textContent='Confirmar y ejecutar esta tarea';
      execute.addEventListener('click',async()=>{if(taskPosting)return;taskPosting=true;execute.disabled=true;
        try{const result=await window.ToneAPI.json('/api/tonetti/task-plans/execute',{token:plan.token});taskStatus.textContent=result.message;await pollTask();}
        catch(err){taskStatus.textContent=err.message+' Consulta los registros antes de preparar otro plan.';}finally{taskPosting=false;}
      });taskPlan.replaceChildren(title,description,requirements,checks,notice,execute);taskStatus.textContent='Plan preparado. No se ha ejecutado ninguna acción.';
    }catch(err){taskStatus.textContent=err.message;}finally{taskPosting=false;}
  });
  $('tonettiNew').addEventListener('click',async()=>{try{const data=await window.ToneAPI.json('/api/tonetti/conversations',{title:'Nueva conversación'});select(data.id);}catch(e){showError(e.message);}});
  $('tonettiRename').addEventListener('submit',async e=>{e.preventDefault();try{await window.ToneAPI.json('/api/tonetti/conversations',{id:conversation,title:$('tonettiName').value.trim()});$('tonettiRenamePanel').open=false;refresh();}catch(exc){showError(exc.message);}});
  $('tonettiOlder').addEventListener('click',async()=>{const epoch=generation;try{const top=list.scrollHeight,data=await window.ToneAPI.json('/api/tonetti?conversation='+conversation+'&before='+allMessages[0].id);if(epoch!==generation)return;allMessages=data.messages.concat(allMessages);hasMore=!!data.has_more;renderMessages();list.scrollTop=list.scrollHeight-top;}catch(e){showError(e.message);}});
  async function addFiles(selected){
    if(uploading||posting)return;showError('');uploading=true;send.disabled=true;
    try{for(const file of selected){if(staged.length>=4)throw Error('Máximo cuatro adjuntos por mensaje');if(file.size>8*1024*1024)throw Error('Cada archivo debe ocupar como máximo 8 MB');if(file.type.startsWith('image/')&&staged.filter(x=>x.kind==='image').length>=2)throw Error('Máximo dos fotos por mensaje');status.textContent='Preparando '+file.name+'…';const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=()=>reject(Error('No se pudo leer el archivo'));reader.readAsDataURL(file);});const result=await window.ToneAPI.json('/api/tonetti/attachments',{name:file.name,data},{timeoutMs:30000});staged.push(result);renderChips();}}
    catch(e){showError(e.message);}finally{uploading=false;files.value='';refresh();}
  }
  $('tonettiAttach').addEventListener('click',()=>files.click());files.addEventListener('change',()=>addFiles([...files.files]));
  const drop=$('tonettiWorkspace');let drag=0;
  drop.addEventListener('dragenter',e=>{if(e.dataTransfer.types.includes('Files')){e.preventDefault();drag++;drop.classList.add('tonetti-dragging');}});
  drop.addEventListener('dragover',e=>{if(e.dataTransfer.types.includes('Files'))e.preventDefault();});
  drop.addEventListener('dragleave',()=>{if(--drag<=0){drag=0;drop.classList.remove('tonetti-dragging');}});
  drop.addEventListener('drop',e=>{e.preventDefault();drag=0;drop.classList.remove('tonetti-dragging');addFiles([...e.dataTransfer.files]);});
  input.addEventListener('paste',e=>{const images=[...(e.clipboardData?.files||[])];if(images.length){e.preventDefault();addFiles(images);}});
  input.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing&&matchMedia('(min-width: 768px)').matches){e.preventDefault();form.requestSubmit();}});
  form.addEventListener('submit',async e=>{
    e.preventDefault();if(posting||uploading||send.disabled)return;const message=input.value.trim()||(staged.length?'Analiza estos adjuntos.':'');if(!message)return;showError('');posting=true;send.disabled=true;
    try{await window.ToneAPI.json('/api/tonetti/chat',{message,conversation_id:conversation,attachments:staged.map(x=>x.id)});input.value='';staged=[];drafts.delete(conversation);renderChips();list.scrollTop=list.scrollHeight;}
    catch(exc){showError(exc.message);}finally{posting=false;await refresh();}
  });
  document.addEventListener('click',e=>{if(e.target.closest('[data-phone-go="tonetti"]'))refresh();});
  window.addEventListener('pagehide',()=>{clearTimeout(timer);clearTimeout(taskTimer);clearInterval(elapsedTimer);});
})();
