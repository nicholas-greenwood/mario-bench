import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, writeFile, mkdir, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { parseDataset, formatRunCost } from '../lib/data.ts';
import { hydrateRecoveryProofs, readPublishedIndex } from '../lib/read-results.mjs';
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

const recoveryParent = 'e1c1086b8dc2d5613deaad37cbc75003dedaf7564cf82802a17b0e81fcdb8371';
const hashValue = value => createHash('sha256').update(typeof value === 'string' ? value : JSON.stringify(value, Object.keys(value).sort())).digest('hex');
function recoveryFixture(selected = 0) {
  const data = stateOnlyFixture(), cohort = data.common_benchmark, base = cohort.manifest;
  base.protocol_sha256 = recoveryParent;
  cohort.release_provenance = { source_manifest_sha256: 'c'.repeat(64) };
  for (const trial of cohort.trials) trial.protocol_sha256 = recoveryParent;
  for (const row of cohort.rows) row.protocol_sha256 = recoveryParent;
  const authority = { protocol_id: 'mario-state-technical-recovery-v1', protocol_sha256: 'b'.repeat(64),
    parent_protocol_sha256: recoveryParent, parent_manifest_file_sha256: 'c'.repeat(64), parent_audit_sha256: hash,
    prefix_proof_sha256: hash, phase: 'technical_recovery', preregistered: true, frozen_at_utc: '2026-01-03T00:00:00Z',
    tracks: ['state'], native_frame_budget: 6000, native_frame_cap: 6000, cadence_native_frames: 4, life_budget: 1,
    retries_after_initial: 2, max_continuations_per_slot: 1, provider_seed: null, emulator_seed: 0,
    provider_outcome_unknown_attempt_count: 5, slots: [],
  };
  for (let i = 0; i < 8; i++) {
    const original = cohort.trials[i * 3 + 2], pair = base.eligible_model_provider_pairs[i];
    Object.assign(original, { status: 'infra_error', rankable: false, technical_pending: true, flag_get: false,
      completed: false, death: false, progress_pct: null, native_frames: 400, decisions: 100, native_frames_to_completion: null,
      attempt_proof: { source_episode_sha256: hashValue(original.id), request_intent_count: 103, request_result_count: 103,
        error_attempt_count: 3, unanswered_attempt_count: 0, terminal_at_utc: '2026-01-02T01:00:00Z' } });
    const kind = i < 5 ? 'timeout_then_socket_gaierror_dns' : i < 7 ? 'socket_gaierror_dns' : 'typed_service_429';
    const pin = { id: pair.model_id, request_model: pair.request_model, provider: pair.provider,
      expected_returned_model: pair.expected_returned_model, expected_returned_provider_names: pair.expected_returned_provider_names };
    authority.slots.push({ original_trial_id: original.id, child_run_id: `${original.id}-recovery`, model_id: original.model_id,
      track: 'state', repeat_id: 2, local_rng_seed: null, emulator_seed: 0, temperature: null,
      parent_episode_sha256: original.attempt_proof.source_episode_sha256, parent_abort_status: 'infra_error', failure_kind: kind,
      checkpoint_native_frame: 400, checkpoint_ram_sha256: hash, checkpoint_rgb_sha256: hash, checkpoint_observation_sha256: hash,
      controller_history_sha256: hash, failed_request_sha256: hash, controller_sha256: hash, pin_sha256: null, pin_payload: pin,
      rng_mode: 'not_used_native_choice', rng_state_sha256: null, failed_decision_index: 100, failed_stage: 'motor',
      parent_valid_native_actions: 100, parent_http_attempts: 103, remaining_native_frame_budget: 5600,
      provider_outcome_unknown_attempt_count: i < 5 ? 1 : 0, no_observed_valid_choice_discarded: true, unmatched_ledger_intent_count: 0,
      failed_attempt_chain: [0, 1, 2].map(attempt => ({ attempt, error: kind === 'typed_service_429' ? 'HTTP429' : i < 5 && attempt === 0 ? 'TimeoutError' : 'gaierror',
        error_type: kind === 'typed_service_429' ? 'http' : 'transport', http_status: kind === 'typed_service_429' ? 429 : null,
        request_sha256: hash, valid: false, retryable: true, raw_response_present: kind === 'typed_service_429', native_answers_present: false })),
    });
  }
  const slot = authority.slots[selected], original = cohort.trials.find(t => t.id === slot.original_trial_id);
  const checkpointKeys = ['checkpoint_native_frame', 'checkpoint_ram_sha256', 'checkpoint_rgb_sha256', 'checkpoint_observation_sha256',
    'controller_history_sha256', 'failed_request_sha256', 'controller_sha256', 'pin_sha256', 'rng_mode', 'rng_state_sha256'];
  const child = { ...structuredClone(original), id: slot.child_run_id, record_kind: 'technical_continuation', phase: 'technical_recovery',
    protocol_sha256: authority.protocol_sha256, parent_protocol_sha256: recoveryParent, parent_episode_sha256: slot.parent_episode_sha256,
    resolves_original_trial_id: original.id, status: 'game_over', rankable: true, technical_pending: false, native_replay_verified: true,
    level: '1-1', start_x: 40, started_at_utc: '2026-01-04T00:00:00Z', native_frames: 404, decisions: 101, continuation_native_frames: 4,
    continuation_decisions: 1, completed: false, flag_get: false, death: true, progress_pct: 40, max_progress_x: 1288.4,
    cadence_native_frames: 4, trace_href: 'common/recovery/child.json', trace_sha256: hash,
    attempt_proof: { source_episode_sha256: hashValue(slot.child_run_id), scope: 'composed_trajectory', request_intent_count: 104, request_result_count: 104,
      error_attempt_count: 3, unanswered_attempt_count: 0, native_audit_sha256: null },
    cost_usd: .12, cost_provenance: { ...structuredClone(billing), request_count: 104, source_request_count: 104, source_attempt_count: 104,
      costed_request_count: 104, actual_costed_request_count: 104, error_count: 3, joined_attempt_count: 104 },
  };
  const logical = { ...structuredClone(child), id: original.id, logical_trial_id: original.id, source_run_id: child.id,
    record_kind: 'technical_resolution', base_protocol_sha256: recoveryParent };
  const proof = { schema_version: 1, verified: true, original_trial_id: original.id, child_run_id: child.id,
    parent_protocol_sha256: recoveryParent, recovery_protocol_sha256: authority.protocol_sha256,
    parent_episode_sha256: slot.parent_episode_sha256, child_episode_sha256: child.attempt_proof.source_episode_sha256,
    original_attempt_count: 103, recovery_attempt_count: 1, joined_attempt_count: 104,
    original_error_attempt_count: 3, recovery_error_attempt_count: 0, joined_error_attempt_count: 3,
    original_request_result_count: 103, recovery_request_result_count: 1, joined_request_result_count: 104,
    original_unanswered_attempt_count: 0, recovery_unanswered_attempt_count: 0, joined_unanswered_attempt_count: 0,
    provider_outcome_unknown_attempt_count: selected < 5 ? 1 : 0, new_provider_outcome_unknown_attempt_count: 0,
    total_provider_outcome_unknown_attempt_count: selected < 5 ? 1 : 0, no_observed_valid_choice_discarded: true,
    prefix_replay_verified: true, failed_body_identical: true, controller_pin_history_rng_verified: true, total_native_budget_verified: true,
    total_native_frames: 404, new_native_frames: 4, total_native_frame_budget: 6000,
  };
  const resolution = { original_trial_id: original.id, child_run_id: child.id, parent_episode_sha256: slot.parent_episode_sha256,
    child_episode_sha256: child.attempt_proof.source_episode_sha256, proof_href: 'common/recovery/proof.json', proof_sha256: null,
    prefix_replay_verified: true, failed_body_identical: true, controller_pin_history_rng_verified: true, total_native_budget_verified: true,
    effective_trial: logical };
  cohort.technical_recovery = { manifest: authority, continuations: [child], resolutions: [resolution] };
  return { data, authority, slot, child, logical, proof, resolution, original, checkpointKeys };
}

