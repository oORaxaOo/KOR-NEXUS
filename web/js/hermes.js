(() => {
'use strict';
const $ = id => document.getElementById(id);
const state = {conversation:'main', messages:[], conversations:[], busy:false, connected:false, poll:null, lastMessageFingerprint:''};
const safe = value => String(value ?? '');
function node(tag, cls, content) {
  const element = document.createElement(tag);
  if (cls) element.className = cls;
  if (content !== undefined) element.textContent = safe(content);
  return element;
}
function notice(message, error=false) {
  const box=$('hermesNotice');
  box.textContent=message;
  box.className='hermes-notice'+(error?' error':'');
}
async function api(path, options={}) {
  const response=await fetch('/api'+path,{
    headers:{'Accept':'application/json','Content-Type':'application/json'},
    cache:'no-store',
    ...options
  });
  let data;
  try { data=await response.json(); }
  catch { throw new Error('Ungültige Antwort vom KOR-NEXUS-Kern.'); }
  if (!response.ok || data.ok===false) throw new Error(data.error||('HTTP '+response.status));
  return data;
}
function renderConnection(info) {
  state.connected=Boolean(info.connected);
  $('hermesLed').classList.toggle('online',state.connected);
  $('hermesConnection').textContent=state.connected?'HERMES VERBUNDEN':'HERMES OFFLINE';
  $('hermesLastSeen').textContent=info.last_seen_at?('· '+new Date(info.last_seen_at).toLocaleTimeString()):'';
  if (!info.configured) notice('Bridge noch nicht eingerichtet. Im KOR-NEXUS-Repository integrations/hermes/setup.sh ausführen und die ausgegebenen YAML-Blöcke zu Hermes hinzufügen.');
  else if (!state.connected) notice('Bridge ist eingerichtet, aber Hermes ist nicht erreichbar. Prüfe, ob KOR-NEXUS läuft und das Hermes Gateway neu gestartet wurde.');
  else notice('Verbindung hergestellt. Nachrichten werden über das lokale Hermes Gateway verarbeitet.');
}
function renderConversations() {
  const root=$('hermesConversations'); root.replaceChildren();
  $('hermesConversationCount').textContent=String(state.conversations.length)+' KANÄLE';
  const known=new Set(state.conversations.map(x=>x.conversation_id));
  if (!known.has(state.conversation)) state.conversations.unshift({conversation_id:state.conversation,last_message:'Neue Unterhaltung',message_count:0});
  state.conversations.sort((a,b)=>a.conversation_id===state.conversation?-1:b.conversation_id===state.conversation?1:0);
  for (const item of state.conversations) {
    const id=safe(item.conversation_id);
    const button=node('button','hermes-conversation'+(id===state.conversation?' active':''));
    button.type='button';
    button.append(node('strong','',id==='main'?'HAUPTKANAL':id));
    button.append(node('small','',safe(item.last_message||'Noch keine Nachrichten').slice(0,110)));
    button.addEventListener('click',()=>selectConversation(id));
    root.append(button);
  }
}
function renderMessages() {
  const root=$('hermesMessages'); root.replaceChildren();
  $('hermesChatTitle').textContent=state.conversation==='main'?'Hauptkanal':state.conversation;
  $('hermesMessageCount').textContent=state.messages.length+' NACHRICHTEN';
  if (!state.messages.length) {
    root.append(node('div','hermes-empty','Noch keine Nachrichten in diesem Kanal. Schreibe Hermes, um die Unterhaltung zu beginnen.'));
    return;
  }
  for (const message of state.messages) {
    const direction=safe(message.direction);
    const bubble=node('article','hermes-message '+(direction==='user'?'user':direction==='assistant'?'assistant':'system'));
    bubble.append(node('div','',safe(message.content)));
    const meta=[safe(message.sender_name|| (direction==='assistant'?'Hermes':direction==='user'?'Du':'System'))];
    if(message.created_at) meta.push(new Date(message.created_at).toLocaleTimeString());
    bubble.append(node('small','',meta.join(' · ')));
    root.append(bubble);
  }
  root.scrollTop=root.scrollHeight;
}
async function loadStatus() {
  const status=await api('/hermes/status');
  renderConnection(status);
}
async function loadConversations() {
  const data=await api('/hermes/conversations');
  state.conversations=Array.isArray(data.items)?data.items:[];
  renderConversations();
}
async function loadMessages() {
  const data=await api('/hermes/messages?conversation_id='+encodeURIComponent(state.conversation)+'&limit=200');
  const next=Array.isArray(data.items)?data.items:[];
  const fingerprint=next.map(m=>safe(m.id)+':'+safe(m.status)).join('|');
  if(fingerprint!==state.lastMessageFingerprint) {
    state.lastMessageFingerprint=fingerprint;
    state.messages=next;
    renderMessages();
  }
}
async function refresh() {
  try {
    await Promise.all([loadStatus(),loadConversations(),loadMessages()]);
  } catch(error) {
    renderConnection({connected:false,configured:true});
    notice(error.message,true);
  }
}
async function selectConversation(id) {
  if(!id || id===state.conversation)return;
  state.conversation=id;
  state.lastMessageFingerprint='';
  renderConversations();
  try { await loadMessages(); }
  catch(error) { notice(error.message,true); }
}
async function sendMessage() {
  const input=$('hermesInput');
  const content=input.value.trim();
  if(!content || state.busy)return;
  state.busy=true;
  $('hermesSend').disabled=true;
  try {
    await api('/hermes/messages',{method:'POST',body:JSON.stringify({conversation_id:state.conversation,content})});
    input.value='';
    await Promise.all([loadMessages(),loadConversations()]);
    notice('Nachricht an Hermes übergeben.');
  } catch(error) {
    notice(error.message,true);
  } finally {
    state.busy=false;
    $('hermesSend').disabled=false;
    input.focus();
  }
}
$('hermesComposer').addEventListener('submit',event=>{event.preventDefault();sendMessage();});
$('hermesInput').addEventListener('keydown',event=>{
  if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendMessage();}
});
$('hermesNewConversation').addEventListener('click',async()=>{
  const id='kanal-'+new Date().toISOString().slice(0,10)+'-'+Math.random().toString(36).slice(2,6);
  await selectConversation(id);
  renderConversations();
  renderMessages();
});
refresh();
state.poll=window.setInterval(refresh,2500);
window.addEventListener('beforeunload',()=>{if(state.poll)window.clearInterval(state.poll);});
})();
