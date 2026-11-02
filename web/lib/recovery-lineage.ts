/** Optional, separately registered continuations; never additional quality trials. */
type Raw = Record<string, unknown>;
export type RecoveryLineage = { childRunId: string; originalTraceHref: string; childTraceHref: string; proofHref: string };
export type RecoverySummary = { protocolSha256: string; planned: number; resolved: number; originalUnknownProviderAttempts: number };
const obj = (v: unknown): Raw | null => v !== null && typeof v === 'object' && !Array.isArray(v) ? v as Raw : null;
const rows = (v: unknown) => Array.isArray(v) ? v.map(obj).filter((x): x is Raw => x !== null) : [];
const str = (v: unknown) => typeof v === 'string' ? v : '';
const int = (v: unknown) => Number.isInteger(v) ? v as number : -1;
const sha = (v: unknown) => /^[a-f0-9]{64}$/.test(str(v));
const href = (v: unknown): v is string => typeof v === 'string' && !!v && !v.startsWith('/') && !v.includes(':') && !v.split('/').includes('..');
const canonical = (v: unknown): string => JSON.stringify(v && typeof v === 'object' && !Array.isArray(v)
  ? Object.fromEntries(Object.entries(v).sort(([a], [b]) => a.localeCompare(b)).map(([k, x]) => [k, JSON.parse(canonical(x))]))
  : Array.isArray(v) ? v.map(x => JSON.parse(canonical(x))) : v);
const same = (a: unknown, b: unknown) => canonical(a) === canonical(b);
const parentProtocol = 'e1c1086b8dc2d5613deaad37cbc75003dedaf7564cf82802a17b0e81fcdb8371';
const checkpointKeys = ['checkpoint_native_frame', 'checkpoint_ram_sha256', 'checkpoint_rgb_sha256', 'checkpoint_observation_sha256',
  'controller_history_sha256', 'failed_request_sha256', 'controller_sha256', 'pin_sha256', 'rng_mode', 'rng_state_sha256'];
const metricKeys = ['model_id', 'track', 'repeat_id', 'local_rng_seed', 'emulator_seed', 'temperature', 'native_frame_budget', 'life_budget',
  'native_frames', 'decisions', 'status', 'rankable', 'technical_pending', 'native_replay_verified', 'progress_pct', 'max_progress_x',
  'flag_get', 'completed', 'death', 'native_frames_to_completion', 'returned_model', 'provider', 'level', 'start_x', 'started_at_utc',
  'frames', 'cadence_native_frames', 'continuation_native_frames', 'continuation_decisions'];
const gradeKeys = ['native_frames', 'level', 'start_x', 'started_at_utc', 'status', 'rankable', 'progress_pct', 'max_progress_x', 'flag_get',
  'completed', 'death', 'native_frames_to_completion', 'decisions', 'native_frame_budget', 'life_budget', 'cadence_native_frames', 'repeat_id',
  'local_rng_seed', 'emulator_seed', 'temperature', 'model_id', 'track', 'phase', 'protocol_sha256', 'parent_protocol_sha256',
  'resolves_original_trial_id', 'parent_episode_sha256', 'checkpoint', 'reconstructed_checkpoint', 'native_replay_verified',
  'continuation_native_frames', 'continuation_decisions'];
const checks = ['prefix_replay_verified', 'failed_body_identical', 'controller_pin_history_rng_verified', 'total_native_budget_verified'];

