import {chromium} from 'playwright';
import {spawn} from 'node:child_process';
import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
const server=spawn('.venv/bin/python',['scripts/ui-fixture.py','8878']);let browser;
try{
  for(let i=0;i<50;i++){try{if((await fetch('http://127.0.0.1:8878/')).ok)break;}catch{}await new Promise(r=>setTimeout(r,100));}
  browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE||undefined});
  const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));let sent=false,conversations=[{id:1,title:'Historial anterior'}],message='',attachments=[];
  const reply='**Emby**: 192.168.1.177\n\n<img src=x onerror=alert(1)>\n\n```python\nprint("Tone")\n```\n\n[Inseguro](javascript:alert(1))';
  await page.route('**/api/tonetti?*',r=>{const cid=Number(new URL(r.request().url()).searchParams.get('conversation'));return r.fulfill({json:{model:'gemma4:12b',version:'0.0.7',memory:{total_messages:2104},busy:false,conversation_id:cid,conversations,messages:sent?[{id:1,role:'user',content:message,state:'done',attachments},{id:2,role:'assistant',content:reply,state:'done',timing:{elapsed_seconds:12.4}}]:[]}});});
  await page.route('**/api/tonetti/chat',r=>{assert.equal(r.request().headers()['x-dashboard-action'],'write');const data=r.request().postDataJSON();assert.equal(data.conversation_id,1);message=data.message;sent=true;return r.fulfill({status:202,json:{accepted:true}});});
  await page.route('**/api/tonetti/conversations',r=>{const data=r.request().postDataJSON();if(data.id)conversations.find(x=>x.id===data.id).title=data.title;else conversations.push({id:2,title:data.title});return r.fulfill({json:{id:data.id||2}});});
  await page.route('**/api/tonetti/attachments',r=>r.fulfill({status:201,json:{id:'a'.repeat(32),name:'nota.txt',kind:'document'}}));
  let launches=0;
  await page.route('**/api/scheduled-tasks',r=>r.fulfill({json:{tasks:[{id:'dashboard-backups',name:'Copias verificadas',enabled:true,can_run:true}]}}));
  await page.route('**/api/tonetti/task-plans',r=>{assert.deepEqual(r.request().postDataJSON(),{id:'dashboard-backups'});return r.fulfill({status:201,json:{token:'a'.repeat(48),name:'Copias verificadas',description:'Copias consistentes',requirements:['Mac disponible'],checks:['Validar integridad'],notice:'Sin ejecutar',executor:'Dashboard'}});});
  await page.route('**/api/tonetti/task-plans/execute',r=>{assert.deepEqual(r.request().postDataJSON(),{token:'a'.repeat(48)});launches++;return r.fulfill({status:202,json:{message:'Iniciada'}});});
  await page.route('**/api/tonetti/task-plans/status',r=>r.fulfill({json:{plan_state:'accepted',result:{state:'partial',message:'Prueba sintética: falta validar copia'}}}));
  await mkdir('test-results/tonetti',{recursive:true});
  for(const width of [320,390,768,1440,2560,3440]){
    sent=false;conversations=[{id:1,title:'Historial anterior'}];await page.setViewportSize({width,height:1000});await page.goto('http://127.0.0.1:8878/');
    await page.locator('#view-inicio [data-phone-go="tonetti"]').click();
    await page.locator('.tonetti-options>summary').click();await page.locator('#tonettiTaskPanel summary').click();await page.locator('#tonettiTaskSelect option[value="dashboard-backups"]').waitFor({state:'attached'});
    await page.locator('#tonettiTaskForm button').click();await page.locator('#tonettiTaskPlan h3').waitFor();assert.equal(launches,0);
    await page.locator('#tonettiTaskPlan button').click();assert(await page.locator('#tonettiTaskPlan button').isDisabled());await page.locator('#tonettiTaskPlan button').evaluate(button=>button.click());await page.locator('#tonettiTaskStatus').getByText('Parcial · Prueba sintética: falta validar copia').waitFor();assert.equal(launches,1);launches=0;
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'plan overflow '+width);
    await page.screenshot({path:`test-results/tonetti/plan-${width}.png`,fullPage:true});await page.locator('#tonettiTaskPanel summary').click();await page.locator('.tonetti-options>summary').click();
    await page.locator('#tonettiFiles').setInputFiles({name:'nota.txt',mimeType:'text/plain',buffer:Buffer.from('Nota Tone')});await page.locator('#tonettiAttachments').getByText('nota.txt').waitFor();
    await page.locator('#tonettiAttachments').getByRole('button',{name:'Quitar nota.txt'}).click();
    await page.evaluate(()=>{const transfer=new DataTransfer();transfer.items.add(new File(['Nota Tone'],'nota.txt',{type:'text/plain'}));document.getElementById('tonettiWorkspace').dispatchEvent(new DragEvent('drop',{bubbles:true,dataTransfer:transfer}));});
    await page.locator('#tonettiAttachments').getByText('nota.txt').waitFor();
    await page.locator('#tonettiInput').fill('IP Emby');await page.waitForFunction(()=>!document.getElementById('tonettiSend').disabled);await page.locator('#tonettiSend').click();
    await page.locator('#tonettiMessages strong').getByText('Emby',{exact:true}).waitFor();
    await page.locator('.tonetti-elapsed').getByText('Trabajó durante 12 s').waitFor();
    assert.equal(await page.locator('#tonettiMessages img').count(),0);assert.equal(await page.locator('#tonettiMessages a[href^="javascript:"]').count(),0);assert.equal(await page.locator('#tonettiMessages pre code').textContent(),'print("Tone")');
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'overflow '+width);
    await page.screenshot({path:`test-results/tonetti/${width}.png`,fullPage:true});
    await page.locator('#tonettiNew').click();await page.waitForFunction(()=>document.querySelector('#tonettiThreads [aria-current="true"]')?.textContent==='Nueva conversación');
    await page.locator('#tonettiRenamePanel summary').click();await page.locator('#tonettiName').fill('Red de casa');await page.locator('#tonettiRename button').click();await page.locator('#tonettiTitle').getByText('Red de casa').waitFor();
    if(width<768)await page.locator('#tonettiHistory summary').click();await page.locator('#tonettiThreads').getByText('Historial anterior').click();await page.locator('#tonettiTitle').getByText('Historial anterior').waitFor();
  }
  // Pending text is visible, the timer advances, and Markdown is applied only on completion.
  await page.unroute('**/api/tonetti?*');let pending=true;const began=new Date(Date.now()-5000).toISOString();
  await page.route('**/api/tonetti?*',r=>r.fulfill({json:{busy:pending,conversations:[{id:1,title:'Flujo sintético'}],memory:{total_messages:2},messages:[{id:2,role:'assistant',content:pending?'Texto progresivo':'**Texto final**',state:pending?'pending':'done',at:began,timing:pending?{}:{elapsed_seconds:6.1}}]}}));
  await page.goto('http://127.0.0.1:8878/');await page.locator('#view-inicio [data-phone-go="tonetti"]').click();
  await page.getByText('Texto progresivo',{exact:true}).waitFor();assert.match(await page.locator('.tonetti-elapsed').textContent(),/Trabajando · \d+ s/);assert(await page.locator('#tonettiSend').isDisabled());
  pending=false;await page.locator('#tonettiMessages strong').getByText('Texto final',{exact:true}).waitFor();await page.getByText('Trabajó durante 6 s',{exact:true}).waitFor();
  assert.deepEqual(errors,[]);console.log('Tonetti: six widths, picker/drop attachments, Markdown/code, XSS safety, create/rename/resume conversations, no JS errors.');
}finally{if(browser)await browser.close();server.kill();}