async function prepareRecovery(fixture, mutate = () => {}) {
  // Hydrate once to derive Python-compatible canonical pin digests.
  const resolutions = fixture.data.common_benchmark.technical_recovery.resolutions;
  fixture.data.common_benchmark.technical_recovery.resolutions = [];
  await hydrateRecoveryProofs(fixture.data, () => { throw new Error('no proofs yet'); });
  fixture.data.common_benchmark.technical_recovery.resolutions = resolutions;
  for (const slot of fixture.authority.slots) slot.pin_sha256 = slot._computed_pin_sha256;
  const checkpoint = Object.fromEntries(fixture.checkpointKeys.map(k => [k, fixture.slot[k]]));
  fixture.child.checkpoint = structuredClone(checkpoint); fixture.child.reconstructed_checkpoint = structuredClone(checkpoint);
  fixture.logical.checkpoint = structuredClone(checkpoint); fixture.logical.reconstructed_checkpoint = structuredClone(checkpoint);
  fixture.proof.declared_checkpoint = structuredClone(checkpoint); fixture.proof.reconstructed_checkpoint = structuredClone(checkpoint);
  const { attempt_proof, ...grade } = fixture.child;
  fixture.proof.result = { ...structuredClone(grade), frames: fixture.child.native_frames };
  mutate(fixture);
  const bytes = Buffer.from(JSON.stringify(fixture.proof)), proofHash = createHash('sha256').update(bytes).digest('hex');
  fixture.resolution.proof_sha256 = proofHash;
  fixture.child.attempt_proof.native_audit_sha256 = proofHash; fixture.logical.attempt_proof.native_audit_sha256 = proofHash;
  await hydrateRecoveryProofs(fixture.data, () => bytes);
  return parseDataset(fixture.data);
}

test('an audited continuation resolves one logical slot, preserving66 source records and the new authority', async () => {
  const fixture = recoveryFixture(), before = structuredClone(fixture.original), parsed = await prepareRecovery(fixture);
  const cohort = parsed.commonBenchmark, trajectory = cohort.trials.find(t => t.id === fixture.original.id);
  assert.equal(cohort.rows.length, 22); assert.equal(cohort.trials.length, 66);
  assert.equal(cohort.rows[0].meanProgressPct, 80); assert.equal(cohort.technicalRecovery.resolved, 1);
  assert.equal(trajectory.phase, 'technical_recovery'); assert.equal(trajectory.protocol_sha256, fixture.authority.protocol_sha256);
  assert.equal(trajectory.base_protocol_sha256, recoveryParent); assert.equal(trajectory.source_run_id, fixture.child.id);
  assert.deepEqual(fixture.original, before, 'original abort is not rewritten');
  assert.equal(cohort.rows[0].meanCostUsd, null, 'unknown original provider outcome prevents a child-only bill');
  assert.ok(parsed.observations.find(r => r.id === fixture.original.id).name.endsWith('(technical continuation)'));
  assert.ok(!parsed.observations.some(r => r.id === fixture.child.id), 'a continuation is not a fourth quality trial');
});

for (const [reason, mutate] of [
  ['replayed RAM differs', f => { f.proof.reconstructed_checkpoint.checkpoint_ram_sha256 = 'd'.repeat(64); }],
  ['failed body differs', f => { f.child.reconstructed_checkpoint.failed_request_sha256 = 'd'.repeat(64); }],
  ['source hash differs', f => { f.resolution.parent_episode_sha256 = 'd'.repeat(64); }],
  ['wrong seed', f => { f.child.local_rng_seed = 5; }],
  ['wrong pin', f => { f.child.returned_model = 'other/model'; }],
  ['extra6000 frame budget', f => { f.child.native_frames = 6400; f.logical.native_frames = 6400; f.proof.total_native_frames = 6400; }],
  ['child remains infrastructure', f => { f.child.status = 'infra_error'; f.child.rankable = false; }],
  ['missing lineage proof', f => { f.proof.verified = false; }],
  ['post-freeze start missing', f => { delete f.child.started_at_utc; }],
  ['audit grade forged in public copies', f => { for (const t of [f.child, f.logical]) Object.assign(t, { status: 'completed', flag_get: true, completed: true, death: false, progress_pct: 100, native_frames_to_completion: 404 }); }],
  ['wrong level', f => { f.child.level = f.logical.level = '1-2'; }],
  ['arbitrary logical trace', f => { f.logical.trace_href = 'common/not-the-child.json'; }],
  ['new provider unknown outcome dropped', f => { f.proof.new_provider_outcome_unknown_attempt_count = 1; }],
]) test(`recovery rejects ${reason} without replacing the original`, async () => {
  const fixture = recoveryFixture(), parsed = await prepareRecovery(fixture, mutate);
  assert.equal(parsed.commonBenchmark.rows[0].meanProgressPct, null);
  assert.equal(parsed.commonBenchmark.technicalRecovery?.resolved ?? 0, 0);
});