export function resolveTechnicalRecovery(cohort: Raw, originals: Raw[], stateOnly: boolean, validOutcome: (trial: Raw) => boolean) {
  const effective = new Map<string, Raw>();
  const none = { effective, summary: null as RecoverySummary | null };
  const overlay = obj(cohort.technical_recovery), authority = obj(overlay?.manifest), base = obj(cohort.manifest);
  if (!overlay || !authority || !base || !stateOnly || base.protocol_sha256 !== parentProtocol
    || originals.length !== 66 || new Set(originals.map(t => t.id)).size !== 66) return none;
  const frozen = Date.parse(str(authority.frozen_at_utc));
  const provenance = obj(cohort.release_provenance);
  if (authority.protocol_id !== 'mario-state-technical-recovery-v1' || authority.phase !== 'technical_recovery'
    || authority.preregistered !== true || !sha(authority.protocol_sha256) || authority.protocol_sha256 === parentProtocol
    || authority.parent_protocol_sha256 !== parentProtocol || !Number.isFinite(frozen)
    || authority.parent_manifest_file_sha256 !== provenance?.source_manifest_sha256
    || !sha(authority.parent_manifest_file_sha256) || !sha(authority.parent_audit_sha256) || !sha(authority.prefix_proof_sha256)
    || !same(authority.tracks, ['state']) || authority.native_frame_budget !== 6000 || authority.native_frame_cap !== 6000
    || authority.cadence_native_frames !== 4 || authority.life_budget !== 1 || authority.retries_after_initial !== 2
    || authority.max_continuations_per_slot !== 1 || authority.provider_seed !== null || authority.emulator_seed !== 0
    || authority.provider_outcome_unknown_attempt_count !== 5) return none;
  const slots = rows(authority.slots), children = rows(overlay.continuations), resolutions = rows(overlay.resolutions);
  const aborted = originals.filter(t => t.rankable !== true);
  if (slots.length !== 8 || aborted.length !== 8 || new Set(slots.map(s => s.original_trial_id)).size !== 8
    || new Set(slots.map(s => s.child_run_id)).size !== 8
    || !slots.every(s => aborted.some(t => t.id === s.original_trial_id))) return none;
  const schedule = rows(base.repeat_schedule), pairs = rows(base.eligible_model_provider_pairs);
  const controller = obj(base.observation_and_controller_hashes)?.state_controller_sha256;
  let unknown = 0;
  const kinds = { timeout_then_socket_gaierror_dns: 0, socket_gaierror_dns: 0, typed_service_429: 0 };
  for (const slot of slots) {
    const original = originals.find(t => t.id === slot.original_trial_id)!, attempt = obj(original.attempt_proof);
    const prescribed = schedule.find(t => t.episode_id === original.id), pin = pairs.find(p => p.model_id === original.model_id && p.track === 'state');
    const payload = obj(slot.pin_payload), frame = int(slot.checkpoint_native_frame), actions = int(original.decisions);
    const chain = rows(slot.failed_attempt_chain), terminal = chain.at(-1);
    const timeoutCount = chain.filter(a => a.error === 'TimeoutError').length;
    if (!prescribed || !pin || !payload || !attempt || original.status !== 'infra_error' || original.rankable !== false
      || original.model_id !== prescribed.model_id || original.track !== 'state' || original.repeat_id !== prescribed.repeat_id
      || original.local_rng_seed !== null || original.emulator_seed !== 0 || original.temperature !== null
      || original.level !== '1-1' || original.native_frame_budget !== 6000 || original.life_budget !== 1
      || original.technical_pending !== true || original.flag_get !== false || original.death !== false
      || original.phase !== 'evaluation' || original.protocol_sha256 !== parentProtocol
      || slot.parent_abort_status !== original.status || slot.parent_episode_sha256 !== attempt.source_episode_sha256
      || !sha(slot.parent_episode_sha256) || !str(slot.child_run_id) || originals.some(t => t.id === slot.child_run_id)
      || slot.model_id !== original.model_id || slot.track !== 'state' || slot.repeat_id !== original.repeat_id
      || slot.local_rng_seed !== null || slot.temperature !== null || slot.emulator_seed !== 0
      || frame < 0 || frame >= 6000 || original.native_frames !== frame || actions < 0 || frame !== actions * 4
      || slot.parent_valid_native_actions !== actions || slot.failed_decision_index !== actions || slot.failed_stage !== 'motor'
      || slot.remaining_native_frame_budget !== 6000 - frame || slot.rng_mode !== 'not_used_native_choice' || slot.rng_state_sha256 !== null
      || checkpointKeys.filter(k => k.endsWith('_sha256') && k !== 'rng_state_sha256').some(k => !sha(slot[k]))
      || slot.controller_sha256 !== controller || slot._computed_pin_sha256 !== slot.pin_sha256
      || payload.id !== pin.model_id || (payload.request_model ?? payload.id) !== pin.request_model
      || payload.expected_returned_model !== pin.expected_returned_model
      || !same(payload.provider, pin.provider) || !same(payload.expected_returned_provider_names, pin.expected_returned_provider_names)
      || slot.no_observed_valid_choice_discarded !== true || slot.unmatched_ledger_intent_count !== 0
      || attempt.unanswered_attempt_count !== 0 || attempt.request_intent_count !== attempt.request_result_count
      || slot.parent_http_attempts !== attempt.request_intent_count
      || int(attempt.request_result_count) - int(attempt.error_attempt_count) !== actions
      || !Number.isFinite(Date.parse(str(attempt.terminal_at_utc))) || Date.parse(str(attempt.terminal_at_utc)) > frozen
      || chain.length < 1 || chain.length > 3 || chain.some(a => a.request_sha256 !== slot.failed_request_sha256
        || a.valid !== false || a.native_answers_present !== false || a.retryable !== true)
      || !terminal || int(slot.provider_outcome_unknown_attempt_count) < timeoutCount) return none;
    const kind = str(slot.failure_kind) as keyof typeof kinds;
    if (!Object.hasOwn(kinds, kind)) return none;
    kinds[kind]++; unknown += int(slot.provider_outcome_unknown_attempt_count);
    if (kind === 'typed_service_429') {
      if (terminal.http_status !== 429 || terminal.raw_response_present !== true) return none;
    } else if (terminal.error !== 'gaierror' || terminal.error_type !== 'transport' || terminal.http_status !== null
      || terminal.raw_response_present !== false || (kind === 'timeout_then_socket_gaierror_dns' ? timeoutCount < 1 : timeoutCount !== 0)) return none;
  }
  if (unknown !== 5 || kinds.timeout_then_socket_gaierror_dns !== 5 || kinds.socket_gaierror_dns !== 2 || kinds.typed_service_429 !== 1
    || new Set(children.map(c => c.id)).size !== children.length || new Set(resolutions.map(r => r.original_trial_id)).size !== resolutions.length
    || children.some(c => !slots.some(s => s.child_run_id === c.id))
    || resolutions.some(r => !slots.some(s => s.original_trial_id === r.original_trial_id && s.child_run_id === r.child_run_id))) return none;
  for (const resolution of resolutions) {
    const slot = slots.find(s => s.original_trial_id === resolution.original_trial_id)!;
    const original = originals.find(t => t.id === slot.original_trial_id)!, originalAttempt = obj(original.attempt_proof)!;
    const child = children.find(c => c.id === slot.child_run_id), logical = obj(resolution.effective_trial), proof = obj(resolution.proof);
    const childAttempt = obj(child?.attempt_proof), checkpoint = obj(child?.checkpoint), reconstructed = obj(child?.reconstructed_checkpoint);
    const declared = obj(proof?.declared_checkpoint), replayed = obj(proof?.reconstructed_checkpoint);
    const grade = obj(proof?.result);
    const pin = pairs.find(p => p.model_id === original.model_id && p.track === 'state')!;
    if (!child || !logical || !proof || !grade || !childAttempt || !checkpoint || !reconstructed || !declared || !replayed
      || child.record_kind !== 'technical_continuation' || child.phase !== 'technical_recovery'
      || child.protocol_sha256 !== authority.protocol_sha256 || child.parent_protocol_sha256 !== parentProtocol
      || child.resolves_original_trial_id !== original.id || child.parent_episode_sha256 !== slot.parent_episode_sha256
      || child.model_id !== original.model_id || child.track !== 'state' || child.repeat_id !== original.repeat_id
      || child.local_rng_seed !== null || child.temperature !== null || child.emulator_seed !== 0
      || child.native_frame_budget !== 6000 || child.cadence_native_frames !== 4 || child.life_budget !== 1
      || child.level !== '1-1' || logical.level !== '1-1' || child.start_x !== 40
      || child.returned_model !== pin.expected_returned_model || !Array.isArray(pin.expected_returned_provider_names)
      || !pin.expected_returned_provider_names.includes(child.provider)
      || (child.request_model !== undefined && child.request_model !== pin.request_model)
      || !Number.isFinite(Date.parse(str(child.started_at_utc))) || Date.parse(str(child.started_at_utc)) < frozen
      || child.rankable !== true || child.technical_pending === true || child.native_replay_verified !== true
      || !['completed', 'game_over', 'frame_budget'].includes(str(child.status)) || !validOutcome(child)
      || resolution.parent_episode_sha256 !== slot.parent_episode_sha256 || resolution.child_episode_sha256 !== childAttempt.source_episode_sha256
      || !sha(resolution.child_episode_sha256) || !sha(resolution.proof_sha256) || childAttempt.native_audit_sha256 !== resolution.proof_sha256
      || resolution.proof_verified_sha256 !== resolution.proof_sha256 || !href(resolution.proof_href)
      || !href(original.trace_href) || !href(child.trace_href)
      || checks.some(k => resolution[k] !== true || proof[k] !== true)
      || proof.schema_version !== 1 || proof.verified !== true || proof.pending_unexecuted === true
      || proof.original_trial_id !== original.id || proof.child_run_id !== child.id
      || proof.parent_protocol_sha256 !== parentProtocol || proof.recovery_protocol_sha256 !== authority.protocol_sha256
      || proof.parent_episode_sha256 !== slot.parent_episode_sha256 || proof.child_episode_sha256 !== childAttempt.source_episode_sha256
      || proof.no_observed_valid_choice_discarded !== true
      || grade.frames !== child.native_frames || gradeKeys.some(k => !Object.hasOwn(grade, k) || !same(grade[k], child[k]))
      || checkpointKeys.some(k => !same(slot[k], checkpoint[k]) || !same(checkpoint[k], reconstructed[k])
        || !same(checkpoint[k], declared[k]) || !same(checkpoint[k], replayed[k]))
      || proof.total_native_frame_budget !== 6000 || int(proof.total_native_frames) <= int(slot.checkpoint_native_frame)
      || int(proof.total_native_frames) > 6000 || proof.total_native_frames !== child.native_frames
      || proof.new_native_frames !== child.continuation_native_frames
      || proof.new_native_frames !== int(child.native_frames) - int(slot.checkpoint_native_frame)
      || logical.id !== original.id || logical.logical_trial_id !== original.id || logical.source_run_id !== child.id
      || logical.record_kind !== 'technical_resolution' || logical.phase !== 'technical_recovery'
      || logical.protocol_sha256 !== authority.protocol_sha256 || logical.base_protocol_sha256 !== parentProtocol
      || !sha(child.trace_sha256) || logical.trace_href !== child.trace_href || logical.trace_sha256 !== child.trace_sha256
      || logical.replay_href !== child.replay_href || logical.replay_sha256 !== child.replay_sha256 || logical.profile_href !== child.profile_href
      || metricKeys.some(k => !same(logical[k], child[k]))) continue;
    const oldCount = int(originalAttempt.request_intent_count), newCount = int(proof.recovery_attempt_count);
    const oldErrors = int(originalAttempt.error_attempt_count), newErrors = int(proof.recovery_error_attempt_count);
    const joined = oldCount + newCount, joinedErrors = oldErrors + newErrors;
    const oldUnknown = int(slot.provider_outcome_unknown_attempt_count), newUnknown = int(proof.new_provider_outcome_unknown_attempt_count);
    if (oldCount < 1 || newCount < 1 || proof.original_attempt_count !== oldCount
      || proof.joined_attempt_count !== joined || childAttempt.scope !== 'composed_trajectory' || childAttempt.request_intent_count !== joined
      || proof.original_error_attempt_count !== oldErrors || newErrors < 0 || newErrors > newCount || proof.joined_error_attempt_count !== joinedErrors
      || proof.original_request_result_count !== oldCount || proof.recovery_request_result_count !== newCount || proof.joined_request_result_count !== joined
      || proof.original_unanswered_attempt_count !== 0 || proof.recovery_unanswered_attempt_count !== 0 || proof.joined_unanswered_attempt_count !== 0
      || proof.provider_outcome_unknown_attempt_count !== oldUnknown
      || newUnknown < 0 || newUnknown > newErrors || proof.total_provider_outcome_unknown_attempt_count !== oldUnknown + newUnknown
      || childAttempt.unanswered_attempt_count !== 0 || childAttempt.request_result_count !== joined || childAttempt.error_attempt_count !== joinedErrors
      || joined - joinedErrors !== child.decisions || newCount - newErrors !== child.continuation_decisions
      || child.continuation_decisions !== int(child.decisions) - int(original.decisions)) continue;
    const projected: Raw = { ...logical };
    const billing = obj(projected.cost_provenance);
    const billedScope = billing && billing.joined_attempt_count === joined
      && ['request_count', 'source_request_count', 'source_attempt_count'].every(k => billing[k] === joined)
      && billing.error_count === joinedErrors
      && proof.total_provider_outcome_unknown_attempt_count === 0;
    if (!billedScope) {
      for (const k of ['cost_usd', 'cost_estimate_usd', 'openrouter_cost_usd', 'upstream_cost_usd', 'upstream_cost_estimate_usd']) projected[k] = null;
      projected.cost_provenance = billing ? { ...billing, coverage_complete: false } : null;
    }
    projected.recovery_lineage = { childRunId: str(child.id), originalTraceHref: str(original.trace_href), childTraceHref: str(child.trace_href), proofHref: resolution.proof_href } satisfies RecoveryLineage;
    effective.set(str(original.id), projected);
  }
  return { effective, summary: { protocolSha256: str(authority.protocol_sha256), planned: 8, resolved: effective.size, originalUnknownProviderAttempts: 5 } };
}

