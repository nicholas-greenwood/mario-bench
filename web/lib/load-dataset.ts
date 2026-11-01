import path from 'node:path';
import { parseDataset } from './data';
import { readPublishedIndex } from './read-results.mjs';

/** Reads the prepared static copy at build time; run `npm run prepare-assets` first. */
export async function loadDataset() {
  const file = path.join(process.cwd(), 'public', 'benchmark-data', 'index.json');
  try {
    return parseDataset(await readPublishedIndex(file));
  } catch (error) {
    throw new Error(`could not read ${file}. run npm run prepare-assets first`, { cause: error });
  }
}
