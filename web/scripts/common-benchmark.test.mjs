import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, writeFile, mkdir, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { parseDataset, formatRunCost } from '../lib/data.ts';
import { readPublishedIndex } from '../lib/read-results.mjs';
import { renderResults } from './update-readme-results.mjs';

const legacy = JSON.parse(await readFile(new URL('../../results/index.json', import.meta.url), 'utf8'));
const hash = 'a'.repeat(64);
const billing = {
  kind: 'recorded_response_usage', cost_basis: 'all_in_inference', coverage_complete: true,
  attempt_scope_verified: true, source_request_count: 10, source_attempt_count: 10,
  request_count: 10, costed_request_count: 10, actual_costed_request_count: 10,
  error_count: 0, unreceipted_count: 0, unreceipted_attempt_count: 0, unbilled_error_attempts_unknown: 0,
  includes_retries: true, includes_auxiliary_calls: true,
};

function fixture(track = 'state') {
  const trials = [0, 1, 2].map(repeat => ({
    id: `common-fixture-${track}-${repeat}`, model_id: 'fixture/model', display_name: 'fixture model',
    request_model: 'fixture/model', returned_model: 'fixture/model-v1', provider: 'fixture provider',
    track, level: '1-1', phase: 'evaluation', protocol_sha256: hash, repeat_id: repeat,
    local_rng_seed: track === 'image' ? 101 + repeat : null, emulator_seed: 0,
    temperature: track === 'image' ? .05 : null,
    started_at_utc: '2026-01-02T00:00:00Z', native_frame_budget: 6000, life_budget: 1,
    rankable: true, native_replay_verified: true, native_frames: [1200, 600, 1800][repeat], decisions: 10,
    status: repeat < 2 ? 'completed' : 'game_over', flag_get: repeat < 2,
    progress_pct: repeat < 2 ? 100 : 40, native_frames_to_completion: repeat < 2 ? [1200, 600][repeat] : null,
    cost_usd: [.03, .06, .09][repeat], cost_provenance: structuredClone(billing),
    trace_href: `common/traces/${track}-${repeat}.json`, profile_href: 'common/profiles/protocol.json', replay_href: null,
  }));
  return { ...structuredClone(legacy), common_benchmark: {
    manifest: {
      protocol_id: 'common-fixture-v1', protocol_sha256: hash, phase: 'evaluation', preregistered: true,
      frozen_at_utc: '2026-01-01T00:00:00Z', level: '1-1',
      observation_and_controller_hashes: { observer: hash, controller: hash },
      pilot_selection_evidence: { state_gate_passed: true, selected_image_temperature_gate_passed: true,
        selected_temperature: .05, pilot_protocol_sha256: hash, pilot_summary_sha256: hash,
        pilot_audit_sha256: hash, selection_href: 'common/pilot/selection.json' },
      repeat_schedule: trials.map(({ id, model_id, track, repeat_id, local_rng_seed, emulator_seed }) => ({ episode_id: id, model_id, track, repeat_id, local_rng_seed, emulator_seed })),
      eligible_model_provider_pairs: [{ model_id: 'fixture/model', track, request_model: 'fixture/model', expected_returned_model: 'fixture/model-v1',
        provider: { only: ['fixture provider'], allow_fallbacks: false }, expected_returned_provider_names: ['fixture provider'] }],
    },
    trials,
    rows: [{ model_id: 'fixture/model', display_name: 'fixture model', track, level: '1-1', protocol_sha256: hash,
      expected_trials: 3, valid_trials: 3, coverage_complete: true,
      expected_trial_ids: trials.map(trial => trial.id), recorded_trial_ids: trials.map(trial => trial.id),
      mean_progress_pct: 999, best_clear_game_seconds: 999 }],
  } };
}

const result = data => parseDataset(data).commonBenchmark?.rows[0];

