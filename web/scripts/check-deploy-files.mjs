// Check the source archive boundary without reading any real secrets.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';

const sandbox = await mkdtemp(path.join(tmpdir(), 'mario-deploy-filter-'));
try {
  await writeFile(path.join(sandbox, '.gitignore'), await readFile(new URL('../../.vercelignore', import.meta.url)));
  execFileSync('git', ['init', '--quiet', sandbox]);
  const included = ['README.md', '.vercelignore', 'web/app/page.tsx', 'web/scripts/update-readme-results.mjs', 'results/index.json', 'results/replays/example.mp4'];
  const excluded = ['.env', 'web/.env.local', '.venv/bin/python', 'playground/private.json', '.vercel/project.json', 'web/node_modules/example.js', 'web/.next/server.js', 'web/public/benchmark-data/index.json', 'web/public/game/mario.nes'];
  const candidates = [...included, ...excluded];
  const output = execFileSync('git', ['-c', 'core.excludesFile=/dev/null', '-C', sandbox, 'check-ignore', '--no-index', '--stdin'], { input: candidates.join('\n') + '\n', encoding: 'utf8' });
  const ignored = new Set(output.trim().split('\n'));
  for (const file of included) assert.ok(!ignored.has(file), `required build input excluded: ${file}`);
  for (const file of excluded) assert.ok(ignored.has(file), `private or generated input included: ${file}`);
  console.log('deployment filter includes README, website and results; excludes secrets, research and generated assets');
} finally {
  await rm(sandbox, { recursive: true, force: true });
}
