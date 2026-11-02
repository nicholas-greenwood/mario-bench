// Node 24 reads the same TypeScript selector used by the website.
import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { formatRunCost, parseDataset, unavailableProgress } from '../lib/data.ts';
import { readPublishedIndex } from '../lib/read-results.mjs';

const begin = '<!-- BEGIN GENERATED RESULTS -->';
const end = '<!-- END GENERATED RESULTS -->';
const root = new URL('../../', import.meta.url);
const escape = value => String(value).replaceAll('|', '\\|').replaceAll('\n', ' ');

export function renderResults(index) {
  const dataset = parseDataset(index), published = dataset.observations;
  if (published.some(run => run.level !== '1-1')) throw new Error('README tables currently cover world 1-1 only');
  const rawById = new Map([...index.examples, ...(index.observations ?? []), ...(index.technical_diagnostics ?? []),
    ...dataset.commonBenchmarks.flatMap(cohort => cohort.trials).map(trial => ({ ...trial, verified: trial.native_replay_verified })),
  ].map(run => [run.id, run]));
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
        `[trace](results/${raw.trace_href})`, `[profile](results/${raw.profile_href})`,
        raw.recovery_lineage && `[original abort](results/${raw.recovery_lineage.originalTraceHref})`,
        raw.recovery_lineage && `[proof](results/${raw.recovery_lineage.proofHref})`].filter(Boolean).join(' · ');
      lines.push(`| ${escape(run.name.toLowerCase())} | ${progress} | ${seconds} | ${formatRunCost(run) ?? '-'} | ${links} <!-- run:${run.id} --> |`);
    }
    lines.push('');
  }
  if (!dataset.commonBenchmark) return lines.join('\n') + end;
  const benchmark = [begin, '',
    dataset.commonBenchmarks.length > 1 ? 'mean progress over 3 prespecified evaluation runs per model and input; state and image use separate frozen protocols' : 'mean progress over 3 prespecified evaluation runs per model and input, using the same frozen protocol',
    'pending means the 3 prescribed results are not fully confirmed; best clear is the fastest completed run',
    'mean cost/run requires complete billing for all 3 runs; ~ includes a byok list-price estimate',
    `[protocol and trial evidence](results/${index.common_cohort_href ?? 'index.json'})`, ''];
  if (dataset.commonBenchmark.stateOnly && !dataset.commonBenchmarks.some(cohort => cohort.imageOnly)) benchmark.push('common image track: calibration pending. image replays and history remain development runs', '');
  for (const cohort of dataset.commonBenchmarks) {
    const recovery = cohort.technicalRecovery;
    if (recovery) benchmark.push(`${cohort.imageOnly ? 'pixels: ' : ''}${recovery.resolved}/${recovery.planned} technical interruptions resolved under a separate registered authority; original attempts and verified continuation proofs remain linked`, '');
  }
  for (const [track, title] of [['state', 'state'], ['image', 'pixels only']]) {
    const cohorts = dataset.commonBenchmarks.filter(cohort => cohort.rows.some(row => row.track === track));
    if (!cohorts.length) continue;
    const rows = cohorts.flatMap(cohort => cohort.rows).filter(row => row.track === track).sort((a, b) =>
      (b.meanProgressPct ?? -1) - (a.meanProgressPct ?? -1) || a.name.localeCompare(b.name));
    benchmark.push(`### ${title}`, '');
    if (cohorts.some(cohort => cohort.imageOnly)) benchmark.push('shared image progress baseline; native clears are outcomes. earlier failed calibration gates remain failed; historical mechanics evidence is not a scored final trial', `[image protocol and trial evidence](results/${index.common_image_cohort_href ?? index.common_cohort_href ?? 'index.json'})`, '');
    benchmark.push(
      '| model | mean progress | best clear (game s) | mean cost/run (usd) | valid runs | evidence |',
      '| --- | ---: | ---: | ---: | ---: | --- |');
    for (const row of rows) {
      const evidence = row.recordedTrialIds.map((id, position) => {
        const trial = rawById.get(id);
        return trial?.trace_href ? `[run ${position + 1}](results/${trial.trace_href})` : null;
      }).filter(Boolean).join(' · ') || '-';
      benchmark.push(`| ${escape(row.name.toLowerCase())} | ${row.meanProgressPct === null ? row.availability === 'unavailable' ? 'unavailable' : 'pending' : `${row.meanProgressPct.toFixed(2)}%`} | ${row.bestClearSeconds === null ? '-' : row.bestClearSeconds.toFixed(2)} | ${formatRunCost({ costUsd: row.meanCostUsd, costEstimateUsd: row.meanCostEstimateUsd }) ?? '-'} | ${row.validTrials}/3 | ${evidence} |`);
    }
    benchmark.push('', '<details>', '<summary>completed-run timing</summary>', '');
    for (const row of rows) benchmark.push(`- ${escape(row.name.toLowerCase())}: ${row.coverageComplete ? `${row.nCompleted}/3 completed; mean completed time ${row.meanCompletedSeconds === null ? 'unavailable' : `${row.meanCompletedSeconds.toFixed(2)} game s`}` : row.availability === 'unavailable' ? 'unavailable (technical)' : 'pending'}`);
    benchmark.push('', '</details>', '');
  }
  benchmark.push('<details>', '<summary>individual runs and development history</summary>', '', ...lines.slice(1), '</details>', '', end);
  return benchmark.join('\n');
}

export function replaceResults(readme, generated) {
  const start = readme.indexOf(begin), finish = readme.indexOf(end);
  if (start < 0 || finish < start) throw new Error('README generated-results markers are missing');
  return readme.slice(0, start) + generated + readme.slice(finish + end.length);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const readmeUrl = new URL('README.md', root);
  const index = await readPublishedIndex(new URL('results/index.json', root));
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
