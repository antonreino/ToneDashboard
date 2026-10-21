const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('web/dashboard.js','utf8');
const ids=['services','homeHosts','homeMetrics','amuleQueuePanel','downloadPanel','downloadInfo','historyPanel','lines'];
const nodes=new Map();let moves=0;
for(const id of ids)nodes.set(id,{id,value:'retained',closest(){return this}});
for(const id of ['phoneServicesSlot','phoneHostsSlot','phoneMetricsSlot','phoneAmuleQueueSlot','phoneDownloadSlot','phoneDownloadInfoSlot','phoneHistorySlot','phoneSettingsSlot'])nodes.set(id,{append(node){node.parent=this;moves++}});
const selections=[];
const folds=[{open:true},{open:true}];const context={phoneMedia:{matches:false},phoneMoves:[],updateNavigationSelection:view=>selections.push(view),document:{getElementById:id=>nodes.get(id),querySelector:selector=>selector==='.view.active'?{id:'view-tareas'}:null,querySelectorAll:()=>folds}};
vm.createContext(context);vm.runInContext(source.slice(source.indexOf('function applyPhoneLayout'),source.indexOf('function renderPhoneSummary')),context);
context.applyPhoneLayout();assert.equal(moves,8);
for(const mobile of [true,false,true,false]){context.phoneMedia.matches=mobile;context.applyPhoneLayout();assert.equal(moves,8);assert.equal(nodes.get('amuleQueuePanel').parent,nodes.get('phoneAmuleQueueSlot'));assert.equal(nodes.get('lines').value,'retained');assert.equal(folds[0].open,!mobile)}
assert.deepEqual(selections,['tareas','tareas','tareas','tareas','tareas']);
console.log('Shared layout: single controls and queues, repeat resize preserves values and parents, adaptive disclosures');
