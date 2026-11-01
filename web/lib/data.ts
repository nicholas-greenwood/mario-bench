/** Public benchmark results, served from public/benchmark-data (copied from ../results). */
export const DATA_BASE = '/benchmark-data/';

export type Track = 'state' | 'image';

export type Run = {
  id: string;
  aliasIds: string[];
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
const isJsonRetest = (raw: RawExample) => raw.data_class === 'technical_serialization_diagnostic'
  && raw.verified === true && raw.experiment_config?.state_serialization === 'json_object'
  && (raw.completed === true || raw.death === true);
const displayName = (raw: RawExample) => text(raw.display_name, text(raw.model_id)) + (isJsonRetest(raw) ? ' (json retest)' : '');

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
    modelId: text(raw.model_id), name: displayName(raw),
    provider: text(raw.provider), track: raw.mode, level: text(raw.level, '1-1'),
    // A failed API episode has no score, even if some movement was observed.
    progressPct: num(raw.progress_pct), nativeFrames: num(raw.native_frames), decisions: num(raw.decisions),
    completed, status: text(raw.status), clearFrames: completed ? num(raw.speedrun_score_native_frames) : null,
    clearSeconds: completed ? num(raw.nominal_game_seconds_to_completion) : null,
    cadence: num(config.cadence), previousScreens: num(config.previous_screens), profile: text(config.profile),
    retrospective: config.retrospective === true, matchedCohort: config.matched_cohort === true,
    replaySrc: replay ? DATA_BASE + replay : null, traceSrc: DATA_BASE + text(raw.trace_href),
  };
}

export function parseDataset(index: unknown): Dataset {
  const data = index as { examples?: RawExample[]; observations?: RawExample[]; technical_diagnostics?: RawExample[]; generated_at_utc?: string; leaderboard_ready?: boolean; model_counts?: { state?: number; image?: number } };
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
      (canonical.alias_ids as string[]).push(aliasId);
      byEpisode.delete(aliasId);
    }
  }
  const published = [...byEpisode.values()];
  return {
    runs: published.filter(raw => text(raw.replay_href)).map(toRun),
    observations: published.map(toObservation),
    generatedAt: text(data.generated_at_utc),
    leaderboardReady: data.leaderboard_ready === true,
    catalogue: { state: num(data.model_counts?.state) ?? 0, image: num(data.model_counts?.image) ?? 0 },
  };
}

export const trackLabel = (track: Track) => (track === 'image' ? 'pixels' : 'state');

export function formatProgress(value: number) {
  return value >= 100 ? '100%' : `${(Math.floor(value * 10) / 10).toFixed(1)}%`;
}

export function formatSeconds(value: number | null) {
  return value === null ? null : `${value.toFixed(2)} s`;
}

export type Side = 'a' | 'b';
