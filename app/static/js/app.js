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
