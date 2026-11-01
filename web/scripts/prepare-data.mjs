// Copies the published benchmark results into an ignored static folder.
// All *_href fields in index.json are relative, so the folder is served as-is.
import { createHash } from 'node:crypto';
import { cp, mkdir, readFile, rm, stat } from 'node:fs/promises';

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

const index = JSON.parse(await readFile(new URL('index.json', destination), 'utf8'));
for (const example of index.examples) {
  for (const key of ['replay', 'trace', 'profile']) {
    const href = example[`${key}_href`];
    const expected = example[`${key}_sha256`];
    if (!href || !expected) continue;
    const actual = hash(await readFile(new URL(href, destination)));
    if (actual !== expected) throw new Error(`${example.id}: ${key} checksum mismatch`);
  }
}
console.log(`Prepared ${index.examples.length} benchmark examples in public/benchmark-data`);
