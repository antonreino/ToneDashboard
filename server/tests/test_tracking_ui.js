const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(path.join(__dirname,'../../web/dashboard.js'),'utf8');
const script = source.slice(source.indexOf('function euroPrice('),source.indexOf('async function loadLogs(){'));
const nodes = new Map();
const get = id => {
  if(!nodes.has(id))nodes.set(id,{innerHTML:'',textContent:'',value:'300',scrollHeight:0,scrollTop:0,clientHeight:0,events:{},addEventListener(type,callback){this.events[type]=callback;}});
  return nodes.get(id);
};
const ps5={id:'ps5',ean:'',family:'ps5',name:'PlayStation 5'};
let data={available:true,products:[ps5,{id:'switch2',ean:'',family:'switch2',name:'Switch'},{id:'ean:0711719021247',ean:'0711719021247',family:'ean',name:'Cafetera'}],inactive_products:[],active_offers:[{family:'ps5',price:60000,title:'PS5 cara'},{family:'ps5',price:40000,title:'PS5 barata'},{family:'switch2',price:50000,title:'Switch oferta'},{family:'ean',ean:'0711719021247',price:9900,title:'Cafetera oferta'}],history:[],events:[]};
const requests=[];
const context={URL,Intl,document:{getElementById:get},linesEl:get('lines'),esc:String,formatHistoryDate:()=>'',table:()=>'',confirm:()=>true,fetch:async(url,options)=>{
  if(options?.method==='POST'){const body=JSON.parse(options.body);requests.push([url,body,options.headers]);if(url.endsWith('/remove')){assert.equal(body.id,'ps5');data.products=data.products.filter(p=>p.id!==body.id);data.inactive_products=[ps5];data.active_offers=data.active_offers.filter(o=>o.family!=='ps5');}else if(url.endsWith('/restore')){data.products.push(ps5);data.inactive_products=[];}return {ok:true,json:async()=>({ok:true})};}
  return {ok:true,json:async()=>data};
}};
vm.createContext(context);vm.runInContext(script,context);
(async()=>{
  await context.loadDeals();let html=get('eanProductCards').innerHTML;
  for(const id of ['ps5','switch2','ean:0711719021247'])assert(html.includes(`data-remove-tracking="${id}"`));
  assert(html.indexOf('PS5 barata')<html.indexOf('PS5 cara'));assert(html.includes('Switch oferta'));assert(html.includes('Cafetera oferta'));
  await get('eanProductCards').events.click({target:{closest:()=>({dataset:{removeTracking:'ps5'}})}});
  html=get('eanProductCards').innerHTML;assert(!html.includes('data-remove-tracking="ps5"'));assert(html.includes('data-remove-tracking="switch2"'));assert(html.includes('Cafetera oferta'));assert(get('inactiveProducts').innerHTML.includes('data-restore-tracking="ps5"'));
  await get('inactiveProducts').events.click({target:{closest:()=>({dataset:{restoreTracking:'ps5'}})}});
  assert(get('eanProductCards').innerHTML.includes('data-remove-tracking="ps5"'));assert.equal(get('inactiveProducts').innerHTML,'');assert(requests.every(r=>r[2]['X-Dashboard-Action']==='write'));
  console.log('Unified PS5/Switch/EAN cards: grouping, price order, removal and restore passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
