/** Image continuations retain the original 48-slot evaluation identity. */
import type { RecoverySummary } from './recovery-lineage.ts';
type Raw = Record<string, unknown>;
const obj = (v: unknown): Raw | null => v !== null && typeof v === 'object' && !Array.isArray(v) ? v as Raw : null;
const rows = (v: unknown): Raw[] => Array.isArray(v) ? v.map(obj).filter((x): x is Raw => x !== null) : [];
const str = (v: unknown) => typeof v === 'string' ? v : '';
const int = (v: unknown) => Number.isInteger(v) ? v as number : -1;
const sha = (v: unknown) => /^[a-f0-9]{64}$/.test(str(v));
const href = (v: unknown): v is string => !!str(v) && !str(v).startsWith('/') && !str(v).includes(':') && !str(v).split('/').includes('..');
const canonical = (v: unknown): string => JSON.stringify(v && typeof v === 'object' && !Array.isArray(v)
  ? Object.fromEntries(Object.entries(v).sort(([a], [b]) => a.localeCompare(b)).map(([k, x]) => [k, JSON.parse(canonical(x))]))
  : Array.isArray(v) ? v.map(x => JSON.parse(canonical(x))) : v);
const same = (a: unknown, b: unknown) => canonical(a) === canonical(b);
const cleanCheckpoint = ({_computed_rng_state_sha256,_computed_session_controls_sha256,...value}:Raw)=>value;
const cleanSlot = ({_computed_pin_sha256,...slot}:Raw)=>({...slot,checkpoint:cleanCheckpoint(obj(slot.checkpoint)??{})});
const parent = '2f11c42b8d47f8cd8959e828243acacb8abcf83c478a6206508ebd635004fdf1';
const checks = ['prefix_replay_verified','failed_body_identical','controller_pin_history_rng_verified','total_native_budget_verified'];
const gradeKeys = ['model_id','track','level','repeat_id','local_rng_seed','temperature','emulator_seed','native_frame_budget','life_budget','cadence_native_frames',
  'status','rankable','technical_pending','completed','flag_get','death','native_frames','frames','decisions','continuation_native_frames','continuation_decisions',
  'native_frames_to_completion','start_x','max_progress_x','progress_pct','native_replay_verified','started_at_utc','checkpoint','reconstructed_checkpoint',
  'phase','protocol_sha256','parent_protocol_sha256','resolves_original_trial_id','parent_episode_sha256'];
const metricKeys = [...gradeKeys.filter(k => !['protocol_sha256','resolves_original_trial_id'].includes(k)), 'returned_model','provider','trace_href','trace_sha256','replay_href','replay_sha256','profile_href'];

