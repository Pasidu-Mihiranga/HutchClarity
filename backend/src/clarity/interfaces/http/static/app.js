/* Shared helpers for the Clarity pages. No framework, no build step. */

/* The signed-in session.

   Held in memory only: a token in localStorage outlives the tab and the
   demo, and this one is a bearer credential. Reloading signs you out, which
   is the honest behaviour. */
let session = { token: null, who: null };

function signIn(token, who) { session = { token, who }; }
function signOut() { session = { token: null, who: null }; }
function signedIn() { return session.token !== null; }

async function api(path, method = 'GET', body = null) {
  const options = { method, headers: { 'Accept': 'application/json' } };
  if (session.token) {
    options.headers['Authorization'] = `Bearer ${session.token}`;
  }
  if (body !== null) {
    options.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(body);
  }
  const response = await fetch(path, options);
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;

  if (!response.ok) {
    // The API speaks RFC 9457 problem details, so surface the real reason
    // rather than a generic failure.
    const detail = payload && (payload.detail || payload.title);
    const error = new Error(detail || `Request failed (${response.status})`);
    error.code = payload && payload.code;
    error.status = response.status;
    throw error;
  }
  return payload;
}

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

function fmtDate(iso) {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'
  });
}

function show(id) { document.getElementById(id).classList.remove('hidden'); }
function hide(id) { document.getElementById(id).classList.add('hidden'); }

function showError(error) {
  const box = document.getElementById('error');
  if (!box) { console.error(error); return; }
  const code = error.code ? ` <span class="mono">(${esc(error.code)})</span>` : '';
  box.innerHTML = `<div class="error">${esc(error.message)}${code}</div>`;
  box.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function clearError() {
  const box = document.getElementById('error');
  if (box) box.innerHTML = '';
}
