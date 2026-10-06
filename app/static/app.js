const plannerFields = document.querySelector('#planner-fields');
const plannerForm = document.querySelector('#planner-form');
const statusMessage = document.querySelector('#status-message');
const resultsSection = document.querySelector('#results-section');
const historySection = document.querySelector('#history-section');
const dialog = document.querySelector('#account-dialog');
let planner = 'home';
let authMode = 'login';
let currentUser = null;

const formMarkup = {
  home: `<div class="form-grid"><label class="wide">Total budget (₹)<input name="budget" type="number" min="1" max="10000000" step="100" placeholder="e.g. 50000" required></label><label>Rooms or areas<input name="room_types" maxlength="240" placeholder="Living room, bedroom" required></label><label>Style preference<input name="style" maxlength="120" placeholder="Minimal, warm, colorful"></label><label class="wide">What do you need?<input name="needs" maxlength="200" placeholder="Lighting, curtains, storage"></label></div>`,
  party: `<div class="form-grid"><label>Total budget (₹)<input name="budget" type="number" min="1" max="10000000" step="100" placeholder="e.g. 40000" required></label><label>Number of guests<input name="guests" type="number" min="1" max="5000" step="1" placeholder="e.g. 35" required></label><label>Event type<input name="event_type" maxlength="80" placeholder="Birthday, wedding, dinner" required></label><label>Venue preference<input name="venue" maxlength="120" placeholder="At home, restaurant, outdoors"></label><label class="wide">Style or priorities<input name="style" maxlength="120" placeholder="Casual, vegetarian, kid-friendly"></label></div>`,
  jewelry: `<div class="form-grid"><label>Total budget (₹)<input name="budget" type="number" min="1" max="10000000" step="100" placeholder="e.g. 8000" required></label><label>Occasion<input name="occasion" maxlength="100" placeholder="Wedding, celebration, work" required></label><label>Style preference<input name="style" maxlength="120" placeholder="Classic, modern, minimal"></label><label>Outfit colors or notes<input name="outfit_notes" maxlength="160" placeholder="Optional: navy blue, gold accents"></label><label class="wide upload-label">Optional outfit photo <span class="upload-hint">JPEG, PNG or WebP · max 5 MB</span><input name="image" type="file" accept="image/jpeg,image/png,image/webp"></label></div>`
};

function renderFields() { plannerFields.innerHTML = formMarkup[planner]; }
renderFields();

document.querySelectorAll('.planner-tab').forEach(button => button.addEventListener('click', () => {
  planner = button.dataset.planner;
  document.querySelectorAll('.planner-tab').forEach(tab => { const active = tab === button; tab.classList.toggle('active', active); tab.setAttribute('aria-selected', String(active)); });
  renderFields(); statusMessage.textContent = ''; resultsSection.hidden = true;
}));

function setStatus(message, kind = '') { statusMessage.textContent = message; statusMessage.className = `status-message ${kind}`; }
function money(value) { return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(value); }

plannerForm.addEventListener('submit', async event => {
  event.preventDefault(); setStatus('Putting your plan together…');
  const button = document.querySelector('#submit-button'); button.disabled = true;
  const form = new FormData(plannerForm);
  const data = Object.fromEntries([...form.entries()].filter(([key, value]) => key !== 'image' && value !== '').map(([key, value]) => [key, key === 'budget' || key === 'guests' ? Number(value) : value]));
  const request = new FormData(); request.set('payload', JSON.stringify(data));
  const photo = form.get('image'); if (photo?.size) request.set('image', photo);
  try {
    const response = await fetch(`/api/recommendations/${planner}`, { method: 'POST', body: request });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || 'Unable to create a plan.');
    showResult(result); setStatus('Your plan is ready.', 'success');
  } catch (error) { setStatus(error.message || 'Something went wrong. Please try again.', 'error'); }
  finally { button.disabled = false; }
});