test('extra resolutions and attempts to recover valid deaths invalidate the overlay', async () => {
  const duplicate = recoveryFixture();
  const parsed = await prepareRecovery(duplicate, f => f.data.common_benchmark.technical_recovery.resolutions.push(structuredClone(f.resolution)));
  assert.equal(parsed.commonBenchmark.technicalRecovery, null);
  const death = recoveryFixture(); death.original.rankable = true; death.original.status = 'game_over'; death.original.death = true;
  assert.equal((await prepareRecovery(death)).commonBenchmark.technicalRecovery, null);
});

test('proof bytes and pin payloads are checked, not trusted boolean attestations', async () => {
  const fixture = recoveryFixture(); await prepareRecovery(fixture);
  await assert.rejects(hydrateRecoveryProofs(fixture.data, () => Buffer.from('{}')), /checksum mismatch/);
  const wrongPin = recoveryFixture();
  const parsed = await prepareRecovery(wrongPin, f => { f.slot.pin_payload.request_model = 'other/model'; });
  assert.equal(parsed.commonBenchmark.technicalRecovery, null);
});

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
    delete data.common_benchmark; delete data.common_image_cohort_href; data.common_cohort_href = 'common/index.json';
    await writeFile(path.join(directory, 'index.json'), JSON.stringify(data));
    assert.equal(result(await readPublishedIndex(path.join(directory, 'index.json'))).meanProgressPct, 80);
    data.common_cohort_href = '../outside.json';
    await writeFile(path.join(directory, 'index.json'), JSON.stringify(data));
    await assert.rejects(readPublishedIndex(path.join(directory, 'index.json')), /escapes/);
  } finally { await rm(directory, { recursive: true, force: true }); }
});


function imageOnlyFixture() {
  const data = fixture('image'), cohort = data.common_benchmark, manifest = cohort.manifest;
  const templates = structuredClone(cohort.trials), row = structuredClone(cohort.rows[0]), pair = structuredClone(manifest.eligible_model_provider_pairs[0]);
  Object.assign(manifest, { evaluation_scope: 'image_progress_baseline', tracks: ['image'],
    protocol_id: 'mario-common-image-h7-progress-baseline-v1', temperature: .05, cadence_native_frames: 7,
    native_frame_budget: 6000, life_budget: 1, provider_seed: null, emulator_seed: 0, requested_native_hold: 7,
    media: { current_full_size: [512,480], past_full_screens: 1, own_controls: 2 },
    sampling: { temperature: .05, final_seeds: [101,102,103] }, software_sha256: { 'fixed-controller.py': hash },
    roster_source_sha256: hash, actual_rom_sha256: hash, initial_observation_sha256: hash, initial_screen_sha256: hash,
  });
  delete manifest.pilot_selection_evidence;
  manifest.observation_and_controller_hashes.image_controller_sha256 = '658d541b1df18a58fc37eb465f39d05d66b58a1074666b3fd70ab36848e0f6a4';
  manifest.acceptance_contract = { mode: 'explicit_progress_baseline_v1', track: 'image', positive_pilot_required: false,
    native_clear_is_outcome: true, prior_failed_pilot_gates_preserved: true, preflight_model_count: 16, preflight_audit_complete: true,
    spec_sha256: '86e4974bc01f983980c1773184e75900856d55a3d68fa6fc32c43c416e91bf29',
    ...Object.fromEntries(['historical_mechanics_proof_sha256','preflight_protocol_sha256','preflight_report_sha256','preflight_audit_sha256','image_controller_sha256'].map(key => [key, hash])),
    image_controller_sha256: '658d541b1df18a58fc37eb465f39d05d66b58a1074666b3fd70ab36848e0f6a4',
    historical_mechanics_proof_sha256: '9599dea865c7b675e7ee33b2ff1c98b6b34bca0abf21d2da15c6cbb9ae1be7f1',
    historical_mechanics: { trace_sha256: '30392705e81db66ea234bfd71ac64e9cab2cca3dc1577829a620d3ff8f48432d',
      exact_native_requests: 268, native_flag_frame: 1871, development_seed: 0, development_temperature: .05,
      not_a_scored_final_trial: true, pure_policy_sha256: '19cdd3382f9919d4b474691b2fc78cb676e1382d94b1fd43b21280e6039483da', runtime_sha256: '0a7fc35cd2654b20d386814c9376d905b57bde927ab3d0c4e0dfc66664dae95b' },
    negative_calibration_proofs: [
      ['66cd3ae7b068fc57add4b783328dceb5f7992ca55a8737a14ea2eef02ad9dd62', '983ea565f48b385490f7b018b5119faad816b0ca3468310b56e6be74bdf61f31'],
      ['4f489c937469d7d68379fe83bc8d457faae83e67e0b00bdb39bc4ecddc105194', 'a505e41e1847a576904feea5d63f21d716a47ec12c79f2fa02835454f554026b'],
      ['3f6b8108c02a5a60bc91c841a868d9ff3724bb2de92d17b53ac5c431b4812675', '38f081ab2fc0d3ca22ca90790585adc4ba7cafde15e27f8431636caad95ba8a0'],
    ].map(([protocol_sha256,certificate_sha256]) => ({protocol_sha256,certificate_sha256,native_image_clears:0})),
  };
  manifest.repeat_schedule = []; manifest.eligible_model_provider_pairs = []; cohort.trials = []; cohort.rows = [];
  for (let model = 0; model < 16; model++) {
    const modelId = `fixture/image-model-${model}`;
    const trials = templates.map(trial => ({ ...structuredClone(trial), id: `image-final-fixture-${model}-${trial.repeat_id}`,
      model_id: modelId, request_model: modelId, returned_model: `${modelId}-v1`,
      status: 'game_over', progress_pct: 30 + trial.repeat_id, flag_get: false, native_frames_to_completion: null, cadence_native_frames: 7,
    }));
    cohort.trials.push(...trials);
    manifest.repeat_schedule.push(...trials.map(({id,model_id,track,repeat_id,local_rng_seed,emulator_seed,temperature}) =>
      ({episode_id:id,model_id,track,repeat_id,local_rng_seed,emulator_seed,temperature})));
    manifest.eligible_model_provider_pairs.push({...pair,model_id:modelId,request_model:modelId,expected_returned_model:`${modelId}-v1`});
    cohort.rows.push({...row,model_id:modelId,expected_trial_ids:trials.map(trial=>trial.id),recorded_trial_ids:trials.map(trial=>trial.id)});
  }
  return data;
}