function stateOnlyFixture() {
  const data = fixture(), cohort = data.common_benchmark, manifest = cohort.manifest;
  const templates = structuredClone(cohort.trials), rowTemplate = structuredClone(cohort.rows[0]);
  const pairTemplate = structuredClone(manifest.eligible_model_provider_pairs[0]);
  manifest.protocol_id = 'mario-common-state-compact-v2-evaluation-v1';
  manifest.evaluation_scope = 'state_only'; manifest.tracks = ['state'];
  manifest.image_evaluation_status = 'calibration_pending';
  manifest.native_frame_budget = 6000; manifest.life_budget = 1; manifest.cadence_native_frames = 4;
  manifest.observation_and_controller_hashes.state_controller_sha256 = hash;
  manifest.pilot_selection_evidence = { state_gate_passed: true, state_native_clear_count: 2,
    state_preflight_model_count: 22, state_pilot_episode_count: 4,
    state_preflight_audit_complete: true, state_pilot_audit_complete: true,
    ...Object.fromEntries(['state_preflight_protocol_sha256', 'state_preflight_report_sha256', 'state_preflight_audit_sha256',
      'state_pilot_protocol_sha256', 'state_pilot_summary_sha256', 'state_pilot_audit_sha256',
      'state_selection_sha256', 'state_controller_sha256'].map(key => [key, hash])),
  };
  manifest.repeat_schedule = []; manifest.eligible_model_provider_pairs = []; cohort.trials = []; cohort.rows = [];
  for (let model = 0; model < 22; model++) {
    const modelId = `fixture/state-model-${model}`;
    const trials = templates.map(trial => ({ ...structuredClone(trial), id: `state-only-fixture-${model}-${trial.repeat_id}`,
      model_id: modelId, request_model: modelId, returned_model: `${modelId}-v1`,
    }));
    cohort.trials.push(...trials);
    manifest.repeat_schedule.push(...trials.map(({ id, model_id, track, repeat_id, local_rng_seed, emulator_seed, temperature }) =>
      ({ episode_id: id, model_id, track, repeat_id, local_rng_seed, emulator_seed, temperature })));
    manifest.eligible_model_provider_pairs.push({ ...pairTemplate, model_id: modelId, request_model: modelId, expected_returned_model: `${modelId}-v1` });
    cohort.rows.push({ ...rowTemplate, model_id: modelId, expected_trial_ids: trials.map(trial => trial.id), recorded_trial_ids: trials.map(trial => trial.id) });
  }
  return data;
}

test('explicit state-only authority accepts exactly 22 models and 66 fresh state trials without fabricating an image gate', () => {
  const data = stateOnlyFixture(), parsed = parseDataset(data), cohort = parsed.commonBenchmark;
  assert.ok(cohort?.stateOnly);
  assert.equal(cohort.rows.length, 22);
  assert.equal(cohort.trials.length, 66);
  assert.ok(cohort.rows.every(row => row.track === 'state' && row.meanProgressPct === 80));
  assert.equal(data.common_benchmark.manifest.pilot_selection_evidence.selected_image_temperature_gate_passed, undefined);
  const imageHistory = value => parseDataset(value).observations.filter(run => run.track === 'image').map(run => [run.id, run.progressPct, run.costUsd, run.costEstimateUsd]);
  assert.deepEqual(imageHistory(data), imageHistory(legacy), 'image history stays development evidence, not new image means');
  const generated = renderResults(data), primary = generated.split('<summary>individual runs and development history</summary>')[0];
  assert.ok(primary.includes('common image track: calibration pending'));
  assert.ok(!primary.includes('### pixels only'));
  assert.ok(generated.includes('### pixels only'), 'full image development history remains accessible');
});

test('state-only rows still require all 3 prescribed valid trials', () => {
  const data = stateOnlyFixture(); data.common_benchmark.trials[2].technical_pending = true;
  const cohort = parseDataset(data).commonBenchmark;
  assert.equal(cohort.rows.length, 22);
  assert.equal(cohort.rows[0].meanProgressPct, null);
  assert.equal(cohort.rows[0].validTrials, 2);
  assert.equal(cohort.rows[1].meanProgressPct, 80);
});

