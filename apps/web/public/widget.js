/**
 * NakTahu embeddable widget — load via:
 * <script src="https://naktahu.netlify.app/widget.js"
 *   data-api-key="nkt_live_..."
 *   data-domain="tax"
 *   data-lang="bm"
 *   data-theme="light"
 *   data-title="Ask NakTahu"
 *   data-white-label="false"></script>
 */
(function () {
  'use strict';

  var script = document.currentScript;
  if (!script) return;

  var apiKey = script.getAttribute('data-api-key') || '';
  var domain = script.getAttribute('data-domain') || '';
  var lang = script.getAttribute('data-lang') || 'bm';
  var theme = script.getAttribute('data-theme') || 'light';
  var title = script.getAttribute('data-title') || 'NakTahu';
  var whiteLabel = script.getAttribute('data-white-label') === 'true';
  var apiBase = script.getAttribute('data-api-base') || '';

  if (!apiKey) {
    console.error('[NakTahu] data-api-key is required');
    return;
  }

  if (!apiBase) {
    var src = script.src || '';
    try {
      apiBase = new URL(src).origin;
    } catch (_e) {
      apiBase = '';
    }
  }

  var isDark = theme === 'dark';
  var rootId = 'naktahu-widget-root';

  if (document.getElementById(rootId)) return;

  var styles = document.createElement('style');
  styles.textContent =
    '#' +
    rootId +
    ' *{box-sizing:border-box;font-family:system-ui,-apple-system,sans-serif}' +
    '#' +
    rootId +
    ' .nkt-bubble{position:fixed;bottom:20px;right:20px;width:56px;height:56px;border-radius:50%;border:none;cursor:pointer;z-index:99998;box-shadow:0 4px 20px rgba(0,0,0,.2);display:flex;align-items:center;justify-content:center;font-size:24px}' +
    '#' +
    rootId +
    ' .nkt-panel{position:fixed;bottom:88px;right:20px;width:380px;height:520px;max-width:calc(100vw - 40px);max-height:calc(100vh - 120px);border-radius:16px;z-index:99999;display:none;flex-direction:column;overflow:hidden;box-shadow:0 8px 40px rgba(0,0,0,.18)}' +
    '#' +
    rootId +
    ' .nkt-panel.open{display:flex}' +
    '#' +
    rootId +
    ' .nkt-header{padding:12px 16px;font-weight:600;font-size:14px;display:flex;justify-content:space-between;align-items:center}' +
    '#' +
    rootId +
    ' .nkt-messages{flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:8px}' +
    '#' +
    rootId +
    ' .nkt-msg{padding:10px 12px;border-radius:12px;font-size:13px;line-height:1.45;max-width:90%}' +
    '#' +
    rootId +
    ' .nkt-msg.user{align-self:flex-end}' +
    '#' +
    rootId +
    ' .nkt-msg.bot{align-self:flex-start}' +
    '#' +
    rootId +
    ' .nkt-input-row{display:flex;gap:8px;padding:12px;border-top:1px solid rgba(0,0,0,.08)}' +
    '#' +
    rootId +
    ' .nkt-input{flex:1;border:1px solid rgba(0,0,0,.12);border-radius:10px;padding:8px 12px;font-size:13px;outline:none}' +
    '#' +
    rootId +
    ' .nkt-send{border:none;border-radius:10px;padding:8px 14px;font-size:13px;font-weight:600;cursor:pointer}' +
    '#' +
    rootId +
    ' .nkt-brand{font-size:10px;text-align:center;padding:4px;opacity:.6}';

  var light = {
    bubble: '#2563EB',
    bubbleText: '#fff',
    panel: '#fff',
    header: '#18181b',
    userBg: '#2563EB',
    userText: '#fff',
    botBg: '#f4f4f5',
    botText: '#27272a',
    send: '#2563EB',
    sendText: '#fff',
  };
  var dark = {
    bubble: '#3b82f6',
    bubbleText: '#fff',
    panel: '#0A0F1E',
    header: '#f4f4f5',
    userBg: '#2563EB',
    userText: '#fff',
    botBg: 'rgba(255,255,255,.08)',
    botText: '#e4e4e7',
    send: '#3b82f6',
    sendText: '#fff',
  };
  var c = isDark ? dark : light;

  var root = document.createElement('div');
  root.id = rootId;

  var bubble = document.createElement('button');
  bubble.className = 'nkt-bubble';
  bubble.setAttribute('aria-label', 'Open chat');
  bubble.style.background = c.bubble;
  bubble.style.color = c.bubbleText;
  bubble.textContent = '💬';

  var panel = document.createElement('div');
  panel.className = 'nkt-panel';
  panel.style.background = c.panel;

  var header = document.createElement('div');
  header.className = 'nkt-header';
  header.style.color = c.header;
  header.innerHTML =
    '<span>' +
    (whiteLabel ? title : title) +
    '</span><button type="button" aria-label="Close" style="background:none;border:none;cursor:pointer;font-size:18px;opacity:.6">×</button>';
  header.querySelector('button').onclick = function () {
    panel.classList.remove('open');
  };

  var messages = document.createElement('div');
  messages.className = 'nkt-messages';

  var inputRow = document.createElement('div');
  inputRow.className = 'nkt-input-row';
  if (isDark) inputRow.style.borderColor = 'rgba(255,255,255,.1)';

  var input = document.createElement('input');
  input.className = 'nkt-input';
  input.type = 'text';
  input.placeholder = lang === 'bm' ? 'Tanya sesuatu…' : 'Ask something…';
  if (isDark) {
    input.style.background = 'rgba(255,255,255,.05)';
    input.style.borderColor = 'rgba(255,255,255,.15)';
    input.style.color = '#fff';
  }

  var sendBtn = document.createElement('button');
  sendBtn.className = 'nkt-send';
  sendBtn.textContent = lang === 'bm' ? 'Hantar' : 'Send';
  sendBtn.style.background = c.send;
  sendBtn.style.color = c.sendText;

  var brand = document.createElement('div');
  brand.className = 'nkt-brand';
  brand.textContent = whiteLabel ? '' : 'Powered by NakTahu';
  brand.style.display = whiteLabel ? 'none' : 'block';

  inputRow.appendChild(input);
  inputRow.appendChild(sendBtn);
  panel.appendChild(header);
  panel.appendChild(messages);
  panel.appendChild(inputRow);
  if (!whiteLabel) panel.appendChild(brand);
  root.appendChild(bubble);
  root.appendChild(panel);

  document.head.appendChild(styles);
  document.body.appendChild(root);

  if (whiteLabel) {
    fetch(apiBase + '/api/v1/public/config', {
      headers: { 'X-NakTahu-Key': apiKey },
    })
      .then(function (res) {
        return res.ok ? res.json() : null;
      })
      .then(function (cfg) {
        if (cfg && !cfg.white_label) {
          brand.style.display = 'block';
          brand.textContent = 'Powered by NakTahu';
        }
      })
      .catch(function () {});
  }

  bubble.onclick = function () {
    panel.classList.toggle('open');
    if (panel.classList.contains('open')) input.focus();
  };

  function addMsg(text, role) {
    var el = document.createElement('div');
    el.className = 'nkt-msg ' + (role === 'user' ? 'user' : 'bot');
    el.style.background = role === 'user' ? c.userBg : c.botBg;
    el.style.color = role === 'user' ? c.userText : c.botText;
    el.textContent = text;
    messages.appendChild(el);
    messages.scrollTop = messages.scrollHeight;
    return el;
  }

  function ask(query) {
    if (!query.trim()) return;
    addMsg(query, 'user');
    input.value = '';
    sendBtn.disabled = true;
    var botEl = addMsg(lang === 'bm' ? 'Memikir…' : 'Thinking…', 'bot');

    var body = { query: query, language: lang };
    if (domain) body.domain = domain;

    fetch(apiBase + '/api/v1/public/query', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-NakTahu-Key': apiKey,
      },
      body: JSON.stringify(body),
    })
      .then(function (res) {
        if (!res.ok) throw new Error('API error ' + res.status);
        return res.json();
      })
      .then(function (data) {
        botEl.textContent = data.answer || (lang === 'bm' ? 'Tiada jawapan.' : 'No answer.');
      })
      .catch(function () {
        botEl.textContent =
          lang === 'bm' ? 'Ralat. Sila cuba lagi.' : 'Error. Please try again.';
      })
      .finally(function () {
        sendBtn.disabled = false;
      });
  }

  sendBtn.onclick = function () {
    ask(input.value);
  };
  input.onkeydown = function (e) {
    if (e.key === 'Enter') ask(input.value);
  };
})();
