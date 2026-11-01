// Run with Node 24: node --disable-warning=MODULE_TYPELESS_PACKAGE_JSON scripts/check-game.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { NES } from 'jsnes';
import { BUTTON, DemoDriver, bootMario, marioOutcome, marioProgress, marioX, releaseButtons } from '../lib/game.ts';

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

for (const [seed, expected] of [[0, 'complete'], [1, 'death']]) {
  bootMario(nes, rom);
  const driver = new DemoDriver(seed);
  let outcome = null;
  let frame = 0;
  for (; frame < 1800 && !outcome; frame++) {
    driver.step(nes);
    nes.frame();
    outcome = marioOutcome(nes);
  }
  assert.equal(outcome, expected);
  assert.equal(nes.cpu.mem[0x75c], 0, 'stop before leaving World 1-1');
  console.log(`seed ${seed}: ${outcome} at x=${marioX(nes)} after ${frame} frames`);
}
assert.equal(nes.opts.onAudioSample, null, 'no audio output is connected');
assert.equal(nes.opts.emulateSound, false);
bootMario(nes, rom);
assert.equal(marioX(nes), 40, 'restart returns to the beginning');
console.log('game smoke check passed: boot, walk, run/jump, restart, death, flag and mute');
