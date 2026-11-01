// Headless, muted browser check of the public page against results/index.json.
// BASE_URL=http://127.0.0.1:3112 node scripts/check-ui.mjs
import { chromium } from '@playwright/test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';

const BASE = process.env.BASE_URL ?? 'http://127.0.0.1:3112';
const CHROME = process.env.CHROME ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const shots = new URL('../screenshots/', import.meta.url).pathname;
await fs.mkdir(shots, { recursive: true });

const index = await (await fetch(`${BASE}/benchmark-data/index.json`)).json();
const examples = index.examples;
const observations = index.observations;
const replays = [...new Map([...examples, ...observations.filter(e => e.replay_href)].map(e => [e.id, e])).values()];
assert.ok(examples.length > 0);
const pct = v => (v >= 100 ? '100%' : `${(Math.floor(v * 10) / 10).toFixed(1)}%`);

const browser = await chromium.launch({ executablePath: CHROME, headless: true, args: ['--mute-audio', '--disable-gpu', '--autoplay-policy=no-user-gesture-required'] });
const errors = [];
async function open(width, height = 1000, scheme = 'light') {
  const context = await browser.newContext({ viewport: { width, height }, colorScheme: scheme });
  const page = await context.newPage();
  page.on('pageerror', e => errors.push(`${width}: ${e.message}`));
  page.on('console', m => { if (m.type() === 'error') errors.push(`${width}: ${m.text()}`); });
  await page.goto(BASE + '/', { waitUntil: 'networkidle' });
  await page.waitForFunction(() => [...document.querySelectorAll('video')].every(v => v.readyState >= 1 && v.duration > 0));
  return { context, page };
}
const pauseAll = page => page.evaluate(() => document.querySelectorAll('video').forEach(v => { v.pause(); v.currentTime = 4; }));
const noOverflow = page => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth);

// Desktop
const { context, page } = await open(1440, 1000);
assert.ok(await page.locator('h1').isVisible());
assert.ok(await page.getByText(/fixed number of frames per action/).isVisible());
assert.ok(await page.getByText(/not a ranking/).isVisible());

// every recorded run, with the exact identity and numbers from the index
const rows = page.locator('tbody tr');
assert.equal(await rows.count(), observations.length, 'all published observations shown by default');
assert.equal(observations.filter(e => e.mode === 'state').length, index.observation_counts.state);
assert.equal(observations.filter(e => e.mode === 'image').length, index.observation_counts.image);
for (const e of observations) {
  const cells = await page.locator(`tr[data-run-id="${e.id}"] td`).allInnerTexts();
  assert.ok(cells[0].includes(e.model_id), `${e.id}: exact model identity`);
  assert.equal(cells[2], e.progress_pct === null ? '–' : pct(e.progress_pct), `${e.id}: no invented score`);
  assert.equal(Number(cells[4].replaceAll(',', '')), e.native_frames);
  if (e.status === 'api_abort') assert.equal(cells[6], 'incomplete');
  else if (/abort/.test(e.status)) assert.equal(cells[6], 'aborted');
  if (!e.replay_href) assert.ok((await page.locator(`tr[data-run-id="${e.id}"] a`).getAttribute('href')).endsWith(e.trace_href));
}
// Check null-score sorting in both directions before moving to the replay view.
for (let i = 0; i < 2; i++) {
  await page.getByRole('columnheader').filter({ hasText: 'progress' }).getByRole('button').click();
  const ids = await rows.evaluateAll(els => els.map(el => el.dataset.runId));
  assert.ok(ids.slice(-2).every(id => observations.find(e => e.id === id).progress_pct === null));
}
await page.getByRole('button', { name: `replays (${replays.length})`, exact: true }).click();
assert.equal(await rows.count(), replays.length);
for (const e of replays) {
  const cells = await page.locator(`tr[data-run-id="${e.id}"] td`).allInnerTexts();
  assert.ok(cells[0].includes(e.display_name) && cells[0].includes(e.model_id), `${e.id} identity`);
  assert.equal(cells[1], e.mode === 'image' ? 'pixels' : 'state');
  assert.equal(cells[2], e.progress_pct === null ? '–' : pct(e.progress_pct));
  assert.equal(cells[3], e.completed ? `${e.nominal_game_seconds_to_completion.toFixed(2)} s` : '–');
  assert.equal(Number(cells[4].replace(/,/g, '')), e.native_frames);
  assert.equal(Number(cells[5]), e.decisions);
}
assert.equal(await page.getByText(/cost|\$/i).count(), 0, 'no cost is shown for api runs');

// real, silent replays
const videos = await page.locator('video').evaluateAll(vs => vs.map(v => ({ src: v.currentSrc, muted: v.muted, inline: v.playsInline, audio: v.webkitAudioDecodedByteCount, paused: v.paused })));
assert.equal(videos.length, 2);
for (const v of videos) {
  assert.ok(replays.some(e => v.src.endsWith('/benchmark-data/' + e.replay_href)), v.src);
  assert.ok(v.muted && v.inline && v.audio === 0 && !v.paused);
}