test('explicit image progress baseline accepts 16 independent fresh three-run means without a calibration clear', () => {
  const parsed = parseDataset(imageOnlyFixture()), cohort = parsed.commonBenchmark;
  assert.equal(cohort?.imageOnly, true); assert.equal(cohort.rows.length, 16);
  assert.ok(cohort.rows.every(row => row.meanProgressPct === 31 && row.bestClearSeconds === null && row.nCompleted === 0));
  assert.equal(parsed.observations.length, parseDataset(legacy).observations.length + 48);
  const rendered = renderResults(imageOnlyFixture()); assert.match(rendered, /earlier failed calibration gates remain failed/);

});
for (const [name, mutate] of [
  ['old scope cannot bypass its positive gate', c => {delete c.manifest.evaluation_scope;}],
  ['no mixed tracks', c => {c.manifest.repeat_schedule[0].track='state';}],
  ['no seed0 witness substitution', c => {c.manifest.repeat_schedule[0].local_rng_seed=0;}],
  ['no seed9001 calibration substitution', c => {c.manifest.repeat_schedule[0].local_rng_seed=9001;}],
  ['all16 pairs required', c => {c.manifest.eligible_model_provider_pairs.pop();}],
  ['one common temperature', c => {c.manifest.temperature=.2;}],
  ['no fabricated positive gate', c => {c.manifest.pilot_selection_evidence={selected_image_temperature_gate_passed:true};}],
  ['real16 preflight required', c => {c.manifest.acceptance_contract.preflight_audit_complete=false;}],
  ['historical witness not a final trial', c => {c.manifest.acceptance_contract.historical_mechanics.not_a_scored_final_trial=false;}],
  ['negative evidence retained', c => {c.manifest.acceptance_contract.negative_calibration_proofs[0].native_image_clears=1;}],
  ['controller hash fixed', c => {c.manifest.acceptance_contract.image_controller_sha256='e'.repeat(64);}],
  ['full current image required', c => {c.manifest.media.current_full_size=[256,240];}],
  ['hold7 fixed', c => {c.manifest.requested_native_hold=8;}],
]) test(`image branch rejects ${name}`,()=>{const data=imageOnlyFixture();mutate(data.common_benchmark);assert.equal(parseDataset(data).commonBenchmark,null);});
test('technical image trial keeps mean and speed pending and costs unknown',()=>{
  const data=imageOnlyFixture();data.common_benchmark.trials[0].technical_pending=true;
  const row=parseDataset(data).commonBenchmark.rows[0];assert.equal(row.meanProgressPct,null);assert.equal(row.bestClearSeconds,null);assert.equal(row.meanCostUsd,null);
});
test('state and image cohorts retain separate protocol means and all actual trials',()=>{
  const data=stateOnlyFixture(), image=imageOnlyFixture().common_benchmark;image.manifest.protocol_sha256='f'.repeat(64);
  for(const trial of image.trials)trial.protocol_sha256='f'.repeat(64);for(const row of image.rows)row.protocol_sha256='f'.repeat(64);
  data.common_image_benchmark=image;const parsed=parseDataset(data);
  assert.equal(parsed.commonBenchmarks.length,2);assert.equal(parsed.commonBenchmarks[0].rows.length,22);assert.equal(parsed.commonBenchmarks[1].rows.length,16);
  assert.equal(parsed.observations.length,parseDataset(legacy).observations.length+66+48);
  assert.equal(new Set(parsed.observations.map(run=>run.id)).size,parsed.observations.length);
  assert.match(renderResults(data),/state and image use separate frozen protocols/);
  assert.doesNotMatch(renderResults(data),/common image track: calibration pending/);
  const stateMean=parsed.commonBenchmarks[0].rows[0].meanProgressPct;image.trials[0].progress_pct=5;
  assert.equal(parseDataset(data).commonBenchmarks[0].rows[0].meanProgressPct,stateMean);
});
test('additional image cohort cannot replace an existing prescribed state ID',()=>{
  const data=stateOnlyFixture(),image=imageOnlyFixture().common_benchmark;
  image.manifest.repeat_schedule[0].episode_id=data.common_benchmark.manifest.repeat_schedule[0].episode_id;
  data.common_image_benchmark=image;assert.equal(parseDataset(data).commonBenchmarks.length,1);
});
test('pending image cohort exposes 16 pending rows without a historical witness score',()=>{
  const data=imageOnlyFixture();data.common_benchmark.trials=[];for(const row of data.common_benchmark.rows){row.coverage_complete=false;row.recorded_trial_ids=[];}
  const parsed=parseDataset(data);assert.equal(parsed.commonBenchmark.rows.length,16);assert.ok(parsed.commonBenchmark.rows.every(row=>row.meanProgressPct===null&&row.bestClearSeconds===null&&row.meanCostUsd===null));
  assert.equal(parsed.observations.length,parseDataset(legacy).observations.length);
});

test('independent tracks cannot share a protocol digest',()=>{
  const data=stateOnlyFixture();data.common_image_benchmark=imageOnlyFixture().common_benchmark;
  assert.equal(parseDataset(data).commonBenchmarks.length,1);
});
test('one image run with a different control cadence cannot enter the mean',()=>{
  const data=imageOnlyFixture();data.common_benchmark.trials[0].cadence_native_frames=4;
  assert.equal(parseDataset(data).commonBenchmark.rows[0].meanProgressPct,null);
});
test('published loader attaches image and state cohorts independently',async()=>{
  const directory=await mkdtemp(path.join(os.tmpdir(),'mario-dual-cohort-'));
  try {
    const state=stateOnlyFixture(),image=imageOnlyFixture().common_benchmark;image.manifest.protocol_sha256='f'.repeat(64);
    for(const trial of image.trials)trial.protocol_sha256='f'.repeat(64);for(const row of image.rows)row.protocol_sha256='f'.repeat(64);
    const index={...structuredClone(legacy),common_cohort_href:'state.json',common_image_cohort_href:'image.json'};
    await writeFile(path.join(directory,'index.json'),JSON.stringify(index));
    await writeFile(path.join(directory,'state.json'),JSON.stringify({schema_version:1,common_benchmark:state.common_benchmark}));
    await writeFile(path.join(directory,'image.json'),JSON.stringify({schema_version:1,common_benchmark:image}));
    const parsed=parseDataset(await readPublishedIndex(path.join(directory,'index.json')));
    assert.equal(parsed.commonBenchmarks.length,2);assert.equal(parsed.commonBenchmarks[1].rows.length,16);
  } finally {await rm(directory,{recursive:true,force:true});}
});

