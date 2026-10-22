(()=>{'use strict';
const $=id=>document.getElementById(id);
let cached=[];
const audioExt=/\.(mp3|m4a|ogg|opus|wav|flac)$/i;
function setText(id,value){const n=$(id);if(n)n.textContent=String(value??'')}
function size(n){if(!n)return '0 B';const units=['B','KiB','MiB','GiB'];let i=0;while(n>=1024&&i<units.length-1){n/=1024;i++}return (i? n.toFixed(1):String(n|0))+' '+units[i]}
function status(message){setText('cockpitStatus',message)}
function play(item){
 if(!item||!item.available||!item.path){status('Dieses Medium ist nicht lokal verfügbar.');return}
 const isAudio=audioExt.test(item.filename);
 const video=$('kor-offline-player'),audio=$('kor-offline-audio'),placeholder=$('player-placeholder');
 for(const p of [video,audio]){p.pause();p.removeAttribute('src');p.hidden=true;p.load()}
 const player=isAudio?audio:video;
 player.src=item.path;player.hidden=false;placeholder.hidden=true;
 player.play().then(()=>status('LOKAL WIEDERGABE: '+item.title)).catch(()=>status('Datei bereit. Drücke Play, falls die Wiedergabe nicht automatisch startet.'));
 player.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'nearest'});
}
function render(items){
 const host=$('emergency-media-list');host.replaceChildren();
 if(!items.length){const e=document.createElement('div');e.className='empty';e.textContent='Noch keine Medien im Archiv. Lege Video-/Audiodateien in den angezeigten Ordner.';host.append(e);return}
 for(const item of items){
  const row=document.createElement('div');row.className='cockpit-media-row'+(item.available?'':' unavailable');
  const main=document.createElement('div');main.className='cockpit-media-meta';
  const title=document.createElement('strong');title.textContent=item.title;
  const detail=document.createElement('small');detail.textContent=(item.category||'Medium')+' · '+(item.available?size(item.size_bytes):'FEHLT / NICHT LESBAR');
  main.append(title,detail);
  const badge=document.createElement('span');badge.className='cockpit-file-status';badge.textContent=item.available?'BEREIT':'FEHLT';
  const favorite=document.createElement('button');favorite.type='button';favorite.className='btn ghost small';favorite.textContent=item.is_favorite?'★':'☆';favorite.setAttribute('aria-label',item.is_favorite?'Favorit entfernen':'Als Notfall-Favorit markieren');favorite.title=favorite.getAttribute('aria-label');
  favorite.addEventListener('click',async()=>{favorite.disabled=true;try{const response=await fetch('/api/media/favorite',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:item.id,favorite:!item.is_favorite})});if(!response.ok)throw Error('Speichern fehlgeschlagen');await refresh()}catch(e){status('Favorit konnte nicht gespeichert werden.')}finally{favorite.disabled=false}});
  const button=document.createElement('button');button.type='button';button.className='btn ghost small';button.textContent='▶';button.disabled=!item.available;button.setAttribute('aria-label','Abspielen: '+item.title);button.addEventListener('click',()=>play(item));
  row.append(main,badge,favorite,button);host.append(row);
 }
}
async function refresh(){
 const button=$('cockpitRefresh');if(button)button.disabled=true;
 status('Prüfe Dateien und Speicherplatz …');
 try{
  const response=await fetch('/api/media/readiness',{cache:'no-store'});if(!response.ok)throw Error('HTTP '+response.status);
  const data=await response.json();cached=Array.isArray(data.items)?data.items:[];
  setText('readiness-score-badge','READY: '+data.readiness_score+'%');
  $('readiness-score-badge').classList.toggle('cockpit-score-warn',data.readiness_score<100);
  setText('cockpitTotal',data.available_items+' / '+data.total_items);
  setText('cockpitMissing',data.missing_items);
  setText('cockpitFree',data.free_storage_gb+' GB');
  setText('cockpitVaultPath',data.vault_dir);
  render(cached);
  status(data.missing_items?'WARNUNG: '+data.missing_items+' Ressource(n) fehlen oder sind nicht lesbar.':'BEREIT: Alle registrierten Ressourcen sind lokal lesbar.');
 }catch(e){status('Prüfung fehlgeschlagen: '+(e.message||'Lokaler Dienst nicht erreichbar.'))}
 finally{if(button)button.disabled=false}
}
function emergency(){
 const ready=cached.filter(i=>i.available);
 if(!ready.length){status('KEINE LOKALEN MEDIEN. Lege zuerst Dateien in den angezeigten Archivordner.');return}
 document.body.classList.add('cockpit-active');
 const chosen=ready.find(i=>i.is_favorite)||ready[0];
 play(chosen);
}
document.addEventListener('DOMContentLoaded',()=>{
 $('cockpitRefresh')?.addEventListener('click',refresh);
 $('panic-button')?.addEventListener('click',emergency);
 refresh();
});
window.KorOfflineCockpit={refresh,play};
})();