const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
(async () => {
  const listeners = {};
  const input = {value:'test-password-only'};
  const status = {textContent:''};
  const form = {addEventListener:(name, fn) => listeners.submit=fn};
  const forget = {addEventListener:(name, fn) => listeners.forget=fn};
  const panel = {style:{}, querySelector:q=>q==='input'?input:q==='form'?form:q==='[data-forget]'?forget:status,
    querySelectorAll:()=>[{},{}],addEventListener:(name,fn)=>listeners[name]=fn};
  let request, reloaded=0;
  const location={origin:'https://dashboard.test',reload:()=>reloaded++};
  const document={createElement:()=>panel,body:{append:()=>{}},addEventListener:(name,fn)=>listeners[name]=fn};
  const context={document,location,fetch:async(url,opts)=>{request={url,opts};return {ok:true,json:async()=>({remembered:true})};}};
  vm.runInNewContext(fs.readFileSync('orbit_devices.js','utf8'), context);
  listeners.submit({preventDefault(){}});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(input.value,'');
  assert.equal(request.url,'https://dashboard.test/api/orbit/remember');
  assert.equal(request.opts.headers['X-Orbit-Pair-Password'],'test-password-only');
  assert.equal(request.opts.credentials,'same-origin');
  assert.equal(reloaded,1);
  listeners.forget(); await new Promise(resolve=>setImmediate(resolve));
  assert.equal(request.url,'https://dashboard.test/api/orbit/forget');
  assert.equal(request.opts.headers['X-Orbit-Pair-Password'],undefined);
  input.value='must-clear';document.hidden=true;listeners.visibilitychange();assert.equal(input.value,'');
  console.log('Orbit device UI: registration, revocation and secret clearing passed');
})();
