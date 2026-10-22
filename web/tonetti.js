(() => {
  const list=document.getElementById('tonettiMessages'), form=document.getElementById('tonettiForm'), status=document.getElementById('tonettiStatus'), send=document.getElementById('tonettiSend');
  let timer=null, reading=false, rerun=false, posting=false, signature="";
  async function refresh(){
    if(reading){rerun=true;return;} reading=true;
    try{
      const data=await window.ToneAPI.json('/api/tonetti');
      const nextSignature=JSON.stringify(data.messages);
      if(nextSignature!==signature){
      signature=nextSignature;list.replaceChildren();
      for(const item of data.messages){
        const article=document.createElement('article'); article.className='tonetti-message '+item.role;
        const label=document.createElement('strong');label.textContent=item.role==='user'?'Tú':'Tonetti';
        const text=document.createElement('p');text.textContent=item.state==='pending'?'Preparando respuesta…':item.content;
        article.append(label,text);
        if(item.sources?.length){
          const details=document.createElement('details'),summary=document.createElement('summary'),refs=document.createElement('p');
          summary.textContent='Contexto recuperado';refs.textContent=[...new Set(item.sources.map(s=>s.reference))].join(' · ');details.append(summary,refs);article.append(details);
        }
        list.append(article);
      }
      if(!data.messages.length){const p=document.createElement('p');p.textContent='Pregunta por tu infraestructura, Dashboard o PS5.';list.append(p);}
      }
      send.disabled=data.busy||posting; status.textContent=data.busy?'Tonetti está pensando…':'Tonetti '+(data.version||'0.0.1')+' · '+data.model+(data.memory?' · '+data.memory.total_messages+' mensajes guardados':'');
      clearTimeout(timer);if(data.busy||document.getElementById('view-tonetti').classList.contains('active'))timer=setTimeout(refresh,data.busy?2000:5000);
    }catch(e){status.textContent=e.message;}finally{reading=false;if(rerun){rerun=false;clearTimeout(timer);timer=setTimeout(refresh,0);}}
  }
  form.addEventListener('submit',async e=>{
    e.preventDefault();if(posting)return;const input=document.getElementById('tonettiInput');if(!input.value.trim())return;
    const error=document.getElementById('tonettiError');error.hidden=true;error.textContent='';
    posting=true;send.disabled=true;
    try{await window.ToneAPI.json('/api/tonetti/chat',{message:input.value.trim()});input.value='';list.scrollTop=list.scrollHeight;}
    catch(e){error.textContent=e.message;error.hidden=false;}finally{posting=false;await refresh();}
  });
  document.addEventListener('click',e=>{if(e.target.closest('[data-phone-go="tonetti"]'))refresh();});
})();
