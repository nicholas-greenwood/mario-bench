/** A separate, frozen evaluation cohort. Development examples never enter a mean. */
export type CommonTrack = 'state' | 'image';
type Raw = Record<string, unknown>;
type Cost = { costUsd: number | null; costEstimateUsd: number | null };
type CostReader = (trial: Raw) => Cost;

export type CommonResult = {
  id: string;
  modelId: string;
  name: string;
  track: CommonTrack;
  expectedTrialIds: string[];
  recordedTrialIds: string[];
  validTrialIds: string[];
  validTrials: number;
  coverageComplete: boolean;
  meanProgressPct: number | null;
  bestClearSeconds: number | null;
  meanCompletedSeconds: number | null;
  nCompleted: number;
  meanCostUsd: number | null;
  meanCostEstimateUsd: number | null;
  representativeRunId: string | null;
};

export type CommonBenchmark = {
  protocolId: string;
  protocolSha256: string;
  frozenAt: string;
  rows: CommonResult[];
  trials: Raw[];
};

const object = (value: unknown): Raw | null => value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Raw : null;
const string = (value: unknown) => typeof value === 'string' ? value : '';
const number = (value: unknown) => typeof value === 'number' && Number.isFinite(value) ? value : null;
const integer = (value: unknown) => Number.isInteger(value) ? value as number : null;
const records = (value: unknown) => Array.isArray(value) ? value.map(object).filter((row): row is Raw => row !== null) : [];
const strings = (value: unknown) => Array.isArray(value) && value.every(item => typeof item === 'string') ? value as string[] : [];
const track = (value: unknown): value is CommonTrack => value === 'state' || value === 'image';
const key = (row: Raw) => `${string(row.model_id)}\u0000${string(row.track)}`;
const sameIds = (a: string[], b: string[]) => a.length === b.length && new Set(a).size === a.length && a.every(id => b.includes(id));
const safeHref = (value: unknown) => typeof value === 'string' && value.length > 0 && !value.startsWith('/') && !value.includes(':') && !value.split('/').includes('..');

function validOutcome(trial: Raw) {
  const frames = integer(trial.native_frames), progress = number(trial.progress_pct);
  if (trial.technical_pending === true || trial.rankable !== true || trial.native_replay_verified !== true || frames === null || frames < 0 || frames > 6000
    || progress === null || progress < 0 || progress > 100) return false;
  if (trial.status === 'completed') {
    return trial.flag_get === true && progress === 100 && frames > 0 && trial.native_frames_to_completion === frames;
  }
  if (trial.flag_get !== false || progress > 99.9 || trial.native_frames_to_completion != null) return false;
  if (trial.status === 'game_over') return frames > 0;
  if (trial.status === 'frame_budget') return frames === 6000;
  // A bad head or parser is technical by default, not an invented model score.
  return trial.status === 'model_contract_failure' && trial.technical_pending === false
    && trial.model_contract_failure_proven === true && safeHref(trial.failure_proof_href);
}

