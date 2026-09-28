let state = null;
let selectedRoute = [];
const colors = { low: '#2fca80', medium: '#f7a642', high: '#ea5a5a' };
const svg = document.getElementById('network');

function escapeHtml(value) { return String(value).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }
function point(node) { return { x: 100 + ((node.longitude - 77.59) / .01) * 600, y: 470 - ((node.latitude - 12.965) / .01) * 380 }; }
function render() {
  if (!state) return;
  const intersections = Object.fromEntries(state.intersections.map(n => [n.id, n]));
  const roads = state.roads.map(road => {
    const a = point(intersections[road.from_node]), b = point(intersections[road.to_node]);
    const active = selectedRoute.includes(road.id);
    const colour = road.blocked ? '#751d2a' : colors[road.congestion_level];
    return `<line class="road" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="${active ? '#4bb7ff' : colour}" stroke-width="${active ? 13 : 8}"/><text x="${(a.x+b.x)/2}" y="${(a.y+b.y)/2-8}" fill="#b8c9db" font-size="11">${road.id}</text>`;
  }).join('');
  const nodes = state.intersections.map(node => { const p = point(node); return `<circle cx="${p.x}" cy="${p.y}" r="12" fill="#d8e7f5"/><text class="node-label" x="${p.x-5}" y="${p.y+5}">${node.id}</text>`; }).join('');
  const vehicles = state.vehicles.map(vehicle => { const p=point(vehicle); return `<circle class="vehicle" cx="${p.x}" cy="${p.y}" r="5"><title>${vehicle.id}: ${Math.round(vehicle.speed_kmph)} km/h</title></circle>`; }).join('');
  svg.innerHTML = `<rect width="800" height="540" fill="#0b1929"/><path d="M30 90 H770 M30 270 H770 M30 450 H770 M120 30 V510 M400 30 V510 M680 30 V510" stroke="#244258" stroke-width="1" opacity=".45"/>` + roads + nodes + vehicles;
  document.getElementById('summary').innerHTML = [
    ['Live vehicle detections', state.camera?.vehicle_count ?? '—'], ['High congestion roads', state.summary.high_congestion_roads],
    ['Active incidents', state.summary.active_incidents], ['Average speed', `${state.summary.average_network_speed_kmph} km/h`]
  ].map(([label, value]) => `<div class="card"><p>${label}</p><strong>${value}</strong></div>`).join('');
  document.getElementById('vehicle-count').textContent = state.summary.active_vehicles;
  document.getElementById('incident-total').textContent = state.summary.active_incidents;
  document.getElementById('updated-at').textContent = `Updated ${new Date().toLocaleTimeString([], {hour:'2-digit', minute:'2-digit', second:'2-digit'})}`;
  document.getElementById('incident-list').innerHTML = state.incidents.length ? state.incidents.map(i => `<div class="incident"><div><span class="incident-icon">!</span><strong>${escapeHtml(i.road_id)} · ${escapeHtml(i.severity)}</strong></div><p>${escapeHtml(i.message)}</p><button onclick="clearIncident('${i.id}')">Resolve incident</button></div>`).join('') : '<p class="empty-state">No incidents require attention.</p>';
  document.getElementById('road-health').innerHTML = [...state.roads].sort((a,b) => a.current_speed_kmph-b.current_speed_kmph).slice(0,5).map(road => `<div class="road-row"><span class="road-dot ${road.blocked ? 'high' : road.congestion_level}"></span><strong>${road.id}</strong><div class="road-meter"><i style="width:${Math.max(8, road.current_speed_kmph / road.speed_limit_kmph * 100)}%" class="${road.blocked ? 'high' : road.congestion_level}"></i></div><span>${Math.round(road.current_speed_kmph)} km/h</span></div>`).join('');
  renderCamera(state.camera);
  renderResponseLayer(state.alerts || [], state.signals || []);
}
function renderResponseLayer(alerts, signals) {
  const traveller = alerts.filter(alert => alert.audience === 'traveller');
  const police = alerts.filter(alert => alert.audience === 'police' || alert.audience === 'traffic_control');
  document.getElementById('traveller-alerts').innerHTML = traveller.length ? traveller.map(alert => `<div class="traveller-alert"><span>!</span><div><strong>${escapeHtml(alert.title)}</strong><p>${escapeHtml(alert.message)}</p></div></div>`).join('') : '<p class="empty-state">Your route is clear. FlowMirror will notify you if conditions change.</p>';
  document.getElementById('police-count').textContent = police.length;
  document.getElementById('police-alerts').innerHTML = police.length ? police.map(alert => `<div class="police-alert"><strong>${escapeHtml(alert.title)}</strong><p>${escapeHtml(alert.message)}</p><button onclick="acknowledgeAlert('${alert.id}')">Acknowledge dispatch</button></div>`).join('') : '<p class="empty-state">No incidents awaiting police response.</p>';
  document.getElementById('signal-list').innerHTML = signals.map(signal => `<div class="signal-row"><span class="signal-lamp ${signal.mode}"></span><div><strong>${signal.intersection_id} · ${escapeHtml(signal.phase_label)}</strong><p>${escapeHtml(signal.reason)}</p></div><div class="signal-time"><b>${signal.green_seconds}s</b><span>green</span><button onclick="toggleSignal('${signal.id}','${signal.mode === 'adaptive' ? 'emergency' : 'adaptive'}')">${signal.mode === 'adaptive' ? 'Emergency' : 'Auto'}</button></div></div>`).join('');
}
function renderCamera(camera) {
  if (!camera) return;
  const running = camera.state === 'running';
  const badge = document.getElementById('camera-state');
  badge.textContent = running ? 'ANALYSING' : camera.state === 'error' ? 'SOURCE ERROR' : 'NO SOURCE';
  badge.className = `camera-state ${running ? 'active' : camera.state === 'error' ? 'error' : ''}`;
  document.getElementById('camera-message').textContent = camera.message;
  document.getElementById('camera-speed').textContent = running ? `${camera.average_speed_kmph} km/h estimate` : '— km/h estimate';
  document.getElementById('camera-metrics').innerHTML = `<div><span>Vehicles</span><strong>${running ? camera.vehicle_count : '—'}</strong></div><div><span>Traffic state</span><strong class="${camera.congestion || ''}">${running ? camera.congestion : 'Waiting'}</strong></div><div><span>Stopped risk</span><strong>${running ? (camera.stopped_vehicle_risk ? 'Detected' : 'Clear') : '—'}</strong></div>`;
  const feed = document.getElementById('camera-feed'), placeholder = document.getElementById('camera-placeholder');
  if (running) { if (!feed.getAttribute('src')) feed.src = '/api/camera/stream?ts=' + Date.now(); feed.style.display = 'block'; placeholder.style.display = 'none'; }
  else { feed.removeAttribute('src'); feed.style.display = 'none'; placeholder.style.display = 'grid'; }
}
function renderChart(samples) {
  const chart = document.getElementById('speed-chart');
  const values = samples.slice(-50).map(s => s.average_speed_kmph);
  if (!values.length) { chart.innerHTML = ''; return; }
  const min = Math.max(0, Math.min(...values) - 4), max = Math.max(...values, 40);
  const points = values.map((value, index) => `${36 + index * (690 / Math.max(values.length - 1, 1))},${155 - ((value - min) / (max - min || 1)) * 115}`).join(' ');
  const area = `${points} 726,155 36,155`;
  chart.innerHTML = `<defs><linearGradient id="speed-fill" x1="0" x2="0" y1="0" y2="1"><stop stop-color="#56c6ff" stop-opacity=".35"/><stop offset="1" stop-color="#56c6ff" stop-opacity="0"/></linearGradient></defs><path d="M36 40 H726 M36 97 H726 M36 155 H726" stroke="#29465e" stroke-width="1"/><text x="2" y="44" fill="#9db1c7" font-size="11">${max} km/h</text><text x="2" y="159" fill="#9db1c7" font-size="11">${min} km/h</text><polygon points="${area}" fill="url(#speed-fill)"/><polyline points="${points}" fill="none" stroke="#56c6ff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/><text x="36" y="182" fill="#9db1c7" font-size="11">Earlier</text><text x="680" y="182" fill="#9db1c7" font-size="11">Now</text>`;
}
function populateSelectors() {
  if (!state || document.getElementById('source').options.length) return;
  const options = state.intersections.map(n => `<option value="${n.id}">${n.id} - ${n.name}</option>`).join('');
  document.getElementById('source').innerHTML = options; document.getElementById('destination').innerHTML = options;
  document.getElementById('source').value = 'B'; document.getElementById('destination').value = 'H';
}
async function findRoute() {
  const source = document.getElementById('source').value, destination = document.getElementById('destination').value;
  const response = await fetch(`/api/route?source=${source}&destination=${destination}`); const route = await response.json();
  if (!response.ok) { document.getElementById('route-result').textContent = route.detail; return; }
  selectedRoute = route.roads; document.getElementById('route-result').innerHTML = `<strong>${route.nodes.join(' → ')}</strong><br>${route.estimated_minutes} estimated minutes`; render();
}
async function createIncident() { await fetch('/api/incidents', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({road_id:'B-E', type:'suspected_accident', severity:'high'}) }); }
async function clearIncident(id) { await fetch(`/api/incidents/${id}`, { method:'DELETE' }); }
async function acknowledgeAlert(id) { await fetch(`/api/alerts/${id}/acknowledge`, {method:'POST'}); }
async function toggleSignal(id, mode) { await fetch(`/api/signals/${id}/mode`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode})}); }
async function uploadVideo() { const file = document.getElementById('video-file').files[0]; if (!file) { document.getElementById('camera-message').textContent = 'Choose a CCTV video file first.'; return; } const body = new FormData(); body.append('video', file); document.getElementById('camera-message').textContent = 'Uploading CCTV footage…'; const response = await fetch('/api/camera/video', {method:'POST', body}); const data = await response.json(); if (!response.ok) document.getElementById('camera-message').textContent = data.detail || 'Upload failed.'; }
async function startWebcam() { await fetch('/api/camera/webcam', {method:'POST'}); }
async function stopCamera() { await fetch('/api/camera/stop', {method:'POST'}); }
window.clearIncident = clearIncident;
window.acknowledgeAlert = acknowledgeAlert; window.toggleSignal = toggleSignal;
document.getElementById('route-button').onclick = findRoute; document.getElementById('traveller-route-button').onclick = findRoute; document.getElementById('incident-button').onclick = createIncident; document.getElementById('upload-button').onclick = uploadVideo; document.getElementById('webcam-button').onclick = startWebcam; document.getElementById('stop-camera-button').onclick = stopCamera;
function connect() {
  const ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/live`);
  ws.onopen = () => { const badge=document.getElementById('connection'); badge.textContent='Live'; badge.className='status live'; };
  ws.onmessage = event => { state=JSON.parse(event.data); populateSelectors(); render(); fetch('/api/analytics').then(r=>r.json()).then(data=>renderChart(data.samples)); };
  ws.onclose = () => { const badge=document.getElementById('connection'); badge.textContent='Reconnecting'; badge.className='status'; setTimeout(connect, 1500); };
}
connect();
