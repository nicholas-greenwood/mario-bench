/** Public benchmark results, served from public/benchmark-data (copied from ../results). */
import { parseCommonBenchmark, type CommonBenchmark } from './common-benchmark.ts';

export const DATA_BASE = '/benchmark-data/';

export type Track = 'state' | 'image';
export type CostProvenance = {
  kind: string;
  cost_basis: string;
  request_count: number;
  costed_request_count: number;
  actual_costed_request_count: number;
  coverage_complete: boolean;
  attempt_scope_verified: boolean;
  source_request_count: number;
  source_attempt_count: number;
  error_count: number;
  unreceipted_count: number;
  unreceipted_attempt_count: number;
  unbilled_error_attempts_unknown: number;
  includes_retries: boolean;
  includes_auxiliary_calls: boolean;
  upstream_cost_basis?: string | null;
};

export type Run = {
  id: string;
  aliasIds: string[];
  recoveryLineage: { originalTraceSrc: string; childTraceSrc: string; proofSrc: string } | null;
  modelId: string;
  name: string;
  provider: string;
  track: Track;
  level: string;
  progressPct: number | null;
  completed: boolean;
  status: string;
  nativeFrames: number;
  decisions: number;
  costUsd: number | null;
  costEstimateUsd: number | null;
  openrouterCostUsd: number | null;
  upstreamCostUsd: number | null;
  upstreamCostEstimateUsd: number | null;
  costProvenance: CostProvenance | null;
  /** Native frames to the flag; null when the run did not finish. */
  clearFrames: number | null;
  clearSeconds: number | null;
  cadence: number | null;
  previousScreens: number | null;
  profile: string;
  retrospective: boolean;
  matchedCohort: boolean;
  replaySrc: string;
  traceSrc: string;
};

export type Dataset = {
  runs: Run[];
  observations: Result[];
  generatedAt: string;
  leaderboardReady: boolean;
  catalogue: { state: number; image: number };
  commonBenchmark: CommonBenchmark | null;
};

export type Result = Omit<Run, 'progressPct' | 'nativeFrames' | 'decisions' | 'replaySrc'> & {
  progressPct: number | null;
  nativeFrames: number | null;
  decisions: number | null;
  replaySrc: string | null;
};

type RawExample = Record<string, unknown> & { experiment_config?: Record<string, unknown> };

const num = (value: unknown) => (typeof value === 'number' && Number.isFinite(value) ? value : null);
const text = (value: unknown, fallback = '') => (typeof value === 'string' ? value : fallback);
function runCost(raw: RawExample) {
  const provenance = raw.cost_provenance && typeof raw.cost_provenance === 'object' && !Array.isArray(raw.cost_provenance)
    ? raw.cost_provenance as CostProvenance : null;
  const value = num(raw.cost_usd);
  const complete = provenance && provenance.kind === 'recorded_response_usage' && provenance.cost_basis === 'all_in_inference'
    && provenance.coverage_complete === true
    && provenance.attempt_scope_verified === true
    && provenance.source_request_count === provenance.request_count
    && provenance.source_attempt_count === provenance.request_count
    && Number.isInteger(provenance.error_count) && provenance.error_count >= 0
    && provenance.error_count <= provenance.request_count
    && provenance.unreceipted_count === 0 && provenance.unreceipted_attempt_count === 0
    && provenance.unbilled_error_attempts_unknown === 0
    && provenance.includes_retries === true && provenance.includes_auxiliary_calls === true
    && Number.isInteger(provenance.request_count) && provenance.request_count > 0
    && provenance.costed_request_count === provenance.request_count;
  const nonnegative = (amount: unknown) => { const result = num(amount); return result !== null && result >= 0 ? result : null; };
  const actualComplete = complete && provenance.actual_costed_request_count === provenance.request_count;
  const estimateComplete = complete && provenance.upstream_cost_basis === 'openrouter_activity_list_price_estimate'
    && Number.isInteger(provenance.actual_costed_request_count) && provenance.actual_costed_request_count >= 0
    && provenance.actual_costed_request_count < provenance.request_count;
  const recorded = provenance?.kind === 'recorded_response_usage';
  return {
    costUsd: actualComplete && value !== null && value >= 0 ? value : null,
    costEstimateUsd: estimateComplete ? nonnegative(raw.cost_estimate_usd) : null,
    openrouterCostUsd: recorded ? nonnegative(raw.openrouter_cost_usd) : null,
    upstreamCostUsd: recorded ? nonnegative(raw.upstream_cost_usd) : null,
    upstreamCostEstimateUsd: recorded ? nonnegative(raw.upstream_cost_estimate_usd) : null,
    costProvenance: provenance ?? null,
  };
}
const isJsonRetest = (raw: RawExample) => raw.data_class === 'technical_serialization_diagnostic'
  && raw.verified === true && raw.experiment_config?.state_serialization === 'json_object'
  && (raw.completed === true || raw.death === true);
