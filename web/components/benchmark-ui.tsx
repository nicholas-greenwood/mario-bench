'use client';

import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, ArrowUp, Moon, Pause, Play, RotateCcw, Sun, X } from 'lucide-react';
import { useBenchmark } from './benchmark-provider';
import GameCanvas from './game-canvas';
import { formatProgress, formatSeconds, trackLabel, type Run, type Side } from '../lib/data';

export function Masthead() {
  const { theme, toggleTheme } = useBenchmark();
  return (
    <header className="masthead">
      <a href="/" className="wordmark">mario bench</a>
      <div className="masthead-end">
        <span className="mono faint">world 1-1</span>
        <button className="icon-button" aria-label={`switch to ${theme === 'light' ? 'dark' : 'light'} theme`} onClick={toggleTheme}>
          {theme === 'light' ? <Moon size={15} /> : <Sun size={15} />}
        </button>
      </div>
    </header>
  );
}

export function Intro() {
  return (
    <section className="intro" aria-labelledby="intro-title">
      <p className="eyebrow mono faint">hackathon project</p>
      <h1 id="intro-title">mario bench gives decision models the controller in super mario bros. and measures how far they get.</h1>
      <div className="intro-detail">
        <p>the game freezes while a model thinks, then plays its chosen buttons for a fixed number of native frames. api latency never touches the game clock, so clear time counts gameplay frames only.</p>
        <p>there are 2 tracks. state models read a compact view of game memory; pixels models only see screenshots.</p>
        <p>every published run is replayed offline from its recorded inputs and has to match frame for frame before its progress and clear time count.</p>
      </div>
    </section>
  );
}

function outcome(run: Run) {
  return run.completed ? `cleared in ${formatSeconds(run.clearSeconds)}` : `reached ${formatProgress(run.progressPct)}`;
}

export function ReplayPane({ side }: { side: Side }) {
  const { runA, runB, activeSide, setActiveSide, playing, speed, restartKey } = useBenchmark();
  const run = side === 'a' ? runA : runB;
  const video = useRef<HTMLVideoElement>(null);
  const [failed, setFailed] = useState(false);
  const active = activeSide === side;

  const sync = () => {
    const element = video.current;
    if (!element) return;
    element.muted = true;
    element.defaultMuted = true;
    element.defaultPlaybackRate = speed;
    element.playbackRate = speed;
    if (playing) void element.play().catch(() => {});
    else element.pause();
  };
  useEffect(sync, [run.id, playing, speed]);
  useEffect(() => { if (video.current) video.current.currentTime = 0; }, [restartKey]);
  useEffect(() => setFailed(false), [run.id]);

  return (
    <figure className="pane" data-side={side} data-run-id={run.id}>
      <div className="screen">
        <video
          key={run.id}
          ref={video}
          src={run.replaySrc}
          muted
          playsInline
          loop
          preload="auto"
          disablePictureInPicture
          aria-label={`recorded ${trackLabel(run.track)} run by ${run.modelId}`}
          onLoadedMetadata={sync}
          onError={() => setFailed(true)}
        />
        {failed && <div className="screen-note" role="status">replay unavailable</div>}
      </div>
      <figcaption className="caption">
        <button className={`slot${active ? ' is-active' : ''}`} aria-pressed={active} aria-label={`send table selections to pane ${side}`} onClick={() => setActiveSide(side)}>{side}</button>
        <div className="caption-body">
          <div className="caption-line">
            <span className="caption-name">{run.name}</span>
            <span className="caption-result mono">{outcome(run)}</span>
          </div>
          <div className="caption-meta mono faint">
            <span className="caption-id">{run.modelId}</span>
            <span>{trackLabel(run.track)}{run.cadence !== null ? ` · every ${run.cadence} frames` : ''}</span>
          </div>
        </div>
      </figcaption>
    </figure>
  );
}

const SPEEDS = [0.5, 1, 2];

export function Transport() {
  const { playing, setPlaying, speed, setSpeed, restart } = useBenchmark();
  return (
    <div className="transport" role="group" aria-label="replay controls">
      <div className="transport-buttons">
        <button className="icon-button" aria-label={playing ? 'pause replays' : 'play replays'} onClick={() => setPlaying(!playing)}>
          {playing ? <Pause size={14} fill="currentColor" strokeWidth={0} /> : <Play size={14} fill="currentColor" strokeWidth={0} />}
        </button>
        <button className="icon-button" aria-label="restart replays" onClick={restart}><RotateCcw size={14} /></button>
        <div className="speeds" role="group" aria-label="replay speed">
          {SPEEDS.map(value => (
            <button key={value} className="speed mono" aria-pressed={speed === value} aria-label={`${value}× speed`} onClick={() => setSpeed(value)}>{value}×</button>
          ))}
        </div>
      </div>
      <p className="transport-note faint">native game speed, api waits cut out</p>
    </div>
  );
}

