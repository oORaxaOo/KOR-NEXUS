(()=> {
  'use strict';
  const $ = id => document.getElementById(id);
  const statusNode = $('mesh-network-status');
  const stream = $('console-log-stream');
  const body = document.body;
  if (!statusNode || !stream) return;

  function setBigScreen(active) {
    body.classList.toggle('kor-big-screen-active', active);
    const button = $('big-screen-trigger');
    if (button) button.textContent = active ? 'HUD AUSBLENDEN / ESC' : 'HUD EINBLENDEN / ESC';
  }
  const params = new URLSearchParams(window.location.search);
  setBigScreen(params.get('native') === '1');

  const button = $('big-screen-trigger');
  if (button) button.addEventListener('click', () => setBigScreen(!body.classList.contains('kor-big-screen-active')));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !event.defaultPrevented) {
      setBigScreen(!body.classList.contains('kor-big-screen-active'));
    }
  });

  async function updateMeshStatus() {
    try {
      const response = await fetch('./api/mesh/status', {cache:'no-store'});
      if (!response.ok) throw new Error('HTTP ' + response.status);
      const data = await response.json();
      const peers = Array.isArray(data.connected_peers) ? data.connected_peers : [];
      statusNode.textContent = peers.length
        ? '🌐 MESH: GEKOPPELT [' + peers.length + ' AKTIVE EINHEIT(EN)] · ' + peers.join(', ')
        : '🌐 MESH: AUTARK · SUCHE AKTIV [0 VERBINDUNGEN]';
      statusNode.classList.toggle('mesh-connected', peers.length > 0);
      statusNode.classList.remove('mesh-error');
    } catch (_) {
      statusNode.textContent = '🌐 MESH: STATUS NICHT VERFÜGBAR';
      statusNode.classList.remove('mesh-connected');
      statusNode.classList.add('mesh-error');
    }
  }

  async function updateConsoleLogs() {
    if (!body.classList.contains('kor-big-screen-active')) return;
    try {
      const response = await fetch('./api/console/logs', {cache:'no-store'});
      if (!response.ok) throw new Error('HTTP ' + response.status);
      const data = await response.json();
      const fragment = document.createDocumentFragment();
      for (const entry of (Array.isArray(data.logs) ? data.logs : []).slice(-50)) {
        const line = document.createElement('div');
        const level = String(entry.level || 'INFO').toUpperCase();
        const component = String(entry.component || 'SYSTEM');
        const time = String(entry.time || '');
        const message = String(entry.message || '');
        line.className = 'console-log-line level-' + level.toLowerCase().replace(/[^a-z0-9_-]/g, '');
        line.textContent = '[' + time + '] [' + level + '] [' + component + '] ' + message;
        fragment.appendChild(line);
      }
      stream.replaceChildren(fragment);
      stream.scrollTop = stream.scrollHeight;
    } catch (_) {
      // Temporary startup/shutdown errors are expected; retry on the next poll.
    }
  }

  updateMeshStatus();
  updateConsoleLogs();
  window.setInterval(updateMeshStatus, 5000);
  window.setInterval(updateConsoleLogs, 2000);
})();