// every column sorts both ways; missing values stay last
const headers = page.locator('thead th');
const count = await headers.count();
assert.equal(count, 7);
const parse = (text, col) => {
  if (text === '–') return null;
  if (col === 0) return text.split('\n')[0].trim().toLowerCase();
  if (col === 1) return text;
  if (col === 6) return text;
  return Number(text.replace(/[,%s ]/g, ''));
};
for (let col = 0; col < count; col++) {
  let previous;
  for (let pass = 0; pass < 2; pass++) {
    await headers.nth(col).locator('button').click();
    const dir = await headers.nth(col).getAttribute('aria-sort');
    assert.ok(dir === 'ascending' || dir === 'descending');
    for (let other = 0; other < count; other++) if (other !== col) assert.equal(await headers.nth(other).getAttribute('aria-sort'), 'none');
    const values = (await page.locator(`tbody tr td:nth-child(${col + 1})`).allInnerTexts()).map(t => parse(t, col));
    const present = values.filter(v => v !== null);
    assert.deepEqual(values.slice(present.length), Array(values.length - present.length).fill(null), `col ${col} nulls last`);
    for (let i = 1; i < present.length; i++) {
      const c = typeof present[i] === 'string' ? present[i - 1].localeCompare(present[i]) : present[i - 1] - present[i];
      assert.ok(dir === 'ascending' ? c <= 0 : c >= 0, `col ${col} ${dir}`);
    }
    if (pass === 1) assert.notEqual(dir, previous, `col ${col} toggles`);
    previous = dir;
  }
}

// a row click loads that replay into the chosen pane; rows only tint on hover
await page.getByRole('button', { name: 'send table selections to pane b' }).click();
const loaded = await page.locator('[data-side]').evaluateAll(fs => fs.map(f => f.dataset.runId));
const pick = observations.find(e => e.replay_href && !examples.some(example => example.id === e.id) && e.progress_pct !== null && !loaded.includes(e.id));
await page.locator(`tr[data-run-id="${pick.id}"] td:nth-child(3)`).click();
await page.waitForFunction(id => document.querySelector('[data-side="b"]').dataset.runId === id, pick.id);
await page.waitForFunction(href => document.querySelector('[data-side="b"] video').currentSrc.endsWith(href), pick.replay_href);
assert.equal(await page.locator('[data-side="a"]').getAttribute('data-run-id'), loaded[0]);
// An API-abort prefix is playable while retaining its absent score and label.
const prefix = observations.find(e => e.replay_href && e.progress_pct === null);
assert.ok(prefix);
await page.locator(`tr[data-run-id="${prefix.id}"] td:nth-child(3)`).click();
await page.waitForFunction(id => document.querySelector('[data-side="b"]').dataset.runId === id, prefix.id);
await page.waitForFunction(href => {
  const video = document.querySelector('[data-side="b"] video');
  return video.currentSrc.endsWith(href) && video.readyState >= 2;
}, prefix.replay_href);
assert.equal(await page.locator('[data-side="b"] .caption-result').innerText(), 'incomplete');
await page.locator(`tr[data-run-id="${pick.id}"]`).hover();
const hovered = await page.locator(`tr[data-run-id="${pick.id}"]`).evaluate(r => getComputedStyle(r).backgroundColor);
assert.notEqual(hovered, 'rgba(0, 0, 0, 0)', 'hover tints the row');
await page.mouse.move(2, 2);
await page.waitForTimeout(250);
const tints = await rows.evaluateAll(rs => rs.map(r => [r, ...r.cells].map(c => getComputedStyle(c).backgroundColor)).flat());
assert.ok(tints.every(c => c === 'rgba(0, 0, 0, 0)'), `rows stay neutral: ${tints}`);

// shared transport
await page.getByRole('button', { name: 'pause replays' }).click();
assert.ok(await page.locator('video').evaluateAll(vs => vs.every(v => v.paused)));
await page.getByRole('button', { name: '2× speed' }).click();
assert.ok(await page.locator('video').evaluateAll(vs => vs.every(v => v.playbackRate === 2)));
await page.getByRole('button', { name: 'restart replays' }).click();
assert.ok(await page.locator('video').evaluateAll(vs => vs.every(v => v.currentTime < 1.5 && !v.paused)));

// no horizontal rules outside the table, including pseudo-elements
const rules = await page.evaluate(() => {
  const bad = [];
  for (const el of document.querySelectorAll('body *')) {
    if (el.closest('table') || el.tagName === 'HR') { if (el.tagName === 'HR') bad.push('hr'); continue; }
    for (const pseudo of [null, '::before', '::after']) {
      const s = getComputedStyle(el, pseudo);
      const w = side => parseFloat(s[`border${side}Width`]) > 0 && s[`border${side}Style`] !== 'none';
      const all = w('Top') && w('Bottom') && w('Left') && w('Right');
      if ((w('Top') || w('Bottom')) && !all) bad.push(`${el.tagName}.${el.className}${pseudo ?? ''}`);
      if (pseudo && s.content !== 'none' && parseFloat(s.height) <= 2 && parseFloat(s.width) > 40) bad.push(`${el.className}${pseudo} line`);
    }
  }
  return bad;
});
assert.deepEqual(rules, []);