export function resolveImageRecovery(cohort: Raw, originals: Raw[], imageOnly: boolean, validOutcome: (trial: Raw) => boolean) {
  const effective = new Map<string, Raw>();
  const none = { effective, summary: null as RecoverySummary | null };
  const overlay = obj(cohort.technical_recovery), authority = obj(overlay?.manifest), base = obj(cohort.manifest);
  if (!imageOnly || !overlay || !authority || base?.protocol_sha256 !== parent || originals.length !== 48
    || new Set(originals.map(t => t.id)).size !== 48) return none;
  const prefix = obj(authority._verified_prefix_proof), source = obj(prefix?.source_log_sha256), provenance = obj(cohort.release_provenance);
  const frozen = Date.parse(str(authority.frozen_at_utc));
  if (authority.protocol_id !== 'mario-image-technical-recovery-v1' || authority.acceptance_mode !== 'same_checkpoint_technical_recovery_v1'
    || authority.phase !== 'technical_recovery' || authority.preregistered !== true || !sha(authority.protocol_sha256)
    || authority.protocol_sha256 === parent || authority.parent_protocol_sha256 !== parent || !Number.isFinite(frozen)
    || authority.parent_manifest_file_sha256 !== provenance?.source_manifest_sha256 || !sha(authority.parent_manifest_file_sha256)
    || !sha(authority.parent_audit_sha256) || !sha(authority.prefix_proof_sha256) || !href(authority.prefix_proof_href)
    || authority._verified_prefix_proof_sha256 !== authority.prefix_proof_sha256 || prefix?.verified !== true || prefix.parent_protocol_sha256 !== parent
    || !source || Object.keys(source).length !== 48 || !same(authority.tracks,['image']) || authority.native_frame_budget !== 6000
    || authority.native_frame_cap !== 6000 || authority.cadence_native_frames !== 7 || authority.requested_native_hold !== 7
    || authority.life_budget !== 1 || authority.temperature !== .05 || authority.provider_seed !== null || authority.emulator_seed !== 0
    || authority.max_continuations_per_slot !== 1 || authority.retries_after_initial !== 2) return none;
  const slots = rows(authority.slots), aborted = originals.filter(t => t.rankable !== true);
  const children = rows(overlay.continuations), resolutions = rows(overlay.resolutions);
  if (!slots.length || slots.length !== aborted.length || new Set(slots.map(s=>s.original_trial_id)).size !== slots.length
    || new Set(slots.map(s=>s.child_run_id)).size !== slots.length || !same(prefix.slots, slots.map(cleanSlot))
    || new Set(children.map(c=>c.id)).size !== children.length || new Set(resolutions.map(r=>r.original_trial_id)).size !== resolutions.length
    || children.some(c=>!slots.some(s=>s.child_run_id===c.id))
    || resolutions.some(r=>!slots.some(s=>s.original_trial_id===r.original_trial_id&&s.child_run_id===r.child_run_id))) return none;
  for (const original of originals) {
    const attempt = obj(original.attempt_proof), terminal = Date.parse(str(attempt?.terminal_at_utc));
    if (!attempt || source[str(original.id)] !== attempt.source_episode_sha256 || !sha(attempt.source_episode_sha256)
      || !sha(attempt.native_audit_sha256) || original.native_replay_verified !== true || !Number.isFinite(terminal) || terminal > frozen
      || int(attempt.request_intent_count) < 1 || int(attempt.request_result_count) < 0 || int(attempt.error_attempt_count) < 0
      || int(attempt.unanswered_attempt_count) < 0 || int(attempt.error_attempt_count)>int(attempt.request_result_count)
      || (original.rankable===true&&(!validOutcome(original)||attempt.unanswered_attempt_count!==0||int(attempt.request_result_count)-int(attempt.error_attempt_count)!==original.decisions))
      || int(attempt.request_intent_count)-int(attempt.request_result_count)!==attempt.unanswered_attempt_count) return none;
  }
  const schedule = rows(base.repeat_schedule), pairs = rows(base.eligible_model_provider_pairs);
  let unknown = 0;
  for (const slot of slots) {
    const original = originals.find(t=>t.id===slot.original_trial_id), cp = obj(slot.checkpoint), payload = obj(slot.pin_payload);
    const prescribed = schedule.find(s=>s.episode_id===slot.original_trial_id), pair = pairs.find(p=>p.model_id===slot.model_id&&p.track==='image');
    const attempt = obj(original?.attempt_proof), controls = rows(cp?.session_controls), previous = rows(cp?.previous_images);
    const rng = cp?.rng_state, state = Array.isArray(rng) && Array.isArray(rng[1]) ? rng[1] : [];
    const actions = int(slot.parent_valid_native_actions), frame = int(cp?.checkpoint_native_frame), mode = slot.continuation_mode;
    const inherited = mode === 'reuse_recorded_valid_response' ? 1 : 0;
    if (!original || !cp || !payload || !pair || !prescribed || !attempt || !aborted.includes(original)
      || original.status !== 'infra_error' || original.technical_pending !== true || original.rankable !== false
      || original.flag_get !== false || original.death !== false || original.phase !== 'evaluation' || original.protocol_sha256 !== parent
      || slot.parent_abort_status !== 'infra_error' || slot.parent_episode_sha256 !== attempt.source_episode_sha256
      || slot.child_run_id !== str(original.id)+'--image-technical-recovery-v1' || originals.some(t=>t.id===slot.child_run_id)
      || ['model_id','track','repeat_id','temperature','emulator_seed','local_rng_seed'].some(k=>!same(slot[k],original[k])||!same(slot[k],prescribed[k]))
      || original.level !== '1-1' || slot.track !== 'image' || slot.temperature !== .05 || slot.emulator_seed !== 0
      || slot.local_rng_seed !== 101+int(slot.repeat_id) || slot.failed_stage !== 'motor' || slot.failed_decision_index !== actions
      || actions < 0 || original.decisions !== actions || frame !== actions*7 || original.native_frames !== frame || frame < 0 || frame >= 6000
      || original.native_frame_budget !== 6000 || original.life_budget !== 1 || original.cadence_native_frames !== 7
      || slot.remaining_native_frame_budget !== 6000-frame || slot.parent_http_attempts !== attempt.request_intent_count
      || !['fresh_after_observed_failures','reuse_recorded_valid_response','unanswered_no_resend'].includes(str(mode))
      || int(slot.failed_attempt_chain)<1 || int(slot.failed_attempt_chain)>3
      || (mode==='fresh_after_observed_failures'&&slot.failed_attempt_chain!==3)
      || slot.unmatched_ledger_intent_count !== attempt.unanswered_attempt_count
      || (mode==='unanswered_no_resend' ? int(slot.unmatched_ledger_intent_count)!==1 : slot.unmatched_ledger_intent_count!==0)
      || int(attempt.request_result_count)-int(attempt.error_attempt_count)!==actions+inherited
      || int(slot.provider_outcome_unknown_attempt_count)<int(attempt.unanswered_attempt_count)
      || int(slot.provider_outcome_unknown_attempt_count)>int(attempt.error_attempt_count)+int(attempt.unanswered_attempt_count)
      || slot.no_observed_valid_choice_discarded !== true
      || ['checkpoint_ram_sha256','checkpoint_rgb_sha256','checkpoint_observation_sha256','controller_history_sha256','session_controls_sha256',
        'current_png_sha256','failed_request_sha256','controller_sha256','pin_sha256','rng_state_sha256'].some(k=>!sha(cp[k]))
      || cp.controller_sha256 !== obj(base.observation_and_controller_hashes)?.image_controller_sha256
      || slot._computed_pin_sha256 !== cp.pin_sha256 || payload.id !== pair.model_id || (payload.request_model??payload.id)!==pair.request_model
      || payload.expected_returned_model!==pair.expected_returned_model || !same(payload.provider,pair.provider)
      || !same(payload.expected_returned_provider_names,pair.expected_returned_provider_names)
      || cp._computed_rng_state_sha256 !== cp.rng_state_sha256 || cp._computed_session_controls_sha256 !== cp.session_controls_sha256
      || cp.rng_mode !== 'global_full12_temperature_sampling' || cp.rng_draw_count !== actions || !Array.isArray(rng)
      || rng.length!==3 || rng[0]!==3 || rng[2]!==null || state.length!==625
      || state.slice(0,-1).some(n=>!Number.isInteger(n)||n<0||n>4294967295)
      || cp.rng_mt_index!==state[624] || cp.rng_mt_index!==(actions===0?624:((actions*2-1)%624)+1)
      || controls.length!==Math.min(2,actions) || controls.some((c,index)=>c.frame!==frame-(controls.length-index)*7||c.frames!==7||!obj(c.buttons))
      || previous.length!==Math.min(1,actions) || previous.some(p=>p.frame!==frame-7||!sha(p.png_sha256))
      || (inherited ? !sha(slot.inherited_parent_valid_response_sha256)||!sha(slot.inherited_parent_receipt_id_sha256)
        : slot.inherited_parent_valid_response_sha256!=null||slot.inherited_parent_receipt_id_sha256!=null)) return none;
    unknown+=int(slot.provider_outcome_unknown_attempt_count);
  }
  if (unknown!==authority.provider_outcome_unknown_attempt_count) return none;
  for (const resolution of resolutions) {
    const slot = slots.find(s=>s.original_trial_id===resolution.original_trial_id)!;
    const original = originals.find(t=>t.id===slot.original_trial_id)!, child = children.find(c=>c.id===slot.child_run_id);
    const logical = obj(resolution.effective_trial), proof = obj(resolution.proof), grade = obj(proof?.result);
    const attempt = obj(child?.attempt_proof), old = obj(original.attempt_proof)!;
    const pair = pairs.find(p=>p.model_id===slot.model_id&&p.track==='image')!;
    const cp = obj(slot.checkpoint)!;
    if (!child||!logical||!proof||!grade||!attempt||slot.continuation_mode==='unanswered_no_resend'
      || child.phase!=='technical_recovery'||child.record_kind!=='technical_continuation'||child.protocol_sha256!==authority.protocol_sha256
      || child.parent_protocol_sha256!==parent||child.resolves_original_trial_id!==original.id||child.parent_episode_sha256!==slot.parent_episode_sha256
      || ['model_id','track','repeat_id','local_rng_seed','temperature','emulator_seed'].some(k=>!same(child[k],slot[k]))
      || child.level!=='1-1'||child.start_x!==40||!Number.isFinite(child.max_progress_x)||!Number.isFinite(original.max_progress_x)
      ||Number(child.max_progress_x)<Number(original.max_progress_x)||child.native_frame_budget!==6000||child.life_budget!==1||child.cadence_native_frames!==7
      || child.returned_model!==pair.expected_returned_model||!Array.isArray(pair.expected_returned_provider_names)||!pair.expected_returned_provider_names.includes(child.provider)
      || (child.request_model!==undefined&&child.request_model!==pair.request_model)||!validOutcome(child)
      || !['completed','game_over','frame_budget'].includes(str(child.status))
      || !Number.isFinite(Date.parse(str(child.started_at_utc)))||Date.parse(str(child.started_at_utc))<frozen
      || !same(child.checkpoint,cleanCheckpoint(cp))||!same(child.reconstructed_checkpoint,cleanCheckpoint(cp))
      || proof.schema_version!==1||proof.verified!==true||proof.pending_unexecuted===true
      || resolution.proof_verified_sha256!==resolution.proof_sha256||!sha(resolution.proof_sha256)||!href(resolution.proof_href)
      || proof.original_trial_id!==original.id||proof.child_run_id!==child.id||proof.parent_protocol_sha256!==parent||proof.recovery_protocol_sha256!==authority.protocol_sha256
      || resolution.parent_episode_sha256!==slot.parent_episode_sha256||proof.parent_episode_sha256!==slot.parent_episode_sha256
      || resolution.child_episode_sha256!==attempt.source_episode_sha256||proof.child_episode_sha256!==attempt.source_episode_sha256
      || !sha(attempt.source_episode_sha256)||attempt.native_audit_sha256!==resolution.proof_sha256
      || checks.some(k=>resolution[k]!==true||proof[k]!==true)||proof.no_observed_valid_choice_discarded!==true
      || !same(proof.declared_checkpoint,cleanCheckpoint(cp))||!same(proof.reconstructed_checkpoint,cleanCheckpoint(cp))
      || gradeKeys.some(k=>!Object.hasOwn(grade,k)||!same(grade[k],child[k]))
      || proof.total_native_frame_budget!==6000||proof.total_native_frames!==child.native_frames||int(child.native_frames)<=int(cp.checkpoint_native_frame)
      || proof.new_native_frames!==child.continuation_native_frames||int(child.native_frames)-int(cp.checkpoint_native_frame)!==child.continuation_native_frames
      || logical.id!==original.id||logical.logical_trial_id!==original.id||logical.source_run_id!==child.id||logical.record_kind!=='technical_resolution'
      || logical.phase!=='technical_recovery'||logical.protocol_sha256!==authority.protocol_sha256||logical.base_protocol_sha256!==parent
      || metricKeys.some(k=>!same(logical[k],child[k]))||!href(child.trace_href)||!sha(child.trace_sha256)||!href(original.trace_href)) continue;
    const oldCount=int(old.request_intent_count), newCount=int(proof.recovery_attempt_count), joined=oldCount+newCount;
    const inherited=slot.continuation_mode==='reuse_recorded_valid_response'?1:0;
    const oldErrors=int(old.error_attempt_count), newErrors=int(proof.recovery_error_attempt_count), errors=oldErrors+newErrors;
    const unknownNew=int(proof.new_provider_outcome_unknown_attempt_count), unknownTotal=int(slot.provider_outcome_unknown_attempt_count)+unknownNew;
    if(newCount<0||newErrors<0||newErrors>newCount||(!inherited&&newCount<1)||proof.inherited_parent_valid_choice_count!==inherited
      || ['inherited_parent_valid_response_sha256','inherited_parent_receipt_id_sha256'].some(k=>!same(proof[k]??null,slot[k]??null))
      || proof.original_attempt_count!==oldCount||proof.joined_attempt_count!==joined||proof.original_error_attempt_count!==oldErrors||proof.joined_error_attempt_count!==errors
      || proof.original_request_result_count!==old.request_result_count||proof.recovery_request_result_count!==newCount||proof.joined_request_result_count!==joined
      || proof.original_unanswered_attempt_count!==0||proof.recovery_unanswered_attempt_count!==0||proof.joined_unanswered_attempt_count!==0
      || attempt.scope!=='composed_trajectory'||attempt.request_intent_count!==joined||attempt.request_result_count!==joined||attempt.error_attempt_count!==errors||attempt.unanswered_attempt_count!==0
      || joined-errors!==child.decisions||newCount-newErrors+inherited!==child.continuation_decisions
      || child.continuation_decisions!==int(child.decisions)-int(original.decisions)
      || proof.provider_outcome_unknown_attempt_count!==slot.provider_outcome_unknown_attempt_count||unknownNew<0||unknownNew>newErrors
      || proof.total_provider_outcome_unknown_attempt_count!==unknownTotal)continue;
    const projected:Raw={...logical},billing=obj(projected.cost_provenance);
    if(!billing||billing.joined_attempt_count!==joined||['request_count','source_request_count','source_attempt_count'].some(k=>billing[k]!==joined)
      ||billing.error_count!==errors||unknownTotal!==0){
      for(const k of ['cost_usd','cost_estimate_usd','openrouter_cost_usd','upstream_cost_usd','upstream_cost_estimate_usd'])projected[k]=null;
      projected.cost_provenance=billing?{...billing,coverage_complete:false}:null;
    }
    projected.recovery_lineage={childRunId:child.id,originalTraceHref:original.trace_href,childTraceHref:child.trace_href,proofHref:resolution.proof_href};
    effective.set(str(original.id),projected);
  }
  return {effective,summary:{protocolSha256:str(authority.protocol_sha256),planned:slots.length,resolved:effective.size,originalUnknownProviderAttempts:unknown}};
}
