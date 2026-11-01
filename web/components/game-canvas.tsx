'use client';

import { useEffect, useRef, useState } from 'react';
import {
  BUTTON, DemoDriver, NES_HEIGHT, NES_WIDTH, bootMario, loadMarioROM,
  marioOutcome, marioProgress, releaseButtons,
  type Emulator, type GameMode, type GameOutcome,
} from '../lib/game';

export interface GameCanvasProps {
  mode: GameMode;
  paused?: boolean;
  speed?: number;
  seed?: number;
  resetKey?: number;
  onProgress?: (percent: number) => void;
  onEnd?: (outcome: GameOutcome) => void;
  className?: string;
}

const keys: Record<string, number> = {
  ArrowLeft: BUTTON.left, ArrowRight: BUTTON.right, ArrowUp: BUTTON.a,
  ShiftLeft: BUTTON.b, ShiftRight: BUTTON.b,
};

export default function GameCanvas({
  mode, paused = false, speed = 1, seed = 0, resetKey = 0,
  onProgress, onEnd, className,
}: GameCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const settings = useRef({ paused, speed, onProgress, onEnd });
  settings.current = { paused, speed, onProgress, onEnd };
  const [status, setStatus] = useState('loading World 1-1…');

  useEffect(() => {
    if (mode !== 'human' || paused) return;
    const frame = requestAnimationFrame(() => canvasRef.current?.focus({ preventScroll: true }));
    return () => cancelAnimationFrame(frame);
  }, [mode, paused]);

  useEffect(() => {
    let disposed = false;
    let raf = 0;
    let nes: Emulator | undefined;
    let removeKeys = () => {};
    setStatus('loading World 1-1…');

    async function start() {
      try {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const context = canvas.getContext('2d', { alpha: false });
        if (!context) throw new Error('Your browser could not create a game canvas.');
        context.imageSmoothingEnabled = false;
        const image = context.createImageData(NES_WIDTH, NES_HEIGHT);
        const rgba = new Uint32Array(image.data.buffer);
        const [jsnes, rom] = await Promise.all([import('jsnes'), loadMarioROM()]);
        if (disposed) return;
        let draw = false;
        const engine = new jsnes.NES({
          emulateSound: false,
          onFrame(frame: ArrayLike<number>) {
            if (!draw || disposed) return;
            for (let i = 0; i < rgba.length; i++) rgba[i] = 0xff000000 | frame[i];
            context!.putImageData(image, 0, 0);
          },
        }) as unknown as Emulator;
        nes = engine;
        bootMario(engine, rom);
        let driver = new DemoDriver(seed);
        let episode = 0;
        let ended = false;
        let elapsed = 0;
        let maxProgress = 0;
        let lastProgress = -1;
        let previousTime = 0;
        let accumulator = 0;

        const reboot = () => {
          draw = false;
          bootMario(engine, rom);
          driver = new DemoDriver(seed + ++episode);
          ended = false;
          elapsed = 0;
          maxProgress = 0;
          lastProgress = -1;
          draw = true;
        };

        // Distinct replay cards open on different parts of the actual level.
        if (mode === 'replay') {
          const warmup = 70 + Math.abs(seed % 4) * 55;
          for (let frame = 0; frame < warmup; frame++) {
            driver.step(engine);
            engine.frame();
            if (marioOutcome(engine)) reboot();
          }
        }
        draw = true;
        engine.frame();
        setStatus('');

        if (mode === 'human') {
          const held = new Set<string>();
          const keyDown = (event: KeyboardEvent) => {
            const button = keys[event.code];
            if (button === undefined) return;
            event.preventDefault();
            if (settings.current.paused || ended) return;
            held.add(event.code);
            engine.buttonDown(1, button);
          };
          const keyUp = (event: KeyboardEvent) => {
            const button = keys[event.code];
            if (button === undefined) return;
            event.preventDefault();
            held.delete(event.code);
            if (![...held].some((code) => keys[code] === button)) engine.buttonUp(1, button);
          };
          const release = () => { held.clear(); releaseButtons(engine); };
          canvas.addEventListener('keydown', keyDown);
          canvas.addEventListener('keyup', keyUp);
          canvas.addEventListener('blur', release);
          window.addEventListener('blur', release);
          document.addEventListener('visibilitychange', release);
          removeKeys = () => {
            release();
            canvas.removeEventListener('keydown', keyDown);
            canvas.removeEventListener('keyup', keyUp);
            canvas.removeEventListener('blur', release);
            window.removeEventListener('blur', release);
            document.removeEventListener('visibilitychange', release);
          };
          if (!settings.current.paused) canvas.focus({ preventScroll: true });
        }

        const animate = (now: number) => {
          if (disposed) return;
          const delta = previousTime ? Math.min(now - previousTime, 80) : 0;
          previousTime = now;
          if (!settings.current.paused && !document.hidden && !ended) {
            accumulator += delta * Math.max(0.1, Math.min(4, settings.current.speed));
            let frames = 0;
            while (accumulator >= 1000 / 60 && frames++ < 16) {
              accumulator -= 1000 / 60;
              if (mode === 'replay') driver.step(engine);
              // Only paint the last useful emulated frame in this animation tick.
              draw = accumulator < 1000 / 60 || frames === 16;
              engine.frame();
              elapsed++;
              maxProgress = Math.max(maxProgress, marioProgress(engine));
              const outcome = marioOutcome(engine);
              if (outcome || (mode === 'replay' && elapsed > 1600)) {
                releaseButtons(engine);
                if (outcome === 'complete') maxProgress = 100;
                settings.current.onEnd?.(outcome ?? 'death');
                if (mode === 'human') ended = true;
                else reboot();
                accumulator = 0;
                break;
              }
            }
            const rounded = Math.round(maxProgress * 10) / 10;
            if (rounded !== lastProgress) {
              lastProgress = rounded;
              settings.current.onProgress?.(rounded);
            }
          } else {
            accumulator = 0;
            if (settings.current.paused) releaseButtons(engine);
          }
          raf = requestAnimationFrame(animate);
        };
        raf = requestAnimationFrame(animate);
      } catch (error) {
        if (!disposed) setStatus(error instanceof Error ? error.message : 'The game could not be loaded.');
      }
    }
    void start();
    return () => {
      disposed = true;
      cancelAnimationFrame(raf);
      removeKeys();
      if (nes) releaseButtons(nes);
    };
  }, [mode, seed, resetKey]);

  return (
    <div className={['game-canvas', className].filter(Boolean).join(' ')} style={{ position: 'relative', width: '100%', height: mode === 'human' ? '100%' : undefined, aspectRatio: '256 / 240', background: '#10100e' }}>
      <canvas
        ref={canvasRef}
        width={NES_WIDTH}
        height={NES_HEIGHT}
        tabIndex={mode === 'human' ? 0 : -1}
        aria-label={mode === 'human' ? 'World 1-1. Left and right arrows move, up arrow jumps, shift runs.' : 'Scripted Mario gameplay demo'}
        onPointerDown={() => mode === 'human' && canvasRef.current?.focus({ preventScroll: true })}
        style={{ display: 'block', width: '100%', height: '100%', imageRendering: 'pixelated', outlineOffset: 3 }}
      />
      {status && <div role="status" style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', color: '#eee9dc', fontSize: 13, padding: 24, textAlign: 'center' }}>{status}</div>}
    </div>
  );
}
