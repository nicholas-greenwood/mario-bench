'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import type { Dataset, Run, Side } from '../lib/data';
import type { GameOutcome } from '../lib/game';

/** v1 used the stale 3168 denominator, so those scores are discarded. */
const HUMAN_KEY = 'mario-bench-human-v2';
const LEGACY_KEYS = ['mario-bench-personal-score-v1'];
const THEME_KEY = 'mario-bench-theme';

export type HumanBest = { bestPct: number; attempts: number; clearFrames: number | null };
const EMPTY_BEST: HumanBest = { bestPct: 0, attempts: 0, clearFrames: null };

function readBest(): HumanBest {
  try {
    LEGACY_KEYS.forEach(key => localStorage.removeItem(key));
    const saved = JSON.parse(localStorage.getItem(HUMAN_KEY) || 'null');
    if (!saved || !Number.isInteger(saved.attempts) || saved.attempts < 1 || !Number.isFinite(saved.bestPct)) return EMPTY_BEST;
    return {
      bestPct: Math.max(0, Math.min(100, saved.bestPct)),
      attempts: saved.attempts,
      clearFrames: Number.isInteger(saved.clearFrames) && saved.clearFrames > 0 ? saved.clearFrames : null,
    };
  } catch { return EMPTY_BEST; }
}

function writeBest(best: HumanBest) {
  try { localStorage.setItem(HUMAN_KEY, JSON.stringify(best)); } catch { /* storage can be unavailable */ }
}

function useBenchmarkState(dataset: Dataset) {
  const runs = dataset.runs;
  const initial = useMemo(() => ({
    a: (runs.find(run => run.track === 'state' && run.completed) ?? runs.find(run => run.track === 'state') ?? runs[0]).id,
    b: (runs.find(run => run.track === 'image' && run.completed) ?? runs.find(run => run.track === 'image') ?? runs[1] ?? runs[0]).id,
  }), [runs]);
  const [slots, setSlots] = useState<Record<Side, string>>(initial);
  const [activeSide, setActiveSide] = useState<Side>('a');
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState(1);
  const [restartKey, setRestartKey] = useState(0);
  const [theme, setTheme] = useState<'light' | 'dark'>('light');

  const [humanOpen, setHumanOpen] = useState(false);
  const [humanPaused, setHumanPaused] = useState(false);
  const [humanProgress, setHumanProgress] = useState(0);
  const [humanOutcome, setHumanOutcome] = useState<GameOutcome | null>(null);
  const [humanReset, setHumanReset] = useState(0);
  const [best, setBest] = useState<HumanBest>(EMPTY_BEST);
  const bestRef = useRef(best);
  const commitBest = useCallback((next: HumanBest, persist = true) => {
    bestRef.current = next;
    setBest(next);
    if (persist) writeBest(next);
  }, []);

  useEffect(() => {
    commitBest(readBest(), false);
    let saved: string | null = null;
    try { saved = localStorage.getItem(THEME_KEY); } catch { /* storage can be unavailable */ }
    const initial = saved === 'dark' || saved === 'light' ? saved : matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    document.documentElement.dataset.theme = initial;
    setTheme(initial);
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) setPlaying(false);
  }, [commitBest]);

  const toggleTheme = () => {
    const next = theme === 'light' ? 'dark' : 'light';
    setTheme(next);
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem(THEME_KEY, next); } catch { /* theme still works for this visit */ }
  };

  const runById = (id: string) => runs.find(run => run.id === id || run.aliasIds.includes(id)) ?? runs[0];
  const watch = (id: string) => {
    const run = runs.find(run => run.id === id || run.aliasIds.includes(id));
    if (!run) return;
    setSlots(current => ({ ...current, [activeSide]: run.id }));
    setPlaying(true);
  };

  const onHumanProgress = (pct: number) => {
    setHumanProgress(pct);
    if (pct > bestRef.current.bestPct) commitBest({ ...bestRef.current, bestPct: pct }, false);
  };
  const onHumanEnd = (outcome: GameOutcome, frames: number) => {
    setHumanOutcome(outcome);
    const current = bestRef.current;
    const clearFrames = outcome === 'complete' ? Math.min(frames, current.clearFrames ?? Infinity) : current.clearFrames;
    commitBest({ ...current, bestPct: outcome === 'complete' ? 100 : current.bestPct, clearFrames });
  };
  const startHuman = () => {
    commitBest({ ...bestRef.current, attempts: bestRef.current.attempts + 1 });
    setHumanProgress(0);
    setHumanOutcome(null);
    setHumanPaused(false);
    setHumanReset(key => key + 1);
    setHumanOpen(true);
  };
  const stopHuman = () => {
    writeBest(bestRef.current);
    setHumanOpen(false);
    setHumanPaused(false);
  };
  useEffect(() => {
    const save = () => { if (bestRef.current.attempts) writeBest(bestRef.current); };
    addEventListener('pagehide', save);
    return () => removeEventListener('pagehide', save);
  }, []);

  return {
    dataset, runs, slots, runA: runById(slots.a), runB: runById(slots.b), activeSide, setActiveSide, watch,
    playing, setPlaying, speed, setSpeed, restartKey, restart: () => { setRestartKey(key => key + 1); setPlaying(true); },
    theme, toggleTheme,
    humanOpen, humanPaused, setHumanPaused, humanProgress, humanOutcome, humanReset, best,
    onHumanProgress, onHumanEnd, startHuman, stopHuman,
  };
}

type ContextType = ReturnType<typeof useBenchmarkState>;
const BenchmarkContext = createContext<ContextType | null>(null);

export function BenchmarkProvider({ dataset, children }: { dataset: Dataset; children: ReactNode }) {
  const state = useBenchmarkState(dataset);
  return <BenchmarkContext.Provider value={state}>{children}</BenchmarkContext.Provider>;
}

export function useBenchmark() {
  const context = useContext(BenchmarkContext);
  if (!context) throw new Error('useBenchmark requires BenchmarkProvider');
  return context;
}

export type { Run };
