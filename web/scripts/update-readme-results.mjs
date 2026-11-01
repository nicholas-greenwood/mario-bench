// Node 24 reads the same TypeScript selector used by the website.
import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { formatRunCost, parseDataset, unavailableProgress } from '../lib/data.ts';

const begin = '<!-- BEGIN GENERATED RESULTS -->';
const end = '<!-- END GENERATED RESULTS -->';
const root = new URL('../../', import.meta.url);
const escape = value => String(value).replaceAll('|', '\\|').replaceAll('\n', ' ');

export function renderResults(index) {
  const published = parseDataset(index).observations;
  if (published.some(run => run.level !== '1-1')) throw new Error('README tables currently cover world 1-1 only');
  const rawById = new Map([...index.examples, ...(index.observations ?? []), ...(index.technical_diagnostics ?? [])].map(run => [run.id, run]));
  const lines = [begin, '',
    `${published.length} published runs, matching the website's all runs view, on world 1-1`,
    'individual development runs use different settings; these are not model averages or a ranking', '',
    'the json retest is a separate retrospective run; its overlapping prefix is evidence only',
    '[serialization diagnostics and prefix](results/diagnostics/openai-state-serialization.json)', '',
    'cost is usd; ~ includes a byok list-price estimate, and missing billing is shown as -', ''];
  for (const [track, title] of [['state', 'state'], ['image', 'pixels only']]) {
    const runs = published.filter(run => run.track === track).sort((a, b) =>
      (b.progressPct ?? -1) - (a.progressPct ?? -1)
      || (a.clearSeconds ?? Infinity) - (b.clearSeconds ?? Infinity)
      || a.id.localeCompare(b.id));
    lines.push(`### ${title}`, '',
      '| model | observed progress | clear time (game s) | cost (usd) | evidence |',
      '| --- | ---: | ---: | ---: | --- |');
    for (const run of runs) {
      const raw = rawById.get(run.id);
      if (run.completed && (run.progressPct !== 100 || raw.verified !== true || run.clearSeconds === null)) {
        throw new Error(`${run.id}: completion requires verified 100% and a clear time`);
      }
      if (!run.completed && run.progressPct === 100) throw new Error(`${run.id}: failed run cannot score 100%`);
      const progress = run.progressPct === null ? unavailableProgress(run.status)
        : `${run.progressPct.toFixed(2)}%${/abort/.test(run.status) ? ' (aborted)' : ''}`;
      const seconds = run.completed ? run.clearSeconds.toFixed(2) : '-';
      const links = [raw.replay_href && `[replay](results/${raw.replay_href})`,
        `[trace](results/${raw.trace_href})`, `[profile](results/${raw.profile_href})`].filter(Boolean).join(' · ');
      lines.push(`| ${escape(run.name.toLowerCase())} | ${progress} | ${seconds} | ${formatRunCost(run) ?? '-'} | ${links} <!-- run:${run.id} --> |`);
    }
    lines.push('');
  }
  return lines.join('\n') + end;
}

export function replaceResults(readme, generated) {
  const start = readme.indexOf(begin), finish = readme.indexOf(end);
  if (start < 0 || finish < start) throw new Error('README generated-results markers are missing');
  return readme.slice(0, start) + generated + readme.slice(finish + end.length);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const readmeUrl = new URL('README.md', root);
  const index = JSON.parse(await readFile(new URL('results/index.json', root), 'utf8'));
  const before = await readFile(readmeUrl, 'utf8');
  const after = replaceResults(before, renderResults(index));
  if (process.argv.includes('--check')) {
    if (before !== after) throw new Error('README results are stale; run npm --prefix web run update:readme');
    console.log('README results match the website published runs');
  } else {
    await writeFile(readmeUrl, after);
    console.log('updated README results from the website published runs');
  }
}
