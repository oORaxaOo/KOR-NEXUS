(() => {
  'use strict';

  const $ = (selector) => document.querySelector(selector);
  const panel = $('#lilithPanel');
  const openButton = $('#lilithOpen');
  const closeButton = $('#lilithClose');
  const newChatButton = $('#lilithNewChat');
  const statusNode = $('#lilithStatus');
  const topStatus = $('#lilithTopStatus');
  const messages = $('#lilithMessages');
  const form = $('#lilithForm');
  const input = $('#lilithInput');
  const sendButton = $('#lilithSend');
  const inputCount = $('#lilithInputCount');

  if (!panel || !openButton || !form || !input || !messages) return;

  const SESSION_KEY = 'korNexusLilithSessionV1';
  const MAX_MESSAGE = 12000;
  let busy = false;
  let previousFocus = null;

  function createSessionId() {
    if (window.crypto && typeof window.crypto.randomUUID === 'function') {
      return window.crypto.randomUUID().replaceAll('-', '');
    }
    const bytes = new Uint8Array(16);
    if (window.crypto && typeof window.crypto.getRandomValues === 'function') {
      window.crypto.getRandomValues(bytes);
      return Array.from(bytes, (value) => value.toString(16).padStart(2, '0')).join('');
    }
    return String(Date.now().toString(16)) + String(Math.random().toString(16).slice(2));
  }

  function getSessionId() {
    try {
      let value = window.localStorage.getItem(SESSION_KEY);
      if (!value || !/^[A-Za-z0-9_.-]{1,80}$/.test(value)) {
        value = createSessionId();
        window.localStorage.setItem(SESSION_KEY, value);
      }
      return value;
    } catch (_error) {
      return createSessionId();
    }
  }

  let sessionId = getSessionId();

  function setStatus(available, detail) {
    const label = available ? 'VERBUNDEN' : 'OFFLINE';
    statusNode.classList.toggle('is-online', Boolean(available));
    statusNode.classList.toggle('is-offline', !available);
    statusNode.querySelector('span').textContent = detail || label;
    statusNode.setAttribute('aria-label', label);
    topStatus.classList.toggle('is-online', Boolean(available));
    topStatus.classList.toggle('is-offline', !available);
    topStatus.title = detail || label;
  }

  async function refreshStatus() {
    try {
      const response = await fetch('/api/lilith/status', {
        method: 'GET',
        headers: { 'Accept': 'application/json' },
        cache: 'no-store',
        credentials: 'same-origin'
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || ('HTTP ' + response.status));
      setStatus(Boolean(data.available), data.detail || (data.available ? 'Hermes-Gateway verbunden.' : 'Hermes ist nicht verbunden.'));
    } catch (_error) {
      setStatus(false, 'Hermes-Verbindung nicht erreichbar.');
    }
  }

  function scrollToLatest() {
    messages.scrollTop = messages.scrollHeight;
  }

  function addMessage(role, text, extraClass = '') {
    const bubble = document.createElement('article');
    bubble.className = 'lilith-message lilith-message-' + role + (extraClass ? ' ' + extraClass : '');
    const label = document.createElement('div');
    label.className = 'lilith-message-label';
    label.textContent = role === 'user' ? 'DU' : role === 'assistant' ? 'LILITH' : 'SYSTEM';
    const body = document.createElement('div');
    body.className = 'lilith-message-body';
    body.textContent = String(text);
    bubble.append(label, body);
    messages.appendChild(bubble);
    scrollToLatest();
    return bubble;
  }

  function updateComposer() {
    const length = input.value.length;
    inputCount.textContent = length.toLocaleString('de-DE') + ' / 12.000';
    sendButton.disabled = busy || !input.value.trim() || length > MAX_MESSAGE;
    if (length > MAX_MESSAGE) inputCount.classList.add('is-over-limit');
    else inputCount.classList.remove('is-over-limit');
  }

  function openPanel() {
    previousFocus = document.activeElement;
    panel.hidden = false;
    document.body.classList.add('lilith-open');
    input.focus();
    refreshStatus();
  }

  function closePanel() {
    panel.hidden = true;
    document.body.classList.remove('lilith-open');
    if (previousFocus && typeof previousFocus.focus === 'function') previousFocus.focus();
  }

  function newSession() {
    if (busy) return;
    sessionId = createSessionId();
    try {
      window.localStorage.setItem(SESSION_KEY, sessionId);
    } catch (_error) {
      // The page can continue with the in-memory session.
    }
    messages.replaceChildren();
    const welcome = document.createElement('div');
    welcome.className = 'lilith-welcome';
    const mark = document.createElement('span');
    mark.className = 'lilith-welcome-mark';
    mark.textContent = '✦';
    const heading = document.createElement('strong');
    heading.textContent = 'Neue Sitzung eröffnet';
    const copy = document.createElement('p');
    copy.textContent = 'Diese Unterhaltung verwendet eine neue Hermes-Sitzung. Deine anderen Kanäle bleiben davon getrennt.';
    welcome.append(mark, heading, copy);
    messages.appendChild(welcome);
    input.value = '';
    updateComposer();
    input.focus();
  }

  async function sendMessage(message) {
    if (busy || !message.trim() || message.length > MAX_MESSAGE) return;
    busy = true;
    updateComposer();
    addMessage('user', message);
    const waiting = addMessage('assistant', 'Lilith verarbeitet deine Nachricht…', 'is-pending');
    const waitingBody = waiting.querySelector('.lilith-message-body');
    input.value = '';
    updateComposer();
    input.focus();

    try {
      const response = await fetch('/api/lilith/message', {
        method: 'POST',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ session_id: sessionId, message }),
        cache: 'no-store',
        credentials: 'same-origin'
      });
      const data = await response.json();
      if (!response.ok || data.ok === false) {
        throw new Error(data.error || ('Anfrage fehlgeschlagen (HTTP ' + response.status + ').'));
      }
      waiting.classList.remove('is-pending');
      waitingBody.textContent = typeof data.response === 'string' ? data.response : 'Lilith hat keine Textantwort zurückgegeben.';
      setStatus(true, 'Hermes-Gateway verbunden.');
    } catch (error) {
      waiting.classList.remove('is-pending');
      waiting.classList.add('is-error');
      waitingBody.textContent = error instanceof Error ? error.message : 'Die Nachricht konnte nicht übermittelt werden.';
      refreshStatus();
    } finally {
      busy = false;
      updateComposer();
      scrollToLatest();
    }
  }

  openButton.addEventListener('click', openPanel);
  closeButton.addEventListener('click', closePanel);
  newChatButton.addEventListener('click', newSession);
  panel.addEventListener('click', (event) => {
    if (event.target === panel) closePanel();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !panel.hidden) closePanel();
  });
  input.addEventListener('input', updateComposer);
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      form.requestSubmit();
    }
  });
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    void sendMessage(input.value);
  });

  updateComposer();
  setStatus(false, 'Noch nicht verbunden');
})();