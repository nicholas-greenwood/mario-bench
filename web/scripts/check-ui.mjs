// Headless, muted browser check of the public page against results/index.json.
// BASE_URL=http://127.0.0.1:3112 node scripts/check-ui.mjs
import { chromium } from '@playwright/test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { formatCost, formatRunCost, formatSeconds, parseDataset } from '../lib/data.ts';
import { hydrateRecoveryProofs } from '../lib/read-results.mjs';

const BASE = process.env.BASE_URL ?? 'http://127.0.0.1:3112';
const CHROME = process.env.CHROME ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const shots = new URL('../screenshots/', import.meta.url).pathname;
await fs.mkdir(shots, { recursive: true });

const index = await (await fetch(`${BASE}/benchmark-data/index.json`)).json();
for (const [hrefKey,valueKey] of [['common_cohort_href','common_benchmark'],['common_image_cohort_href','common_image_benchmark']]) {
  if (!index[hrefKey]) continue;
  const common = await (await fetch(`${BASE}/benchmark-data/${index[hrefKey]}`)).json();
  index[valueKey] = common.common_benchmark;
}
await hydrateRecoveryProofs(index, async relative => {
  const response = await fetch(`${BASE}/benchmark-data/${relative}`);
  if (!response.ok) throw new Error(`recovery proof ${relative}: HTTP ${response.status}`);
  return Buffer.from(await response.arrayBuffer());
});
const examples = index.examples;
const observations = index.observations;
const parsed = parseDataset(index);
const rawById = new Map([...examples, ...observations, ...(index.technical_diagnostics ?? []), ...parsed.commonBenchmarks.flatMap(cohort => cohort.trials)].map(e => [e.id, e]));
const published = parsed.observations.map(run => ({ ...rawById.get(run.id), id: run.id, model_id: run.modelId,
  display_name: run.name, mode: run.track, status: run.status, completed: run.completed,
  progress_pct: run.progressPct, native_frames: run.nativeFrames, decisions: run.decisions,
  nominal_game_seconds_to_completion: run.clearSeconds,
  replay_href: run.replaySrc?.replace('/benchmark-data/', '') ?? null,
  trace_href: run.traceSrc.replace('/benchmark-data/', ''),
}));
const playableIds = new Set(parsed.runs.map(run => run.id));
const replays = published.filter(e => playableIds.has(e.id));
assert.equal(published.length, parsed.observations.length);
assert.equal(replays.length, parsed.runs.length);
assert.ok(published.length >= 42 && replays.length >= 41, 'previous published runs remain available');
const mercuryPixels = parsed.runs.filter(run => run.modelId === 'inception/mercury-decide' && run.track === 'image');
const originalMercury = mercuryPixels.find(run => run.id === 'mercury-pixels-partial');
assert.ok(originalMercury, 'original replay ID retained');
assert.deepEqual(originalMercury.aliasIds, ['pixels-best-inception--mercury-decide']);
const repeated = parseDataset({ ...index, observations: [...observations, { ...examples.find(e => e.id === 'mercury-pixels-partial'), id: 'independent-repeat' }] });
assert.equal(repeated.runs.filter(run => run.modelId === 'inception/mercury-decide' && run.track === 'image').length, mercuryPixels.length + 1, 'independent repeat IDs survive even when source contents match');
assert.ok(examples.length > 0);
const receipt = { attempt_scope_verified: true, source_request_count: 1, source_attempt_count: 1, error_count: 0, unreceipted_count: 0, unreceipted_attempt_count: 0, unbilled_error_attempts_unknown: 0, kind: 'recorded_response_usage', cost_basis: 'all_in_inference', request_count: 1, costed_request_count: 1, actual_costed_request_count: 1, coverage_complete: true, includes_retries: true, includes_auxiliary_calls: true };
const costFixture = (value, provenance) => parseDataset({ examples: [{ ...examples[0], cost_usd: value, cost_provenance: provenance }], observations: [] }).runs[0].costUsd;
assert.equal(costFixture(0, receipt), 0, 'verified actual zero remains zero');
assert.equal(costFixture(.00898152, { ...receipt, request_count: 116, costed_request_count: 116, actual_costed_request_count: 116, source_request_count: 117, source_attempt_count: 117, error_count: 1, unreceipted_count: 1, unreceipted_attempt_count: 1, unbilled_error_attempts_unknown: 1 }), null, '116 receipts plus an unreceipted error are 117 attempts, not an exact total');
assert.equal(costFixture(.1, { ...receipt, attempt_scope_verified: undefined }), null, 'inherited receipt-only certificates do not certify all attempts');
assert.equal(costFixture(.1, { ...receipt, error_count: 1 }), .1, 'an error with an explicit billed receipt can still be fully covered');
assert.equal(costFixture(0, { ...receipt, request_count: 0, costed_request_count: 0, actual_costed_request_count: 0 }), null, 'an empty ledger is unknown, not a free run');
assert.equal(costFixture(null, receipt), null, 'missing billing is unknown');
assert.equal(costFixture(1, undefined), null, 'a number without billing provenance is unknown');
assert.equal(costFixture(.1, { ...receipt, kind: 'catalogue_estimate' }), null, 'estimates are never displayed as actual costs');
assert.equal(costFixture(.1, { ...receipt, cost_basis: 'unknown' }), null, 'unverified billing basis stays unknown');
assert.equal(costFixture(.1, { ...receipt, coverage_complete: false }), null, 'partial receipts do not become exact totals');
assert.equal(costFixture(.1, { ...receipt, request_count: 2 }), null, 'every request must have a recorded cost');
assert.equal(costFixture(.1, { ...receipt, includes_retries: false }), null, 'omitted retries make complete run cost unknown');
assert.equal(costFixture(.1, { ...receipt, includes_auxiliary_calls: false }), null, 'omitted auxiliary calls make complete run cost unknown');
assert.equal(costFixture(-1, receipt), null, 'invalid negative billing is unknown');
assert.equal(formatCost(null), null);
assert.equal(formatCost(0), '$0.00');
assert.equal(formatCost(.001234), '$0.001234');
assert.equal(formatCost(.0000001), '<$0.000001');
const byokEstimate = parseDataset({ examples: [{ ...examples[0], cost_usd: 0, cost_estimate_usd: .031234,
  openrouter_cost_usd: 0, upstream_cost_estimate_usd: .031234,
  cost_provenance: { ...receipt, actual_costed_request_count: 0, upstream_cost_basis: 'openrouter_activity_list_price_estimate' },
}], observations: [] }).runs[0];
assert.equal(byokEstimate.costUsd, null, 'zero openrouter credits do not imply free byok inference');
assert.equal(byokEstimate.costEstimateUsd, .031234);
assert.equal(formatRunCost(byokEstimate), '~$0.031234');
assert.equal(formatRunCost({ costUsd: .02, costEstimateUsd: .03 }), '$0.02', 'actual cost takes precedence over an estimate');
const aliasBilling = parseDataset({ ...index,
  examples: examples.map(e => e.id === 'mercury-pixels-partial' ? { ...e, cost_usd: null, cost_provenance: null } : e),
  observations: observations.map(e => e.id === 'pixels-best-inception--mercury-decide' ? { ...e, cost_usd: .012345, cost_provenance: receipt } : e),
});
assert.equal(aliasBilling.runs.find(run => run.id === 'mercury-pixels-partial').costUsd, .012345);
assert.equal(aliasBilling.observations.find(run => run.id === 'mercury-pixels-partial').costUsd, .012345, 'known episode alias has the same cost in both views');
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
if (parsed.commonBenchmark) {
  const table = page.locator('[data-common-benchmark]').first();
  assert.ok(await table.isVisible(), 'a valid evaluation cohort is the primary view');
  if (parsed.commonBenchmark.stateOnly && !parsed.commonBenchmarks.some(cohort => cohort.imageOnly)) {
    assert.ok(await page.getByText('common image track: calibration pending. image replays and history remain development runs.', { exact: true }).isVisible());
    assert.equal(await table.locator('tr[data-track="image"]').count(), 0);
  }
  for (const cohort of parsed.commonBenchmarks) {
    const cohortTable = page.locator(`[data-common-protocol="${cohort.protocolSha256}"]`);
    assert.equal(await cohortTable.locator('tbody tr').count(), cohort.rows.length);
    for (const row of cohort.rows) {
      const element = cohortTable.locator(`tr[data-common-model="${row.modelId}"][data-track="${row.track}"]`);
      const cells = await element.locator('td').allInnerTexts();
      assert.equal(cells[2], row.meanProgressPct === null ? 'pending' : `${row.meanProgressPct.toFixed(2)}%`);
      assert.equal(cells[3], formatSeconds(row.bestClearSeconds) ?? '–');
      assert.equal(cells[4], formatRunCost({ costUsd: row.meanCostUsd, costEstimateUsd: row.meanCostEstimateUsd }) ?? '–');
      assert.equal(await element.getAttribute('data-run-id'), null, 'a mean is not a replay episode');
    }
  }
  const evidence = parsed.commonBenchmark.rows.find(row => row.recordedTrialIds.length);
  if (evidence) {
    await table.locator(`tr[data-common-model="${evidence.modelId}"][data-track="${evidence.track}"]`).getByRole('button', { name: `${evidence.recordedTrialIds.length} runs`, exact: true }).click();
    const filtered = await page.locator('tbody tr').evaluateAll(rows => rows.map(row => row.dataset.runId));
    assert.deepEqual(filtered.sort(), [...evidence.recordedTrialIds].sort(), 'evidence opens the actual trial IDs');
  }
  await page.getByRole('button', { name: `all runs (${published.length})`, exact: true }).click();
}
assert.ok(await page.locator('h1').isVisible());
assert.ok(await page.getByText(/fixed number of frames per action/).isVisible());
assert.ok(await page.getByText(/not a ranking/).isVisible());
for (const [side, track] of [['a', 'state'], ['b', 'image']]) {
  const preferred = replays.find(e => e.mode === track && e.completed) ?? replays.find(e => e.mode === track);
  if (preferred) assert.equal(await page.locator(`[data-side="${side}"]`).getAttribute('data-run-id'), preferred.id, `default ${track} replay prefers a verified clear`);
}