// all three game screens match, and the human game shows the full frame without an inset border
await page.getByRole('button', { name: 'play world 1-1' }).click();
await page.locator('.human-screen [role="status"]').waitFor({ state: 'detached' });
const boxes = await page.locator('.screen').evaluateAll(s => s.map(e => { const r = e.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; }));
assert.equal(boxes.length, 3);
assert.ok(boxes.every(b => Math.abs(b[0] - boxes[0][0]) <= 1 && Math.abs(b[1] - boxes[0][1]) <= 1), `screens match: ${JSON.stringify(boxes)}`);
const media = await page.locator('.screen video, .screen canvas').evaluateAll(m => m.map(e => { const r = e.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; }));
assert.ok(media.every(m => Math.abs(m[0] - boxes[0][0]) <= 1 && Math.abs(m[1] - boxes[0][1]) <= 1), `media fills screens: ${JSON.stringify(media)}`);
const edges = await page.locator('.human-screen canvas').evaluate(c => {
  const d = c.getContext('2d').getImageData(0, 0, 256, 240).data;
  const dark = (x, y) => { const i = (y * 256 + x) * 4; return d[i] + d[i + 1] + d[i + 2] < 30; };
  return { top: dark(128, 2), right: dark(252, 60), bottom: dark(128, 237), left: dark(10, 60) };
});
assert.deepEqual(edges, { top: false, right: false, bottom: false, left: false }, 'no black overscan border on the human game');

// human keyboard play, live progress and a persisted, separate personal best
const canvas = page.locator('.human-screen canvas');
await canvas.focus();
await page.keyboard.down('ArrowRight');
await page.keyboard.down('Shift');
await page.waitForTimeout(900);
await page.keyboard.up('Shift');
await page.keyboard.up('ArrowRight');
const live = parseFloat(await page.getByTestId('human-progress').innerText());
assert.ok(live > 0 && live < 100, `human progress ${live}`);
await page.getByRole('button', { name: 'stop playing' }).click();
const best = await page.getByTestId('human-best').innerText();
assert.match(best, /^best \d+\.\d% · 1 attempt$/);
await page.reload({ waitUntil: 'networkidle' });
assert.equal(await page.getByTestId('human-best').innerText(), best);
assert.equal(await rows.count(), observations.length, 'human best never joins the model table');

// theme toggle persists
const lightBg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
await page.getByRole('button', { name: 'switch to dark theme' }).click();
assert.equal(await page.evaluate(() => document.documentElement.dataset.theme), 'dark');
assert.notEqual(await page.evaluate(() => getComputedStyle(document.body).backgroundColor), lightBg);
await page.reload({ waitUntil: 'networkidle' });
assert.equal(await page.evaluate(() => document.documentElement.dataset.theme), 'dark');
assert.ok(await noOverflow(page));
await page.waitForFunction(() => [...document.querySelectorAll('video')].every(v => v.readyState >= 2));
await pauseAll(page);
await page.screenshot({ path: shots + 'redesign-desktop-dark.png', fullPage: true });
await context.close();

// fresh contexts per viewport avoid compositor artefacts in screenshots
for (const [width, name] of [[1920, 'wide'], [1440, 'desktop'], [1280, 'laptop'], [1024, 'small-desktop'], [768, 'tablet'], [390, 'mobile']]) {
  const { context, page } = await open(width, width === 390 ? 844 : 1000);
  assert.ok(await noOverflow(page), `${width} has no page overflow`);
  assert.ok(await page.locator('.table-scroll').evaluate(el => el.scrollWidth <= el.clientWidth), `${width} table fits without scrolling`);
  assert.equal(await page.getByRole('columnheader', { name: 'cadence', exact: true }).count(), 0);
  assert.equal(await page.getByText('saved in this browser · no frame limit', { exact: true }).count(), 0);
  assert.equal(await page.locator('tbody tr').count(), observations.length);
  assert.ok(await page.locator('h1').isVisible());
  const screens = await page.locator('.screen').evaluateAll(s => s.map(e => e.getBoundingClientRect().width));
  assert.ok(screens.every(w => w > 120 && w <= width), `${width} screens ${screens}`);
  // phones give the playable game the full width; wider layouts keep all 3 screens identical
  if (width > 560) assert.ok(screens.every(w => Math.abs(w - screens[0]) <= 1), `${width} screens match ${screens}`);
  await page.waitForFunction(() => [...document.querySelectorAll('video')].every(v => v.readyState >= 2));
  await pauseAll(page);
  await page.screenshot({ path: `${shots}redesign-${name}.png`, fullPage: true });
  await context.close();
}

await browser.close();
assert.deepEqual(errors, []);
console.log(`ui check passed: ${observations.length} observations, ${replays.length} playable runs, null scores, abort status, 7 sortable columns, no table scrolling at 6 widths, hover-only rows, matched screens, human play, themes`);
