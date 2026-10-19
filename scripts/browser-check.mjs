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
  assert.deepEqual(errors,[]);
  console.log('Browser checks: responsive layouts, operations, forms, unique controls, preferences, offline warning; no JavaScript exceptions.');
}finally{if(browser)await browser.close();server.kill();}
