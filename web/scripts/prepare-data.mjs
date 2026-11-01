// Copies the published benchmark results into an ignored static folder.
// All *_href fields in index.json are relative, so the folder is served as-is.
import { createHash } from 'node:crypto';
import { cp, mkdir, readFile, rm, stat } from 'node:fs/promises';
import { readPublishedIndex } from '../lib/read-results.mjs';

const source = new URL('../../results/', import.meta.url);
const destination = new URL('../public/benchmark-data/', import.meta.url);
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const exists = url => stat(url).then(() => true, () => false);

if (!(await exists(new URL('index.json', source)))) {
  if (await exists(new URL('index.json', destination))) process.exit(0);
  throw new Error('results/index.json was not found. Build from the repository checkout so ../results is available.');
}

await rm(destination, { recursive: true, force: true });
await mkdir(destination, { recursive: true });
await cp(source, destination, { recursive: true, filter: path => !path.endsWith('README.md') });

const index = await readPublishedIndex(new URL('index.json', destination));
for (const example of [...index.examples, ...(index.observations ?? []), ...(index.technical_diagnostics ?? []), ...[index.common_benchmark, index.common_image_benchmark].flatMap(cohort => cohort?.trials ?? []), ...[index.common_benchmark,index.common_image_benchmark].flatMap(cohort=>cohort?.technical_recovery?.continuations??[])]) {
  for (const key of ['replay', 'trace', 'profile']) {
    const href = example[`${key}_href`];
    const expected = example[`${key}_sha256`];
    if (!href || !expected) continue;
    const actual = hash(await readFile(new URL(href, destination)));
    if (actual !== expected) throw new Error(`${example.id}: ${key} checksum mismatch`);
  }
}
const replays = new Set([...index.examples, ...(index.observations ?? [])].map(record => record.replay_href).filter(Boolean));
console.log(`Prepared ${index.observations?.length ?? 0} observations and ${replays.size} replay videos in public/benchmark-data`);
