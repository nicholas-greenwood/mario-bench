/** The local demo uses an actual NES emulator. No audio device is ever created. */
export type GameOutcome = 'death' | 'complete';
export const NES_WIDTH = 256;
export const NES_HEIGHT = 240;
/** Calibrated World 1-1 endpoints, matching the benchmark evaluator. */
export const START_X = 40;
export const GOAL_X = 3161;

export const BUTTON = { a: 0, b: 1, select: 2, start: 3, up: 4, down: 5, left: 6, right: 7 } as const;
export interface Emulator {
  cpu: { mem: number[] };
  /** jsnes paints an 8-pixel black overscan border unless this is false. */
  ppu: { clipToTvSize: boolean; palTable: { curTable: Uint32Array; loadDefaultPalette(): void; makeTables(): void; setEmphasis(value: number): void } };
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

/**
 * jsnes's NTSC table renders the sky purple. Its default table is much closer to the
 * recorded replays, but is packed as RGB while frames are BGR, so swap the channels.
 */
function applyReplayPalette(nes: Emulator) {
  const palette = nes.ppu.palTable;
  palette.loadDefaultPalette();
  palette.curTable = palette.curTable.map(c => ((c & 0xff) << 16) | (c & 0xff00) | ((c >> 16) & 0xff));
  palette.makeTables();
  palette.setEmphasis(0);
}

/** Skip the title and pre-level card, then return at the first controllable frame. */
export function bootMario(nes: Emulator, rom: string) {
  nes.loadROM(rom);
  // loadROM recreates the PPU; show the full 256x240 frame, like the recorded replays.
  nes.ppu.clipToTvSize = false;
  applyReplayPalette(nes);
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

/** Progress before the flag is capped at 99.9; only a real flag completion scores 100. */
export function marioProgress(nes: Emulator) {
  return Math.min(99.9, Math.max(0, (marioX(nes) - START_X) / (GOAL_X - START_X) * 100));
}

export function marioOutcome(nes: Emulator): GameOutcome | null {
  const ram = nes.cpu.mem;
  if (ram[0xe] === 0xb || ram[0xe] === 6 || ram[0xb5] > 1) return 'death';
  const flag = Array.from({ length: 6 }, (_, i) => ram[0x16 + i]).includes(0x31);
  if ((flag && ram[0x1d] === 3) || ram[0x770] === 2 || ram[0x75c] > 0 || ram[0x75f] > 0) return 'complete';
  return null;
}
