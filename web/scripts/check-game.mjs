// Run with Node 24: node --disable-warning=MODULE_TYPELESS_PACKAGE_JSON scripts/check-game.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { NES } from 'jsnes';
import { BUTTON, GOAL_X, START_X, bootMario, marioOutcome, marioProgress, marioX, releaseButtons } from '../lib/game.ts';

const rom = readFileSync(new URL('../public/game/mario.nes', import.meta.url), 'binary');
const nes = new NES({ emulateSound: false });
bootMario(nes, rom);
assert.equal(marioX(nes), 40);
assert.equal(nes.cpu.mem[0x75c], 0);
assert.equal(nes.cpu.mem[0x75f], 0);
assert.equal(marioOutcome(nes), null);
assert.equal(marioProgress(nes), 0);

nes.buttonDown(1, BUTTON.right);
for (let frame = 0; frame < 30; frame++) nes.frame();
const walkingX = marioX(nes);
assert.ok(walkingX > 40, 'right moves Mario without holding run');
releaseButtons(nes);

bootMario(nes, rom);
for (let frame = 0; frame < 40; frame++) nes.frame();
assert.equal(marioX(nes), 40, 'human game stays still without input');

bootMario(nes, rom);
nes.buttonDown(1, BUTTON.right);
nes.buttonDown(1, BUTTON.b);
for (let frame = 0; frame < 30; frame++) nes.frame();
assert.ok(marioX(nes) > walkingX, 'holding run moves farther than walking');
nes.buttonDown(1, BUTTON.a);
for (let frame = 0; frame < 20; frame++) nes.frame();
assert.ok(nes.cpu.mem[0xce] < 176, 'jump lifts Mario while running');
releaseButtons(nes);

// Running right without jumping meets the first goomba; progress must stop at the death frame.
bootMario(nes, rom);
nes.buttonDown(1, BUTTON.right);
let outcome = null;
let best = 0;
for (let frame = 0; frame < 900 && !outcome; frame++) {
  nes.frame();
  outcome = marioOutcome(nes);
  if (!outcome) best = Math.max(best, marioProgress(nes));
}
releaseButtons(nes);
assert.equal(outcome, 'death');
assert.ok(best > 0 && best < 20, `death recorded at ${best.toFixed(1)}%`);
console.log(`walk right: death at ${best.toFixed(1)}%`);

// Calibrated mapping: (x - 40) / (3161 - 40), never 100 without the flag.
assert.equal(START_X, 40);
assert.equal(GOAL_X, 3161);
nes.cpu.mem[0x6d] = Math.floor(1600 / 256); nes.cpu.mem[0x86] = 1600 % 256;
assert.ok(Math.abs(marioProgress(nes) - (1560 / 3121) * 100) < 1e-9);
nes.cpu.mem[0x6d] = Math.floor(3200 / 256); nes.cpu.mem[0x86] = 3200 % 256;
assert.equal(marioProgress(nes), 99.9);
assert.equal(nes.opts.onAudioSample, null, 'no audio output is connected');
assert.equal(nes.opts.emulateSound, false);
bootMario(nes, rom);
assert.equal(marioX(nes), 40, 'restart returns to the beginning');
console.log('game smoke check passed: boot, walk, run/jump, death, progress mapping, restart and mute');
