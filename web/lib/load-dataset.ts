import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { parseDataset } from './data';

/** Reads the prepared static copy at build time; run `npm run prepare-assets` first. */
export async function loadDataset() {
  const file = path.join(process.cwd(), 'public', 'benchmark-data', 'index.json');
  try {
    return parseDataset(JSON.parse(await readFile(file, 'utf8')));
  } catch (error) {
    throw new Error(`could not read ${file}. run npm run prepare-assets first`, { cause: error });
  }
}
