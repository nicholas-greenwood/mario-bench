'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { ArrowUp, ArrowLeft, ArrowRight, ChevronLeft, ChevronRight, Moon, Pause, Play, RotateCcw, Sun, X } from 'lucide-react';
import { useBenchmark } from './benchmark-provider';
import GameCanvas from './game-canvas';
import type { Side } from '../lib/data';
export { default as Leaderboard } from './results-table';

export function SiteNav() {
  const { theme, toggleTheme, setOpenMethodology, openMethodology } = useBenchmark();
  return <><header className="site-nav">
    <Link href="/" className="brand">mario bench</Link>
    <div className="nav-actions"><span className="level-label">1-1</span><button className="about-button" onClick={() => setOpenMethodology(true)}>about</button><button className="icon-button" aria-label={`switch to ${theme === 'light' ? 'dark' : 'light'} mode`} onClick={toggleTheme}>{theme === 'light' ? <Moon size={16} /> : <Sun size={16} />}</button></div>
  </header>{openMethodology && <AboutDialog />}</>;
}

export function ReplayCard({ side }: { side: Side }) {
  const state = useBenchmark();
  const model = side === 'left' ? state.leftModel : state.rightModel;
  const run = side === 'left' ? state.leftRun : state.rightRun;
  const index = side === 'left' ? state.leftRunIndex : state.rightRunIndex;
  return <article className={`replay-card ${state.activeSlot === side ? 'is-active' : ''}`} data-side={side}>
    <button className="replay-header replay-select" onClick={() => state.setActiveSlot(side)} aria-label={`select ${side} replay, ${model.name}`} aria-pressed={state.activeSlot === side}>
      <span className="model-name">{model.name}</span><span className="replay-score">{run.score.toFixed(1)}<small>%</small></span>
    </button>
    <div className="replay-screen"><GameCanvas mode="replay" paused={!state.playing} speed={state.speed} seed={run.seed} resetKey={state.resetKey} /></div>
    <div className="replay-footer"><span className="replay-attempt">{index === 0 ? 'best run' : `run ${index + 1}`}<span> / {model.runs.length}</span></span><div className="attempt-navigation"><button className="icon-button" aria-label={`previous ${model.name} replay`} onClick={() => state.cycleRun(side, -1)}><ChevronLeft size={16} /></button><button className="icon-button" aria-label={`next ${model.name} replay`} onClick={() => state.cycleRun(side, 1)}><ChevronRight size={16} /></button></div></div>
  </article>;
}

export function ArenaControls() {
  const { playing, setPlaying, speed, setSpeed, restartReplay } = useBenchmark();
  return <div className="arena-controls" aria-label="replay controls"><button className="icon-button" aria-label={playing ? 'pause replays' : 'play replays'} onClick={() => setPlaying(!playing)}>{playing ? <Pause size={14} fill="currentColor" /> : <Play size={14} fill="currentColor" />}</button><button className="icon-button" aria-label="restart replays" onClick={restartReplay}><RotateCcw size={15} /></button><button className="speed-button" aria-label={`replay speed ${speed} times; click to change`} onClick={() => setSpeed(speed === 1 ? 2 : speed === 2 ? .5 : 1)}>{speed}×</button></div>;
}

function TouchControls() {
  function send(code: string, down: boolean) {
    const canvas = document.querySelector<HTMLCanvasElement>('.human-game-screen canvas');
    canvas?.focus({ preventScroll: true });
    canvas?.dispatchEvent(new KeyboardEvent(down ? 'keydown' : 'keyup', { code, bubbles: true, cancelable: true }));
  }
  const controls = [
    { code: 'ArrowLeft', label: 'move left', content: <ArrowLeft size={20} /> },
    { code: 'ArrowUp', label: 'jump', content: <ArrowUp size={20} /> },
    { code: 'ArrowRight', label: 'move right', content: <ArrowRight size={20} /> },
    { code: 'ShiftLeft', label: 'run', content: 'shift' },
  ];
  return <div className="touch-controls" aria-label="touch game controls">{controls.map(({ code, label, content }) => <button key={code} aria-label={label} onPointerDown={event => { event.preventDefault(); event.currentTarget.setPointerCapture(event.pointerId); send(code, true); }} onPointerUp={() => send(code, false)} onPointerCancel={() => send(code, false)} onContextMenu={event => event.preventDefault()}>{content}</button>)}</div>;
}

export function HumanSeat({ idle = false }: { idle?: boolean }) {
  const { playerDistance, setPlayerDistance, humanOutcome, setHumanOutcome, humanReset, startHumanPlay, setOpenPlay } = useBenchmark();
  const [paused, setPaused] = useState(false);
  useEffect(() => { setPaused(false); }, [humanReset]);
  return <article className={`replay-card human-seat ${idle ? 'is-idle' : ''}`} aria-label="your Mario game">
    <div className="replay-header"><span className="model-name">you</span><span className="human-seat-actions">{!idle && <><span className="replay-score">{playerDistance.toFixed(1)}<small>%</small></span><button className="icon-button" aria-label="stop playing" onClick={() => setOpenPlay(false)}><X size={15} /></button></>}</span></div>
    <div className="replay-screen human-game-screen"><GameCanvas mode="human" paused={idle || paused || !!humanOutcome} resetKey={humanReset} onProgress={setPlayerDistance} onEnd={setHumanOutcome} />
      {idle ? <div className="game-overlay"><button className="play-button" onClick={startHumanPlay}><Play size={14} />play Mario</button></div> : humanOutcome ? <div className="game-overlay result-overlay"><span className="result-score">{playerDistance.toFixed(1)}<small>%</small></span><span>{humanOutcome === 'complete' ? 'level cleared' : 'end of run'}</span><button className="play-button" onClick={startHumanPlay}><RotateCcw size={15} />try again</button></div> : paused && <div className="game-overlay"><button className="play-button" onClick={() => setPaused(false)}><Play size={14} />resume</button></div>}
    </div>
    <div className="replay-footer human-seat-controls">{!idle && <><span className="key-hints" aria-label="left and right arrows move; up jumps; Shift runs"><kbd>←</kbd><kbd>↑</kbd><kbd>→</kbd><kbd className="modifier-key">shift</kbd></span><button className="icon-button" disabled={!!humanOutcome} aria-label={paused ? 'resume game' : 'pause game'} onClick={() => setPaused(!paused)}>{paused ? <Play size={14} /> : <Pause size={14} />}</button></>}</div>
    {!idle && <TouchControls />}
  </article>;
}

function AboutDialog() {
  const { setOpenMethodology } = useBenchmark();
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => { dialog.current?.showModal(); }, []);
  const close = () => setOpenMethodology(false);
  return <dialog ref={dialog} className="about-dialog" aria-label="about the benchmark" onCancel={close} onClick={event => { if (event.target === event.currentTarget) close(); }}><button className="dialog-close icon-button" aria-label="close" onClick={close}><X size={18} /></button><h2>about the benchmark</h2><p>decision models play Super Mario Bros., World 1-1.</p><dl><div><dt>score</dt><dd>furthest progress through the level, from 0 to 100%</dd></div><div><dt>your result</dt><dd>your best score and attempt count are saved in this browser. your cost is zero.</dd></div><div><dt>controls</dt><dd>← → move, ↑ jumps, Shift runs</dd></div><div><dt>demo data</dt><dd>model results are illustrative. replay scenes are scripted demonstrations.</dd></div></dl></dialog>;
}