test('a frozen state-only cohort with no final trials stays pending without inventing zero scores', () => {
  const data = stateOnlyFixture(); data.common_benchmark.trials = [];
  for (const row of data.common_benchmark.rows) { row.coverage_complete = false; row.recorded_trial_ids = []; }
  const parsed = parseDataset(data), cohort = parsed.commonBenchmark;
  assert.equal(cohort.rows.length, 22);
  assert.ok(cohort.rows.every(row => row.validTrials === 0 && row.meanProgressPct === null
    && row.bestClearSeconds === null && row.meanCompletedSeconds === null && row.meanCostUsd === null && row.meanCostEstimateUsd === null));
  assert.equal(parsed.observations.length, parseDataset(legacy).observations.length);
  const combined = fixture(); combined.common_benchmark.trials = [];
  assert.equal(parseDataset(combined).commonBenchmark, null, 'the existing combined branch is unchanged');
});

for (const [reason, mutate] of [
  ['nonexplicit scope', manifest => { delete manifest.evaluation_scope; }],
  ['mixed declared tracks', manifest => { manifest.tracks.push('image'); }],
  ['fake image gate', manifest => { manifest.pilot_selection_evidence.selected_image_temperature_gate_passed = true; }],
  ['fake selected temperature', manifest => { manifest.pilot_selection_evidence.selected_temperature = .05; }],
  ['wrong state protocol', manifest => { manifest.protocol_id = 'other-state-protocol'; }],
  ['incomplete preflight', manifest => { manifest.pilot_selection_evidence.state_preflight_model_count = 21; }],
  ['missing pilot case', manifest => { manifest.pilot_selection_evidence.state_pilot_episode_count = 3; }],
  ['unverified native pilot', manifest => { manifest.pilot_selection_evidence.state_pilot_audit_complete = false; }],
  ['boolean clear count', manifest => { manifest.pilot_selection_evidence.state_native_clear_count = true; }],
  ['no native clear', manifest => { manifest.pilot_selection_evidence.state_native_clear_count = 0; }],
  ['controller proof mismatch', manifest => { manifest.observation_and_controller_hashes.state_controller_sha256 = 'b'.repeat(64); }],
  ['missing source hash', manifest => { delete manifest.pilot_selection_evidence.state_preflight_audit_sha256; }],
  ['wrong state cadence', manifest => { manifest.cadence_native_frames = 8; }],
]) test(`state-only scope rejects ${reason}`, () => {
  const data = stateOnlyFixture(); mutate(data.common_benchmark.manifest);
  assert.equal(parseDataset(data).commonBenchmark, null);
});

test('state-only scope rejects image schedule, roster, trial and row contamination or omitted models', () => {
  for (const field of ['repeat_schedule', 'eligible_model_provider_pairs']) {
    const data = stateOnlyFixture(); data.common_benchmark.manifest[field][0].track = 'image';
    assert.equal(parseDataset(data).commonBenchmark, null);
  }
  for (const field of ['trials', 'rows']) {
    const data = stateOnlyFixture(); data.common_benchmark[field][0].track = 'image';
    assert.equal(parseDataset(data).commonBenchmark, null);
  }
  const missing = stateOnlyFixture(); missing.common_benchmark.manifest.repeat_schedule.pop();
  assert.equal(parseDataset(missing).commonBenchmark, null);
  const missingModel = stateOnlyFixture(); missingModel.common_benchmark.manifest.eligible_model_provider_pairs.pop();
  assert.equal(parseDataset(missingModel).commonBenchmark, null);
});

test('three native trials produce independently recomputed means and completed-only timing', () => {
  const row = result(fixture());
  assert.equal(row.meanProgressPct, 80);
  assert.equal(row.bestClearSeconds, 10);
  assert.equal(row.meanCompletedSeconds, 15);
  assert.equal(row.nCompleted, 2);
  assert.ok(Math.abs(row.meanCostUsd - .06) < 1e-12);
  assert.equal(row.meanCostEstimateUsd, null);
  assert.equal(row.representativeRunId, 'common-fixture-state-1');
  const parsed = parseDataset(fixture());
  const before = parseDataset(legacy);
  assert.equal(parsed.observations.length, before.observations.length + 3);
  assert.equal(parsed.runs.length, before.runs.length, 'an aggregate is never a pretend replay');
  assert.ok(!parsed.observations.some(run => run.id === row.id));
});