function TouchControls() {
  const send = (code: string, down: boolean) => {
    const canvas = document.querySelector<HTMLCanvasElement>('.human-screen canvas');
    canvas?.focus({ preventScroll: true });
    canvas?.dispatchEvent(new KeyboardEvent(down ? 'keydown' : 'keyup', { code, bubbles: true, cancelable: true }));
  };
  const controls = [
    { code: 'ArrowLeft', label: 'move left', content: <ArrowLeft size={18} /> },
    { code: 'ArrowRight', label: 'move right', content: <ArrowRight size={18} /> },
    { code: 'ShiftLeft', label: 'run', content: 'run' },
    { code: 'ArrowUp', label: 'jump', content: <ArrowUp size={18} /> },
  ];
  return (
    <div className="touch-pad" aria-label="touch controls">
      {controls.map(({ code, label, content }) => (
        <button
          key={code}
          aria-label={label}
          onPointerDown={event => { event.preventDefault(); event.currentTarget.setPointerCapture(event.pointerId); send(code, true); }}
          onPointerUp={() => send(code, false)}
          onPointerCancel={() => send(code, false)}
          onContextMenu={event => event.preventDefault()}
        >{content}</button>
      ))}
    </div>
  );
}

export function HumanPane() {
  const { humanOpen, humanProgress, humanOutcome, humanReset, humanPaused, setHumanPaused, onHumanProgress, onHumanEnd, startHuman, stopHuman, best } = useBenchmark();
  const idle = !humanOpen;
  const bestClear = best.clearFrames !== null ? formatSeconds(best.clearFrames / 60) : null;
  return (
    <section className="human" aria-labelledby="human-title">
      <h2 id="human-title" className="section-label">your turn</h2>
      <figure className="pane">
        <div className="screen human-screen">
          <GameCanvas paused={idle || humanPaused || !!humanOutcome} resetKey={humanReset} onProgress={onHumanProgress} onEnd={onHumanEnd} />
          {idle ? (
            <div className="screen-overlay"><button className="primary" onClick={startHuman}><Play size={13} fill="currentColor" strokeWidth={0} />play world 1-1</button></div>
          ) : humanOutcome ? (
            <div className="screen-overlay is-result" role="status">
              <span className="result-figure mono">{formatProgress(humanProgress)}</span>
              <span>{humanOutcome === 'complete' ? 'you reached the flag' : 'run over'}</span>
              <button className="primary" onClick={startHuman}><RotateCcw size={13} />try again</button>
            </div>
          ) : humanPaused ? (
            <div className="screen-overlay"><button className="primary" onClick={() => setHumanPaused(false)}><Play size={13} fill="currentColor" strokeWidth={0} />resume</button></div>
          ) : null}
        </div>
        <figcaption className="caption">
          <div className="caption-body">
            <div className="caption-line">
              <span className="caption-name">you</span>
              <span className="caption-result mono" data-testid="human-progress">{idle ? '' : formatProgress(humanProgress)}</span>
              {!idle && (
                <span className="caption-actions">
                  <button className="icon-button" disabled={!!humanOutcome} aria-label={humanPaused ? 'resume game' : 'pause game'} onClick={() => setHumanPaused(!humanPaused)}>{humanPaused ? <Play size={13} /> : <Pause size={13} />}</button>
                  <button className="icon-button" aria-label="stop playing" onClick={stopHuman}><X size={14} /></button>
                </span>
              )}
            </div>
            <div className="caption-meta mono faint">
              <span data-testid="human-best">{best.attempts ? `best ${formatProgress(best.bestPct)}${bestClear ? `, cleared in ${bestClear}` : ''} · ${best.attempts} ${best.attempts === 1 ? 'attempt' : 'attempts'}` : 'no attempts yet'}</span>
              <span className="keys" aria-label="arrows move, up jumps, shift runs"><kbd>←</kbd><kbd>→</kbd><kbd>↑</kbd><kbd>shift</kbd></span>
            </div>
          </div>
        </figcaption>
      </figure>
      {!idle && <TouchControls />}
      <p className="human-note faint">kept in this browser and played without a frame budget, so it sits apart from the model runs</p>
    </section>
  );
}

export function Colophon() {
  const { dataset } = useBenchmark();
  return (
    <footer className="colophon faint">
      <p>the model catalogue covers {dataset.catalogue.state} state and {dataset.catalogue.image} pixels-compatible model/provider pairs. {dataset.runs.length} showcases have video; development observations retain their action traces.</p>
      <p><a href="/benchmark-data/index.json">raw data</a> · generated {dataset.generatedAt.slice(0, 10)}</p>
    </footer>
  );
}
