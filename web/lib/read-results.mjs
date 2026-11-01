import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

/** Resolve the optional cohort identically for the website and README. */
export async function readPublishedIndex(file) {
  const filename = path.resolve(file instanceof URL ? fileURLToPath(file) : file);
  const index = JSON.parse(await readFile(filename, 'utf8'));
  if (typeof index.common_cohort_href === 'string') {
    const directory = path.dirname(filename);
    const cohortFile = path.resolve(directory, index.common_cohort_href);
    if (!cohortFile.startsWith(directory + path.sep)) throw new Error('common cohort path escapes the published dataset');
    const cohort = JSON.parse(await readFile(cohortFile, 'utf8'));
    if (cohort.schema_version !== 1 || !cohort.common_benchmark) throw new Error(`${cohortFile}: invalid common cohort schema`);
    index.common_benchmark = cohort.common_benchmark;
  }
  return index;
}
