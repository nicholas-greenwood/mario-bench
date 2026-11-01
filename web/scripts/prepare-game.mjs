import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { unzipSync } from 'fflate';

const destination = new URL('../public/game/mario.nes', import.meta.url);
const assetHash = 'ec299b990e8bfee8ba46e3f61d63b2e1ae5b8a2e431de84e2e4bbd692dc53586';
const packageHash = 'e61e2b451ed6d841dff3fc5c8238031529c6932f567ebfb32e6dad17b75957e3';
const packageURL = 'https://files.pythonhosted.org/packages/a6/ea/2f81cec9c3095d746f706f906e33baefd92d833cc4f54d795ce1d6cb457d/gym_super_mario_bros-9.1.0-py3-none-any.whl';
const entry = 'gym_super_mario_bros/_roms/super-mario-bros.nes';
const hash = bytes => createHash('sha256').update(bytes).digest('hex');

try {
  if (hash(await readFile(destination)) === assetHash) process.exit(0);
} catch (error) {
  if (error.code !== 'ENOENT') throw error;
}

const response = await fetch(packageURL, { signal: AbortSignal.timeout(30_000) });
if (!response.ok) throw new Error(`Game-data dependency returned HTTP ${response.status}`);
const archive = new Uint8Array(await response.arrayBuffer());
if (hash(archive) !== packageHash) throw new Error('Game-data package checksum mismatch');
const game = unzipSync(archive)[entry];
if (!game || hash(game) !== assetHash) throw new Error('Game asset checksum mismatch');
await mkdir(new URL('../public/game/', import.meta.url), { recursive: true });
await writeFile(destination, game);
console.log('Prepared the pinned World 1-1 game asset');
