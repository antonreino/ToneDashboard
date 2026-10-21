import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdir } from 'node:fs/promises';
const server=spawn('.venv/bin/python',['scripts/ui-fixture.py','8877'],{stdio:'inherit'});
let browser;
try{
  for(let i=0;i<50;i++){
    try{const r=await fetch('http://127.0.0.1:8877/');if(r.ok)break;}catch{}
    await new Promise(r=>setTimeout(r,100));
  }
  browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE||undefined});const page=await browser.newPage();const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await mkdir('test-results/browser',{recursive:true});
  await page.goto('http://127.0.0.1:8877/');
  await page.getByText('Todo en orden',{exact:true}).waitFor();
  for(const width of [390,768,1440,2560]){
    await page.setViewportSize({width,height:1000});
    for(const name of ['Inicio','Descargas','Chollos','Más']){
      await page.locator('.phone-nav').getByRole('button',{name,exact:true}).click();
      await page.getByRole('heading',{name,exact:true,level:1}).waitFor();
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`Overflow ${name} at ${width}`);
      assert.equal(await page.locator('#amuleSearchForm').count(),1);
      await page.screenshot({path:`test-results/browser/${width}-${name}.png`,fullPage:true});
    }
    await page.getByRole('button',{name:/Revisar archivos/}).click();
    await page.getByRole('textbox',{name:'Título',exact:true}).fill('Edited title');
    await page.setViewportSize({width:width===390?1440:390,height:1000});
    assert.equal(await page.getByRole('textbox',{name:'Título',exact:true}).inputValue(),'Edited title');
    await page.screenshot({path:`test-results/browser/${width}-organizer.png`,fullPage:true});
    await page.locator('.phone-nav').getByRole('button',{name:'Más',exact:true}).click();
    await page.getByRole('button',{name:/Diagnóstico Conexiones/}).click();
    await page.getByText('Verificadas · 2026-10-17T00:00:00Z',{exact:true}).waitFor();
  }
  await page.locator('.phone-nav').getByRole('button',{name:'Chollos',exact:true}).click();
  await page.setViewportSize({width:390,height:1000});
  await page.locator('#view-chollos details:has(#dealHistory) > summary').click();
  assert(await page.locator('#dealHistory').evaluate(el=>el.closest('.panel').getBoundingClientRect().left-el.closest('details').getBoundingClientRect().left)>=12);
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:'test-results/browser/390-deal-activity.png',fullPage:true});
  await page.locator('.phone-nav').getByRole('button',{name:'Más',exact:true}).click();
  await page.getByRole('button',{name:/Equipos y servicios/}).click();
  assert(await page.locator('#homeHosts .host-panel').first().evaluate(el=>el.getBoundingClientRect().left-el.closest('details').getBoundingClientRect().left)>=12);
  await page.locator('.phone-nav').getByRole('button',{name:'Chollos',exact:true}).click();
  await page.getByRole('button',{name:'Alertas',exact:true}).click();
  await page.getByRole('heading',{name:'Alertas de PlayStation 5'}).waitFor();
  await page.getByRole('button',{name:'Cerrar ventana'}).click();
  await page.locator('.phone-nav').getByRole('button',{name:'Inicio',exact:true}).click();
  await page.route('**/api/dashboard?*',route=>route.abort());
  await page.getByRole('button',{name:'Actualizar información'}).click();
  await page.locator('#connectionNotice').waitFor({state:'visible'});
  for (const width of [390,1440]) {
    await page.setViewportSize({width,height:1000});
    await page.locator('.phone-nav').getByRole('button',{name:'Orbit',exact:true}).click();
    await page.route('**/api/orbit/pair-code', async route => {
      assert.equal(route.request().headers()['x-orbit-action'],'reveal-code');
      await route.fulfill({json:{code:'123456',console_woken:true}});
    });
    await page.locator('#orbitReveal').click();
    await page.locator('#orbitPairPassword').fill('test-only-password');
    await page.locator('#orbitPairForm button[type=submit]').click();
    await page.getByText(/PS5 encendida desde reposo/).waitFor();
    assert.equal(await page.locator('#orbitPairPassword').inputValue(),'');
    await page.locator('#orbitPairClose').click();
    await page.waitForFunction(()=>document.getElementById('orbitPairResult').textContent==='');
    await page.unroute('**/api/orbit/pair-code');
  }
  const animeFixtures=[
    {id:'aoashi',title:'Ao Ashi',status:'active',cover:'https://cover.test/aoashi.jpg',dub_status:'Sin fecha confirmada de doblaje castellano'},
    {id:'black-clover',title:'Black Clover',status:'archived',cover:'https://cover.test/black.jpg',dub_status:'Sin fecha confirmada de doblaje castellano'},
    {id:'long-title',title:'From Overshadowed to Overpowered: Second Reincarnation of a Talentless Sage',status:'archived',cover:'https://cover.test/long.jpg',season_note:'Una descripción más larga para comprobar que las notas de todas las fichas empiezan en la misma fila.',dub_status:'Castellano: pendiente'},
    {id:'tiny',title:'Una serie',status:'archived',cover:'https://cover.test/tiny.jpg'},
    {id:'other',title:'Otra historia con nombre de varias líneas y una continuación todavía sin fecha',status:'archived',cover:'https://cover.test/other.jpg'},
    {id:'cached',title:'Portada guardada',status:'archived',cover:'/api/anime-calendar/covers/cached.jpg'}
  ];
  await page.route('**/api/anime-calendar/covers/*.jpg',route=>route.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="300" height="420"><rect width="300" height="420" fill="navy"/></svg>'}));
  await page.route('**/api/anime-calendar',route=>route.fulfill({json:{checked_at:'2026-10-19',series:animeFixtures,events:[{series:'aoashi',season:2,episode:4,date:'2026-10-25',version:'jp-original'}]}}));
  await page.route('https://cover.test/**',route=>route.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="300" height="190"><rect width="300" height="190" fill="navy"/></svg>'}));
  for(const width of [390,768,1440,2560]){
    await page.setViewportSize({width,height:1000});
    await page.locator('.phone-nav').getByRole('button',{name:'Más',exact:true}).click();
    await page.locator('#animeCalendarOpen').click();
    await page.locator('.anime-card h3').getByText('Ao Ashi',{exact:true}).waitFor();
    assert.equal(await page.locator('.anime-card img').first().getAttribute('alt'),'Portada de Ao Ashi');
    assert(await page.locator('.anime-card').first().textContent().then(t=>t.includes('25 de octubre')&&t.includes('ESTRENO EN JAPÓN · JST')));
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.locator('.anime-card img').evaluateAll(images=>Promise.all(images.map(img=>{img.loading='eager';return img.decode();})));
    const layout=await page.locator('.anime-card').evaluateAll(cards=>cards.map(card=>{
      const poster=card.querySelector('.anime-card__poster').getBoundingClientRect();
      const buttons=[...card.querySelectorAll('.anime-card__actions button')].map(b=>b.getBoundingClientRect());
      return {ratio:poster.width/poster.height,buttons:buttons.map(b=>({left:b.left,right:b.right,top:b.top,bottom:b.bottom,height:b.height})),fit:getComputedStyle(card.querySelector('img')).objectFit,top:card.getBoundingClientRect().top,title:card.querySelector('h3').getBoundingClientRect().top,note:card.querySelector('.anime-card__note').getBoundingClientRect().top,body:card.querySelector('.anime-card__events').getBoundingClientRect().top,dub:card.querySelector('.anime-card__dub').getBoundingClientRect().top,actions:card.querySelector('.anime-card__actions').getBoundingClientRect().top};
    }));
    assert.equal(layout.length,6);for(const card of layout){assert(Math.abs(card.ratio-5/7)<.01);for(const button of card.buttons)assert(button.height>=44);for(let i=0;i<card.buttons.length;i++)for(let j=i+1;j<card.buttons.length;j++){const a=card.buttons[i],b=card.buttons[j];assert(a.right+11<=b.left||b.right+11<=a.left||a.bottom+11<=b.top||b.bottom+11<=a.top,'Anime actions overlap or spacing too small');}assert.equal(card.fit,'contain');}
    for(const card of layout){const row=layout.filter(other=>Math.abs(other.top-card.top)<1);for(const other of row)for(const key of ['title','note','body','dub','actions'])assert(Math.abs(card[key]-other[key])<1,`Misaligned ${key} at ${width}`);}
    await page.getByText('Esperando temporada',{exact:true}).first().waitFor();
    await page.screenshot({path:`test-results/browser/${width}-anime-calendar.png`,fullPage:true});
  }

  await page.setViewportSize({width:390,height:1000});
  let manual=[];
  await page.unroute('**/api/anime-calendar');
  await page.route('**/api/anime-calendar',route=>route.fulfill({json:{checked_at:'2026-10-19',series:manual,events:[]}}));
  await page.route('**/api/anime-calendar/series',async route=>{
    assert.equal(route.request().headers()['x-dashboard-action'],'write');
    const body=route.request().postDataJSON();
    if(body.action==='add')manual=[{id:'custom-test',title:body.title,status:'archived',cover:'/api/anime-calendar/covers/cached.jpg'}];else manual=[];
    await route.fulfill({json:{ok:true,id:'custom-test'}});
  });
  await page.locator('#animeCalendarAdd').click();
  await page.locator('#animeAddTitle').fill('Frieren <img src=x>');
  await page.locator('#animeAddForm button[type=submit]').click();
  await page.getByRole('heading',{name:'Frieren <img src=x>',exact:true}).waitFor();
  assert.equal(await page.locator('.anime-card img').count(),1);
  await page.locator('.anime-card img').evaluate(img=>img.decode());
  assert.equal(await page.locator('.anime-card img').getAttribute('src'),'/api/anime-calendar/covers/cached.jpg');
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  page.once('dialog',dialog=>dialog.dismiss());
  await page.getByRole('button',{name:'Quitar Frieren <img src=x> del seguimiento',exact:true}).click();
  assert.equal(manual.length,1);
  page.once('dialog',dialog=>dialog.accept());
  await page.getByRole('button',{name:'Quitar Frieren <img src=x> del seguimiento',exact:true}).click();
  await page.waitForFunction(()=>document.querySelectorAll('.anime-card').length===0);

  const amuleFailure='No se pudo comunicar con aMule. Reintentaremos la conexión automáticamente.';
  await page.route('**/api/amule',route=>route.fulfill({status:503,json:{error:amuleFailure}}));
  await page.route('**/api/amule/search',route=>{
    assert.equal(route.request().postDataJSON().network,'global');
    return route.fulfill({status:503,json:{error:amuleFailure}});
  });
  for(const width of [390,1440]){
    await page.setViewportSize({width,height:1000});
    await page.locator('.phone-nav').getByRole('button',{name:'Descargas',exact:true}).click();
    await page.locator('#view-descargas [data-phone-go="amule"]').click();
    await page.locator('#amuleStatus').filter({hasText:amuleFailure}).waitFor();
    assert.equal(await page.locator('#amuleNetwork').inputValue(),'global');
    assert.equal(await page.locator('#amuleNetwork option').count(),1);
    await page.locator('#amuleQuery').fill('test title');
    await page.locator('#amuleSearchForm button[type=submit]').click();
    await page.waitForFunction(()=>document.getElementById('amuleSearchForm').querySelector('button[type=submit]').disabled===false);
    assert.equal(await page.getByText(amuleFailure,{exact:true}).count(),1);
    assert.equal(await page.locator('#amuleActionStatus').textContent(),'');
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.screenshot({path:`test-results/browser/${width}-amule-error.png`,fullPage:true});
  }
  // New read-only task catalogue, preserved disclosures and safely rendered logs.
  await page.unroute('**/api/dashboard?*');
  for(const width of [320,390,600,768,1024,1440,2560]){
    await page.setViewportSize({width,height:1000});
    await page.locator('.phone-nav').getByRole('button',{name:'Inicio',exact:true}).click();
    await page.locator('#view-inicio [data-phone-go="tareas"]').click();
    await page.locator('.scheduled-card h3').getByText('Anime: Japón y avisos',{exact:true}).waitFor();
    assert.equal(await page.locator('.scheduled-card').count(),3);
    assert.equal(await page.locator('.scheduled-result small').getByText('Último resultado',{exact:true}).count(),3);
    assert.equal(await page.locator('.scheduled-follow-up').getByText(/Una incidencia antigua/).count(),1);
    assert.equal(await page.locator('.phone-nav [aria-current=page]:visible').count(),1);
    const boxes=await page.locator('.scheduled-card').evaluateAll(cards=>cards.map(card=>({top:card.getBoundingClientRect().top,meta:card.querySelector('.scheduled-meta').getBoundingClientRect().top,description:card.querySelector('.scheduled-description').getBoundingClientRect().top})));
    for(const box of boxes)for(const other of boxes.filter(b=>Math.abs(b.top-box.top)<1)){assert(Math.abs(box.meta-other.meta)<1);assert(Math.abs(box.description-other.description)<1);}
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`Task overflow at ${width}`);
    const task=page.locator('.scheduled-card').first();
    const log=task.locator('details').last();
    if(!await log.evaluate(el=>el.open))await log.locator('summary').click();
    await page.locator('#scheduledRefresh').click();
    await page.waitForFunction(()=>!document.getElementById('scheduledRefresh').disabled);
    assert(await task.locator('details').last().evaluate(el=>el.open));
    assert.equal(await page.locator('[data-task-id="future"]').getByText('Sin registros',{exact:true}).count(),2);
    assert.equal(await page.evaluate(()=>getComputedStyle(document.documentElement).colorScheme),'light');
    await page.screenshot({path:`test-results/browser/${width}-scheduled-tasks.png`,fullPage:true});
  }
  await page.route('**/api/scheduled-tasks',route=>route.fulfill({status:503,json:{error:'Sin conexión al catálogo'}}));
  await page.locator('#scheduledRefresh').click();
  await page.getByText(/Se conserva la última lectura/).waitFor();
  assert.equal(await page.locator('.scheduled-card').count(),3);
  await page.unroute('**/api/scheduled-tasks');
  await page.route('**/api/scheduled-tasks',route=>route.fulfill({json:{checked_at:'2026-10-21T12:00:00Z',summary:{total:1,active:1,paused:0,attention:0},warnings:['Catálogo parcialmente disponible'],tasks:[{id:'safe',name:'<img src=x onerror=alert(1)>',description:'Texto <script>unsafe</script>',enabled:true,status:'ok',schedule:'Cada 3 horas',executor:'Codex',logs:[{at:'invalid',status:'<script>',message:'<img src=x onerror=alert(1)>'}]}]}}));
  await page.locator('#scheduledRefresh').click();
  await page.getByRole('heading',{name:'<img src=x onerror=alert(1)>',exact:true}).waitFor();
  assert.equal(await page.locator('.scheduled-card img,.scheduled-card script').count(),0);
  await page.locator('#scheduledWarnings').filter({hasText:'Catálogo parcialmente disponible'}).waitFor();
  // Verify secondary views remain accessible and fit the viewport after redesign.
  for(const width of [390,1440]){
    await page.setViewportSize({width,height:1000});
    for(const [route,title] of [['equipos','Equipos'],['estadisticas','Estadísticas'],['historial','Historial'],['ajustes','Preferencias'],['logs','Logs']]){
      await page.locator('.phone-nav').getByRole('button',{name:'Más',exact:true}).click();
      await page.locator(`#view-mas [data-phone-go="${route}"]`).click();
      await page.getByRole('heading',{name:title,exact:true,level:1}).waitFor();
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${route} overflow ${width}`);
      assert.equal(await page.locator('.phone-nav [aria-current=page]:visible').count(),1);
      await page.screenshot({path:`test-results/browser/${width}-${route}.png`,fullPage:true});
    }
  }
  for(const route of ['calendario','tareas','logs']){
    await page.locator('.phone-nav').getByRole('button',{name:'Más',exact:true}).click();
    await page.locator(`#view-mas [data-phone-go="${route}"]`).click();
    for(const width of [390,1440,390]){await page.setViewportSize({width,height:1000});await page.waitForFunction(()=>[...document.querySelectorAll('.phone-nav [aria-current=page]')].filter(el=>el.getClientRects().length).length===1);assert.equal(await page.locator('.phone-nav [aria-current=page]:visible').count(),1);}
  }
  assert.deepEqual(errors,[]);
  console.log('Browser checks: responsive layouts, operations, forms, unique controls, preferences, offline warning; no JavaScript exceptions.');
}finally{if(browser)await browser.close();server.kill();}