test('validated technical resolution completes the effective three-trial cohort despite immutable original coverage',async()=>{
  const f=recoveryFixture();f.data.common_benchmark.rows[0].coverage_complete=false;
  const parsed=await prepareRecovery(f);assert.equal(parsed.commonBenchmark.rows[0].validTrials,3);assert.equal(parsed.commonBenchmark.rows[0].coverageComplete,true);assert.notEqual(parsed.commonBenchmark.rows[0].meanProgressPct,null);
  assert.equal(f.data.common_benchmark.rows[0].coverage_complete,false);
});

async function unavailableFixture(mutate=()=>{}) {
  const f=recoveryFixture();await prepareRecovery(f);f.data.common_benchmark.technical_recovery.resolutions=[];
  Object.assign(f.child,{status:'infra_error',rankable:false,technical_pending:true,completed:false,death:false,progress_pct:null,cost_usd:null});
  Object.assign(f.child.attempt_proof,{request_intent_count:107,request_result_count:107,error_attempt_count:6,terminal_at_utc:'2026-01-05T00:00:00Z'});
  Object.assign(f.proof,{recovery_attempt_count:4,joined_attempt_count:107,recovery_error_attempt_count:3,joined_error_attempt_count:6,recovery_request_result_count:4,joined_request_result_count:107});
  const {attempt_proof,proof,proof_sha256,proof_href,proof_verified_sha256,...grade}=f.child;f.proof.result={...structuredClone(grade),frames:f.child.native_frames};
  mutate(f);const bytes=Buffer.from(JSON.stringify(f.proof));f.child.proof_href='common/recovery/closed-infra.json';f.child.proof_sha256=createHash('sha256').update(bytes).digest('hex');
  f.child.attempt_proof.native_audit_sha256=f.child.proof_sha256;await hydrateRecoveryProofs(f.data,()=>bytes);
  return {f,parsed:parseDataset(f.data)};
}
test('audited closed technical child marks mean unavailable without adding a score or a trial',async()=>{
  const {f,parsed}=await unavailableFixture(),row=parsed.commonBenchmark.rows[0];assert.equal(row.availability,'unavailable');assert.equal(row.meanProgressPct,null);assert.equal(row.bestClearSeconds,null);assert.equal(row.meanCostUsd,null);
  assert.equal(parsed.commonBenchmark.trials.length,66);assert.match(renderResults(f.data),/unavailable \|/);
});
for(const [name,change] of [
 ['unclosed attempt',f=>delete f.child.attempt_proof.terminal_at_utc],
 ['unanswered request',f=>f.child.attempt_proof.unanswered_attempt_count=1],
 ['wrong protocol',f=>f.child.protocol_sha256=hash],
 ['unverified native proof',f=>f.proof.verified=false],
 ['wrong native grade',f=>f.proof.result.native_frames=6000],
 ['wrong child source',f=>f.proof.child_episode_sha256=hash],
 ['wrong checkpoint',f=>f.proof.reconstructed_checkpoint.checkpoint_ram_sha256='b'.repeat(64)],
 ['wrong joined error count',f=>f.proof.joined_error_attempt_count=0],
])test(`technical availability remains pending with ${name}`,async()=>{const {parsed}=await unavailableFixture(change);assert.equal(parsed.commonBenchmark.rows[0].availability,'pending');assert.equal(parsed.commonBenchmark.rows[0].meanProgressPct,null);});
test('missing image trials remain pending rather than becoming terminal technical outcomes',()=>{
  const data=imageOnlyFixture();data.common_benchmark.trials=[];const cohort=parseDataset(data).commonBenchmark;assert.ok(cohort.rows.every(r=>r.availability==='pending'));
});

const imageParent = '2f11c42b8d47f8cd8959e828243acacb8abcf83c478a6206508ebd635004fdf1';
const canonicalJson = value => value && typeof value === 'object' && !Array.isArray(value)
  ? Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonicalJson(value[key])])) : Array.isArray(value)?value.map(canonicalJson):value;