// every recorded run, with the exact identity and numbers from the index
const rows = page.locator('tbody tr');
assert.equal(await page.getByRole('columnheader', { name: 'frames', exact: true }).count(), 0);
assert.equal(await page.getByRole('columnheader', { name: 'cost', exact: true }).count(), 1);
assert.equal(await rows.count(), published.length, 'every published run shown by default');
const clearIds = examples.filter(e => e.completed).map(e => e.id).sort();
for (const id of ['pplx-state-clear', 'mercury-state-clear', 'drex-state-clear', 'liquid-state-clear']) assert.ok(clearIds.includes(id), `${id}: previous verified clear remains published`);
assert.ok(published.filter(e => e.completed).length >= clearIds.length, 'showcase clears remain alongside fresh evaluation trials');
for (const id of clearIds) {
  assert.ok(published.some(e => e.id === id && e.completed), `${id}: showcase clear belongs to all runs`);
  assert.ok(replays.some(e => e.id === id && e.completed), `${id}: showcase clear is playable`);
}
for (const e of replays) assert.equal(await page.locator(`tr[data-run-id="${e.id}"][data-replay="true"]`).count(), 1, `${e.id}: replay belongs to all runs`);
for (const id of clearIds) assert.equal(await page.locator(`tr[data-run-id="${id}"] td`).nth(6).innerText(), 'cleared');
const mercuryRuns = published.filter(e => e.model_id === 'inception/mercury-decide' && e.mode === 'state');
assert.ok(mercuryRuns.length >= 2, 'distinct state profiles and fresh trials for one model stay separate');
assert.ok(mercuryRuns.some(e => e.completed) && mercuryRuns.some(e => !e.completed));
const noActions = published.find(e => e.id === 'state-c4-jaredpalmer--kev-4b');
assert.ok(noActions && !noActions.replay_href && noActions.progress_pct === null && noActions.native_frames === 0);
assert.equal(observations.filter(e => e.mode === 'state').length, index.observation_counts.state);
assert.equal(observations.filter(e => e.mode === 'image').length, index.observation_counts.image);
for (const e of published) {
  const cells = await page.locator(`tr[data-run-id="${e.id}"] td`).allInnerTexts();
  assert.ok(cells[0].includes(e.model_id), `${e.id}: exact model identity`);
  assert.equal(cells[2], e.progress_pct === null ? '–' : pct(e.progress_pct), `${e.id}: no invented score`);
  assert.equal(cells[4], formatRunCost(parsed.observations.find(run => run.id === e.id)) ?? '–', `${e.id}: actual cost, marked estimate or unknown`);
  if (e.status === 'api_abort') assert.equal(cells[6], 'api error');
  else if (/abort/.test(e.status)) assert.equal(cells[6], 'aborted');
  if (!e.replay_href) assert.ok((await page.locator(`tr[data-run-id="${e.id}"] a`).getAttribute('href')).endsWith(e.trace_href));
}
// Check null-score sorting in both directions before moving to the replay view.
for (let i = 0; i < 2; i++) {
  await page.getByRole('columnheader').filter({ hasText: 'progress' }).getByRole('button').click();
  const ids = await rows.evaluateAll(els => els.map(el => el.dataset.runId));
  assert.ok(ids.slice(-2).every(id => published.find(e => e.id === id).progress_pct === null));
}
await page.getByRole('button', { name: `replays (${replays.length})`, exact: true }).click();
assert.equal(await rows.count(), replays.length);
for (const e of replays) {
  const cells = await page.locator(`tr[data-run-id="${e.id}"] td`).allInnerTexts();
  assert.ok(cells[0].includes(e.display_name) && cells[0].includes(e.model_id), `${e.id} identity`);
  assert.equal(cells[1], e.mode === 'image' ? 'pixels' : 'state');
  assert.equal(cells[2], e.progress_pct === null ? '–' : pct(e.progress_pct));
  assert.equal(cells[3], e.completed ? `${e.nominal_game_seconds_to_completion.toFixed(2)} s` : '–');
  assert.equal(cells[4], formatRunCost(parsed.runs.find(run => run.id === e.id)) ?? '–');
  assert.equal(Number(cells[5]), e.decisions);
}

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
  return Number(text.replace(/[~<,$%s ]/g, ''));
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
assert.equal(await page.locator('[data-side="b"] .caption-result').innerText(), 'api error');
await page.locator(`tr[data-run-id="${pick.id}"]`).hover();
await page.waitForFunction(id => {
  const row = document.querySelector(`tr[data-run-id="${id}"]`);
  return row && getComputedStyle(row).backgroundColor !== 'rgba(0, 0, 0, 0)';
}, pick.id);
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
if (parsed.commonBenchmark) await page.getByRole('button', { name: `all runs (${published.length})`, exact: true }).click();
assert.equal(await rows.count(), published.length, 'human best never joins the model table');

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
  if (parsed.commonBenchmark) {
    assert.ok(await page.locator('[data-common-benchmark]').first().isVisible());
    assert.ok(await noOverflow(page), `${width} benchmark has no page overflow`);
    assert.ok(await page.locator('.table-scroll').evaluateAll(elements => elements.every(el => el.scrollWidth <= el.clientWidth)), `${width} benchmark table fits`);
    await page.getByRole('button', { name: `all runs (${published.length})`, exact: true }).click();
  }
  assert.ok(await noOverflow(page), `${width} has no page overflow`);
  assert.ok(await page.locator('.table-scroll').evaluateAll(elements => elements.every(el => el.scrollWidth <= el.clientWidth)), `${width} table fits without scrolling`);
  assert.equal(await page.getByRole('columnheader', { name: 'cadence', exact: true }).count(), 0);
  assert.equal(await page.getByRole('columnheader', { name: 'frames', exact: true }).count(), 0);
  assert.equal(await page.locator('td[data-label="frames"]').count(), 0);
  assert.equal(await page.locator('td[data-label="cost"]').count(), published.length);
  assert.equal(await page.getByText('saved in this browser · no frame limit', { exact: true }).count(), 0);
  assert.equal(await page.locator('tbody tr').count(), published.length);
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
console.log(`ui check passed: ${published.length} published runs, ${replays.length} playable runs, verified costs/unknown billing, no frames column, ${clearIds.length} matching clears, aliases, 7 sortable columns, no table scrolling at 6 widths`);
