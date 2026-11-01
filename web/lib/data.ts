/** Public benchmark results, served from public/benchmark-data (copied from ../results). */
export const DATA_BASE = '/benchmark-data/';

export type Track = 'state' | 'image';

export type Run = {
  id: string;
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
    modelId: text(raw.model_id),
    name: text(raw.display_name, text(raw.model_id)),
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
    id: text(raw.id), modelId: text(raw.model_id), name: text(raw.display_name, text(raw.model_id)),
    provider: text(raw.provider), track: raw.mode, level: text(raw.level, '1-1'),
    // A failed API episode has no score, even if some movement was observed.
    progressPct: num(raw.progress_pct), nativeFrames: num(raw.native_frames), decisions: num(raw.decisions),
    completed, status: text(raw.status), clearFrames: completed ? num(raw.speedrun_score_native_frames) : null,
    clearSeconds: completed ? num(raw.nominal_game_seconds_to_completion) : null,
    cadence: num(config.cadence), previousScreens: num(config.previous_screens), profile: text(config.profile),
    replaySrc: replay ? DATA_BASE + replay : null, traceSrc: DATA_BASE + text(raw.trace_href),
  };
}

export function parseDataset(index: unknown): Dataset {
  const data = index as { examples?: RawExample[]; observations?: RawExample[]; generated_at_utc?: string; leaderboard_ready?: boolean; model_counts?: { state?: number; image?: number } };
  if (!Array.isArray(data?.examples)) throw new Error('benchmark index has no examples');
  return {
    runs: [...new Map([
      ...data.examples,
      ...(data.observations ?? []).filter(raw => text(raw.replay_href)),
    ].map(raw => [text(raw.id), toRun(raw)] as const)).values()],
    observations: (data.observations ?? []).map(toObservation),
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
