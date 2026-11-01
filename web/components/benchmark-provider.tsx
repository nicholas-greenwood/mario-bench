'use client';

import { createContext, useContext, useEffect, useRef, useState, type ReactNode, type SetStateAction } from 'react';
import { MODELS, type Side } from '../lib/data';

const PERSONAL_SCORE_KEY = 'mario-bench-personal-score-v1';
type PersonalResult = { bestScore: number; runs: number };
type HumanOutcome = 'death' | 'complete' | null;

function savePersonalResult(result: PersonalResult) {
  try { localStorage.setItem(PERSONAL_SCORE_KEY, JSON.stringify(result)); } catch { /* Browser storage may be unavailable. */ }
}

function useBenchmarkState() {
  const [leftId, setLeftId] = useState(MODELS[0].id);
  const [rightId, setRightId] = useState(MODELS[1].id);
  const [leftRunIndex, setLeftRunIndex] = useState(0);
  const [rightRunIndex, setRightRunIndex] = useState(0);
  const [activeSlot, setActiveSlot] = useState<Side>('left');
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState(1);
  const [resetKey, setResetKey] = useState(0);
  const [openPlay, updateOpenPlay] = useState(false);
  const [openMethodology, setOpenMethodology] = useState(false);
  const [playerDistance, updatePlayerDistance] = useState(0);
  const [humanOutcome, updateHumanOutcome] = useState<HumanOutcome>(null);
  const [humanReset, setHumanReset] = useState(0);
  const [theme, setTheme] = useState<'light' | 'dark'>('light');
  const [personalResult, setPersonalResult] = useState<PersonalResult>({ bestScore: 0, runs: 0 });
  const personalRef = useRef(personalResult);
  const distanceRef = useRef(0);
  const outcomeRef = useRef<HumanOutcome>(null);
  const openPlayRef = useRef(false);
  const leftModel = MODELS.find(m => m.id === leftId)!;
  const rightModel = MODELS.find(m => m.id === rightId)!;

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(PERSONAL_SCORE_KEY) || 'null');
      if (saved && Number.isFinite(saved.bestScore) && Number.isInteger(saved.runs) && saved.runs > 0) {
        const result = { bestScore: Math.max(0, Math.min(100, saved.bestScore)), runs: saved.runs };
        personalRef.current = result;
        setPersonalResult(result);
      }
      const savedTheme = localStorage.getItem('mario-bench-theme');
      setTheme(savedTheme === 'dark' || savedTheme === 'light' ? savedTheme : window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    } catch { /* Keep this session playable if saved data is unavailable. */ }
    const save = () => { if (personalRef.current.runs) savePersonalResult(personalRef.current); };
    window.addEventListener('pagehide', save);
    return () => window.removeEventListener('pagehide', save);
  }, []);
  // Save improvements after movement settles; endings and stops also save immediately.
  useEffect(() => {
    if (!personalResult.runs) return;
    const timeout = window.setTimeout(() => savePersonalResult(personalRef.current), 500);
    return () => window.clearTimeout(timeout);
  }, [personalResult]);
  useEffect(() => { document.documentElement.dataset.theme = theme; }, [theme]);

  const toggleTheme = () => {
    const next = theme === 'light' ? 'dark' : 'light';
    setTheme(next);
    try { localStorage.setItem('mario-bench-theme', next); } catch { /* Theme still works without storage. */ }
  };
  const selectModel = (id: string, side?: Side) => {
    if (!MODELS.some(model => model.id === id)) return;
    const target = side || activeSlot;
    setActiveSlot(target);
    if (target === 'left') { setLeftId(id); setLeftRunIndex(0); }
    else { setRightId(id); setRightRunIndex(0); }
    setPlaying(true); setResetKey(k => k + 1);
    const stage = document.getElementById('arena-stage');
    const bounds = stage?.getBoundingClientRect();
    if (bounds && (bounds.top < 0 || bounds.bottom > innerHeight)) stage?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  };
  const setPlayerDistance = (value: SetStateAction<number>) => {
    const next = typeof value === 'function' ? value(distanceRef.current) : value;
    if (!Number.isFinite(next)) return;
    const score = Math.max(0, Math.min(100, next));
    distanceRef.current = score;
    updatePlayerDistance(score);
    if (personalRef.current.runs && score > personalRef.current.bestScore) {
      const result = { ...personalRef.current, bestScore: score };
      personalRef.current = result;
      setPersonalResult(result);
      if (outcomeRef.current) savePersonalResult(result);
    }
  };
  const setHumanOutcome = (value: SetStateAction<HumanOutcome>) => {
    const next = typeof value === 'function' ? value(outcomeRef.current) : value;
    outcomeRef.current = next;
    updateHumanOutcome(next);
    if (next && personalRef.current.runs) savePersonalResult(personalRef.current);
  };
  const setOpenPlay = (value: SetStateAction<boolean>) => {
    const next = typeof value === 'function' ? value(openPlayRef.current) : value;
    openPlayRef.current = next;
    updateOpenPlay(next);
    if (!next && personalRef.current.runs) savePersonalResult(personalRef.current);
  };
  const startHumanPlay = () => {
    const result = { ...personalRef.current, runs: personalRef.current.runs + 1 };
    personalRef.current = result;
    setPersonalResult(result);
    savePersonalResult(result);
    setPlayerDistance(0); setHumanOutcome(null); setHumanReset(k => k + 1); setOpenPlay(true);
  };
  const cycleRun = (side: Side, delta: number) => {
    const model = side === 'left' ? leftModel : rightModel;
    const setter = side === 'left' ? setLeftRunIndex : setRightRunIndex;
    setter(i => (i + delta + model.runs.length) % model.runs.length);
    setResetKey(k => k + 1); setPlaying(true);
  };
  const restartReplay = () => { setResetKey(k => k + 1); };
  return { models: MODELS, leftModel, rightModel, leftRun: leftModel.runs[leftRunIndex], rightRun: rightModel.runs[rightRunIndex], leftRunIndex, rightRunIndex, activeSlot, setActiveSlot, selectModel, cycleRun, playing, setPlaying, speed, setSpeed, resetKey, restartReplay, openPlay, setOpenPlay, openMethodology, setOpenMethodology, theme, toggleTheme, playerDistance, setPlayerDistance, humanOutcome, setHumanOutcome, humanReset, startHumanPlay, hasPlayed: personalResult.runs > 0, playerBestScore: personalResult.bestScore, playerRuns: personalResult.runs };
}

type ContextType = ReturnType<typeof useBenchmarkState>;
const BenchmarkContext = createContext<ContextType | null>(null);

export function BenchmarkProvider({ children }: { children: ReactNode }) {
  const state = useBenchmarkState();
  return <BenchmarkContext.Provider value={state}>{children}</BenchmarkContext.Provider>;
}

export function useBenchmark() {
  const context = useContext(BenchmarkContext);
  if (!context) throw new Error('useBenchmark requires BenchmarkProvider');
  return context;
}
