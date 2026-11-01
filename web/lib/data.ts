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
  progressPct: number;
  completed: boolean;
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
  generatedAt: string;
  leaderboardReady: boolean;
  catalogue: { state: number; image: number };
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
  if (progress === null || frames === null || decisions === null || !replay || (raw.mode !== 'state' && raw.mode !== 'image')) {
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

export function parseDataset(index: unknown): Dataset {
  const data = index as { examples?: RawExample[]; generated_at_utc?: string; leaderboard_ready?: boolean; model_counts?: { state?: number; image?: number } };
  if (!Array.isArray(data?.examples)) throw new Error('benchmark index has no examples');
  return {
    runs: data.examples.map(toRun),
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