const displayName = (raw: RawExample) => text(raw.display_name, text(raw.model_id)) + (isJsonRetest(raw) ? ' (json retest)' : raw.record_kind === 'technical_resolution' ? ' (technical continuation)' : '');
function recoveryLineage(raw: RawExample): Run['recoveryLineage'] {
  const lineage = raw.recovery_lineage as Record<string, unknown> | undefined;
  return lineage && ['originalTraceHref', 'childTraceHref', 'proofHref'].every(k => typeof lineage[k] === 'string')
    ? { originalTraceSrc: DATA_BASE + lineage.originalTraceHref, childTraceSrc: DATA_BASE + lineage.childTraceHref, proofSrc: DATA_BASE + lineage.proofHref } : null;
}

export const isApiError = (status: string) => /api|infra|error|failure/.test(status);
export const unavailableProgress = (status: string) => isApiError(status) ? 'api error' : 'incomplete';

function toRun(raw: RawExample): Run {
  const config = raw.experiment_config ?? {};
  const progress = num(raw.progress_pct);
  const frames = num(raw.native_frames);
  const decisions = num(raw.decisions);
  const replay = text(raw.replay_href);
  if ((progress === null && raw.progress_pct !== null) || frames === null || decisions === null || !replay || (raw.mode !== 'state' && raw.mode !== 'image')) {
    throw new Error(`benchmark example ${String(raw.id)} is missing required fields`);
  }
  const completed = raw.completed === true;
  return {
    id: text(raw.id),
    aliasIds: Array.isArray(raw.alias_ids) ? raw.alias_ids.filter((id): id is string => typeof id === 'string') : [],
    recoveryLineage: recoveryLineage(raw),
    modelId: text(raw.model_id),
    name: displayName(raw),
    provider: text(raw.provider),
    track: raw.mode,
    level: text(raw.level, '1-1'),
    progressPct: progress,
    completed,
    status: text(raw.status, completed ? 'completed' : 'game_over'),
    nativeFrames: frames,
    decisions,
    ...runCost(raw),
    clearFrames: completed ? num(raw.speedrun_score_native_frames) : null,
    clearSeconds: completed ? num(raw.nominal_game_seconds_to_completion) : null,
    cadence: num(config.cadence),
    previousScreens: num(config.previous_screens),
    profile: text(config.profile),
    retrospective: config.retrospective === true,
    matchedCohort: config.matched_cohort === true,
    replaySrc: DATA_BASE + replay,
    traceSrc: DATA_BASE + text(raw.trace_href),
  };
}

function toObservation(raw: RawExample): Result {
  if (raw.mode !== 'state' && raw.mode !== 'image') throw new Error('unknown observation track');
  const config = raw.experiment_config ?? {};
  const completed = raw.completed === true;
  const replay = text(raw.replay_href);
  return {
    id: text(raw.id), aliasIds: Array.isArray(raw.alias_ids) ? raw.alias_ids.filter((id): id is string => typeof id === 'string') : [],
    recoveryLineage: recoveryLineage(raw),
    modelId: text(raw.model_id), name: displayName(raw),
    provider: text(raw.provider), track: raw.mode, level: text(raw.level, '1-1'),
    // A failed API episode has no score, even if some movement was observed.
    progressPct: num(raw.progress_pct), nativeFrames: num(raw.native_frames), decisions: num(raw.decisions),
    ...runCost(raw),
    completed, status: text(raw.status), clearFrames: completed ? num(raw.speedrun_score_native_frames) : null,
    clearSeconds: completed ? num(raw.nominal_game_seconds_to_completion) : null,
    cadence: num(config.cadence), previousScreens: num(config.previous_screens), profile: text(config.profile),
    retrospective: config.retrospective === true, matchedCohort: config.matched_cohort === true,
    replaySrc: replay ? DATA_BASE + replay : null, traceSrc: DATA_BASE + text(raw.trace_href),
  };
}

