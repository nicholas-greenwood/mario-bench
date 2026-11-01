import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';

const canonical = value => value && typeof value === 'object' && !Array.isArray(value)
  ? Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])]))
  : Array.isArray(value) ? value.map(canonical) : value;
const digest = value => createHash('sha256').update(JSON.stringify(canonical(value)).replace(/[\u007f-\uffff]/g, char => `\\u${char.charCodeAt(0).toString(16).padStart(4, '0')}`)).digest('hex');

/** Proof attestations are computed from actual bytes, never accepted from JSON. */
export async function hydrateRecoveryProofs(index, readAsset) {
  const overlay = index.common_benchmark?.technical_recovery;
  if (!overlay) return index;
  for (const slot of overlay.manifest?.slots ?? []) {
    delete slot._computed_pin_sha256;
    if (slot.pin_payload && typeof slot.pin_payload === 'object') slot._computed_pin_sha256 = digest(slot.pin_payload);
  }
  for (const resolution of overlay.resolutions ?? []) {
    delete resolution.proof;
    delete resolution.proof_verified_sha256;
    if (typeof resolution.proof_href !== 'string' || !/^[a-f0-9]{64}$/.test(resolution.proof_sha256 ?? '')) continue;
    const bytes = await readAsset(resolution.proof_href);
    const hash = createHash('sha256').update(bytes).digest('hex');
    if (hash !== resolution.proof_sha256) throw new Error(`${resolution.proof_href}: recovery proof checksum mismatch`);
    resolution.proof = JSON.parse(Buffer.from(bytes).toString('utf8'));
    resolution.proof_verified_sha256 = hash;
  }
  return index;
}

/** Resolve the optional cohort identically for the website and README. */
export async function readPublishedIndex(file) {
  const filename = path.resolve(file instanceof URL ? fileURLToPath(file) : file);
  const index = JSON.parse(await readFile(filename, 'utf8'));
  for (const [hrefKey, valueKey] of [['common_cohort_href', 'common_benchmark'], ['common_image_cohort_href', 'common_image_benchmark']]) {
    if (typeof index[hrefKey] !== 'string') continue;
    const directory = path.dirname(filename);
    const cohortFile = path.resolve(directory, index[hrefKey]);
    if (!cohortFile.startsWith(directory + path.sep)) throw new Error('common cohort path escapes the published dataset');
    const cohort = JSON.parse(await readFile(cohortFile, 'utf8'));
    if (cohort.schema_version !== 1 || !cohort.common_benchmark) throw new Error(`${cohortFile}: invalid common cohort schema`);
    index[valueKey] = cohort.common_benchmark;
  }
  return hydrateRecoveryProofs(index, relative => {
    const directory = path.dirname(filename), asset = path.resolve(directory, relative);
    if (!asset.startsWith(directory + path.sep)) throw new Error('recovery proof path escapes the published dataset');
    return readFile(asset);
  });
}