test('legacy output is unchanged when no evaluation cohort is present', () => {
  assert.equal(parseDataset(legacy).commonBenchmark, null);
  const readme = renderResults(legacy);
  const pilot = fixture(); pilot.common_benchmark.manifest.phase = 'pilot';
  assert.equal(parseDataset(pilot).commonBenchmark, null);
  assert.equal(renderResults(pilot), readme);
  const unregistered = fixture(); unregistered.common_benchmark.manifest.preregistered = false;
  assert.equal(parseDataset(unregistered).commonBenchmark, null);
  const failedPilot = fixture(); failedPilot.common_benchmark.manifest.pilot_selection_evidence.selected_image_temperature_gate_passed = false;
  assert.equal(parseDataset(failedPilot).commonBenchmark, null);
});

test('optional native death flags must agree with the outcome when present', () => {
  const data = fixture();
  assert.equal(result(data).meanProgressPct, 80, 'older exports may omit the optional death flag');
  for (const trial of data.common_benchmark.trials) trial.death = !trial.flag_get;
  assert.equal(result(data).meanProgressPct, 80, 'consistent explicit flags remain valid');
  data.common_benchmark.trials[0].death = true;
  assert.equal(result(data).meanProgressPct, null, 'a completed flag cannot also be a native death');
  data.common_benchmark.trials[0].death = false;
  data.common_benchmark.trials[2].death = false;
  assert.equal(result(data).meanProgressPct, null, 'a declared game-over death cannot explicitly deny death');
});

for (const [reason, mutate] of [
  ['infrastructure', trial => { trial.rankable = false; trial.status = 'technical_pending'; trial.progress_pct = null; }],
  ['contradictory technical pending', trial => { trial.technical_pending = true; }],
  ['protocol mismatch', trial => { trial.protocol_sha256 = 'b'.repeat(64); }],
  ['seed mismatch', trial => { trial.local_rng_seed = 999; }],
  ['mixed decoder temperature', trial => { trial.temperature = .2; }],
  ['provider mismatch', trial => { trial.provider = 'other provider'; }],
  ['unverified replay', trial => { trial.native_replay_verified = false; }],
  ['wrong budget', trial => { trial.native_frame_budget = 7000; }],
  ['failure score beyond the 99.9 clamp', trial => { trial.progress_pct = 99.999; }],
  ['missing start timestamp', trial => { delete trial.started_at_utc; }],
  ['trial before freeze', trial => { trial.started_at_utc = '2025-12-31T23:00:00Z'; }],
]) {
  test(`${reason} leaves the mean pending, never a partial mean or zero`, () => {
    const data = fixture('image'); mutate(data.common_benchmark.trials[2]);
    const parsed = parseDataset(data), row = parsed.commonBenchmark.rows[0];
    assert.equal(row.meanProgressPct, null);
    assert.equal(row.validTrials, 2);
    assert.equal(row.bestClearSeconds, null);
    assert.equal(row.meanCostUsd, null);
    assert.equal(parsed.observations.find(run => run.id === data.common_benchmark.trials[2].id).progressPct, null);
  });
}

test('missing trials and duplicate repeats cannot be silently dropped or replaced', () => {
  const missing = fixture(); missing.common_benchmark.trials.pop();
  assert.equal(result(missing).meanProgressPct, null);
  const repeated = fixture(); repeated.common_benchmark.trials.push({ ...repeated.common_benchmark.trials[2], id: 'another-attempt' });
  assert.equal(result(repeated).meanProgressPct, null);
  assert.equal(result(repeated).validTrials, 2);
  const imported = fixture(); imported.common_benchmark.trials[2].id = legacy.examples[0].id;
  imported.common_benchmark.rows[0].expected_trial_ids[2] = legacy.examples[0].id;
  imported.common_benchmark.rows[0].recorded_trial_ids[2] = legacy.examples[0].id;
  assert.equal(result(imported).meanProgressPct, null, 'legacy showcases are not fresh evaluation trials');
});

test('row IDs cannot replace the prespecified trials and omitted roster models cannot disappear', () => {
  const picked = fixture();
  for (const trial of picked.common_benchmark.trials) trial.id += '-chosen-rerun';
  picked.common_benchmark.rows[0].expected_trial_ids = picked.common_benchmark.trials.map(trial => trial.id);
  picked.common_benchmark.rows[0].recorded_trial_ids = picked.common_benchmark.rows[0].expected_trial_ids;
  assert.equal(result(picked).meanProgressPct, null);
  assert.equal(result(picked).validTrials, 0);
  const omitted = fixture();
  omitted.common_benchmark.manifest.eligible_model_provider_pairs.push({ ...omitted.common_benchmark.manifest.eligible_model_provider_pairs[0], model_id: 'missing/model' });
  assert.equal(parseDataset(omitted).commonBenchmark, null);
});

