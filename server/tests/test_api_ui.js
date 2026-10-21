const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const requests = [];
const context = {window:{}, AbortController, setTimeout, clearTimeout, fetch: async(path, options) => {
  requests.push({path,options}); return {ok:true,json:async()=>({ok:true})};
}};
vm.createContext(context);
vm.runInContext(fs.readFileSync('web/api.js','utf8'), context);
(async () => {
  const api = context.window.ToneAPI.json;
  await api('/api/scheduled-tasks');
  assert.equal(requests[0].options.cache, 'no-store');
  assert.equal(requests[0].options.method, undefined);
  await api('/api/anime-calendar/series', {title:'Test'});
  assert.equal(requests[1].options.method, 'POST');
  assert.equal(requests[1].options.headers['X-Dashboard-Action'], 'write');
  assert.equal(JSON.parse(requests[1].options.body).title, 'Test');
  for (const path of ['https://evil.test/api/', '//evil.test/api/', '/api\\evil', '/other']) await assert.rejects(api(path), /no válida/);
  assert.equal(requests.length, 2);
  context.fetch = async() => ({ok:false,json:async()=>({error:'Consulta rechazada'})});
  await assert.rejects(api('/api/test'), /Consulta rechazada/);
  context.fetch = async() => {const error = new Error(); error.name='AbortError'; throw error;};
  await assert.rejects(api('/api/test'), /tardando demasiado/);
  await assert.rejects(api('/api/test',{}), /sin confirmación/);
  const timers=[];context.setTimeout=(_,ms)=>{timers.push(ms);return 0;};context.clearTimeout=()=>{};context.fetch=async()=>({ok:true,json:async()=>({})});
  await api('/api/anime-calendar/series',{}, {timeoutMs:60000});assert.equal(timers.at(-1),60000);
  await api('/api/test',{}, {timeoutMs:120000});assert.equal(timers.at(-1),60000);
  console.log('Shared API: same-origin paths, bounded timeouts, errors and protected writes.');
})().catch(error=>{console.error(error);process.exitCode=1;});
