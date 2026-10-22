import {chromium} from 'playwright';
import {spawn} from 'node:child_process';
import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
const server=spawn('.venv/bin/python',['scripts/ui-fixture.py','8878']);let browser;
try{
  for(let i=0;i<50;i++){try{if((await fetch('http://127.0.0.1:8878/')).ok)break;}catch{}await new Promise(r=>setTimeout(r,100));}
  browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE||undefined});
  const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));let sent=false;
  await page.route('**/api/tonetti',r=>r.fulfill({json:{model:'qwen3.5:9b-q4_K_M',version:'0.0.1',memory:{total_messages:2104},busy:false,messages:sent?[{role:'user',content:'IP Emby',state:'done'},{role:'assistant',content:'Emby: 192.168.1.177 <img src=x onerror=alert(1)>',state:'done'}]:[]}}));
  await page.route('**/api/tonetti/chat',r=>{assert.equal(r.request().headers()['x-dashboard-action'],'write');sent=true;return r.fulfill({status:202,json:{accepted:true}});});
  await mkdir('test-results/tonetti',{recursive:true});
  for(const width of [320,390,768,1440,2560]){
    await page.setViewportSize({width,height:1000});await page.goto('http://127.0.0.1:8878/');
    await page.locator('#view-inicio [data-phone-go="tonetti"]').click();
    await page.locator('#tonettiInput').fill('IP Emby');await page.locator('#tonettiSend').click();
    await page.locator('#tonettiMessages').getByText('Emby: 192.168.1.177 <img src=x onerror=alert(1)>',{exact:true}).waitFor();
    assert.equal(await page.locator('#tonettiMessages img').count(),0);
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'overflow '+width);
    await page.waitForFunction(()=>!document.getElementById('tonettiSend').disabled);
    await page.screenshot({path:`test-results/tonetti/${width}.png`,fullPage:true});
  }
  assert.deepEqual(errors,[]);console.log('Tonetti: five responsive widths, navigation, send, history, escaped model output, no JS errors.');
}finally{if(browser)await browser.close();server.kill();}
