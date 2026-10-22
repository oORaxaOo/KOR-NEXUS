/* KOR-NEXUS HUD enhancements; no runtime libraries. */
(function(){
'use strict';
var byId=function(id){return document.getElementById(id);};
var esc=function(v){return String(v).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});};
window.createKorLineChart=function(id,values){
 var box=byId(id); if(!box||!Array.isArray(values)||!values.length||values.length>500||values.some(function(v){return typeof v!=='number'||!Number.isFinite(v);}))return;
 var w=300,h=100,p=10,min=Math.min.apply(null,values.concat([0])),max=Math.max.apply(null,values.concat([1])),span=max-min||1;
 var coords=values.map(function(v,i){return [values.length===1?w/2:p+i/(values.length-1)*(w-2*p),h-p-(v-min)/span*(h-2*p)];});
 var points=coords.map(function(p){return p.join(',');}).join(' ');
 var circles=coords.map(function(p){return '<circle cx="'+p[0]+'" cy="'+p[1]+'" r="2.5" fill="#c9a76a"/>';}).join('');
 box.innerHTML='<svg class="kor-line-chart" role="img" aria-label="Verlauf" viewBox="0 0 '+w+' '+h+'" preserveAspectRatio="none"><line x1="0" y1="'+(h/2)+'" x2="'+w+'" y2="'+(h/2)+'" stroke="#33393b" stroke-dasharray="4 4"/><polyline fill="none" stroke="#d44445" stroke-width="2" points="'+points+'"/>'+circles+'</svg>';
};
function ensure(id,tag,cls,parent){var el=byId(id);if(!el){el=document.createElement(tag);el.id=id;if(cls)el.className=cls;(parent||document.body).appendChild(el);}return el;}
function init(){
 var toolbar=ensure('kor-hud-toolbar','div','kor-hud-toolbar',document.body);
 if(!toolbar.childNodes.length)toolbar.innerHTML='<div><strong>KOR // SYSTEM STATUS</strong><span id="kor-mesh-status">MESH: BEREIT</span></div><div class="kor-hud-actions"><button id="kor-big-screen-trigger" type="button">BIG SCREEN: EIN</button><button id="kor-kiosk-trigger" type="button">KIOSK: AUS</button></div>';
 var banner=ensure('hud-alert-banner','div','hud-alert-banner',document.body);banner.setAttribute('role','status');banner.hidden=true;
 var panel=ensure('kor-matrix-console','section','matrix-console-panel',document.body);
 if(!panel.childNodes.length)panel.innerHTML='<div class="console-header">NEXUS SYSTEM LOGS // LIVE OVERVIEW</div><div id="console-log-stream" class="console-stream" aria-live="polite"></div>';
 function big(active){document.body.classList.toggle('kor-big-screen-active',active);var b=byId('kor-big-screen-trigger');if(b)b.textContent=active?'BIG SCREEN: EIN':'BIG SCREEN: AUS';}
 function kiosk(active){document.body.classList.toggle('kor-kiosk-active',active);var b=byId('kor-kiosk-trigger');if(b)b.textContent=active?'KIOSK: EIN':'KIOSK: AUS';}
 byId('kor-big-screen-trigger').addEventListener('click',function(){big(!document.body.classList.contains('kor-big-screen-active'));});
 byId('kor-kiosk-trigger').addEventListener('click',function(){kiosk(!document.body.classList.contains('kor-kiosk-active'));});
 document.addEventListener('keydown',function(e){if(e.key==='Escape'){kiosk(false);big(false);}if(e.key==='F11'){e.preventDefault();big(!document.body.classList.contains('kor-big-screen-active'));}});
 async function mesh(){try{var r=await fetch('/api/mesh/status');if(!r.ok)return;var d=await r.json();var el=byId('kor-mesh-status');el.textContent=d.enabled?'MESH: '+d.connected_peers.length+' KNOTEN':'MESH: DEAKTIVIERT';el.title=d.connected_peers.join(', ');}catch(e){}}
 async function logs(){if(!document.body.classList.contains('kor-big-screen-active'))return;var el=byId('console-log-stream');try{var r=await fetch('/api/console/logs');if(!r.ok)return;var d=await r.json();el.innerHTML=d.logs.map(function(x){return '<div>'+esc(x.message)+' <span>'+esc(x.time)+' · '+esc(x.level)+' · '+esc(x.component)+'</span></div>';}).join('');el.scrollTop=el.scrollHeight;}catch(e){}}
 async function alerts(){try{var r=await fetch('/api/dashboard/projects');if(!r.ok)return;var d=await r.json();var rows=Array.isArray(d.items)?d.items:[];var count=rows.filter(function(p){return ['blockiert','gemischt'].indexOf(String(p.status||'').toLowerCase())>=0;}).length;banner.hidden=!count;banner.textContent=count?'⚠ LAGEHINWEIS: '+count+' Projekt(e) blockiert oder mit gemischtem Status.':'';}catch(e){}}
 big(false);mesh();logs();alerts();setInterval(mesh,5000);setInterval(logs,2000);setInterval(alerts,30000);
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();