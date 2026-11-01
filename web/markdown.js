/* Render model Markdown using DOM nodes only. Never interpret HTML or remote images. */
(() => {
  function inline(target,text){
    const pattern=/(`[^`\n]+`|\*\*[^*\n]+\*\*|__[^_\n]+__|\*[^*\n]+\*|~~[^~\n]+~~|\[[^\]\n]+\]\([^\s)]+\))/g;
    let last=0;for(const match of text.matchAll(pattern)){
      target.append(document.createTextNode(text.slice(last,match.index)));const token=match[0];let node;
      if(token.startsWith('[')){
        const parts=/^\[([^\]]+)\]\(([^)]+)\)$/.exec(token);let url;
        try{url=new URL(parts[2]);}catch{url=null;}
        if(url&&['http:','https:'].includes(url.protocol)&&!url.username&&!url.password){node=document.createElement('a');node.href=url.href;node.rel='noopener noreferrer';node.target='_blank';node.textContent=parts[1];}
        else node=document.createTextNode(token);
      }else{
        const double=token.startsWith('**')||token.startsWith('__')||token.startsWith('~~');
        node=document.createElement(token[0]==='`'?'code':token.startsWith('~~')?'s':double?'strong':'em');node.textContent=token.slice(double?2:1,double?-2:-1);
      }
      target.append(node);last=match.index+token.length;
    }target.append(document.createTextNode(text.slice(last)));
  }
  function render(text){
    const root=document.createElement('div');root.className='tonetti-markdown';const lines=String(text).split('\n');
    for(let i=0;i<lines.length;i++){
      const line=lines[i];if(!line.trim())continue;
      if(/^\s*```/.test(line)){
        const language=line.replace(/^\s*```/,'').trim().slice(0,30);let value='';
        while(++i<lines.length&&!/^\s*```/.test(lines[i]))value+=lines[i]+'\n';
        const wrap=document.createElement('div');wrap.className='tonetti-code';const bar=document.createElement('div'),label=document.createElement('span'),copy=document.createElement('button'),pre=document.createElement('pre'),code=document.createElement('code');
        label.textContent=language||'Código';copy.type='button';copy.textContent='Copiar';copy.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(value);copy.textContent='Copiado';}catch{copy.textContent='Selecciona el código para copiar';}});bar.append(label,copy);code.textContent=value.trimEnd();pre.append(code);wrap.append(bar,pre);root.append(wrap);continue;
      }
      if(line.includes('|')&&i+1<lines.length&&/^\s*\|?\s*:?-{3,}/.test(lines[i+1])){
        const wrap=document.createElement('div'),table=document.createElement('table');wrap.className='tonetti-table';
        function row(value,head){const tr=document.createElement('tr');for(const cell of value.replace(/^\s*\||\|\s*$/g,'').split('|')){const td=document.createElement(head?'th':'td');inline(td,cell.trim());tr.append(td);}table.append(tr);}
        row(line,true);i++;while(i+1<lines.length&&lines[i+1].includes('|'))row(lines[++i],false);wrap.append(table);root.append(wrap);continue;
      }
      const heading=/^(#{1,6})\s+(.*)$/.exec(line),item=/^\s*(?:[-*+] |\d+[.)] )(.*)$/.exec(line),quote=/^>\s?(.*)$/.exec(line);
      if(item){const ordered=/^\s*\d/.test(line),tag=ordered?'ol':'ul';let list=root.lastElementChild;if(!list||list.tagName.toLowerCase()!==tag){list=document.createElement(tag);root.append(list);}const li=document.createElement('li');inline(li,item[1]);list.append(li);continue;}
      const el=document.createElement(heading?'h'+Math.min(heading[1].length+2,6):quote?'blockquote':'p');inline(el,heading?heading[2]:quote?quote[1]:line);root.append(el);
    }return root;
  }
  window.ToneMarkdown={render};
})();
