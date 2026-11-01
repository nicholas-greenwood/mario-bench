/** The local demo uses an actual NES emulator. No audio device is ever created. */
export type GameOutcome = 'death' | 'complete';
export type GameMode = 'replay' | 'human';
export const NES_WIDTH = 256;
export const NES_HEIGHT = 240;
export const COURSE_DISTANCE = 3168;

export const BUTTON = { a: 0, b: 1, select: 2, start: 3, up: 4, down: 5, left: 6, right: 7 } as const;
export interface Emulator {
  cpu: { mem: number[] };
  frame(): void;
  loadROM(data: string): void;
  buttonDown(player: number, button: number): void;
  buttonUp(player: number, button: number): void;
}

let romPromise: Promise<string> | undefined;
export function loadMarioROM(): Promise<string> {
  romPromise ??= fetch('/game/mario.nes').then(async (response) => {
    if (!response.ok) throw new Error('The local game could not be loaded.');
    const bytes = new Uint8Array(await response.arrayBuffer());
    let data = '';
    for (let i = 0; i < bytes.length; i += 8192) {
      data += String.fromCharCode(...bytes.subarray(i, i + 8192));
    }
    return data;
  }).catch((error) => { romPromise = undefined; throw error; });
  return romPromise;
}

export function releaseButtons(nes: Emulator) {
  for (let button = 0; button < 8; button++) nes.buttonUp(1, button);
}

/** Skip the title and pre-level card, then return at the first controllable frame. */
export function bootMario(nes: Emulator, rom: string) {
  nes.loadROM(rom);
  releaseButtons(nes);
  for (let frame = 0; frame < 90; frame++) nes.frame();
  nes.buttonDown(1, BUTTON.start);
  nes.frame();
  nes.buttonUp(1, BUTTON.start);
  for (let frame = 0; frame < 600; frame++) {
    nes.frame();
    const ram = nes.cpu.mem;
    if (ram[0x770] === 1 && ram[0x772] === 3 && ram[0xe] === 8 && ram[0x86] > 0) return;
  }
  throw new Error('The local game did not reach World 1-1.');
}

export function marioX(nes: Emulator) {
  return nes.cpu.mem[0x6d] * 256 + nes.cpu.mem[0x86];
}

export function marioProgress(nes: Emulator) {
  return Math.min(100, Math.max(0, (marioX(nes) - 40) / COURSE_DISTANCE * 100));
}

export function marioOutcome(nes: Emulator): GameOutcome | null {
  const ram = nes.cpu.mem;
  if (ram[0xe] === 0xb || ram[0xe] === 6 || ram[0xb5] > 1) return 'death';
  const flag = Array.from({ length: 6 }, (_, i) => ram[0x16 + i]).includes(0x31);
  if ((flag && ram[0x1d] === 3) || ram[0x770] === 2 || ram[0x75c] > 0 || ram[0x75f] > 0) return 'complete';
  return null;
}

function tile(nes: Emulator, x: number, y: number) {
  if (y < 32 || y > 239) return 0;
  const page = (Math.floor(x / 256) & 1) * 208;
  return nes.cpu.mem[0x500 + page + Math.floor((y - 32) / 16) * 16 + (Math.floor(x / 16) & 15)];
}

/** A deterministic scripted demo controller; these runs are not model submissions. */
export class DemoDriver {
  private jumpFrames = 0;
  private releaseFrames = 0;
  private seed: number;
  constructor(seed = 0) { this.seed = seed; }

  step(nes: Emulator) {
    const ram = nes.cpu.mem;
    const x = marioX(nes);
    const y = ram[0xce];
    const grounded = ram[0x1d] === 0;
    nes.buttonDown(1, BUTTON.right);
    nes.buttonDown(1, BUTTON.b);

    if (this.jumpFrames > 0) {
      nes.buttonDown(1, BUTTON.a);
      this.jumpFrames--;
      if (this.jumpFrames === 0) this.releaseFrames = 5;
      return;
    }
    nes.buttonUp(1, BUTTON.a);
    if (this.releaseFrames > 0) { this.releaseFrames--; return; }
    if (!grounded) return;

    const lead = 40 + Math.abs(this.seed % 3) * 4;
    const obstacle = [18, 30, lead].some((dx) => tile(nes, x + dx, y + 6) !== 0 || tile(nes, x + dx, y + 20) !== 0);
    const gap = tile(nes, x + lead + 8, 216) === 0 && y >= 160;
    let enemy = false;
    for (let i = 0; i < 5; i++) {
      if (!ram[0xf + i] || ram[0x16 + i] >= 0x15) continue;
      const dx = ram[0x6e + i] * 256 + ram[0x87 + i] - x;
      if (dx > -10 && dx < 65 && Math.abs(ram[0xcf + i] - y) < 40) enemy = true;
    }
    if (obstacle || gap || enemy) {
      this.jumpFrames = 25 + Math.abs(this.seed % 4);
      nes.buttonDown(1, BUTTON.a);
    }
  }
}
