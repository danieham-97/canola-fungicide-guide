const fs=require('fs'),vm=require('vm'),assert=require('assert/strict'),crypto=require('crypto');
const html=fs.readFileSync('public/index.html','utf8');
const data=JSON.parse(fs.readFileSync('data/reviewed.json','utf8'));
const cloudConfig=JSON.parse(html.match(/id="cloud-config">(.*?)<\/script>/s)[1]);
const ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);
assert.equal(ids.length,new Set(ids).size,'unique DOM IDs');
function element(id){return {id,value:['claim','kind','basis','frac','registry-filter','research-region','research-type'].includes(id)?'all':'',textContent:'',innerHTML:'',hidden:false,disabled:false,attributes:{},events:{},setAttribute(k,v){this.attributes[k]=v},removeAttribute(k){delete this.attributes[k]},addEventListener(k,f){this.events[k]=f},focus(){},showModal(){this.open=true},close(){this.open=false}}}
const nodes=new Map(ids.map(id=>[id,element(id)]));
for(const [id,value]of Object.entries({'audit-data':data,'saved-state':{},'cloud-config':cloudConfig}))nodes.get(id).textContent=JSON.stringify(value);
const timers=[],events={},storage=new Map();
const rawEPA=Object.fromEntries(data.registry.map(r=>[r.reg,{items:[{eparegno:r.reg,productname:r.name,product_status:r.status,product_status_date:r.statusDate,signal_word:r.signalWord,rup_yn:r.restrictedUse,active_ingredients:r.ingredients,pdffiles:r.documentHistory,altbrandnames:r.aliases.map(altbrandname=>({altbrandname})),transfer_history:r.transfers}]}]));
const context={assert,console,URL,TextDecoder,TextEncoder,AbortController,Blob,crypto:crypto.webcrypto,Uint8Array,ArrayBuffer,Map,Set,Date,JSON,Promise,Math,Number,String,Error,RegExp,rawEPA,
 document:{getElementById(id){assert(nodes.has(id),'missing element '+id);return nodes.get(id)},createElement:element},
 localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)},
 setTimeout(f,ms){timers.push({f,ms});return timers.length},clearTimeout(){},window:{addEventListener(k,f){events[k]=f},print(){}},fetch(){throw Error('Unexpected network request')},getTimers:()=>timers,getEvents:()=>events};
