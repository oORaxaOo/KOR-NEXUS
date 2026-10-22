(() => {
'use strict';
const $ = id => document.getElementById(id);
const state = {repos:[], selected:null, details:null};
const safe = value => String(value ?? '');
function el(tag, cls, text) { const node=document.createElement(tag); if(cls)node.className=cls; if(text!==undefined)node.textContent=safe(text); return node; }
function linkItem(container, title, url, meta='') {
  const item=el('div','gh-item'); const a=el('a','',title); a.href=url||'#'; a.target='_blank'; a.rel='noopener noreferrer'; item.append(a);
  if(meta)item.append(el('small','',meta)); container.append(item);
}
function showStatus(message, kind='') { const n=$('ghStatus'); n.className='gh-status'+(kind?' '+kind:''); n.textContent=message; }
async function api(url, options={}) {
  const response=await fetch(url,{headers:{'Accept':'application/json','Content-Type':'application/json'},...options});
  let data; try{data=await response.json()}catch{throw new Error('Ungültige Antwort vom KOR-NEXUS-Kern.')}
  if(!response.ok || data.ok===false)throw new Error(data.error||('HTTP '+response.status));
  return data;
}
function repoParts(full) { const p=safe(full).split('/'); return {owner:p[0]||'',repo:p[1]||''}; }
function renderRepos() {
 const root=$('ghRepos'); root.replaceChildren(); const filter=$('ghSearch').value.trim().toLowerCase();
 const repos=state.repos.filter(r=>safe(r.full_name).toLowerCase().includes(filter)||safe(r.description).toLowerCase().includes(filter));
 $('ghRepoCount').textContent=state.repos.length+' REPOS';
 if(!repos.length){root.append(el('p','gh-muted',state.repos.length?'Keine Treffer.':'Keine Repositories verfügbar.'));return;}
 for(const repo of repos){
   const b=el('button','gh-repo'+(state.selected===repo.full_name?' active':''));b.type='button';
   b.append(el('strong','',repo.full_name)); b.append(el('small','',((repo.private?'PRIVAT':'ÖFFENTLICH')+' · '+(repo.default_branch||'main')+' · '+(repo.description||'Keine Beschreibung')).slice(0,220)));
   b.addEventListener('click',()=>loadRepo(repo.full_name));root.append(b);
 }
}
function renderItems(id,items,kind) {
 const root=$(id);root.replaceChildren();
 if(!items||!items.length){root.append(el('p','gh-muted','Keine Einträge.'));return;}
 for(const item of items){
  if(kind==='issue')linkItem(root,'#'+item.number+' · '+item.title,item.html_url,'@'+(item.user||'unbekannt')+' · '+(item.updated_at||''));
  else if(kind==='pull')linkItem(root,'#'+item.number+' · '+item.title,item.html_url,(item.draft?'DRAFT · ':'')+(item.head||'?')+' → '+(item.base||'?'));
  else if(kind==='run')linkItem(root,(item.name||'Workflow')+' · '+(item.conclusion||item.status||'unbekannt'),item.html_url,(item.branch||'')+' · '+(item.created_at||''));
  else if(kind==='commit')linkItem(root,(item.sha||'').slice(0,8)+' · '+(item.message||''),item.html_url,item.author||'');
  else if(kind==='branch')root.append(el('div','gh-item',item.name+(item.protected?' · GESCHÜTZT':'')));
 }
}
async function loadRepo(full) {
 state.selected=full; renderRepos(); const {owner,repo}=repoParts(full);
 $('ghRepoTitle').textContent=full;$('ghRepoDescription').textContent='Repository-Daten werden geladen …';
 try{
  const d=await api('/api/github/repository?owner='+encodeURIComponent(owner)+'&repo='+encodeURIComponent(repo));state.details=d;
  $('ghRepoTitle').textContent=d.repository.full_name;$('ghRepoDescription').textContent=d.repository.description||'Keine Beschreibung vorhanden.';
  $('ghDefaultBranch').textContent='DEFAULT: '+d.repository.default_branch;
  renderItems('ghIssues',d.issues,'issue');renderItems('ghPulls',d.pulls,'pull');renderItems('ghRuns',d.runs,'run');renderItems('ghCommits',d.commits,'commit');renderItems('ghBranches',d.branches,'branch');
  const branches=d.branches.map(b=>b.name);
  for(const id of ['ghBranchSource','ghPullHead','ghPullBase','ghWorkflowBranch']){
    const sel=$(id);sel.replaceChildren();sel.append(new Option(id==='ghBranchSource'?'Quellbranch wählen …':id==='ghPullHead'?'Quellbranch wählen …':id==='ghPullBase'?'Zielbranch wählen …':'Workflow-Branch wählen …',''));
    branches.forEach(b=>sel.append(new Option(b,b)));
  }
  if(branches.includes(d.repository.default_branch))$('ghBranchSource').value=d.repository.default_branch;
  if(branches.includes(d.repository.default_branch))$('ghPullBase').value=d.repository.default_branch;
  if(branches.includes(d.repository.default_branch))$('ghWorkflowBranch').value=d.repository.default_branch;
  showStatus('Verbunden mit GitHub. Repository '+full+' geladen.','ok');
 }catch(e){showStatus(e.message,'error');$('ghRepoDescription').textContent=e.message;}
}
async function refresh() {
 $('ghRefresh').disabled=true;showStatus('GitHub-Verbindung und autorisierte Repositories werden geprüft …');
 try{
  const d=await api('/api/github/repositories');state.repos=d.repositories||[];
  const u=d.user?.login||'GitHub-Nutzer';showStatus('Verbunden als '+u+' · '+state.repos.length+' autorisierte Repositories.','ok');
  renderRepos();
  if(state.selected&&state.repos.some(r=>r.full_name===state.selected))await loadRepo(state.selected);
  else if(state.repos.length)await loadRepo(state.repos[0].full_name);
  else showStatus('Anmeldung erfolgreich, aber es wurden keine Repositories gefunden.','error');
 }catch(e){showStatus(e.message+' — Auf diesem Rechner ggf. zuerst „gh auth login“ ausführen.','error');$('ghRepos').replaceChildren(el('p','gh-muted','Keine Verbindung. Anmeldung auf dem Rechner einrichten und aktualisieren.'));}
 finally{$('ghRefresh').disabled=false;}
}
async function submitForm(formId, endpoint, collect, confirmText, successText) {
 $(formId).addEventListener('submit',async event=>{
  event.preventDefault();if(!state.selected){showStatus('Bitte zuerst ein Repository auswählen.','error');return;}
  const payload={...repoParts(state.selected),...collect()};
  if(!confirm(confirmText))return;
  const button=$(formId).querySelector('button[type="submit"]');button.disabled=true;
  try{const result=await api(endpoint,{method:'POST',body:JSON.stringify(payload)});
   showStatus(successText+(result.number?' #'+result.number:'')+(result.html_url?' — '+result.html_url:''),'ok');
   if(result.html_url&&confirm('Aktion erfolgreich. GitHub-Seite jetzt öffnen?'))window.open(result.html_url,'_blank','noopener,noreferrer');
   $(formId).reset();await loadRepo(state.selected);
  }catch(e){showStatus(e.message,'error')}finally{button.disabled=false;}
 });
}
$('ghSearch').addEventListener('input',renderRepos);
$('ghRefresh').addEventListener('click',refresh);
submitForm('ghIssueForm','/api/github/issues',()=>({title:$('ghIssueTitle').value,body:$('ghIssueBody').value}),
 'Dieses Issue jetzt im ausgewählten GitHub-Repository erstellen?','Issue erstellt.');
submitForm('ghBranchForm','/api/github/branches',()=>({branch:$('ghBranchName').value,source:$('ghBranchSource').value}),
 'Neuen Arbeitsbranch im ausgewählten Repository erstellen? Es werden keine Dateien geändert und kein Merge ausgeführt.','Branch erstellt.');
submitForm('ghPullForm','/api/github/pulls',()=>({title:$('ghPullTitle').value,head:$('ghPullHead').value,base:$('ghPullBase').value,body:$('ghPullBody').value}),
 'Pull Request öffnen? Dieser Schritt führt keinen Merge aus.','Pull Request geöffnet.');
submitForm('ghWorkflowForm','/api/github/workflow-dispatch',()=>({workflow:$('ghWorkflowFile').value,branch:$('ghWorkflowBranch').value}),
 'Den ausgewählten GitHub-Actions-Workflow starten? Dies kann CI-Ressourcen verbrauchen.','Workflow wurde an GitHub übergeben.');
refresh();
})();