const jsonBytes = value => Buffer.from(JSON.stringify(canonicalJson(value)));
const bytesHash = value => createHash('sha256').update(value).digest('hex');
function imageRecoveryFixture(inherited=false) {
  const data=imageOnlyFixture(),cohort=data.common_benchmark,base=cohort.manifest;
  base.protocol_sha256=imageParent;for(const row of cohort.rows)row.protocol_sha256=imageParent;
  const source={};for(const trial of cohort.trials){trial.protocol_sha256=imageParent;trial.attempt_proof={source_episode_sha256:hash,native_audit_sha256:hash,
    request_intent_count:10,request_result_count:10,error_attempt_count:0,unanswered_attempt_count:0,terminal_at_utc:'2026-01-03T00:00:00Z'};source[trial.id]=hash;}
  cohort.release_provenance={source_manifest_sha256:'c'.repeat(64)};
  const original=cohort.trials[0],pair=base.eligible_model_provider_pairs[0],oldCount=inherited?56:55;
  Object.assign(original,{status:'infra_error',rankable:false,technical_pending:true,flag_get:false,completed:false,death:false,native_frames:294,frames:294,decisions:42,progress_pct:null,max_progress_x:300,native_frames_to_completion:null,cost_usd:null,cost_estimate_usd:null});
  Object.assign(original.attempt_proof,{request_intent_count:oldCount,request_result_count:oldCount,error_attempt_count:13});
  const pin={id:pair.model_id,request_model:pair.request_model,provider:pair.provider,expected_returned_model:pair.expected_returned_model,expected_returned_provider_names:pair.expected_returned_provider_names};
  const controls=[280,287].map(frame=>({frame,frames:7,buttons:{horizontal:'right',vertical:'released',jump:'released',run:'held'}}));
  const rng=[3,[...Array(624).fill(123),84],null];
  const cp={checkpoint_native_frame:294,checkpoint_ram_sha256:hash,checkpoint_rgb_sha256:hash,checkpoint_observation_sha256:hash,controller_history_sha256:hash,
    session_controls:controls,session_controls_sha256:bytesHash(jsonBytes(controls)),current_png_sha256:hash,previous_images:[{frame:287,png_sha256:hash}],
    failed_request_sha256:hash,controller_sha256:base.observation_and_controller_hashes.image_controller_sha256,pin_sha256:bytesHash(jsonBytes(pin)),
    rng_mode:'global_full12_temperature_sampling',rng_state:rng,rng_state_sha256:bytesHash(jsonBytes(rng)),rng_mt_index:84,rng_draw_count:42};
  const slot={original_trial_id:original.id,child_run_id:original.id+'--image-technical-recovery-v1',parent_episode_sha256:hash,model_id:original.model_id,track:'image',repeat_id:0,
    temperature:.05,emulator_seed:0,local_rng_seed:101,pin_payload:pin,checkpoint:cp,failed_decision_index:42,failed_stage:'motor',failed_attempt_chain:3,
    continuation_mode:inherited?'reuse_recorded_valid_response':'fresh_after_observed_failures',parent_abort_status:'infra_error',parent_valid_native_actions:42,parent_http_attempts:oldCount,
    parent_max_progress_x:300,remaining_native_frame_budget:5706,provider_outcome_unknown_attempt_count:0,no_observed_valid_choice_discarded:true,unmatched_ledger_intent_count:0,
    inherited_parent_valid_response_sha256:inherited?hash:null,inherited_parent_receipt_id_sha256:inherited?hash:null};
  const child={...structuredClone(original),id:slot.child_run_id,record_kind:'technical_continuation',phase:'technical_recovery',protocol_sha256:'e'.repeat(64),parent_protocol_sha256:imageParent,
    resolves_original_trial_id:original.id,parent_episode_sha256:hash,started_at_utc:'2026-01-05T00:00:00Z',status:'game_over',rankable:true,technical_pending:false,death:true,
    progress_pct:40,max_progress_x:1300,native_frames:301,frames:301,decisions:43,continuation_native_frames:7,continuation_decisions:1,start_x:40,
    checkpoint:structuredClone(cp),reconstructed_checkpoint:structuredClone(cp),trace_href:'image-recovery/traces/child.json',trace_sha256:hash,
    attempt_proof:{source_episode_sha256:'d'.repeat(64),native_audit_sha256:null,scope:'composed_trajectory',request_intent_count:56,request_result_count:56,error_attempt_count:13,unanswered_attempt_count:0}};
  const proof={schema_version:1,verified:true,original_trial_id:original.id,child_run_id:child.id,parent_protocol_sha256:imageParent,recovery_protocol_sha256:child.protocol_sha256,
    parent_episode_sha256:hash,child_episode_sha256:'d'.repeat(64),declared_checkpoint:structuredClone(cp),reconstructed_checkpoint:structuredClone(cp),
    prefix_replay_verified:true,failed_body_identical:true,controller_pin_history_rng_verified:true,total_native_budget_verified:true,no_observed_valid_choice_discarded:true,
    original_attempt_count:oldCount,recovery_attempt_count:inherited?0:1,joined_attempt_count:56,original_error_attempt_count:13,recovery_error_attempt_count:0,joined_error_attempt_count:13,
    original_request_result_count:oldCount,recovery_request_result_count:inherited?0:1,joined_request_result_count:56,
    original_unanswered_attempt_count:0,recovery_unanswered_attempt_count:0,joined_unanswered_attempt_count:0,
    inherited_parent_valid_choice_count:inherited?1:0,inherited_parent_valid_response_sha256:slot.inherited_parent_valid_response_sha256,inherited_parent_receipt_id_sha256:slot.inherited_parent_receipt_id_sha256,
    provider_outcome_unknown_attempt_count:0,new_provider_outcome_unknown_attempt_count:0,total_provider_outcome_unknown_attempt_count:0,
    total_native_frames:301,new_native_frames:7,total_native_frame_budget:6000,result:structuredClone(child)};
  const logical={...structuredClone(child),id:original.id,logical_trial_id:original.id,source_run_id:child.id,record_kind:'technical_resolution',base_protocol_sha256:imageParent};
  const resolution={original_trial_id:original.id,child_run_id:child.id,parent_episode_sha256:hash,child_episode_sha256:'d'.repeat(64),proof_href:'image-recovery/proofs/child.json',proof_sha256:null,
    prefix_replay_verified:true,failed_body_identical:true,controller_pin_history_rng_verified:true,total_native_budget_verified:true,effective_trial:logical};
  const authority={protocol_id:'mario-image-technical-recovery-v1',protocol_sha256:child.protocol_sha256,parent_protocol_sha256:imageParent,parent_manifest_file_sha256:'c'.repeat(64),
    parent_audit_sha256:hash,prefix_proof_href:'image-recovery/prefix.json',prefix_proof_sha256:null,acceptance_mode:'same_checkpoint_technical_recovery_v1',
    phase:'technical_recovery',preregistered:true,frozen_at_utc:'2026-01-04T00:00:00Z',slots:[slot],tracks:['image'],native_frame_budget:6000,native_frame_cap:6000,cadence_native_frames:7,
    requested_native_hold:7,life_budget:1,temperature:.05,provider_seed:null,emulator_seed:0,max_continuations_per_slot:1,retries_after_initial:2,provider_outcome_unknown_attempt_count:0};
  const prefix={verified:true,parent_protocol_sha256:imageParent,source_log_sha256:source,slots:[structuredClone(slot)]};
  cohort.technical_recovery={manifest:authority,continuations:[child],resolutions:[resolution]};
  return {data,cohort,original,slot,cp,child,proof,logical,resolution,authority,prefix};
}
async function prepareImageRecovery(f, mutate=()=>{}) {
  mutate(f);f.prefix.slots=structuredClone(f.authority.slots);const proof=jsonBytes(f.proof),prefix=jsonBytes(f.prefix);
  f.resolution.proof_sha256=bytesHash(proof);f.child.attempt_proof.native_audit_sha256=f.resolution.proof_sha256;
  f.child.proof_href=f.resolution.proof_href;f.child.proof_sha256=f.resolution.proof_sha256;
  f.authority.prefix_proof_sha256=bytesHash(prefix);
  await hydrateRecoveryProofs(f.data,p=>Promise.resolve(p===f.resolution.proof_href?proof:prefix));
  return parseDataset(f.data);
}
test('image continuation resolves one original slot without adding a quality trial',async()=>{
  const f=imageRecoveryFixture(),before=JSON.stringify(f.original),parsed=await prepareImageRecovery(f);
  assert.equal(parsed.commonBenchmark.technicalRecovery?.planned,1);assert.equal(parsed.commonBenchmark.technicalRecovery?.resolved,1);
  assert.equal(parsed.commonBenchmark.trials.length,48);assert.equal(parsed.commonBenchmark.rows[0].meanProgressPct,(40+31+32)/3);
  assert.equal(JSON.stringify(f.original),before);assert.equal(parsed.observations.length,parseDataset(legacy).observations.length+48);
  assert.equal(parsed.commonBenchmark.trials[0].source_run_id,f.child.id);assert.equal(parsed.commonBenchmark.trials[0].phase,'technical_recovery');
});
test('received parent choice is reused without another HTTP or billing receipt',async()=>{
  const f=imageRecoveryFixture(true),parsed=await prepareImageRecovery(f);assert.equal(parsed.commonBenchmark.technicalRecovery?.resolved,1);
  assert.equal(f.proof.recovery_attempt_count,0);assert.equal(parsed.commonBenchmark.trials[0].decisions,43);
});
for(const [name,change] of [
  ['wrong image parent',f=>f.authority.parent_protocol_sha256=hash],
  ['missing independent prefix bytes',f=>f.authority.prefix_proof_href=null],
  ['omitted original source',f=>delete f.prefix.source_log_sha256[f.original.id]],
  ['wrong source log',f=>f.prefix.source_log_sha256[f.original.id]='f'.repeat(64)],
  ['valid death retry',f=>{f.original.status='game_over';f.original.rankable=true;f.original.death=true;}],
  ['extra undeclared child',f=>f.cohort.technical_recovery.continuations.push({...f.child,id:'extra-child'})],
  ['different seed',f=>f.slot.local_rng_seed=102],
  ['different temperature',f=>f.authority.temperature=.2],
  ['reset native frame',f=>f.cp.checkpoint_native_frame=0],
  ['missing native RAM',f=>f.cp.checkpoint_ram_sha256=null],
  ['missing current PNG',f=>f.cp.current_png_sha256=null],
  ['missing prior full PNG',f=>f.cp.previous_images=[]],
  ['changed history',f=>f.cp.session_controls[0].frame=0],
  ['changed full MT state',f=>f.cp.rng_state[1][0]=124],
  ['changed MT index',f=>f.cp.rng_mt_index=0],
  ['changed draw count',f=>f.cp.rng_draw_count=0],
  ['unanswered resend',f=>{f.slot.continuation_mode='unanswered_no_resend';f.slot.unmatched_ledger_intent_count=1;}],
  ['forged native grade',f=>{f.child.progress_pct=99;f.logical.progress_pct=99;}],
  ['extra native budget',f=>f.proof.total_native_frame_budget=6294],
  ['child-only attempt scope',f=>f.child.attempt_proof.request_intent_count=1],
  ['duplicate resolution',f=>f.cohort.technical_recovery.resolutions.push(structuredClone(f.resolution))],
  ['extra RNG at inherited boundary',f=>f.proof.inherited_parent_valid_choice_count=1],
])test(`image recovery rejects ${name}`,async()=>{const parsed=await prepareImageRecovery(imageRecoveryFixture(),change);assert.equal(parsed.commonBenchmark.technicalRecovery?.resolved??0,0);assert.equal(parsed.commonBenchmark.rows[0].meanProgressPct,null);});
test('new image child infrastructure failure keeps original mean pending',async()=>{
  const f=imageRecoveryFixture();f.cohort.technical_recovery.resolutions=[];
  Object.assign(f.child,{status:'infra_error',rankable:false,technical_pending:true});const parsed=await prepareImageRecovery(f);
  assert.equal(parsed.commonBenchmark.technicalRecovery?.resolved,0);assert.equal(parsed.commonBenchmark.rows[0].meanProgressPct,null);
});

