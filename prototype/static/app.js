'use strict';
const $ = id => document.getElementById(id);
const buttons = ['start', 'step', 'pause', 'reset'].map($);
let status = null;
let busy = false;
let disconnected = false;
let streamTimer;
const number = (value, digits = 0) => Number.isFinite(Number(value)) && value !== null ? Number(value).toLocaleString(undefined, { maximumFractionDigits: digits }) : '—';
function metric(id, value, unit, digits = 0) {
  const el = $(id);
  el.replaceChildren(document.createTextNode(number(value, digits)));
  if (unit) { const small = document.createElement('small'); small.textContent = ` ${unit}`; el.append(small); }
}
function controlState() {
  const unavailable = busy || !status || disconnected;
  $('start').disabled = unavailable || status.running || status.pending || status.done;
  $('step').disabled = $('start').disabled;
  $('pause').disabled = unavailable || (!status.running && !status.pending);
  $('reset').disabled = unavailable;
  for (const id of ['track', 'cadence', 'model-choice']) $(id).disabled = unavailable || status.running || status.pending;
}
function message(text, error = false) {
  $('connection-message').textContent = text;
  $('connection-message').classList.toggle('error', error);
}
function renderProbabilities(data) {
  const container = $('probabilities');
  container.replaceChildren();
  if (!data || typeof data !== 'object' || !Object.keys(data).length) {
    const p = document.createElement('p'); p.className = 'empty-state'; p.textContent = 'Waiting for the first model decision.'; container.append(p); return;
  }
  const groups = Object.values(data).every(value => typeof value === 'number') ? [['action', data]] : Object.entries(data);
  let count = 0;
  for (const [name, values] of groups.slice(0, 6)) {
    if (!values || typeof values !== 'object') continue;
    const entries = Object.entries(values).filter(([, value]) => typeof value === 'number' && Number.isFinite(value)).slice(0, 12);
    if (!entries.length) continue;
    count++;
    const group = document.createElement('div'); group.className = 'probability-group';
    const label = document.createElement('div'); label.className = 'probability-name'; label.textContent = name.replaceAll('_', ' '); group.append(label);
    for (const [key, raw] of entries) {
      const value = Math.min(1, Math.max(0, raw));
      const row = document.createElement('div'); row.className = 'probability-row';
      const text = document.createElement('span'); text.textContent = key;
      const track = document.createElement('span'); track.className = 'probability-bar';
      const bar = document.createElement('i'); bar.style.width = `${value * 100}%`; track.append(bar);
      const amount = document.createElement('span'); amount.textContent = `${Math.round(value * 100)}%`;
      row.append(text, track, amount); group.append(row);
    }
    container.append(group);
  }
  if (!count) { const p = document.createElement('p'); p.className = 'empty-state'; p.textContent = 'No probability distribution supplied.'; container.append(p); }
}
function render(data) {
  status = data;
  const phase = ({waiting:'WAITING · FROZEN', stepping:'STEPPING', paused:'PAUSED', finished:'FINISHED', error:'STOPPED', loading:'LOADING'})[data.phase] || 'PAUSED';
  $('status-text').textContent = phase;
  $('status-dot').className = `status-dot${data.running ? ' running' : ''}`;
  $('model').textContent = data.model || 'openai/gpt-6-luna-decisions';
  $('track').value = data.track;
  $('cadence').value = String(data.frames_per_action);
  if ([...$('model-choice').options].some(o => o.value === data.model)) $('model-choice').value = data.model;
  $('episode').textContent = `EPISODE ${number(data.episode)}`;
  $('frame').textContent = `FRAME ${number(data.frame)}`;
  const progress = typeof data.progress === 'number' ? Math.min(100, Math.max(0, data.progress * 100)) : null;
  $('progress-text').textContent = progress === null ? '—' : `${number(progress, 1)}%`;
  $('progress-fill').style.width = `${progress || 0}%`;
  if (progress !== null) $('progress').setAttribute('aria-valuenow', progress.toFixed(1));
  $('position').textContent = `X ${number(data.x)}`;
  metric('native-frames', data.frame);
  metric('decisions', data.decisions);
  metric('actions', data.completed_actions);
  metric('remaining', data.batch_remaining);
  const screenshot = data.screenshot;
  $('input-screenshot').hidden = !screenshot;
  if (screenshot) {
    const url = `${screenshot.url}?sha=${screenshot.sha256}`;
    if ($('input-screenshot').getAttribute('src') !== url) $('input-screenshot').src = url;
    $('screenshot-caption').textContent = `Frame ${screenshot.frame} · ${screenshot.width}×${screenshot.height} PNG · ${screenshot.attached ? 'attached to request' : 'preview only; not sent in state track'}`;
  } else $('screenshot-caption').textContent = 'Captured at the same frame as the next decision state.';
  const input = data.buttons || {};
  for (const direction of ['up', 'down', 'left', 'right']) {
    const active = input.horizontal === direction || input.vertical === direction;
    $(`key-${direction}`).classList.toggle('active', active);
    $(`key-${direction}`).setAttribute('aria-label', `${direction}: ${active ? 'pressed' : 'released'}`);
  }
  for (const action of ['jump', 'run']) {
    const active = input[action] === 'held';
    $(`key-${action}`).classList.toggle('active', active);
    $(`key-${action}`).setAttribute('aria-label', `${action}: ${active ? 'pressed' : 'released'}`);
  }
  $('input-caption').textContent = data.phase === 'stepping' ? 'APPLYING' : 'HELD WHEN STEPPING';
  $('outcome').textContent = data.outcome || (data.running ? 'RUN IN PROGRESS' : data.done ? 'EPISODE FINISHED' : 'READY WHEN YOU ARE');
  $('cost').textContent = data.cost_usd == null ? 'COST —' : `COST $${Number(data.cost_usd).toFixed(4)}`;
  $('context').textContent = data.context && Object.keys(data.context).length ? JSON.stringify(data.context, null, 2) : 'No observation received.';
  renderProbabilities(data.probabilities);
  if (!busy) message(data.last_error || (data.pending ? 'The emulator is frozen while the model decides.' : data.running ? 'Applying a fixed native-frame action.' : data.done ? 'Episode complete. Reset to start a new run.' : 'Local runner connected.'), Boolean(data.last_error));
  controlState();
}
async function request(path, method = 'GET', body = {}) {
  const response = await fetch(path, { method, signal: AbortSignal.timeout(4500), cache: 'no-store', ...(method === 'POST' ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {}) });
  if (!response.ok) {
    let detail = '';
    try { const body = await response.json(); detail = typeof body.detail === 'string' ? body.detail : body.error || ''; } catch {}
    throw new Error(detail || `Runner returned HTTP ${response.status}`);
  }
  return response.json();
}
async function poll() {
  try {
    const data = await request('/api/status');
    disconnected = false; render(data);
    if (stream.naturalWidth > 0) $('feed-message').hidden = true;
  } catch {
    disconnected = true;
    $('status-text').textContent = 'DISCONNECTED';
    $('status-dot').className = 'status-dot error';
    message('Cannot reach the local runner. Retrying…', true);
    buttons.forEach(button => { button.disabled = true; });
    controlState();
  } finally { setTimeout(poll, 500); }
}
for (const action of ['start', 'step', 'pause', 'reset']) {
  $(action).addEventListener('click', async () => {
    if (busy) return;
    busy = true; controlState();
    message(action === 'start' || action === 'step' ? 'Capturing a paused observation…' : action === 'pause' ? 'Pausing; pending replies are discarded…' : 'Resetting the emulator…');
    try {
      await request(`/api/${action}`, 'POST');
      render(await request('/api/status'));
    } catch (error) { message(String(error.message || 'The command failed. Please try again.').slice(0, 200), true); }
    finally { busy = false; controlState(); if (disconnected) buttons.forEach(button => { button.disabled = true; }); }
  });
}
for (const id of ['track', 'cadence', 'model-choice']) $(id).addEventListener('change', async () => {
  if (busy) return;
  const options = {track: $('track').value, frames_per_action: Number($('cadence').value), model: $('model-choice').value};
  busy = true; controlState();
  try { render(await request('/api/configure', 'POST', options)); }
  catch (error) { message(String(error.message || 'Could not update the track.').slice(0, 200), true); }
  finally { busy = false; controlState(); }
});
const stream = $('game-stream');
stream.addEventListener('load', () => { $('feed-message').hidden = true; clearTimeout(streamTimer); });
stream.addEventListener('error', () => {
  $('feed-message').hidden = false;
  $('feed-message').querySelector('strong').textContent = 'Waiting for the video feed';
  clearTimeout(streamTimer);
  streamTimer = setTimeout(() => { stream.src = `/stream.mjpg?t=${Date.now()}`; }, 2500);
});
if (stream.complete && stream.naturalWidth) $('feed-message').hidden = true;
controlState();
poll();
