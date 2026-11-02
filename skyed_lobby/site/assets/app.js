/* SkyED Course Hub Lobby 1.3.0 — no frameworks, remote APIs, or unsafe HTML insertion. */
(() => {
  'use strict';
  const KNOWN_ICONS = new Set(['compass','grid','book','bookmark','search','chevron','arrow','sparkles','chat','shapes','target','clock','close','filter','menu','list','heart','language','check']);
  const PALETTES = new Set(['coral','blue','lilac','mint','yellow']);
  const VALID_ROUTES = new Set(['discover','programs','lessons','saved']);
  const TRUSTED_LESSON_HOSTS = new Set(['skyed.org','course.skyed.org']);
  const ui = {
    root: document.querySelector('#main'), nav: document.querySelector('#side-nav'),
    search: document.querySelector('#global-search'), dialog: document.querySelector('#detail-dialog'),
    modal: document.querySelector('#detail-content'), menu: document.querySelector('#menu-toggle'),
    sidebar: document.querySelector('#sidebar'), backdrop: document.querySelector('#backdrop'),
    language: document.querySelector('#language-toggle'), crumb: document.querySelector('#breadcrumb-current'),
    toast: document.querySelector('#toast-region')
  };
  const state = {data: null, page: 'discover', program: null, search: '', level: '', type: '', sort: 'Featured', group: '', language:'en', favorites: new Set(), focusAfterModal: null};
  const english = {
    discover:'Discover',programs:'Programs',lessons:'All lessons',saved:'Saved',search:'Search courses, topics, lessons...',allPrograms:'All programs',allLevels:'All levels',allTypes:'All types',viewAll:'View all',clearFilters:'Clear filters',draft:'Needs content',planned:'Coming soon',save:'Save',savedAction:'Saved',browse:'Browse program',viewDetails:'View details',openLesson:'Open lesson',unlinked:'Waiting for verified lesson link',noResults:'Nothing matching your search',noResultsDetail:'Try a different search, or clear your filters.',collections:'Explore learning paths',collectionDesc:'Find a little adventure for every curious mind.',continue:'Inside the classroom',continueDesc:'A tidy collection of topics, practice, and future discoveries.',featured:'Featured',results:'results',close:'Close',language:'Language',menu:'Open menu',back:'Back',demoNotice:'Draft lobby: example content and lesson links must be approved before publication.',editHint:'Edit this item in content/lobby.json',statusLabel:'Status',notReady:'Not linked yet',details:'Program details',home:'Home',about:'About this space',copyright:'Sky Education · Course Hub',programsCount:'Learning paths',lessonCount:'Lesson placeholders',browseLesson:'Explore lessons',byUnit:'Units',sort:'Sort',emptySaved:'Your collection starts here',emptySavedDetail:'Bookmark a lesson to keep it in this browser.',reset:'Reset',allUnits:'All units',year:'Learning space',showing:'Showing',available:'Available',previewOnly:'Content preview',group:'Unit',level:'Level',type:'Type',duration:'Duration',lesson:'Lesson',program:'Program',minutes:'min',returnToPrograms:'All programs',noLive:'This item is a draft, not a live lesson',pilot:'Pilot',statusNeedsLink:'Needs linking',selected:'Selected'};
  const labels = (key) => (state.language === 'zh' ? state.data?.translations?.zh?.[key] : null) || english[key] || key;
  const elem = (tag, cls = '', text = '') => {const e = document.createElement(tag); if(cls)e.className=cls; if(text !== '') e.textContent=String(text); return e;};
  const icon = (name, cls = '') => {const s=document.createElementNS('http://www.w3.org/2000/svg','svg'); if(cls)s.setAttribute('class',cls);s.setAttribute('aria-hidden','true'); const u=document.createElementNS('http://www.w3.org/2000/svg','use');u.setAttribute('href','#icon-'+(KNOWN_ICONS.has(name)?name:'sparkles'));s.append(u);return s;};
  const add = (parent,...children) => {for(const c of children)if(c)parent.append(c);return parent;};
  const button = (cls, text, fn, title = text) => {const b=elem('button',cls,text);b.type='button';b.setAttribute('aria-label',title);b.addEventListener('click',fn);return b;};
  const clear = (n) => n.replaceChildren();
  const collator = new Intl.Collator('en',{numeric:true,sensitivity:'base'});
  const key = (k) => 'skyed-course-lobby-v1.3-'+k;
  const fromStore = (k,fallback) => {try{return JSON.parse(localStorage.getItem(key(k))) ?? fallback;}catch{return fallback;}};
  const toStore = (k,value) => {try{localStorage.setItem(key(k),JSON.stringify(value));}catch{/* browser storage disabled */}};
  const isString = (x) => typeof x === 'string' && x.length < 2000;
  const allowedLink = (link) => {
    if(!isString(link) || !link.trim() || link.startsWith('//') || /[\u0000-\u001f\\]/.test(link))return null;
    try{
      const parsed=new URL(link,window.location.href);
      if(parsed.username || parsed.password || !['http:','https:'].includes(parsed.protocol))return null;
      if(parsed.origin === window.location.origin && link.startsWith('/') || parsed.protocol==='https:' && TRUSTED_LESSON_HOSTS.has(parsed.hostname))return parsed.href;
      if(parsed.origin===window.location.origin && link.startsWith('#/'))return parsed.href;
    }catch{return null;}
    return null;
  };
  // Future Sunny QLoRA illustrations are local media assets, never remote URLs.
  const safeImagePath = (value) => isString(value) && /^assets\/media\/[a-zA-Z0-9_\/-]+\.(?:png|jpg|jpeg|webp|svg)$/.test(value) && !value.includes('..') ? value : null;
  const imageOrFallback = (path, cls, alt) => {
    const safe=safeImagePath(path);
    if(!safe)return null;
    const image=elem('img',cls);image.src=safe;image.alt=alt;
    image.loading='lazy';image.decoding='async';
    image.addEventListener('error',()=>image.remove());
    return image;
  };
  const isLive = (x) => !x.placeholder && x.status==='published' && Boolean(allowedLink(x.url));
  const heading = (eyebrow,title,desc) => {const block=elem('div','page-heading');const copy=elem('div');add(copy,elem('div','eyebrow',eyebrow),elem('h1','',title),elem('p','',desc));block.append(copy);return block;};
  const hSection = (kicker,title,description,onViewAll) => {const h=elem('div','section-header');const left=elem('div');add(left,elem('div','section-eyebrow',kicker),elem('h2','',title));if(description)left.append(elem('p','',description));h.append(left);if(onViewAll){const b=button('text-action','',onViewAll,labels('viewAll'));add(b,elem('span','',labels('viewAll')),icon('arrow'));h.append(b);}return h;};
  const changePage = (page,program='') => {
    if(!VALID_ROUTES.has(page) && page!=='program')page='discover';
    const fragment=page==='program'&&program?'#/program/'+encodeURIComponent(program):'#/'+page;
    if(window.location.hash===fragment){parseHash();render();}else window.location.hash=fragment;
    closeSidebar();
    window.scrollTo({top:0,behavior:'instant'});
  };
  const parseHash = () => {
    const parts=window.location.hash.replace(/^#\/?/,'').split('/');
    const page=parts[0];
    if(page==='program' && parts[1]){
      let id='';try{id=decodeURIComponent(parts[1]);}catch{/* bad hash */}
      const known=state.data.programs.some(p=>p.id===id);
      state.page=known?'program':'discover';state.program=known?id:null;
    } else {state.page=VALID_ROUTES.has(page)?page:'discover';state.program=null;}
  };
  const toast = (text) => {const item=elem('div','toast',text);ui.toast.append(item);window.setTimeout(()=>item.remove(),2700);};
  const closeSidebar = () => {ui.sidebar.classList.remove('open');ui.backdrop.hidden=true;ui.menu.setAttribute('aria-expanded','false');};
  const renderNav = () => {
    clear(ui.nav);const active=state.page==='program'?'programs':state.page;
    for(const item of state.data.navigation){if(!VALID_ROUTES.has(item.id))continue;const a=elem('a','nav-item'+(active===item.id?' is-active':''));a.href='#/'+item.id;a.setAttribute('aria-current',active===item.id?'page':'false');add(a,icon(item.icon),elem('span','',labels(item.id)));if(item.id==='saved'&&state.favorites.size)a.append(elem('span','nav-count',String(state.favorites.size)));a.addEventListener('click',closeSidebar);ui.nav.append(a);}
  };
  const layoutShell = () => {
    document.documentElement.lang=state.language;
    document.querySelector('#brand-name').firstChild.textContent=state.data.site.brand;
    document.querySelector('#brand-caption').textContent=state.data.site.brandDetail;
    document.querySelector('#footer-copy').textContent=state.data.site.footer;
    document.querySelector('#sidebar-footer').textContent=state.data.site.footer;
    document.querySelector('#language-label').textContent=state.language.toUpperCase();
    ui.search.placeholder=labels('search'); ui.menu.setAttribute('aria-label',labels('menu'));
    document.querySelector('#back-current').href=allowedLink(state.data.site.backToCurrentSiteUrl)||'/';
    document.title=(state.page==='discover'?'Course Hub':labels(state.page==='program'?'programs':state.page))+' | Sky Education';
    ui.crumb.textContent=labels(state.page==='program'?'programs':state.page);
    renderNav();
  };
  const cardProgram = (p) => {
    const cls=PALETTES.has(p.color)?p.color:'blue';
    const card=elem('article','program-card '+cls+(p.featured?' is-featured':''));
    const top=elem('div','program-top');const mark=elem('span','program-icon');mark.append(icon(p.icon));
    const badge=elem('span','card-tag',p.placeholder?labels('planned'):(p.status==='library-awaiting-link'?labels('pilot'):labels('featured')));
    add(top,mark,badge);
    const info=elem('div','program-main');add(info,elem('h3','',p.title),elem('p','',p.subtitle));
    const foot=elem('div','program-meta');const txt=elem('span','',(p.level||labels('allLevels'))+'  ·  '+(p.lessonCount||0)+' '+labels('lessonCount').toLowerCase());
    const arrow=elem('span','program-arrow');arrow.append(icon('arrow'));add(foot,txt,arrow);
    const click=button('program-trigger','',()=>changePage('program',p.id),labels('browse')+': '+p.title);
    add(card,imageOrFallback(p.image,'program-media',p.title+' illustration')||elem('div','program-art'),top,info,foot,click);
    return card;
  };
  const allPrograms = () => [...state.data.programs].sort((a,b)=>Number(a.order||0)-Number(b.order||0));
  const visiblePrograms = () => {
    const q=state.search.toLocaleLowerCase().trim();
    return allPrograms().filter(p=>(!q || [p.title,p.subtitle,p.description,p.category,p.level].join(' ').toLocaleLowerCase().includes(q))&&(!state.level || p.level===state.level));
  };
  const programSection = (page, featuredOnly=false) => {
    const collection=elem('div','program-grid');let pp=visiblePrograms();
    if(featuredOnly && !state.search)pp=pp.slice(0,5);
    for(const p of pp)collection.append(cardProgram(p));
    if(!pp.length)collection.append(emptyState());
    page.append(collection);
  };
  const emptyState = (saved=false) => {const root=elem('section','empty');const ico=elem('div','empty-icon');ico.append(icon(saved?'bookmark':'search'));add(root,ico,elem('h3','',labels(saved?'emptySaved':'noResults')),elem('p','',labels(saved?'emptySavedDetail':'noResultsDetail')));if(!saved)root.append(button('button button-secondary',labels('clearFilters'),()=>{state.search='';ui.search.value='';state.level='';state.type='';state.group='';render();}));return root;};
  const renderIntro = (main) => {
    const intro=heading(state.data.site.eyebrow,state.data.site.title,state.data.site.subtitle);main.append(intro);
    const hero=elem('section','hero');const text=elem('div','hero-text');const cta=button('button button-light','',()=>changePage('programs'));
    add(cta,elem('span','',state.data.site.heroAction),icon('arrow'));
    add(text,elem('span','hero-kicker',state.data.site.heroLabel),elem('h2','',state.data.site.heroTitle),elem('p','',state.data.site.heroDescription),cta);
    const art=elem('div','hero-art');art.setAttribute('aria-hidden','true');add(art,elem('span','hero-ring'),elem('span','hero-disc'),elem('span','hero-orbit','✳'),elem('span','hero-dots','● ● ● ●'));
    const heroImage=imageOrFallback(state.data.site.heroImage,'hero-image',state.data.site.heroTitle);
    if(heroImage){art.replaceChildren(heroImage);}
    add(hero,text,art);main.append(hero);
    const notice=elem('div','notice');add(notice,elem('span','notice-glyph','✦'),elem('span','',state.data.site.announcement));main.append(notice);
  };
  const filterSelect = (label,items,current,onChange) => {
    const wrap=elem('label','filter-select');
    const select=elem('select');select.setAttribute('aria-label',label);
    for(const option of items){const item=elem('option','',option.label);item.value=option.value;select.append(item);}
    select.value=current;
    select.addEventListener('change',()=>onChange(select.value));wrap.append(select);return wrap;
  };
  const filterBar = (pId='') => {
    const box=elem('div','filter-bar');const title=elem('span','filter-heading');add(title,icon('filter'),elem('span','',labels('browseLesson')));box.append(title);
    if(!pId){box.append(filterSelect(labels('allPrograms'),[
      {label:labels('allPrograms'),value:''}, ...state.data.programs.map(x=>({label:x.title,value:x.id}))
    ],state.program||'',v=>{state.program=v;state.group='';render();}));}
    const allLevels = state.data.filters.levels.slice(1);
    box.append(filterSelect(labels('allLevels'),[{value:'',label:labels('allLevels')},...allLevels.map(x=>({value:x,label:x}))],state.level,v=>{state.level=v;render();}));
    box.append(filterSelect(labels('allTypes'),[{value:'',label:labels('allTypes')},...state.data.filters.contentTypes.slice(1).map(x=>({value:x,label:x}))],state.type,v=>{state.type=v;render();}));
    box.append(filterSelect(labels('sort'),state.data.filters.sortOptions.map(x=>({value:x,label:x})),state.sort,v=>{state.sort=v;render();}));
    box.append(button('clear-filters',labels('reset'),()=>{state.level='';state.type='';state.group='';state.program='';state.sort='Featured';state.search='';ui.search.value='';render();},labels('clearFilters')));
    return box;
  };
  const lessonView = (pId='') => {
    const wrapper=elem('section');wrapper.append(filterBar(pId));
    let lessons=[...state.data.lessons];const q=state.search.toLocaleLowerCase().trim();
    lessons=lessons.filter(l=>(!pId||l.programId===pId)&&(!state.program||l.programId===state.program)&&(!state.level||l.level===state.level)&&(!state.type||l.type===state.type)&&(!state.group||l.groupId===state.group)&&(!q||[l.title,l.summary,l.type,l.level,l.groupId,l.tags.join(' ')].join(' ').toLocaleLowerCase().includes(q))&&(state.page!=='saved'||state.favorites.has(l.id)));
    if(state.sort==='A to Z')lessons.sort((a,b)=>collator.compare(a.title,b.title));
    if(state.sort==='Newest')lessons.sort((a,b)=>Number(b.order||0)-Number(a.order||0));
    if(state.sort==='Group order')lessons.sort((a,b)=>collator.compare(a.groupId,b.groupId)||Number(a.order||0)-Number(b.order||0));
    const summary=elem('div','filter-summary');summary.append(elem('span','count-label',labels('showing')+' '+lessons.length+' '+labels('results')));
    const groups=elem('div','unit-chips');
    const unitItems=[{id:'',title:labels('allUnits')},...state.data.groups];
    for(const group of unitItems){const chip=button('unit-chip'+(state.group===group.id?' active':''),group.title,()=>{state.group=group.id;render();});chip.setAttribute('aria-pressed',String(state.group===group.id));groups.append(chip);}
    summary.append(groups);wrapper.append(summary);
    if(lessons.length){const grid=elem('div','lesson-grid');for(const l of lessons)grid.append(cardLesson(l));wrapper.append(grid);}
    else wrapper.append(emptyState(state.page==='saved'&&state.favorites.size===0));
    return wrapper;
  };
  const cardLesson = (lesson) => {
    const card=elem('article','lesson-card');const top=elem('div','lesson-card-top');
    const number=elem('div','lesson-number',String(Number(lesson.order||0)).padStart(2,'0'));
    const label=elem('div','lesson-type',lesson.type||labels('lesson'));const save=button('save-button'+(state.favorites.has(lesson.id)?' is-saved':''),'',()=>toggleFavorite(lesson.id),state.favorites.has(lesson.id)?labels('savedAction'):labels('save'));save.append(icon('bookmark'));save.setAttribute('aria-pressed',String(state.favorites.has(lesson.id)));
    const photo=imageOrFallback(lesson.media,'lesson-thumb',lesson.title+' preview');
    if(photo){number.textContent='';number.append(photo);}
    add(top,number,label,save);
    add(card,top,elem('h3','',lesson.title),elem('p','',lesson.summary));
    const foot=elem('div','lesson-card-foot');const status=elem('span','', '');const dot=elem('span','status-dot'+(isLive(lesson)?' ready':''));add(status,dot,elem('span','',isLive(lesson)?labels('available'):labels('statusNeedsLink')));
    const details=button('detail-link','',()=>openDetail(lesson),labels('viewDetails')+': '+lesson.title);add(details,elem('span','',labels('viewDetails')),icon('arrow'));
    add(foot,status,details);card.append(foot);return card;
  };
  const toggleFavorite = (id) => {if(state.favorites.has(id)){state.favorites.delete(id);toast(labels('save'));}else{state.favorites.add(id);toast(labels('savedAction'));}toStore('favorites',[...state.favorites]);render();};
  const miniStats = () => {const stats=elem('div','mini-stats');for(const [i,n,cap,ico] of [[0,state.data.programs.length,labels('programsCount'),'grid'],[1,state.data.lessons.length,labels('lessonCount'),'book'],[2,state.data.groups.length,labels('byUnit'),'sparkles']]){const tile=elem('div','mini-stat');const wrap=elem('span','stat-icon');wrap.append(icon(ico));const inner=elem('div');add(inner,elem('div','stat-value',String(n)),elem('div','stat-desc',cap));add(tile,wrap,inner);stats.append(tile);}return stats;};
  const renderProgram = (main,p) => {
    const b=button('text-action','',()=>changePage('programs'));add(b,icon('chevron'),elem('span','',labels('returnToPrograms')));main.append(b);
    const pg=heading(p.category+'  /  '+p.level,p.title,p.description);main.append(pg);
    const notice=elem('div','notice');add(notice,elem('span','notice-glyph','✦'),elem('span','',p.placeholder?labels('demoNotice'):labels('unlinked')));main.append(notice);
    const cnt=state.data.lessons.filter(l=>l.programId===p.id).length;
    const headingLine=hSection(labels('byUnit'),labels('continue'),cnt+' '+labels('lessonCount').toLowerCase());main.append(headingLine);
    if(cnt)main.append(lessonView(p.id));else main.append(emptyState());
  };
  const render = () => {
    if(!state.data)return;
    layoutShell();clear(ui.root);
    const main=ui.root;
    if(state.page==='discover'){
      if(!state.search)renderIntro(main);else main.append(heading(labels('search'),labels('results'),state.search));
      main.append(hSection('01 / '+labels('featured'),labels('collections'),labels('collectionDesc'),()=>changePage('programs')));
      programSection(main,true);
      main.append(hSection('02 / '+labels('browseLesson'),labels('continue'),labels('continueDesc'),()=>changePage('lessons')));
      main.append(lessonView());
      if(!state.search)main.append(miniStats());
    } else if(state.page==='programs'){
      main.append(heading('01 / '+labels('programs'),labels('collections'),labels('collectionDesc')));
      const controls=elem('div','filter-bar');const label=elem('span','filter-heading');add(label,icon('filter'),elem('span','',labels('level')));controls.append(label);
      controls.append(filterSelect(labels('allLevels'),[{label:labels('allLevels'),value:''},...state.data.filters.levels.slice(1).map(x=>({label:x,value:x}))],state.level,v=>{state.level=v;render();}));
      controls.append(button('clear-filters',labels('clearFilters'),()=>{state.search='';ui.search.value='';state.level='';render();}));main.append(controls);
      main.append(elem('div','filter-summary',labels('showing')+' '+visiblePrograms().length+' '+labels('programsCount').toLowerCase()));
      programSection(main);
      main.append(miniStats());
    } else if(state.page==='program'){
      const p=state.data.programs.find(p=>p.id===state.program);
      if(p)renderProgram(main,p);else changePage('discover');
    } else if(state.page==='saved'){
      main.append(heading('03 / '+labels('saved'),labels('saved'),labels('emptySavedDetail')));
      main.append(lessonView());
    } else {
      main.append(heading('02 / '+labels('lessons'),labels('lessons'),labels('continueDesc')));
      main.append(lessonView());
    }
  };
  const openDetail = (lesson) => {
    state.focusAfterModal=document.activeElement;
    clear(ui.modal);const modal=elem('div','detail-inner');const top=elem('div','dialog-top');
    const close=button('dialog-close','',()=>ui.dialog.close(),labels('close'));close.append(icon('close'));
    add(top,elem('span','dialog-label',labels('lesson')+' / '+lesson.id),close);
    add(modal,top,elem('h2','',lesson.title),elem('p','',lesson.summary));
    const meta=elem('div','detail-meta');
    const group=state.data.groups.find(g=>g.id===lesson.groupId);
    for(const [label,value] of [[labels('program'),state.data.programs.find(p=>p.id===lesson.programId)?.title||'—'],[labels('group'),group?.title||'—'],[labels('level'),lesson.level||'—'],[labels('type'),lesson.type||'—'],[labels('statusLabel'),isLive(lesson)?labels('available'):labels('statusNeedsLink')]]){
      const line=elem('div','detail-meta-row');add(line,elem('span','',label),elem('span','',value));meta.append(line);
    }modal.append(meta);
    if(!isLive(lesson))modal.append(elem('p','dialog-warning',labels('noLive')+'. '+labels('editHint')+'.'));
    const actions=elem('div','detail-actions');
    if(isLive(lesson))actions.append(button('button button-primary',labels('openLesson'),()=>{window.location.assign(allowedLink(lesson.url));}));
    actions.append(button('button button-secondary',labels('close'),()=>ui.dialog.close()));
    modal.append(actions);ui.modal.append(modal);ui.dialog.showModal();close.focus();
  };
  const validate = (data) => {
    if(!data || data.schemaVersion!==1 || !data.site || !Array.isArray(data.programs) || !Array.isArray(data.groups) || !Array.isArray(data.lessons) || !Array.isArray(data.navigation) || !data.filters)throw Error('Invalid lobby data schema');
    const unique = (list,label) => {const keys=list.map(x=>x.id);if(keys.some(x=>typeof x!=='string'||!/^[a-z0-9-]{1,60}$/.test(x))||new Set(keys).size!==keys.length)throw Error('Invalid '+label+' IDs');};
    unique(data.programs,'program');unique(data.groups,'group');unique(data.lessons,'lesson');
    for(const lesson of data.lessons){if(!data.programs.some(p=>p.id===lesson.programId)||!data.groups.some(g=>g.id===lesson.groupId)||!Array.isArray(lesson.tags))throw Error('Lesson references unknown program, group or tags');}
    for(const p of data.programs){if(!isString(p.title)||!isString(p.subtitle)||!isString(p.description))throw Error('Invalid program text');}
    for(const l of data.lessons){if(!isString(l.title)||!isString(l.summary))throw Error('Invalid lesson text');}
    return data;
  };
  const load = async () => {
    try{
      const res=await fetch('content/lobby.json',{cache:'no-store',credentials:'same-origin'});
      if(!res.ok)throw Error('HTTP '+res.status);
      state.data=validate(await res.json());
      const prefs=fromStore('favorites',[]);const available=new Set(state.data.lessons.map(x=>x.id));state.favorites=new Set(Array.isArray(prefs)?prefs.filter(x=>available.has(x)):[]);
      const remembered=fromStore('language','en');state.language=state.data.site.languages.includes(remembered)?remembered:'en';
      parseHash();render();
    }catch(error){console.error('Course Hub content error:',error.message);const t=document.querySelector('#fatal-template');ui.root.replaceChildren(t.content.cloneNode(true));ui.root.querySelector('#retry-button').addEventListener('click',load);}
  };
  window.addEventListener('hashchange',()=>{if(state.data){parseHash();render();}});
  ui.search.addEventListener('input',()=>{state.search=ui.search.value.trim();render();});
  ui.menu.addEventListener('click',()=>{const now=!ui.sidebar.classList.contains('open');ui.sidebar.classList.toggle('open',now);ui.backdrop.hidden=!now;ui.menu.setAttribute('aria-expanded',String(now));});
  ui.backdrop.addEventListener('click',closeSidebar);
  ui.language.addEventListener('click',()=>{if(!state.data)return;state.language=state.language==='en'?'zh':'en';toStore('language',state.language);render();});
  ui.dialog.addEventListener('close',()=>{if(state.focusAfterModal?.isConnected)state.focusAfterModal.focus();});
  document.addEventListener('keydown',(e)=>{if(e.key==='Escape')closeSidebar();if(e.key==='/'&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName)&&!ui.dialog.open){e.preventDefault();ui.search.focus();}});
  load();
})();