test('image recovery cannot promote an unfinished 47-trial cutoff',async()=>{
  const f=imageRecoveryFixture();f.cohort.trials.pop();const parsed=await prepareImageRecovery(f);assert.equal(parsed.commonBenchmark.technicalRecovery,null);
});
test('unmatched original request remains pending without a resend or a false score',async()=>{
  const f=imageRecoveryFixture();f.slot.continuation_mode='unanswered_no_resend';f.slot.parent_http_attempts=56;f.slot.unmatched_ledger_intent_count=1;f.slot.provider_outcome_unknown_attempt_count=1;
  f.original.attempt_proof.request_intent_count=56;f.original.attempt_proof.unanswered_attempt_count=1;f.authority.provider_outcome_unknown_attempt_count=1;
  f.cohort.technical_recovery.continuations=[];f.cohort.technical_recovery.resolutions=[];
  const parsed=await prepareImageRecovery(f);assert.equal(parsed.commonBenchmark.technicalRecovery?.planned,1);assert.equal(parsed.commonBenchmark.technicalRecovery?.resolved,0);assert.equal(parsed.commonBenchmark.rows[0].meanProgressPct,null);
});
test('image continuation never publishes child-only billing as total spend',async()=>{
  const f=imageRecoveryFixture();f.logical.cost_usd=.01;f.logical.cost_provenance={...billing,joined_attempt_count:1};
  const parsed=await prepareImageRecovery(f);assert.equal(parsed.commonBenchmark.technicalRecovery?.resolved,1);assert.equal(parsed.observations.find(r=>r.id===f.original.id).costUsd,null);
});
test('complete joined image billing retains a verified actual cost',async()=>{
  const f=imageRecoveryFixture();f.logical.cost_usd=.07;f.logical.cost_provenance={...billing,joined_attempt_count:56,request_count:56,costed_request_count:56,actual_costed_request_count:56,source_request_count:56,source_attempt_count:56,error_count:13};
  const parsed=await prepareImageRecovery(f);assert.equal(parsed.commonBenchmark.technicalRecovery?.resolved,1);assert.equal(parsed.observations.find(r=>r.id===f.original.id).costUsd,.07);
});
test('unknown original provider outcome masks both exact and estimated joined billing',async()=>{
  const f=imageRecoveryFixture();f.slot.provider_outcome_unknown_attempt_count=1;f.authority.provider_outcome_unknown_attempt_count=1;f.proof.provider_outcome_unknown_attempt_count=1;f.proof.total_provider_outcome_unknown_attempt_count=1;
  f.logical.cost_usd=.07;f.logical.cost_estimate_usd=.08;f.logical.cost_provenance={...billing,joined_attempt_count:56,request_count:56,costed_request_count:56,actual_costed_request_count:56,source_request_count:56,source_attempt_count:56,error_count:13};
  const parsed=await prepareImageRecovery(f);const run=parsed.observations.find(r=>r.id===f.original.id);assert.equal(run.costUsd,null);assert.equal(run.costEstimateUsd,null);
});

