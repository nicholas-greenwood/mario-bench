'use client';

import { useEffect, useRef, useState } from 'react';
import {
  BUTTON, NES_HEIGHT, NES_WIDTH, bootMario, loadMarioROM,
  marioOutcome, marioProgress, releaseButtons,
  type Emulator, type GameOutcome,
} from '../lib/game';

export interface GameCanvasProps {
  paused?: boolean;
  resetKey?: number;
  onProgress?: (percent: number) => void;
  /** Called once per attempt with the outcome and native frames played. */
  onEnd?: (outcome: GameOutcome, frames: number) => void;
}

const keys: Record<string, number> = {
  ArrowLeft: BUTTON.left, ArrowRight: BUTTON.right, ArrowUp: BUTTON.a,
  ShiftLeft: BUTTON.b, ShiftRight: BUTTON.b,
};
const FRAME_MS = 1000 / 60;

/** Browser-local World 1-1 for human play. The emulator never creates an audio device. */
export default function GameCanvas({ paused = false, resetKey = 0, onProgress, onEnd }: GameCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const settings = useRef({ paused, onProgress, onEnd });
  settings.current = { paused, onProgress, onEnd };
  const [status, setStatus] = useState('loading world 1-1');

  useEffect(() => {
    if (paused) return;
    const frame = requestAnimationFrame(() => canvasRef.current?.focus({ preventScroll: true }));
    return () => cancelAnimationFrame(frame);
  }, [paused]);

  useEffect(() => {
    let disposed = false;
    let raf = 0;
    let nes: Emulator | undefined;
    let removeKeys = () => {};

    async function start() {
      try {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const context = canvas.getContext('2d', { alpha: false });
        if (!context) throw new Error('your browser could not create a game canvas');
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
            context.putImageData(image, 0, 0);
          },
        }) as unknown as Emulator;
        nes = engine;
        bootMario(engine, rom);
        draw = true;
        engine.frame();
        setStatus('');

        let ended = false;
        let frames = 0;
        let best = 0;
        let reported = -1;
        let previous = 0;
        let accumulator = 0;

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
          if (![...held].some(code => keys[code] === button)) engine.buttonUp(1, button);
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

        const animate = (now: number) => {
          if (disposed) return;
          const delta = previous ? Math.min(now - previous, 80) : 0;
          previous = now;
          if (!settings.current.paused && !document.hidden && !ended) {
            accumulator += delta;
            let steps = 0;
            while (accumulator >= FRAME_MS && steps++ < 8) {
              accumulator -= FRAME_MS;
              draw = accumulator < FRAME_MS || steps === 8;
              engine.frame();
              frames++;
              const outcome = marioOutcome(engine);
              // Positions from the death animation or after the flag never count.
              if (!outcome) best = Math.max(best, marioProgress(engine));
              if (outcome) {
                release();
                ended = true;
                if (outcome === 'complete') best = 100;
                settings.current.onProgress?.(best);
                settings.current.onEnd?.(outcome, frames);
                break;
              }
            }
            const rounded = Math.floor(best * 10) / 10;
            if (!ended && rounded !== reported) {
              reported = rounded;
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
        if (!disposed) setStatus(error instanceof Error ? error.message : 'the game could not be loaded');
      }
    }
    void start();
    return () => {
      disposed = true;
      cancelAnimationFrame(raf);
      removeKeys();
      if (nes) releaseButtons(nes);
    };
  }, [resetKey]);

  return (
    <div className="game-canvas">
      <canvas
        ref={canvasRef}
        width={NES_WIDTH}
        height={NES_HEIGHT}
        tabIndex={0}
        aria-label="world 1-1. left and right arrows move, up jumps, shift runs"
        onPointerDown={() => canvasRef.current?.focus({ preventScroll: true })}
      />
      {status && <div role="status" className="game-status">{status}</div>}
    </div>
  );
}
