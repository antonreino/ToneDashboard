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
  browser=await chromium.launch();const page=await browser.newPage();const errors=[];
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
      return {ratio:poster.width/poster.height,gap:buttons[1].top-buttons[0].bottom,fit:getComputedStyle(card.querySelector('img')).objectFit,top:card.getBoundingClientRect().top,title:card.querySelector('h3').getBoundingClientRect().top,note:card.querySelector('.anime-card__note').getBoundingClientRect().top,body:card.querySelector('.anime-card__events').getBoundingClientRect().top,dub:card.querySelector('.anime-card__dub').getBoundingClientRect().top,actions:card.querySelector('.anime-card__actions').getBoundingClientRect().top};
    }));
    assert.equal(layout.length,6);for(const card of layout){assert(Math.abs(card.ratio-5/7)<.01);assert(card.gap>=11);assert.equal(card.fit,'contain');}
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
  assert.deepEqual(errors,[]);
  console.log('Browser checks: responsive layouts, operations, forms, unique controls, preferences, offline warning; no JavaScript exceptions.');
}finally{if(browser)await browser.close();server.kill();}