export function parseDataset(index: unknown): Dataset {
  const data = index as { examples?: RawExample[]; observations?: RawExample[]; technical_diagnostics?: RawExample[]; common_benchmark?: unknown; generated_at_utc?: string; leaderboard_ready?: boolean; model_counts?: { state?: number; image?: number } };
  if (!Array.isArray(data?.examples)) throw new Error('benchmark index has no examples');
  const byId = [...new Map([
    ...data.examples,
    ...(data.observations ?? []),
    // A verified full retest is an additional episode; its overlapping prefix is evidence only.
    ...(data.technical_diagnostics ?? []).filter(isJsonRetest),
  ].map(raw => [text(raw.id), raw] as const)).values()];
  const byEpisode = new Map<string, RawExample>(byId.map(raw => [text(raw.id), { ...raw, alias_ids: [] }]));
  // These exports refer to the same original episode, not independent repeats.
  const episodeAliases = { 'pixels-best-inception--mercury-decide': 'mercury-pixels-partial' };
  for (const [aliasId, canonicalId] of Object.entries(episodeAliases)) {
    const alias = byEpisode.get(aliasId), canonical = byEpisode.get(canonicalId);
    if (!alias || !canonical) continue;
    const aliasSource = (alias.source_hashes ?? {}) as Record<string, unknown>;
    const canonicalSource = (canonical.source_hashes ?? {}) as Record<string, unknown>;
    const sameSource = ['requests_sha256', 'responses_sha256', 'private_replay_sha256']
      .every(key => text(aliasSource[key]) && aliasSource[key] === canonicalSource[key]);
    const sameIdentity = ['model_id', 'mode', 'level', 'native_frames', 'decisions']
      .every(key => alias[key] === canonical[key]);
    if (sameSource && sameIdentity) {
      const canonicalCost = runCost(canonical), aliasCost = runCost(alias);
      if ((canonicalCost.costUsd === null && aliasCost.costUsd !== null)
        || (canonicalCost.costUsd === null && canonicalCost.costEstimateUsd === null && aliasCost.costEstimateUsd !== null)) {
        for (const key of ['cost_usd', 'cost_estimate_usd', 'openrouter_cost_usd', 'upstream_cost_usd', 'upstream_cost_estimate_usd', 'cost_provenance']) canonical[key] = alias[key];
      }
      (canonical.alias_ids as string[]).push(aliasId);
      byEpisode.delete(aliasId);
    }
  }
  const published = [...byEpisode.values()];
  const legacyIds = new Set([...data.examples, ...(data.observations ?? []), ...(data.technical_diagnostics ?? [])].map(raw => text(raw.id)));
  const commonBenchmark = parseCommonBenchmark(data.common_benchmark, legacyIds, runCost);
  const validCommonIds = new Set(commonBenchmark?.rows.flatMap(row => row.validTrialIds) ?? []);
  for (const trial of commonBenchmark?.trials ?? []) {
    if ((trial.track !== 'state' && trial.track !== 'image') || published.some(raw => raw.id === trial.id)) continue;
    const valid = validCommonIds.has(text(trial.id));
    published.push({ ...trial, mode: trial.track,
      completed: valid && trial.flag_get === true,
      progress_pct: valid ? trial.progress_pct : null,
      status: valid ? trial.status : 'technical_pending',
      speedrun_score_native_frames: valid && trial.flag_get === true ? trial.native_frames_to_completion : null,
      nominal_game_seconds_to_completion: valid && trial.flag_get === true ? Number(trial.native_frames_to_completion) / 60 : null,
    });
  }
  return {
    runs: published.filter(raw => text(raw.replay_href) && num(raw.native_frames) !== null && num(raw.decisions) !== null).map(toRun),
    observations: published.map(toObservation),
    generatedAt: text(data.generated_at_utc),
    leaderboardReady: data.leaderboard_ready === true,
    catalogue: { state: num(data.model_counts?.state) ?? 0, image: num(data.model_counts?.image) ?? 0 },
    commonBenchmark,
  };
}

export const trackLabel = (track: Track) => (track === 'image' ? 'pixels' : 'state');

export function formatProgress(value: number) {
  return value >= 100 ? '100%' : `${(Math.floor(value * 10) / 10).toFixed(1)}%`;
}

export function formatSeconds(value: number | null) {
  return value === null ? null : `${value.toFixed(2)} s`;
}

export function formatCost(value: number | null) {
  if (value === null) return null;
  if (value > 0 && value < .000001) return '<$0.000001';
  return `$${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 6 })}`;
}

export function formatRunCost(run: Pick<Run, 'costUsd' | 'costEstimateUsd'>) {
  if (run.costUsd !== null) return formatCost(run.costUsd);
  return run.costEstimateUsd === null ? null : `~${formatCost(run.costEstimateUsd)}`;
}

export type Side = 'a' | 'b';
