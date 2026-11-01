import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { parseDataset, unavailableProgress } from '../lib/data.ts';
import { renderResults, replaceResults } from './update-readme-results.mjs';

const index = JSON.parse(await readFile(new URL('../../results/index.json', import.meta.url), 'utf8'));

test('README includes every website episode once, with exact progress and completed-only time', () => {
  const generated = renderResults(index);
  const ids = [...generated.matchAll(/<!-- run:([^ ]+) -->/g)].map(match => match[1]);
  const runs = parseDataset(index).observations;
  assert.deepEqual([...ids].sort(), runs.map(run => run.id).sort());
  assert.equal(new Set(ids).size, ids.length);
  for (const run of runs) {
    const row = generated.split('\n').find(line => line.includes(`<!-- run:${run.id} -->`));
    const cells = row.split('|').slice(1, -1).map(cell => cell.trim());
    assert.equal(cells.length, 4);
    assert.equal(cells[1], run.progressPct === null ? unavailableProgress(run.status) : `${run.progressPct.toFixed(2)}%${/abort/.test(run.status) ? ' (aborted)' : ''}`);
    assert.equal(cells[2], run.completed ? run.clearSeconds.toFixed(2) : '-');
  }
  for (const table of generated.split('### ').slice(1)) {
    const values = [...table.matchAll(/\| ([\d.]+)%/g)].map(match => Number(match[1]));
    assert.deepEqual(values, [...values].sort((a, b) => b - a));
  }
});

test('alias only merges the proven same episode; diagnostics and independent repeats stay separate', () => {
  const copy = structuredClone(index);
  const alias = copy.observations.find(run => run.id === 'pixels-best-inception--mercury-decide');
  const before = parseDataset(copy).observations.length;
  alias.source_hashes.requests_sha256 = 'different episode';
  assert.equal(parseDataset(copy).observations.length, before + 1);
  const independent = { ...copy.examples[0], id: 'independent-repeat' };
  copy.observations.push(independent);
  assert.ok(parseDataset(copy).observations.some(run => run.id === independent.id));
  assert.ok(!parseDataset(copy).observations.some(run => run.id === 'openai-state-json-object-cohort-prefix'));
});

test('full verified json retest is visible without replacing the original API error or counting its prefix', () => {
  const parsed = parseDataset(index);
  const original = parsed.observations.find(run => run.id === 'state-c4-openai--gpt-6-luna-decisions');
  const retest = parsed.observations.find(run => run.id === 'openai-state-json-object-full-diagnostic');
  assert.equal(original.progressPct, null);
  assert.equal(unavailableProgress(original.status), 'api error');
  assert.equal(retest.name, 'OpenAI: GPT-6 Luna Decisions (json retest)');
  assert.equal(retest.progressPct.toFixed(2), '34.76');
  assert.equal(retest.nativeFrames, 2059);
  assert.equal(retest.decisions, 515);
  assert.equal(retest.clearSeconds, null);
  assert.equal(retest.retrospective, true);
  assert.equal(retest.matchedCohort, false);
  assert.ok(parsed.runs.some(run => run.id === retest.id));
  assert.ok(!parsed.observations.some(run => run.id === 'openai-state-json-object-cohort-prefix'));
  const unverified = structuredClone(index);
  unverified.technical_diagnostics.find(run => run.id === retest.id).verified = false;
  assert.ok(!parseDataset(unverified).observations.some(run => run.id === retest.id));
});

test('updates only the generated block and detects edited table content', () => {
  const generated = renderResults(index);
  const before = `intro\n${generated}\nsetup`;
  assert.equal(replaceResults(before, generated), before);
  assert.equal(replaceResults(before.replace('100.00%', '99.00%'), generated), before);
});
