import { chromium } from '@playwright/test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';

const output = new URL('../screenshots/', import.meta.url).pathname;
await fs.mkdir(output, { recursive: true });
const browser = await chromium.launch({ executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true, args: ['--mute-audio'] });
const page = await browser.newPage({ viewport: { width: 1600, height: 1100 } });
const errors = [];
page.on('pageerror', error => errors.push(error.message));
await page.goto('http://127.0.0.1:3100/focus', { waitUntil: 'networkidle' });
await page.locator('.replay-screen [role="status"]').first().waitFor({ state: 'hidden' });
assert.equal(await page.locator('[data-side]').count(), 2);
assert.equal(await page.locator('canvas').count(), 3);
assert.equal(await page.locator('.player-row').count(), 0);
assert.deepEqual(await page.locator('thead th').allTextContents(), ['#', 'model', 'score', 'cost / run', 'runs']);
assert.equal(await page.locator('.focus-comparison,.race-lane,.prototype-links').count(), 0);
const screens = await page.locator('.replay-screen').evaluateAll(nodes => nodes.map(el => el.getBoundingClientRect().width));
assert.ok(screens.every(width => width > 460 && width < 475), 'game panes match the larger desk size');
await page.getByRole('button', { name: 'watch Gemini 2.5 Pro best replay' }).click();
assert.equal(await page.locator('[data-side="left"] .model-name').textContent(), 'Gemini 2.5 Pro');
await page.getByRole('button', { name: 'next Gemini 2.5 Pro replay' }).click();
assert.match(await page.locator('[data-side="left"] .replay-attempt').textContent(), /run 2/);
await page.getByRole('button', { name: 'play Mario', exact: true }).click();
await page.locator('.human-game-screen [role="status"]').waitFor({ state: 'hidden' });
assert.equal(await page.locator('.player-row .cost-column').textContent(), '$0.000');
const game = page.locator('.human-game-screen canvas');
await game.click();
await page.keyboard.down('ArrowRight');
await page.keyboard.down('Shift');
await page.keyboard.down('ArrowUp');
await page.waitForTimeout(800);
await page.keyboard.up('ArrowUp');
await page.keyboard.up('Shift');
await page.keyboard.up('ArrowRight');
await page.getByRole('button', { name: 'stop playing' }).click();
const personalBest = parseFloat(await page.locator('.player-row .score-cell').textContent());
assert.ok(personalBest > 0);
await page.reload({ waitUntil: 'networkidle' });
assert.equal(parseFloat(await page.locator('.player-row .score-cell').textContent()), personalBest);
assert.equal(await page.locator('.player-row .runs-column').textContent(), '1');
await page.getByRole('button', { name: 'play Mario', exact: true }).click();
assert.equal(await page.locator('.player-row .runs-column').textContent(), '2');
assert.equal(parseFloat(await page.locator('.player-row .score-cell').textContent()), personalBest, 'retry keeps best score');
await page.getByRole('button', { name: 'stop playing' }).click();
await page.getByRole('button', { name: 'cost / run', exact: true }).click();
assert.equal(await page.locator('tbody tr').first().getAttribute('class'), 'player-row');
await page.screenshot({ path: `${output}/field-results.png`, fullPage: true });
for (const width of [390, 768]) {
  await page.setViewportSize({ width, height: 1000 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
  assert.deepEqual(await page.locator('thead th').evaluateAll(nodes => nodes.filter(el => getComputedStyle(el).display !== 'none').map(el => el.textContent)), ['#', 'model', 'score', 'cost / run', 'runs']);
}
for (const route of ['arena', 'scoreboard', 'studio', 'quiet']) {
  assert.equal((await page.request.get(`http://127.0.0.1:3100/${route}`)).status(), 404);
}
assert.deepEqual(errors, []);
console.log('field UI passed: sole layout, larger panes, replay selection, live/persistent personal score, zero cost, retries, sorting, keyboard controls and responsive table');
await browser.close();