test('unattributed invalid actions stay technical; proved model failures retain earned progress', () => {
  const data = fixture(), trial = data.common_benchmark.trials[2];
  trial.status = 'invalid_action'; trial.native_frames = 100; trial.progress_pct = 23;
  assert.equal(result(data).meanProgressPct, null);
  trial.model_contract_failure_proven = true;
  assert.equal(result(data).meanProgressPct, null, 'a flag without proof is insufficient');
  trial.failure_proof_href = 'common/proofs/invalid-action.json';
  assert.equal(result(data).meanProgressPct, null, 'unattributed invalid_action remains technical despite stale proof flags');
  trial.status = 'infra_error'; trial.technical_pending = true;
  assert.equal(result(data).meanProgressPct, null);
  trial.status = 'model_contract_failure'; trial.technical_pending = false;
  assert.equal(result(data).meanProgressPct, 223 / 3);
  trial.model_contract_failure_proven = false; trial.status = 'frame_budget'; trial.native_frames = 6000; trial.progress_pct = 0;
  assert.equal(result(data).meanProgressPct, 200 / 3, 'legal neutral controls through the budget are a real failure');
});

test('mean billing requires all three complete scopes and preserves actual versus estimate', () => {
  const missing = fixture(); missing.common_benchmark.trials[2].cost_provenance.attempt_scope_verified = false;
  assert.equal(result(missing).meanProgressPct, 80, 'billing never affects gameplay progress');
  assert.equal(result(missing).meanCostUsd, null);
  assert.equal(result(missing).meanCostEstimateUsd, null);
  const estimated = fixture(), trial = estimated.common_benchmark.trials[2];
  trial.cost_usd = null; trial.cost_estimate_usd = .12;
  trial.cost_provenance.actual_costed_request_count = 9;
  trial.cost_provenance.upstream_cost_basis = 'openrouter_activity_list_price_estimate';
  const row = result(estimated);
  assert.equal(row.meanCostUsd, null);
  assert.ok(Math.abs(row.meanCostEstimateUsd - .07) < 1e-12);
  assert.equal(formatRunCost({ costUsd: row.meanCostUsd, costEstimateUsd: row.meanCostEstimateUsd }), '~$0.07');
});

test('README uses the same primary aggregate and retains every actual history row', () => {
  const data = fixture(), generated = renderResults(data);
  assert.ok(generated.includes('| mean progress | best clear (game s) | mean cost/run (usd) |'));
  assert.ok(generated.includes('| fixture model | 80.00% | 10.00 | $0.06 | 3/3 |'));
  assert.ok(generated.includes('2/3 completed; mean completed time 15.00 game s'));
  assert.ok(generated.includes('<summary>individual runs and development history</summary>'));
  const ids = [...generated.matchAll(/<!-- run:([^ ]+) -->/g)].map(match => match[1]);
  assert.deepEqual(ids.sort(), parseDataset(data).observations.map(run => run.id).sort());
});

test('website and README resolve the same optional cohort file inside the dataset', async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), 'mario-common-'));
  try {
    const data = fixture();
    await mkdir(path.join(directory, 'common'));
    await writeFile(path.join(directory, 'common/index.json'), JSON.stringify({ schema_version: 1, common_benchmark: data.common_benchmark }));
    delete data.common_benchmark; data.common_cohort_href = 'common/index.json';
    await writeFile(path.join(directory, 'index.json'), JSON.stringify(data));
    assert.equal(result(await readPublishedIndex(path.join(directory, 'index.json'))).meanProgressPct, 80);
    data.common_cohort_href = '../outside.json';
    await writeFile(path.join(directory, 'index.json'), JSON.stringify(data));
    await assert.rejects(readPublishedIndex(path.join(directory, 'index.json')), /escapes/);
  } finally { await rm(directory, { recursive: true, force: true }); }
});
