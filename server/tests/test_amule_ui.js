const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('web/dashboard.js','utf8');
const chunk=source.slice(source.indexOf('// aMule: structured'),source.indexOf("document.querySelectorAll('.tab')"));
const nodes={},calls=[],pending=[];
function node(id){return nodes[id]||= {value:'',textContent:'',innerHTML:'',dataset:{},classList:{contains:()=>false},addEventListener(name,fn){this[name]=fn},querySelector(){return this.button||={disabled:false}}};}
const context={console,AbortController,Set,JSON,document:{hidden:false,getElementById:node},setInterval(){},setTimeout(){return 1},clearTimeout(){},fetch:async(path,opts)=>{calls.push({path,opts});return pending.shift()||{ok:true,json:async()=>({ok:true})}}};
vm.createContext(context);vm.runInContext(source.slice(0,source.indexOf('async function loadDashboard()')),context);vm.runInContext(chunk,context);
const hash='0123456789abcdef0123456789abcdef';
const snapshot={ok:true,search_id:'session',query:'<unsafe>',total:1,results:[{hash,name:'<script>alert(1)</script>.mkv',size:1024,sources:10}],downloads:[],kad_nodes:20,download_speed:1,upload_speed:2};
(async()=>{
 pending.push({ok:true,json:async()=>snapshot});await vm.runInContext('loadAmule()',context);
 assert.match(node('amuleResults').innerHTML,/&lt;script&gt;/);assert(!node('amuleResults').innerHTML.includes('<script>'));assert(node('amuleResultsTitle').textContent.includes('<unsafe>'));
 node('amuleQuery').value=' a title ';node('amuleNetwork').value='kad';node('amuleType').value='Video';
 const form=node('amuleSearchForm');pending.push({ok:true,json:async()=>({search_id:'session'})},{ok:true,json:async()=>snapshot});
 await form.submit({preventDefault(){},currentTarget:form});
 const search=calls.find(c=>c.path==='/api/amule/search');assert.deepEqual(JSON.parse(search.opts.body),{query:'a title',network:'kad',type:'Video'});assert.equal(search.opts.headers['X-Dashboard-Action'],'write');assert(!form.button.disabled);
 const button={dataset:{amuleHash:hash},disabled:false};pending.push({ok:true,json:async()=>({ok:true,already_queued:true})},{ok:true,json:async()=>snapshot});
 await node('amuleResults').click({target:{closest:()=>button}});
 const download=calls.find(c=>c.path==='/api/amule/download');assert.deepEqual(JSON.parse(download.opts.body),{hash,search_id:'session'});assert.match(node('amuleActionStatus').textContent,/ya está en la cola/);
 pending.push({ok:false,json:async()=>({error:'aMule cerrado'})});await vm.runInContext('loadAmule()',context);assert.match(node('amuleStatus').textContent,/cerrado/);
 const count=calls.length;await node('amuleResults').click({target:{closest:()=>button}});assert.equal(calls.length,count);
 console.log('aMule UI: safe rendering, search request, hash-based download, duplicate message, disconnected-state action guard');
})().catch(e=>{console.error(e);process.exitCode=1});