vm.createContext(context);vm.runInContext(fs.readFileSync('src/app.js','utf8'),context);
vm.runInContext(`(async()=>{
let passed=0;function ok(v,name){assert(v,name);passed++;}
ok(DATA.products.length===122&&DATA.registry.length===196,'reviewed scope');
ok(DATA.products.every(p=>p.efficacy===''),'efficacy blank');
ok(($('rows').innerHTML.match(/Efficacy intentionally blank/g)||[]).length===122,'blank rendered efficacy');
ok(getTimers().some(t=>t.f===refreshAll&&t.ms===0),'automatic opening check');
ok(typeof getEvents().online==='function'&&typeof getEvents().pageshow==='function','restoration and online hooks');
$('search').value='Miravis Neo';ok(visibleProducts().length===1,'search');$('clear-search').onclick();ok(visibleProducts().length===122,'clear');
$('registry-filter').value='regional';ok(visibleRegistry().length===12,'regional records');$('registry-filter').value='all';
$('research-region').value='Canada';ok(visibleResearch().length===1,'research region');$('research-region').value='all';
$('state-select').value='IA';renderState();ok($('state-result').innerHTML.includes('Iowa')&&$('state-result').innerHTML.includes('Product approval not checked'),'jurisdiction status');
selectTab('research');ok(!$('research-panel').hidden&&$('guide-panel').hidden,'tab visibility');selectTab('guide');
for(const r of registry)assert.equal(compareEPA(r.reg,rawEPA[r.reg]).differences.length,0,'baseline '+r.reg);passed++;
const p=DATA.products.find(p=>p.id==='miravis_neo'),reg=p.federal.reg;
const snapshot={schema:1,reviewedHash:CLOUD_CONFIG.reviewedHash,generatedAt:new Date().toISOString(),epaChecks:Object.fromEntries(registry.map(r=>[r.reg,{status:'matched',date:new Date().toISOString()}])),checks:Object.fromEntries(DATA.products.map(p=>[p.id,{status:'matched',date:new Date().toISOString()}])),feedChecks:{uk:{status:'matched'},ut:{status:'matched'}},liveRegistry:{},criticalChanges:{},pdfAlerts:{},candidates:[]};
ok(validCloudSnapshot(snapshot),'valid complete shared snapshot');
ok(!validCloudSnapshot({...snapshot,reviewedHash:'other'}),'reject different baseline');
ok(!validCloudSnapshot({...snapshot,checks:{}}),'reject incomplete snapshot');
ok(!validCloudSnapshot({...snapshot,generatedAt:new Date(Date.now()+3600000).toISOString()}),'reject future timestamp');
ok(!validCloudSnapshot({...snapshot,liveRegistry:{'bogus':{}}}),'reject unknown registration');
const originalRequest=request;request=async()=>snapshot;await loadCloudSnapshot();ok(state.cloudSnapshot.reviewedHash===CLOUD_CONFIG.reviewedHash,'load shared results');
ok(sourceState(p).includes('Shared sources checked'),'shared status carries time');
state.cloudSnapshot.criticalChanges[reg]=['Latest document changed'];ok(!directionsAvailable(p),'shared EPA alert withholds directions');
showDetails(p.id);ok($('detail-body').innerHTML.includes('Application directions withheld.')&&!$('detail-body').innerHTML.includes(p.rate),'details held');
ok(makeCSV([p]).includes('Withheld')&&!makeCSV([p]).includes(p.rate),'CSV held');
let downloaded;download=(text,type,name)=>{downloaded={text,type,name}};$('json').onclick();let exportData=JSON.parse(downloaded.text);ok(exportData.products.find(x=>x.id===p.id).rate.includes('Withheld')&&exportData.cloudSnapshot.criticalChanges[reg].length===1,'JSON holds and provenance');
request=async()=>{throw Error('Unavailable')};await loadCloudSnapshot();ok(!directionsAvailable(p)&&cloudStatus.includes('unavailable'),'unavailable shared request retains hold');
state.cloudSnapshot.generatedAt=new Date(Date.now()-31*3600000).toISOString();renderCloudStatus();ok($('cloud-status').textContent.includes('stale')&&!directionsAvailable(p),'stale snapshots retain holds and disclose age');
state.cloudSnapshot.criticalChanges={};state.cloudSnapshot.pdfAlerts[p.id]='PDF changed';ok(!directionsAvailable(p),'shared PDF alert');
state.cloudSnapshot.pdfAlerts={};state.cloudSnapshot.generatedAt=new Date().toISOString();
const older=JSON.parse(JSON.stringify(state.cloudSnapshot));older.generatedAt=new Date(Date.now()-3600000).toISOString();request=async()=>older;await loadCloudSnapshot();ok(cloudStatus.includes('Older shared result'),'older snapshot cannot replace newer evidence');
const clean=JSON.parse(JSON.stringify(state.cloudSnapshot));request=async()=>clean;await loadCloudSnapshot();ok(directionsAvailable(p),'clean same-baseline shared result');
const before=JSON.stringify(DATA),changed=JSON.parse(JSON.stringify(rawEPA[reg]));changed.items[0].product_status='Cancelled';changed.items[0].pdffiles.push({pdffile:'000100-01605-20990101.pdf',pdffile_accepted_date:'January 1, 2099'});
request=async url=>url.endsWith('/'+reg)?changed:rawEPA[url.split('/').pop()];await checkEPA();ok(!directionsAvailable(p)&&state.criticalChanges[reg].length===2,'direct EPA check detects critical changes');ok(JSON.stringify(DATA)===before,'checks never mutate reviewed baseline');
request=async()=>{throw Error('Unavailable')};await checkEPA();ok(!directionsAvailable(p),'failed browser request retains critical hold');
request=async url=>rawEPA[url.split('/').pop()];await checkEPA();ok(directionsAvailable(p),'confirmed browser match clears own hold');
request=originalRequest;const calls=[];loadCloudSnapshot=async()=>{calls.push('shared')};checkEPA=async()=>{calls.push('epa')};checkLabels=async()=>{calls.push('pdf')};checkFeeds=async()=>{calls.push('feeds')};await refreshAll();ok(calls[0]==='shared'&&calls.length===4,'shared data loaded before direct opening checks');
ok(safeUrl('javascript:alert(1)')==='','unsafe links rejected');ok(csvCell('=1+1').charCodeAt(1)===39,'spreadsheet formula escaping');ok(breakEven(30,20)===150&&breakEven(1,0)===null,'economics units');
console.log(JSON.stringify({checksPassed:passed,profiles:DATA.products.length,registrations:registry.length,sharedSnapshot:true}));
})()`,context).catch(e=>{console.error(e);process.exitCode=1});
