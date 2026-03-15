// Close modals on overlay click
document.querySelectorAll('.modal-overlay').forEach(overlay => {
  overlay.addEventListener('click', e => {
    if (e.target === overlay) overlay.style.display = 'none';
  });
});

// Close modals on Escape
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay').forEach(m => m.style.display = 'none');
    const dd = document.getElementById('user-dropdown');
    if (dd) dd.style.display = 'none';
  }
});

// User dropdown toggle
function toggleUserMenu() {
  const dd = document.getElementById('user-dropdown');
  if (dd) dd.style.display = dd.style.display === 'none' ? 'block' : 'none';
}

// Close dropdown on outside click
document.addEventListener('click', e => {
  const dd = document.getElementById('user-dropdown');
  if (dd && !e.target.closest('.sidebar-user')) {
    dd.style.display = 'none';
  }
});

// Assignee autocomplete in new-ticket modal
const assigneeInput = document.getElementById('modal-assignee');
const suggestionsBox = document.getElementById('assignee-suggestions');
if (assigneeInput && suggestionsBox) {
  let users = [];
  fetch('/api/users').then(r => r.json()).then(data => { users = data; });

  assigneeInput.addEventListener('input', () => {
    const q = assigneeInput.value.toLowerCase();
    if (!q || q.length < 1) { suggestionsBox.style.display = 'none'; return; }
    const matches = users.filter(u =>
      u.display_name.toLowerCase().includes(q) || u.username.toLowerCase().includes(q)
    ).slice(0, 6);
    if (!matches.length) { suggestionsBox.style.display = 'none'; return; }
    suggestionsBox.innerHTML = matches.map(u =>
      `<div class="suggestion-item" onclick="selectAssignee('${u.display_name}')">
        <span class="suggestion-avatar" style="background:${u.avatar_color}">${u.display_name[0].toUpperCase()}</span>
        <span>${u.display_name}</span>
        <span class="suggestion-role">${u.role}</span>
      </div>`
    ).join('');
    suggestionsBox.style.display = 'block';
  });

  assigneeInput.addEventListener('blur', () => {
    setTimeout(() => { suggestionsBox.style.display = 'none'; }, 150);
  });
}

function selectAssignee(name) {
  const input = document.getElementById('modal-assignee');
  if (input) input.value = name;
  const box = document.getElementById('assignee-suggestions');
  if (box) box.style.display = 'none';
}

// ── Global Search ─────────────────────────────────────────────────────────────
const searchInput = document.getElementById('global-search-input');
const searchDropdown = document.getElementById('search-dropdown');
const searchKbd = document.getElementById('search-kbd');

if (searchInput) {
  let searchTimer = null;

  // '/' key to focus
  document.addEventListener('keydown', e => {
    if (e.key === '/' && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
      e.preventDefault();
      searchInput.focus();
    }
  });

  searchInput.addEventListener('focus', () => { if (searchKbd) searchKbd.style.display = 'none'; });
  searchInput.addEventListener('blur', () => {
    setTimeout(() => {
      if (searchDropdown) searchDropdown.style.display = 'none';
      if (searchKbd) searchKbd.style.display = '';
    }, 180);
  });

  searchInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      const q = searchInput.value.trim();
      if (q) window.location.href = `/search?q=${encodeURIComponent(q)}`;
    }
    if (e.key === 'Escape') { searchInput.blur(); }
  });

  searchInput.addEventListener('input', () => {
    clearTimeout(searchTimer);
    const q = searchInput.value.trim();
    if (!q) { searchDropdown.style.display = 'none'; return; }
    searchTimer = setTimeout(async () => {
      const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
      const data = await res.json();
      const tickets = data.tickets || [];
      const projects = data.projects || [];
      if (!tickets.length && !projects.length) {
        searchDropdown.innerHTML = '<div class="search-empty">No results</div>';
        searchDropdown.style.display = 'block';
        return;
      }
      let html = '';
      if (tickets.length) {
        html += '<div class="search-section-label">Tickets</div>';
        html += tickets.slice(0, 6).map(t => `
          <a class="search-result-item" href="/tickets/${t.id}">
            <span class="search-key">${t.key}</span>
            <span class="search-title">${t.title}</span>
            <span class="search-meta">${t.status} · ${t.priority}</span>
          </a>`).join('');
      }
      if (projects.length) {
        html += '<div class="search-section-label">Projects</div>';
        html += projects.slice(0, 4).map(p => `
          <a class="search-result-item" href="/projects/${p.id}">
            <span class="search-key" style="color:${p.color}">${p.key}</span>
            <span class="search-title">${p.name}</span>
            <span class="search-meta">${p.status}</span>
          </a>`).join('');
      }
      if (tickets.length + projects.length > 10) {
        html += `<a class="search-see-all" href="/search?q=${encodeURIComponent(q)}">See all results →</a>`;
      }
      searchDropdown.innerHTML = html;
      searchDropdown.style.display = 'block';
    }, 220);
  });
}

// ── Floating Chatbot ──────────────────────────────────────────────────────────
const SESSION_ID = 'widget-' + Math.random().toString(36).slice(2, 8);

function toggleChat() {
  const panel = document.getElementById('chatbot-panel');
  if (!panel) return;
  const open = panel.style.display !== 'none';
  panel.style.display = open ? 'none' : 'flex';
  if (!open) document.getElementById('chatbot-input')?.focus();
}

async function sendChat() {
  const input = document.getElementById('chatbot-input');
  const messages = document.getElementById('chatbot-messages');
  if (!input || !messages) return;
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  input.disabled = true;
  document.getElementById('chatbot-send').disabled = true;

  // Add user message
  messages.innerHTML += `<div class="chat-msg user"><div class="chat-bubble">${escHtml(text)}</div></div>`;
  messages.innerHTML += `<div class="chat-msg assistant" id="chat-thinking"><div class="chat-bubble thinking">&#8226;&#8226;&#8226;</div></div>`;
  messages.scrollTop = messages.scrollHeight;

  try {
    const res = await fetch('/api/ai/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, session_id: SESSION_ID }),
    });
    const data = await res.json();
    document.getElementById('chat-thinking')?.remove();
    const reply = data.reply || '(no response)';
    let extra = '';
    if (data.action_result?.type === 'created') {
      const t = data.action_result.ticket;
      extra = `<a class="chat-action-link" href="/tickets/${t.id}">${t.key}: ${t.title}</a>`;
    } else if (data.action_result?.type === 'updated') {
      const t = data.action_result.ticket;
      if (t) extra = `<a class="chat-action-link" href="/tickets/${t.id}">View ${t.key}</a>`;
    }
    messages.innerHTML += `<div class="chat-msg assistant"><div class="chat-bubble">${renderMd(reply)}${extra}</div></div>`;
  } catch (e) {
    document.getElementById('chat-thinking')?.remove();
    messages.innerHTML += `<div class="chat-msg assistant"><div class="chat-bubble" style="color:#ef4444">Error — please try again.</div></div>`;
  }
  input.disabled = false;
  document.getElementById('chatbot-send').disabled = false;
  input.focus();
  messages.scrollTop = messages.scrollHeight;
}

// Enter to send
document.getElementById('chatbot-input')?.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); }
});

function escHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function renderMd(s) {
  // minimal markdown: **bold**, *italic*, `code`, newlines
  return escHtml(s)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>');
}
