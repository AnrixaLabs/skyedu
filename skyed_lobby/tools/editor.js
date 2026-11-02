/* Local-first content editor. Explicit Save writes only to the guarded loopback workspace. */
(() => {
'use strict';
const id=x=>document.getElementById(x);
const state={data:null,section:'site',selected:0,dirty:false,sessionToken:null,saving:false};
const fields={
 site:[['brand','Brand name','text'],['brandDetail','Small brand label','text'],['eyebrow','Page kicker','text'],['title','Main page heading','text'],['subtitle','Heading description','textarea'],['announcement','Draft information bar','textarea'],['heroLabel','Hero eyebrow','text'],['heroTitle','Hero headline','text'],['heroDescription','Hero description','textarea'],['heroImage','Optional hero image (assets/media/...png)','text'],['heroAction','Hero button label','text'],['footer','Footer text','text'],['backToCurrentSiteUrl','Back to existing website URL','text']],
 programs:[['id','Stable identifier','readonly'],['title','Program title','text'],['subtitle','Card subtitle','textarea'],['description','Program description','textarea'],['image','Optional tile image (assets/media/...png)','text'],['level','Age / level','text'],['category','Category','text'],['color','Tile color','select:coral,lilac,blue,mint,yellow'],['icon','Icon','select:sparkles,book,chat,shapes,target'],['tag','Small card label','text'],['order','Display order','number'],['lessonCount','Display lesson count (update after approved import)','number'],['featured','Featured tile (large)','checkbox'],['placeholder','Placeholder — not an approved program','checkbox'],['status','Publication status','select:planned,library-awaiting-link,published']],
 groups:[['id','Stable group ID','readonly'],['title','Group / unit title','text'],['subtitle','Group description','textarea'],['order','Display order','number']],
 lessons:[['id','Stable lesson ID','readonly'],['programId','Parent program ID','reference:programs'],['groupId','Parent group ID','reference:groups'],['title','Approved lesson title','text'],['summary','Lesson description','textarea'],['type','Content type','select:Vocabulary,Speaking,Listening,Practice,Story'],['level','Age / level','text'],['minutes','Duration (0 if unknown)','number'],['order','Display order','number'],['status','Lesson status','select:needs-link,draft,published'],['url','Approved lesson URL (blank until verified)','text'],['media','Optional media path','text'],['tags','Search tags (comma-separated)','csv']]
};
const el=(tag,cls='',text='')=>{const e=document.createElement(tag);e.className=cls;e.textContent=text;return e;};
const activeItems=()=>state.section==='site'? [state.data.site]:(state.data[state.section]||[]);
const current=()=>activeItems()[state.selected];
const message=(s,error=false)=>{id('alerts').className=error?'error':'';id('alerts').textContent=s;};
const human={site:'Site text',programs:'Programs',groups:'Units & groups',lessons:'Lessons',json:'JSON preview'};
const mustUnique=(arr,label)=>{const ids=arr.map(x=>x.id);if(new Set(ids).size!==ids.length||ids.some(x=>!x||!/^[a-z0-9-]+$/.test(x)))throw Error('Invalid or duplicate '+label+' IDs');};
function validate(data){
 if(!data || data.schemaVersion!==1 || !data.site || !Array.isArray(data.programs)||!Array.isArray(data.groups)||!Array.isArray(data.lessons)||!Array.isArray(data.navigation)||!data.filters)throw Error('Not a valid SkyED lobby schema v1 file');
 mustUnique(data.programs,'program');mustUnique(data.groups,'group');mustUnique(data.lessons,'lesson');
 for(const l of data.lessons){if(!data.programs.some(x=>x.id===l.programId)||!data.groups.some(x=>x.id===l.groupId))throw Error('Lesson '+l.id+' refers to an unknown program or group');if(l.status==='published'&&!isSafeUrl(l.url))throw Error('Published lesson '+l.id+' is missing a safe URL');if(l.media&&!isSafeMedia(l.media))throw Error('Invalid local media path on '+l.id);}
 for(const p of data.programs){if(p.image&&!isSafeMedia(p.image))throw Error('Invalid local image path on '+p.id);}
 if(data.site.heroImage&&!isSafeMedia(data.site.heroImage))throw Error('Invalid hero image path');
 return data;
}
function isSafeMedia(value){return typeof value==='string' && /^assets\/media\/[a-zA-Z0-9_\/-]+\.(png|jpe?g|webp|svg)$/.test(value) && !value.includes('..');}
function isSafeUrl(value){if(typeof value!=='string'||!value.trim()||value.startsWith('//')||/[\\\x00-\x1f]/.test(value))return false;try{const url=new URL(value,window.location.href);if(url.username||url.password)return false;return (url.origin===window.location.origin && value.startsWith('/') || url.protocol==='https:' && ['skyed.org','course.skyed.org'].includes(url.hostname));}catch{return false;}}
function draw(){
 id('page-heading').textContent=human[state.section];id('list-pane').hidden=state.section==='site'||state.section==='json';document.querySelector('.workspace').classList.toggle('single',state.section==='site'||state.section==='json');
 id('form-actions').hidden=state.section==='site'||state.section==='json';
 const list=id('item-list');list.replaceChildren();
 const items=activeItems();id('list-title').textContent=human[state.section];id('list-count').textContent=items.length+' items';
 if(!id('list-pane').hidden)items.forEach((x,i)=>{const b=el('button','list-item'+(i===state.selected?' selected':''),(i+1)+'. '+(x.title||x.id));b.type='button';b.addEventListener('click',()=>{state.selected=i;draw();});list.append(b);});
 id('add-button').hidden=state.section==='site'||state.section==='json';
 const out=id('fields');out.replaceChildren();
 if(state.section==='json'){const p=el('pre','json-preview',JSON.stringify(state.data,null,2));out.append(p);return;}
 const row=current();if(!row){out.append(el('p','empty-note','No items in this section. Use Add item to create one.'));return;}
 for(const [name,label,kind] of fields[state.section]){
  const wrap=el('div','form-field'+(kind==='checkbox'?' checkbox':''));
  const fieldId='field-'+name;const text=el('label','',label);text.htmlFor=fieldId;
  let control;
  if(kind==='textarea'){control=el('textarea');control.rows=3;}
  else if(kind.startsWith('select:')||kind.startsWith('reference:')){control=el('select');let values=[];if(kind.startsWith('select:'))values=kind.slice(7).split(',');else values=state.data[kind.slice(10)].map(x=>x.id);if(!values.includes(String(row[name])))values.unshift(String(row[name]||''));for(const value of values){control.append(el('option','',value));control.lastChild.value=value;}}
  else{control=el('input');control.type=kind==='number'?'number':kind==='checkbox'?'checkbox':'text';if(kind==='readonly')control.readOnly=true;}
  control.id=fieldId;control.name=name;control.setAttribute('aria-label',label);
  if(kind==='checkbox')control.checked=Boolean(row[name]);else control.value=kind==='csv'?(row[name]||[]).join(', '):row[name]??'';
  if(kind==='number')control.min='0';
  control.addEventListener(kind==='checkbox'||kind.startsWith('select:')||kind.startsWith('reference:')?'change':'input',()=>{
   if(kind==='readonly')return;
   let value=control.value;if(kind==='checkbox')value=control.checked;
   if(kind==='number')value=Math.max(0,Math.trunc(Number(value)||0));
   if(kind==='csv')value=value.split(',').map(x=>x.trim()).filter(Boolean);
   row[name]=value;state.dirty=true;id('export-button').textContent='Export JSON ↓ •';
   message('Unsaved changes. Click Save to workspace or Export JSON.');
   if(name==='title'){const selected=list.children[state.selected];if(selected)selected.textContent=(state.selected+1)+'. '+value;}
  });
  wrap.append(text);wrap.append(control);
  if(name==='url')wrap.append(el('span','hint','Only publish after verifying the exact URL and the underlying approved lesson.'));
  if(name==='id')wrap.append(el('span','hint','Locked to protect lesson/program references; duplicates receive a new ID.'));
  out.append(wrap);
 }
}
function newRecord(){
 const section=state.section;if(!['programs','groups','lessons'].includes(section))return;
 const list=state.data[section],seed=Math.max(...list.map(x=>Number(x.order)||0),0)+1;
 let item;
 if(section==='programs')item={id:uniqueId('program',list),title:'New program — edit title',subtitle:'Short editable summary',description:'Replace this placeholder before publishing.',image:'',level:'All ages',category:'English',color:'blue',icon:'book',tag:'Editable example',order:seed,lessonCount:0,featured:false,placeholder:true,status:'planned'};
 if(section==='groups')item={id:uniqueId('unit',list),title:'New unit — edit title',subtitle:'Editable unit description',order:seed};
 if(section==='lessons'){
  if(!state.data.programs.length||!state.data.groups.length){message('Add at least one program and one group first.',true);return;}
  item={id:uniqueId('lesson',list),programId:state.data.programs[0].id,groupId:state.data.groups[0].id,title:'New lesson — edit title',summary:'Replace with the verified lesson description.',type:'Vocabulary',level:'All ages',minutes:0,order:seed,status:'needs-link',url:'',media:'',tags:[]};
 }
 list.push(item);state.selected=list.length-1;state.dirty=true;draw();message('New draft added. Save to workspace to keep changes.');
}
function uniqueId(prefix,list){let n=1;let id;do{id=prefix+'-'+String(n++).padStart(2,'0');}while(list.some(x=>x.id===id));return id;}
function duplicate(){if(state.section==='site'||state.section==='json')return;const item=current();if(!item)return;const copy=JSON.parse(JSON.stringify(item));copy.id=uniqueId(state.section.slice(0,-1),activeItems());copy.title+=' (copy)';if(state.section==='programs'){copy.placeholder=true;copy.status='planned';copy.featured=false;copy.lessonCount=0;}if(state.section==='lessons'){copy.status='needs-link';copy.url='';}copy.order=Math.max(0,...activeItems().map(x=>Number(x.order)||0))+1;activeItems().push(copy);state.selected=activeItems().length-1;state.dirty=true;draw();message('Draft copy created. Save to workspace to keep changes.');}
function remove(){if(state.section==='site'||state.section==='json')return;const item=current();if(!item)return;
 if(state.section==='programs'&&state.data.lessons.some(x=>x.programId===item.id)||state.section==='groups'&&state.data.lessons.some(x=>x.groupId===item.id)){message('Cannot delete this item while lessons reference it. Reassign the lessons first.',true);return;}
 if(!window.confirm('Delete '+(item.title||item.id)+' from the draft?'))return;
 activeItems().splice(state.selected,1);state.selected=Math.max(0,state.selected-1);state.dirty=true;draw();message('Item deleted. Save to workspace to keep changes.');
}
function exportFile(){try{
 validate(state.data);const json=JSON.stringify(state.data,null,2)+'\n';
 const blob=new Blob([json],{type:'application/json'});const url=URL.createObjectURL(blob);
 const link=document.createElement('a');link.href=url;link.download='lobby.json';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),6000);
 state.dirty=false;id('export-button').textContent='Export JSON ↓';message('Export created. Replace site/content/lobby.json with the downloaded lobby.json.');
}catch(e){message('Export blocked: '+e.message,true);}}
async function importFile(event){const file=event.target.files?.[0];if(!file)return;try{if(file.size>1024*1024)throw Error('JSON file exceeds 1 MB');const data=validate(JSON.parse(await file.text()));state.data=data;state.selected=0;state.dirty=true;draw();message('Imported into browser memory. Save to workspace or Export JSON.');}catch(e){message('Import failed: '+e.message,true);}finally{event.target.value='';}}
async function bootstrap(){try{
 const response=await fetch('../site/content/lobby.json',{cache:'no-store'});
 if(!response.ok)throw Error('HTTP '+response.status);
 state.data=validate(await response.json());
 try{
  const session=await fetch('../api/session',{cache:'no-store'});
  if(session.ok){const info=await session.json();if(info.canSave&&typeof info.editorToken==='string'&&info.editorToken.length>=32){state.sessionToken=info.editorToken;id('save-button').hidden=false;}}
 }catch(_error){/* Standalone read-only server: JSON export still works. */}
 draw();message(state.sessionToken?'Ready. Changes are saved locally only when you click Save to workspace.':'Preview-only mode. Export JSON to keep edits.');
}catch(e){message('Unable to open source lobby.json: '+e.message,true);}}
async function saveWorkspace(){
 if(state.saving||!state.sessionToken)return;
 try{
  validate(state.data);state.saving=true;id('save-button').disabled=true;
  const response=await fetch('../api/save-content',{method:'POST',headers:{'Content-Type':'application/json','X-SkyED-Editor-Token':state.sessionToken},body:JSON.stringify(state.data)});
  const result=await response.json();
  if(!response.ok||!result.saved)throw Error(result.error||'HTTP '+response.status);
  state.dirty=false;id('export-button').textContent='Export JSON ↓';
  message('Saved locally to site/content/lobby.json. Refresh Preview to see your changes. No production site was updated.');
 }catch(error){message('Save failed: '+error.message,true);}
 finally{state.saving=false;id('save-button').disabled=false;}
}

for(const btn of document.querySelectorAll('#sections button'))btn.addEventListener('click',()=>{state.section=btn.dataset.section;state.selected=0;for(const b of document.querySelectorAll('#sections button'))b.classList.toggle('active',b===btn);draw();});
id('save-button').addEventListener('click',saveWorkspace);id('export-button').addEventListener('click',exportFile);id('import-file').addEventListener('change',importFile);id('add-button').addEventListener('click',newRecord);id('duplicate-button').addEventListener('click',duplicate);id('remove-button').addEventListener('click',remove);
window.addEventListener('beforeunload',(event)=>{if(state.dirty){event.preventDefault();event.returnValue='';}});
bootstrap();
})();