function showResult(result) {
  document.querySelector('#result-title').textContent = result.title;
  document.querySelector('#result-summary').textContent = result.summary;
  document.querySelector('#result-source').textContent = result.source;
  document.querySelector('#budget-value').textContent = money(result.total_budget);
  document.querySelector('#total-value').textContent = money(result.total_estimated);
  const grid = document.querySelector('#recommendation-grid'); grid.replaceChildren();
  for (const [index, item] of result.items.entries()) {
    const card = document.createElement('article'); card.className = 'recommendation-card';
    const count = document.createElement('span'); count.className = 'item-number'; count.textContent = String(index + 1).padStart(2, '0');
    const category = document.createElement('p'); category.className = 'item-category'; category.textContent = item.category;
    const title = document.createElement('h3'); title.textContent = item.title;
    const rationale = document.createElement('p'); rationale.className = 'item-rationale'; rationale.textContent = item.rationale;
    const row = document.createElement('div'); row.className = 'item-bottom';
    const price = document.createElement('strong'); price.textContent = money(item.estimated_price);
    const link = document.createElement('a'); link.href = item.search_url; link.target = '_blank'; link.rel = 'noopener noreferrer'; link.textContent = `Search ${item.retailer} ↗`;
    row.append(price, link); card.append(count, category, title, rationale, row); grid.append(card);
  }
  for (const [id, values] of [['tips-list', result.tips], ['caveats-list', result.caveats]]) {
    const list = document.getElementById(id); list.replaceChildren();
    values.forEach(text => { const li = document.createElement('li'); li.textContent = text; list.append(li); });
  }
  resultsSection.hidden = false; historySection.hidden = true; resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function refreshSession() {
  const response = await fetch('/api/session'); const data = await response.json(); currentUser = data.user;
  document.querySelector('#account-button').textContent = currentUser ? 'Sign out' : 'Sign in';
  document.querySelector('#history-button').hidden = !currentUser;
}
document.querySelector('#account-button').addEventListener('click', async () => {
  if (currentUser) { await fetch('/api/logout', { method: 'POST' }); currentUser = null; await refreshSession(); setStatus('You are signed out.'); }
  else { setAuthMode('login'); dialog.showModal(); }
});
function setAuthMode(mode) {
  authMode = mode; const registering = mode === 'register';
  document.querySelector('#auth-title').textContent = registering ? 'Create your account' : 'Welcome back';
  document.querySelector('#name-field').hidden = !registering;
  document.querySelector('#name-field input').required = registering;
  document.querySelector('#auth-submit').textContent = registering ? 'Create account' : 'Sign in';
  document.querySelector('#auth-form [name="password"]').autocomplete = registering ? 'new-password' : 'current-password';
  document.querySelector('#login-tab').classList.toggle('active', !registering);
  document.querySelector('#register-tab').classList.toggle('active', registering);
  document.querySelector('#auth-error').textContent = '';
}
document.querySelector('#login-tab').addEventListener('click', () => setAuthMode('login'));
document.querySelector('#register-tab').addEventListener('click', () => setAuthMode('register'));
document.querySelector('#auth-form').addEventListener('submit', async event => {
  event.preventDefault(); const form = new FormData(event.currentTarget); const body = Object.fromEntries(form.entries());
  try {
    const response = await fetch(`/api/${authMode}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const data = await response.json(); if (!response.ok) throw new Error(data.detail || 'Account request failed.');
    dialog.close(); await refreshSession(); setStatus(`Welcome${currentUser?.display_name ? `, ${currentUser.display_name}` : ''}.`, 'success');
  } catch (error) { document.querySelector('#auth-error').textContent = error.message; }
});

document.querySelector('#history-button').addEventListener('click', loadHistory);
document.querySelector('#close-history').addEventListener('click', () => { historySection.hidden = true; });
async function loadHistory() {
  const response = await fetch('/api/history'); const data = await response.json();
  if (!response.ok) return setStatus(data.detail || 'Could not load history.', 'error');
  const list = document.querySelector('#history-list'); list.replaceChildren();
  if (!data.items.length) { list.textContent = 'Your saved plans will show up here.'; }
  data.items.forEach(entry => {
    const card = document.createElement('button'); card.type = 'button'; card.className = 'history-entry';
    const name = document.createElement('strong'); name.textContent = entry.result.title;
    const detail = document.createElement('span'); detail.textContent = `${entry.planner} · ${money(entry.result.total_estimated)} estimated · ${new Date(entry.created_at + 'Z').toLocaleString()}`;
    card.append(name, detail); card.addEventListener('click', () => showResult(entry.result)); list.append(card);
  });
  historySection.hidden = false; resultsSection.hidden = true; historySection.scrollIntoView({ behavior: 'smooth' });
}

fetch('/api/health').then(response => response.json()).then(data => {
  document.querySelector('#mode-badge').textContent = data.recommendation_mode === 'gemini' ? '✦ Gemini AI enabled' : '◌ Demo mode · no API key';
}).catch(() => { document.querySelector('#mode-badge').textContent = 'Service unavailable'; });
refreshSession().catch(() => {});

