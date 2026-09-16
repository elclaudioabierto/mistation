const points = [];
const activity = document.getElementById('activity');
const chart = document.getElementById('listenerChart');
let previousSource = null;
let previousListeners = null;
const controlMessage = document.getElementById('controlMessage');

function esc(value) { return String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

function drawChart() {
  const values = points.length ? points : [0];
  const max = Math.max(4, ...values);
  const left = 22, top = 18, width = 716, height = 215;
  const coords = values.map((value, index) => {
    const x = left + (values.length === 1 ? width : index * width / (values.length - 1));
    const y = top + height - (value / max) * height;
    return [x, y];
  });
  const line = coords.map(([x,y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
  const area = `${line} L${coords.at(-1)[0]},${top + height} L${coords[0][0]},${top + height} Z`;
  chart.innerHTML = [0, .33, .66, 1].map(r => `<line class="chart-grid" x1="${left}" x2="${left+width}" y1="${top+height-r*height}" y2="${top+height-r*height}"/>`).join('') +
    `<path class="chart-area" d="${area}"/><path class="chart-line" d="${line}"/>` +
    (coords.length ? `<circle class="chart-point" cx="${coords.at(-1)[0]}" cy="${coords.at(-1)[1]}" r="5"/>` : '');
}

function addActivity(title, detail) {
  const time = new Date().toLocaleTimeString([], {hour:'numeric', minute:'2-digit'}).toUpperCase();
  const item = document.createElement('div');
  item.className = 'activity-item';
  item.innerHTML = `<span class="activity-icon">•</span><div><strong>${esc(title)}</strong><p>${esc(detail)}</p></div><time>${time}</time>`;
  activity.prepend(item);
  while (activity.children.length > 5) activity.lastElementChild.remove();
}

async function refresh() {
  try {
    const data = await (await fetch('/api/status', {cache:'no-store'})).json();
    const active = data.source !== 'offline';
    const listeners = Number(data.listeners || 0);
    points.push(listeners);
    if (points.length > 36) points.shift();
    drawChart();
    document.getElementById('listeners').textContent = listeners;
    document.getElementById('listenerDelta').textContent = previousListeners === null ? 'Live count' : `${listeners >= previousListeners ? '+' : ''}${listeners - previousListeners} since last check`;
    document.getElementById('source').textContent = active ? data.source : 'Offline';
    document.getElementById('source').style.color = active ? 'var(--green)' : 'var(--muted)';
    document.getElementById('sourceName').textContent = active ? data.source : 'Offline';
    document.getElementById('trackName').textContent = data.current_file || 'Waiting for a broadcast source';
    document.getElementById('currentFile').textContent = data.current_file ? data.current_file.split('/').pop() : 'No source selected';
    document.getElementById('bitrate').textContent = data.encoding?.bitrate || '—';
    document.getElementById('sourceBitrate').textContent = data.encoding?.bitrate || '—';
    document.getElementById('sourceDot').style.background = active ? 'var(--green)' : 'var(--muted)';
    document.getElementById('lastUpdated').textContent = `UPDATED ${new Date().toLocaleTimeString([], {hour:'numeric', minute:'2-digit'})}`;
    document.getElementById('chartRange').textContent = points.length < 6 ? 'Collecting live data…' : `${Math.min(points.length * 5, 180)} SECOND WINDOW`;
    if (previousSource !== null && previousSource !== data.source) addActivity('Source changed', `${previousSource} → ${data.source}`);
    if (previousListeners !== null && previousListeners !== listeners) addActivity('Audience updated', `${listeners} listener${listeners === 1 ? '' : 's'} connected`);
    previousSource = data.source;
    previousListeners = listeners;
  } catch { document.getElementById('lastUpdated').textContent = 'UPDATE FAILED'; }
}

async function switchSource(source) {
  const token = document.getElementById('adminToken').value;
  if (!token) { controlMessage.textContent = 'Enter the admin token first.'; return; }
  controlMessage.textContent = `Switching to ${source}…`;
  try {
    const response = await fetch(`/api/source/${source}`, {method:'POST', headers:{'X-Admin-Token':token}});
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Request failed');
    controlMessage.textContent = `Source set to ${data.source}.`;
    addActivity('Source switched', `Broadcast source set to ${data.source}`);
    refresh();
  } catch (error) { controlMessage.textContent = error.message; }
}

document.querySelectorAll('[data-source]').forEach(button => button.addEventListener('click', () => switchSource(button.dataset.source)));

drawChart();
refresh();
setInterval(refresh, 5000);