/** A closed, audited failed child exhausts its one registered continuation, without earning a score. */
export function closedTechnicalFailures(cohort: Raw, originals: Raw[], authorityValidated: boolean) {
  const exhausted = new Set<string>();
  if (!authorityValidated) return exhausted;
  const overlay = obj(cohort.technical_recovery), authority = obj(overlay?.manifest);
  if (!overlay || authority?.max_continuations_per_slot !== 1) return exhausted;
  const frozen = Date.parse(str(authority.frozen_at_utc));
  const pairs = rows(obj(cohort.manifest)?.eligible_model_provider_pairs);
  for (const child of rows(overlay.continuations)) {
    const slot = rows(authority.slots).find(s => s.child_run_id === child.id);
    const original = originals.find(t => t.id === slot?.original_trial_id), attempt = obj(child.attempt_proof);
    const proof = obj(child.proof), grade = obj(proof?.result), old = obj(original?.attempt_proof);
    const pair = pairs.find(p => p.model_id === child.model_id && p.track === child.track);
    const started = Date.parse(str(child.started_at_utc)), terminal = Date.parse(str(attempt?.terminal_at_utc));
    if (!slot || !original || !attempt || !proof || !grade || !old || !pair
      || child.status !== 'infra_error' || child.rankable !== false || child.technical_pending !== true
      || child.flag_get !== false || child.completed !== false || child.death !== false || child.progress_pct !== null || child.native_frames_to_completion !== null
      || child.native_replay_verified !== true || child.record_kind !== 'technical_continuation' || child.phase !== 'technical_recovery'
      || child.protocol_sha256 !== authority.protocol_sha256 || child.parent_protocol_sha256 !== parentProtocol
      || child.resolves_original_trial_id !== original.id || child.parent_episode_sha256 !== slot.parent_episode_sha256
      || ['model_id','track','repeat_id','local_rng_seed','temperature','emulator_seed'].some(k => !same(child[k],original[k]))
      || child.level !== '1-1' || child.native_frame_budget !== 6000 || child.life_budget !== 1 || child.cadence_native_frames !== 4
      || child.returned_model !== pair.expected_returned_model || !Array.isArray(pair.expected_returned_provider_names) || !pair.expected_returned_provider_names.includes(child.provider)
      || !Number.isFinite(started) || started < frozen || !Number.isFinite(terminal) || terminal < started
      || !sha(child.proof_sha256) || child.proof_verified_sha256 !== child.proof_sha256 || !href(child.proof_href)
      || attempt.native_audit_sha256 !== child.proof_sha256 || !sha(attempt.source_episode_sha256)
      || proof.schema_version !== 1 || proof.verified !== true || proof.pending_unexecuted === true
      || proof.original_trial_id !== original.id || proof.child_run_id !== child.id
      || proof.parent_protocol_sha256 !== parentProtocol || proof.recovery_protocol_sha256 !== authority.protocol_sha256
      || proof.parent_episode_sha256 !== slot.parent_episode_sha256 || proof.child_episode_sha256 !== attempt.source_episode_sha256
      || checks.some(k => proof[k] !== true) || proof.no_observed_valid_choice_discarded !== true
      || grade.frames !== child.native_frames || gradeKeys.some(k => !Object.hasOwn(grade,k) || !same(grade[k],child[k]))
      || grade.technical_pending !== true
      || checkpointKeys.some(k => !same(slot[k],obj(child.checkpoint)?.[k]) || !same(slot[k],obj(child.reconstructed_checkpoint)?.[k])
        || !same(slot[k],obj(proof.declared_checkpoint)?.[k]) || !same(slot[k],obj(proof.reconstructed_checkpoint)?.[k]))
      || proof.total_native_frame_budget !== 6000 || proof.total_native_frames !== child.native_frames
      || int(child.native_frames) < int(slot.checkpoint_native_frame) || int(child.native_frames) >= 6000
      || proof.new_native_frames !== int(child.native_frames)-int(slot.checkpoint_native_frame) || proof.new_native_frames !== child.continuation_native_frames
      || attempt.scope !== 'composed_trajectory' || attempt.unanswered_attempt_count !== 0 || attempt.request_intent_count !== attempt.request_result_count
      || proof.original_attempt_count !== old.request_intent_count || int(proof.recovery_attempt_count) < 1
      || proof.joined_attempt_count !== int(old.request_intent_count)+int(proof.recovery_attempt_count)
      || proof.joined_attempt_count !== attempt.request_intent_count || proof.joined_request_result_count !== attempt.request_result_count
      || proof.original_request_result_count !== old.request_result_count || proof.recovery_request_result_count !== proof.recovery_attempt_count
      || proof.original_error_attempt_count !== old.error_attempt_count || proof.joined_error_attempt_count !== int(old.error_attempt_count)+int(proof.recovery_error_attempt_count)
      || int(proof.recovery_error_attempt_count)<0 || int(proof.recovery_error_attempt_count)>int(proof.recovery_attempt_count)
      || proof.joined_error_attempt_count !== attempt.error_attempt_count || proof.original_unanswered_attempt_count!==0 || proof.recovery_unanswered_attempt_count!==0 || proof.joined_unanswered_attempt_count !== 0
      || int(attempt.request_result_count)-int(attempt.error_attempt_count) !== child.decisions
      || int(proof.recovery_request_result_count)-int(proof.recovery_error_attempt_count) !== child.continuation_decisions) continue;
    exhausted.add(str(original.id));
  }
  return exhausted;
}