test('composed image progress cannot discard the original valid prefix maximum',async()=>{
  const f=imageRecoveryFixture();for(const record of [f.child,f.logical,f.proof.result]){record.max_progress_x=200;record.progress_pct=5;}
  const parsed=await prepareImageRecovery(f);assert.equal(parsed.commonBenchmark.technicalRecovery?.resolved,0);assert.equal(parsed.commonBenchmark.rows[0].meanProgressPct,null);
});

test('image recovery disclosure uses its own dynamic planned and resolved counts',async()=>{
  const image=imageRecoveryFixture();image.cohort.technical_recovery.continuations=[];image.cohort.technical_recovery.resolutions=[];
  await prepareImageRecovery(image);
  const state=recoveryFixture();await prepareRecovery(state);state.data.common_image_benchmark=image.cohort;
  const parsed=parseDataset(state.data);assert.equal(parsed.commonBenchmarks.length,2);
  assert.equal(parsed.commonBenchmarks[1].technicalRecovery.planned,1);assert.equal(parsed.commonBenchmarks[1].technicalRecovery.resolved,0);
  const readme=renderResults(state.data);assert.match(readme,/1\/8 technical interruptions resolved/);assert.match(readme,/pixels: 0\/1 technical interruptions resolved/);
});

function terminalImageFixture() {
  const f=imageRecoveryFixture();f.cohort.technical_recovery.resolutions=[];
  Object.assign(f.child,{status:'infra_error',rankable:false,technical_pending:true,progress_pct:null,death:false,cost_usd:null,cost_estimate_usd:null});
  Object.assign(f.child.attempt_proof,{request_intent_count:59,request_result_count:59,error_attempt_count:16,terminal_at_utc:'2026-01-06T00:00:00Z'});
  Object.assign(f.proof,{recovery_attempt_count:4,joined_attempt_count:59,recovery_request_result_count:4,joined_request_result_count:59,recovery_error_attempt_count:3,joined_error_attempt_count:16});
  f.proof.result=structuredClone(f.child);
  return f;
}
test('proved closed image technical continuation is unavailable without a resolution or score',async()=>{
  const f=terminalImageFixture(),original=JSON.stringify(f.cohort.trials),parsed=await prepareImageRecovery(f),row=parsed.commonBenchmark.rows[0];
  assert.equal(row.availability,'unavailable');assert.equal(row.meanProgressPct,null);assert.equal(row.bestClearSeconds,null);assert.equal(row.meanCostUsd,null);
  assert.equal(parsed.commonBenchmark.technicalRecovery.resolved,0);assert.equal(parsed.commonBenchmark.trials.length,48);assert.equal(f.cohort.technical_recovery.resolutions.length,0);
  assert.equal(JSON.stringify(f.cohort.trials),original);assert.equal(parsed.observations.length,parseDataset(legacy).observations.length+48);assert.match(renderResults(f.data),/unavailable \|/);
});
for(const [name,change] of [
  ['missing terminal timestamp',f=>delete f.child.attempt_proof.terminal_at_utc],
  ['unanswered child request',f=>f.child.attempt_proof.unanswered_attempt_count=1],
  ['mismatched whole-prefix grade',f=>f.proof.result.native_frames=302],
  ['wrong closed source',f=>f.proof.child_episode_sha256=hash],
  ['changed full RNG prefix',f=>f.cp.rng_state[1][0]=456],
  ['wrong joined attempts',f=>f.proof.joined_attempt_count=4],
  ['unverified native result',f=>f.proof.verified=false],
  ['unproved completion',f=>f.child.flag_get=true],
])test(`closed image mean stays pending with ${name}`,async()=>{const parsed=await prepareImageRecovery(terminalImageFixture(),change);assert.equal(parsed.commonBenchmark.rows[0].availability,'pending');assert.equal(parsed.commonBenchmark.rows[0].meanProgressPct,null);});

test('only proved closed image continuations expose trace proof and optional replay links',async()=>{
  const f=terminalImageFixture();f.child.replay_href='image-recovery/replays/closed.mp4';f.child.replay_sha256=hash;
  const parsed=await prepareImageRecovery(f),row=parsed.commonBenchmark.rows[0];assert.deepEqual(row.technicalEvidence,[{originalTrialId:f.original.id,childRunId:f.child.id,traceHref:f.child.trace_href,proofHref:f.child.proof_href,replayHref:f.child.replay_href}]);
  assert.match(renderResults(f.data),/technical replay/);assert.equal(parsed.observations.some(r=>r.id===f.child.id),false);
});
test('unproved terminal image claims expose no continuation evidence',async()=>{
  const parsed=await prepareImageRecovery(terminalImageFixture(),f=>f.proof.verified=false);assert.deepEqual(parsed.commonBenchmark.rows[0].technicalEvidence,[]);
});
test('unsafe optional terminal replay paths are never exposed',async()=>{
  const f=terminalImageFixture();f.child.replay_href='https://example.test/not-proof.mp4';f.child.replay_sha256=hash;const parsed=await prepareImageRecovery(f);
  assert.equal(parsed.commonBenchmark.rows[0].availability,'unavailable');assert.equal(parsed.commonBenchmark.rows[0].technicalEvidence[0].replayHref,null);
});
