const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('web/dashboard.js','utf8'),html=fs.readFileSync('web/index.html','utf8');
const names=[...html.matchAll(/class="tab(?: active)?" data-view="([^"]+)"/g)].map(m=>m[1]);
assert.equal(names.length,0); // One shared navigation, no duplicate desktop routes.
const phoneTabs=[...html.matchAll(/data-phone-tab="([^"]+)"/g)].map(m=>m[1]);assert.deepEqual(phoneTabs,['inicio','descargas','chollos','orbitzero','mas']);
const allNames=['inicio','descargas','mas','equipos','historial','ajustes','logs','chollos','amule','orbitzero','estadisticas','organizer','diagnostico','calendario','tareas'];
const classes=active=>({active,contains(c){return c==='phone-view'?false:this.active},remove(){this.active=false},add(){this.active=true},toggle(c,on){this.active=on}});
const views=allNames.map(name=>({id:'view-'+name,classList:classes(name==='inicio')}));
const tabs=names.map(name=>({dataset:{view:name},classList:classes(name==='inicio'),addEventListener(_,fn){this.click=fn}}));
const phones=phoneTabs.map(name=>({dataset:{phoneTab:name},setAttribute(k,v){this[k]=v},removeAttribute(k){delete this[k]}}));
const desktopNames=[...html.matchAll(/data-desktop-tab="([^"]+)"/g)].map(m=>m[1]);
const desktops=desktopNames.map(name=>({dataset:{desktopTab:name},setAttribute(k,v){this[k]=v},removeAttribute(k){delete this[k]}}));
const nodes=new Map(views.map(v=>[v.id,v]));for(const id of ['phoneTitle','lines','updated','animeCalendarLoad'])nodes.set(id,{value:'300',addEventListener(){},focus(){},click(){}});
const counts={dashboard:0,logs:0,deals:0,orbit:0,amule:0,clear:0};
const context={console,document:{hidden:false,getElementById:id=>nodes.get(id),querySelectorAll:sel=>sel==='.tab'?tabs:sel==='[data-phone-tab]'?phones:sel==='[data-desktop-tab]'?desktops:views},phoneTitles:{},phoneMedia:{matches:true},window:{scrollTo(){}},clearOrbitCode:()=>counts.clear++,loadDashboard:async()=>counts.dashboard++,loadLogs:async()=>counts.logs++,loadDeals:async()=>counts.deals++,loadAmule:async()=>counts.amule++,orbitEnsureLoaded:()=>counts.orbit++,setInterval(){}};
vm.createContext(context);
vm.runInContext(source.slice(source.indexOf('function phoneGroup'),source.indexOf('function applyPhoneLayout')),context);
vm.runInContext(source.slice(source.indexOf("document.querySelectorAll('.tab').forEach"),source.indexOf('// Phone layout:')),context);
context.refreshAll();
const settle=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 await settle();assert.equal(counts.logs,0);
 for(const view of ['logs','chollos','amule','orbitzero','descargas','mas','equipos','historial','ajustes','organizer','diagnostico','calendario','tareas']){
  context.navigateDashboard(view,{focus:true});await settle();assert(views.find(v=>v.id==='view-'+view).classList.active);
  assert.equal(views.filter(v=>v.classList.active).length,1);
  assert.equal(phones.find(p=>p['aria-current']==='page').dataset.phoneTab,context.phoneGroup(view));
  assert.equal([...phones,...desktops].filter(button=>button['aria-current']==='page').length,1);
 }
 assert.equal(counts.logs,1);assert.equal(counts.deals,1);assert(counts.amule>=2);assert.equal(counts.orbit,1);assert(counts.clear>0);
 context.phoneMedia.matches=false;context.navigateDashboard('descargas');await settle();assert(views.find(v=>v.id==='view-descargas').classList.active);assert(counts.amule>=3);
 for(const view of ['calendario','tareas','logs']){
  context.navigateDashboard(view);await settle();
  assert.equal(phones.filter(button=>button['aria-current']==='page').length,0);
  assert.equal(desktops.filter(button=>button['aria-current']==='page').length,1);
  assert.equal(desktops.find(button=>button['aria-current']==='page').dataset.desktopTab,view);
  const before=JSON.stringify(counts);
  for(const mobile of [true,false,true,false]){
   context.phoneMedia.matches=mobile;context.updateNavigationSelection(view);
   assert.equal([...phones,...desktops].filter(button=>button['aria-current']==='page').length,1);
   assert.equal(phones.filter(button=>button['aria-current']==='page').length,mobile?1:0);
   assert.equal(desktops.filter(button=>button['aria-current']==='page').length,mobile?0:1);
   if(mobile)assert.equal(phones.find(button=>button['aria-current']==='page').dataset.phoneTab,'mas');
  }
  assert.equal(JSON.stringify(counts),before,'Resizing navigation must not fetch or clear state');
 }
 console.log('Navigation: shared routes, exactly one current destination across resize, lazy loading and Orbit secret clearing');
})().catch(e=>{console.error(e);process.exitCode=1});