export function parseCommonBenchmark(value: unknown, legacyIds: Set<string>, readCost: CostReader): CommonBenchmark | null {
  const cohort = object(value), manifest = object(cohort?.manifest);
  if (!cohort || !manifest || manifest.phase !== 'evaluation' || manifest.level !== '1-1'
    || manifest.preregistered !== true
    || !string(manifest.protocol_id) || !/^[a-f0-9]{64}$/.test(string(manifest.protocol_sha256))
    || !Number.isFinite(Date.parse(string(manifest.frozen_at_utc)))) return null;
  const pilot = object(manifest.pilot_selection_evidence);
  if (!pilot || pilot.state_gate_passed !== true || pilot.selected_image_temperature_gate_passed !== true
    || ![.05, .2].includes(number(pilot.selected_temperature) ?? -1) || !safeHref(pilot.selection_href)
    || ['pilot_protocol_sha256', 'pilot_summary_sha256', 'pilot_audit_sha256'].some(field => !/^[a-f0-9]{64}$/.test(string(pilot[field])))) return null;
  const schedule = records(manifest.repeat_schedule), pairs = records(manifest.eligible_model_provider_pairs);
  if (!schedule.length || !pairs.length || !object(manifest.observation_and_controller_hashes)) return null;
  const groups = new Map<string, Raw[]>();
  const scheduledIds = new Set<string>();
  for (const entry of schedule) {
    const id = string(entry.episode_id);
    if (!string(entry.model_id) || !track(entry.track) || ![0, 1, 2].includes(integer(entry.repeat_id) ?? -1)
      || !id || scheduledIds.has(id) || legacyIds.has(id) || entry.emulator_seed !== 0) return null;
    scheduledIds.add(id);
    const group = groups.get(key(entry)) ?? [];
    group.push(entry);
    groups.set(key(entry), group);
  }
  if (pairs.length !== groups.size || new Set(pairs.map(key)).size !== pairs.length || pairs.some(pair => !groups.has(key(pair)))) return null;
  for (const group of groups.values()) {
    if (group.length !== 3 || new Set(group.map(entry => entry.repeat_id)).size !== 3) return null;
    if (group[0].track === 'state' && group.some(entry => entry.local_rng_seed !== null)) return null;
    if (group[0].track === 'image' && (group.some(entry => integer(entry.local_rng_seed) === null)
      || new Set(group.map(entry => entry.local_rng_seed)).size !== 3)) return null;
  }
  const trials = records(cohort.trials).filter(trial => string(trial.id) && !legacyIds.has(string(trial.id)) && trial.phase === 'evaluation');
  if (!trials.length) return null;
  const trialCounts = new Map<string, number>();
  for (const trial of trials) trialCounts.set(string(trial.id), (trialCounts.get(string(trial.id)) ?? 0) + 1);
  const byId = new Map(trials.map(trial => [string(trial.id), trial]));
  const rawRows = records(cohort.rows);
  const rows: CommonResult[] = [];
  for (const [groupKey, group] of groups) {
    const identity = group[0], modelId = string(identity.model_id), input = identity.track as CommonTrack;
    const declared = rawRows.filter(row => key(row) === groupKey);
    const row = declared.length === 1 ? declared[0] : {};
    const expected = [...group].sort((a, b) => (a.repeat_id as number) - (b.repeat_id as number)).map(entry => string(entry.episode_id));
    const matchingPairs = pairs.filter(entry => key(entry) === groupKey);
    const pair = matchingPairs.length === 1 ? matchingPairs[0] : undefined;
    const provider = object(pair?.provider);
    const providerNames = strings(pair?.expected_returned_provider_names);
    const pinValid = pair && string(pair.request_model) && string(pair.expected_returned_model)
      && provider?.allow_fallbacks === false && strings(provider.only).length > 0 && providerNames.length > 0;
    const matching = (trial: Raw) => {
      const prescribed = group.find(entry => entry.repeat_id === trial.repeat_id);
      const started = Date.parse(string(trial.started_at_utc));
      return pinValid && prescribed && trial.id === prescribed.episode_id && trial.model_id === modelId && trial.track === input && trial.level === '1-1'
        && trial.protocol_sha256 === manifest.protocol_sha256 && trial.emulator_seed === 0
        && trial.temperature === (input === 'image' ? pilot.selected_temperature : null)
        && trial.local_rng_seed === prescribed.local_rng_seed && trial.native_frame_budget === 6000 && trial.life_budget === 1
        && trial.returned_model === pair.expected_returned_model && providerNames.includes(string(trial.provider))
        && (trial.request_model === undefined || trial.request_model === pair.request_model)
        && Number.isFinite(started) && started >= Date.parse(string(manifest.frozen_at_utc));
    };
    const recorded = expected.filter(id => byId.has(id));
    const nativeTrials = trials.filter(trial => key(trial) === groupKey);
    const valid = recorded.map(id => byId.get(id)!).filter(trial => trialCounts.get(string(trial.id)) === 1
      && nativeTrials.filter(candidate => candidate.repeat_id === trial.repeat_id).length === 1 && matching(trial) && validOutcome(trial));
    const complete = row.expected_trials === 3 && row.coverage_complete === true && row.protocol_sha256 === manifest.protocol_sha256
      && row.level === '1-1' && expected.length === 3 && new Set(expected).size === 3 && valid.length === 3
      && new Set(valid.map(trial => trial.repeat_id)).size === 3 && nativeTrials.length === 3
      && sameIds(strings(row.expected_trial_ids), expected)
      && sameIds(strings(row.recorded_trial_ids), expected);
    const completed = valid.filter(trial => trial.flag_get === true).sort((a, b) => (a.native_frames_to_completion as number) - (b.native_frames_to_completion as number));
    const representative = completed[0] ?? [...valid].sort((a, b) => (b.progress_pct as number) - (a.progress_pct as number))[0];
    const costs = complete ? valid.map(readCost) : [];
    const actualCosts = complete && costs.every(cost => cost.costUsd !== null);
    const estimatedCosts = complete && !actualCosts && costs.every(cost => (cost.costUsd ?? cost.costEstimateUsd) !== null);
    rows.push({
      id: `${manifest.protocol_sha256}:${input}:${modelId}`, modelId,
      name: string(row.display_name) || modelId, track: input,
      expectedTrialIds: expected, recordedTrialIds: recorded, validTrialIds: valid.map(trial => string(trial.id)), validTrials: valid.length, coverageComplete: complete,
      meanProgressPct: complete ? valid.reduce((sum, trial) => sum + (trial.progress_pct as number), 0) / 3 : null,
      bestClearSeconds: complete && completed.length ? (completed[0].native_frames_to_completion as number) / 60 : null,
      meanCompletedSeconds: complete && completed.length ? completed.reduce((sum, trial) => sum + (trial.native_frames_to_completion as number), 0) / completed.length / 60 : null,
      nCompleted: completed.length,
      meanCostUsd: actualCosts ? costs.reduce((sum, cost) => sum + cost.costUsd!, 0) / 3 : null,
      meanCostEstimateUsd: estimatedCosts ? costs.reduce((sum, cost) => sum + (cost.costUsd ?? cost.costEstimateUsd)!, 0) / 3 : null,
      representativeRunId: representative ? string(representative.id) : null,
    });
  }
  return { protocolId: string(manifest.protocol_id), protocolSha256: string(manifest.protocol_sha256), frozenAt: string(manifest.frozen_at_utc), rows, trials };
}
