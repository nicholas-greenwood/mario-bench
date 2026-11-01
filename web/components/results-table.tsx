'use client';

import { useMemo, useState } from 'react';
import { useBenchmark } from './benchmark-provider';
import { formatRunCost, formatProgress, formatSeconds, isApiError, trackLabel, type Result } from '../lib/data';
import CommonBenchmarkTable from './common-benchmark-table';

type Value = string | number | null;
type Column = { key: string; label: string; title?: string; numeric?: boolean; first: 'ascending' | 'descending'; value: (run: Result) => Value };

const statusLabel = (run: Result) => run.completed ? 'cleared' : isApiError(run.status) ? 'api error' : /abort/.test(run.status) ? 'aborted' : /death|game_over/.test(run.status) ? 'not cleared' : run.status.replaceAll('_', ' ');

const COLUMNS: Column[] = [
  { key: 'model', label: 'model', first: 'ascending', value: run => run.name.toLowerCase() },
  { key: 'track', label: 'input', first: 'ascending', value: run => trackLabel(run.track) },
  { key: 'progress', label: 'progress', numeric: true, first: 'descending', value: run => run.progressPct },
  { key: 'clear', label: 'clear time', title: 'native frames to the flag / 60, excluding api waits', numeric: true, first: 'ascending', value: run => run.clearSeconds },
  { key: 'cost', label: 'cost', title: 'inference spend for this run in usd; ~ marks a complete byok list-price estimate', numeric: true, first: 'ascending', value: run => run.costUsd ?? run.costEstimateUsd },
  { key: 'decisions', label: 'decisions', numeric: true, first: 'ascending', value: run => run.decisions },
  { key: 'status', label: 'status', first: 'ascending', value: statusLabel },
];

/** Missing values go last in either direction. */
function compare(a: Value, b: Value) {
  if (a === null || b === null) return 0;
  return typeof a === 'string' || typeof b === 'string' ? String(a).localeCompare(String(b)) : a - b;
}

const natural = (a: Result, b: Result) =>
  (b.progressPct ?? -1) - (a.progressPct ?? -1)
  || (a.clearSeconds ?? Infinity) - (b.clearSeconds ?? Infinity)
  || a.name.localeCompare(b.name)
  || a.track.localeCompare(b.track);

function costTitle(run: Result) {
  const details = [run.costUsd !== null ? `recorded inference spend: $${run.costUsd} usd`
    : run.costEstimateUsd !== null ? `estimated inference spend: $${run.costEstimateUsd} usd; byok uses openrouter activity list prices`
    : 'complete run billing unavailable'];
  if (run.openrouterCostUsd !== null) details.push(`openrouter credits: $${run.openrouterCostUsd} usd`);
  if (run.upstreamCostUsd !== null) details.push(`direct byok provider spend: $${run.upstreamCostUsd} usd`);
  if (run.upstreamCostEstimateUsd !== null) details.push(`estimated direct byok provider spend: $${run.upstreamCostEstimateUsd} usd`);
  return details.join('; ');
}

export default function ResultsTable() {
  const { runs, dataset, watch, slots, activeSide } = useBenchmark();
  const [view, setView] = useState<'benchmark' | 'observations' | 'replays'>(dataset.commonBenchmark ? 'benchmark' : dataset.observations.length ? 'observations' : 'replays');
  const [evidenceIds, setEvidenceIds] = useState<string[] | null>(null);
  const results: Result[] = view === 'observations' ? dataset.observations.filter(run => evidenceIds === null || evidenceIds.includes(run.id)) : runs;
  const playable = new Set(runs.map(run => run.id));
  const [sort, setSort] = useState<{ key: string; direction: 'ascending' | 'descending' }>({ key: 'progress', direction: 'descending' });

  const sorted = useMemo(() => {
    const column = COLUMNS.find(c => c.key === sort.key)!;
    const sign = sort.direction === 'ascending' ? 1 : -1;
    return [...results].sort((a, b) => {
      const av = column.value(a), bv = column.value(b);
      if (av === null && bv !== null) return 1;
      if (bv === null && av !== null) return -1;
      return compare(av, bv) * sign || natural(a, b);
    });
  }, [results, sort]);

  const toggle = (column: Column) => setSort(current => ({
    key: column.key,
    direction: current.key === column.key ? (current.direction === 'ascending' ? 'descending' : 'ascending') : column.first,
  }));

  return (
    <section className="results" aria-labelledby="results-title">
      <div className="results-head">
        <h2 id="results-title" className="section-label">results</h2>
        <div className="result-views" aria-label="result datasets">
          {dataset.commonBenchmark && <button aria-pressed={view === 'benchmark'} onClick={() => setView('benchmark')}>benchmark ({dataset.commonBenchmarks.reduce((sum, cohort) => sum + cohort.rows.length, 0)})</button>}
          <button aria-pressed={view === 'observations'} onClick={() => { setView('observations'); setEvidenceIds(null); }}>all runs ({dataset.observations.length})</button>
          <button aria-pressed={view === 'replays'} onClick={() => { setView('replays'); setEvidenceIds(null); }}>replays ({runs.length})</button>
        </div>
        <p className="results-note">{view === 'benchmark' ? `${dataset.commonBenchmarks.length > 1 ? 'state and image use separate frozen protocols. ' : ''}mean progress over 3 prespecified runs with the same frozen protocol per input. pending means the 3 prescribed results are not fully confirmed. best clear is the fastest completed run.` : view === 'observations' ? 'development runs, not a ranking. aborted runs show observed progress; incomplete runs have no score.' : 'selected runs with different settings, not a ranking.'} cost is usd; ~ includes a byok list-price estimate. missing billing is unknown.</p>
        {view === 'benchmark' && dataset.commonBenchmark?.stateOnly && !dataset.commonBenchmarks.some(cohort => cohort.imageOnly) && <p className="results-note">common image track: calibration pending. image replays and history remain development runs.</p>}
        {view === 'benchmark' && dataset.commonBenchmark?.technicalRecovery && <p className="results-note">{dataset.commonBenchmark.technicalRecovery.resolved}/8 technical continuations independently verified. original aborts and continuation proofs remain linked; incomplete billing stays unknown.</p>}
        {evidenceIds !== null && view === 'observations' && <p className="results-note">showing {results.length} cohort runs <button onClick={() => setEvidenceIds(null)}>show all runs</button></p>}
      </div>
      {view === 'benchmark' && dataset.commonBenchmark ? <>{dataset.commonBenchmarks.map(cohort => <div key={cohort.protocolSha256}>
        {dataset.commonBenchmarks.length > 1 && <h3 className="section-label">{cohort.imageOnly ? 'pixels only' : 'state'}</h3>}
        {cohort.imageOnly && <p className="results-note">shared image progress baseline; a native clear is an outcome, not an entry requirement. earlier failed calibration gates remain failed. historical mechanics evidence is excluded from these fresh runs.</p>}
        <CommonBenchmarkTable cohort={cohort} showRuns={ids => { setEvidenceIds(ids); setView('observations'); }} />
      </div>)}</> : <div className="table-scroll">
        <table className="runs">
          <caption className="visually-hidden">selected development runs; choose a row to watch it in pane {activeSide}</caption>
          <thead>
            <tr>
              {COLUMNS.map(column => {
                const sorted = sort.key === column.key;
                return (
                  <th key={column.key} scope="col" className={column.numeric ? 'num' : undefined} aria-sort={sorted ? sort.direction : 'none'}>
                    <button onClick={() => toggle(column)} title={column.title} data-sorted={sorted || undefined}>
                      {column.label}
                      <span className="sort-mark" aria-hidden="true">{(sorted ? sort.direction : column.first) === 'ascending' ? '↑' : '↓'}</span>
                    </button>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {sorted.map(run => {
              const loaded = (['a', 'b'] as const).filter(side => slots[side] === run.id);
              return (
                <tr key={run.id} data-run-id={run.id} data-replay={playable.has(run.id) || undefined} onClick={playable.has(run.id) ? () => watch(run.id) : undefined}>
                  <td>
                    {playable.has(run.id) ? <button className="run-name" onClick={event => { event.stopPropagation(); watch(run.id); }} aria-label={`watch ${run.name}, ${trackLabel(run.track)} run, in pane ${activeSide}`}>
                      <span>{run.name}{loaded.length > 0 && <span className="loaded mono" aria-label={`in pane ${loaded.join(' and ')}`}>{loaded.join(' ')}</span>}</span>
                      <span className="run-id mono">{run.modelId}</span>
                    </button> : <a className="run-name" href={run.traceSrc} target="_blank" rel="noreferrer" aria-label={`inspect ${run.name}, ${trackLabel(run.track)} action trace`}><span>{run.name}</span><span className="run-id mono">{run.modelId} · trace ↗</span></a>}
                    {run.recoveryLineage && <div className="run-id"><a href={run.recoveryLineage.originalTraceSrc} target="_blank" rel="noreferrer">original abort</a> · <a href={run.recoveryLineage.childTraceSrc} target="_blank" rel="noreferrer">continuation</a> · <a href={run.recoveryLineage.proofSrc} target="_blank" rel="noreferrer">proof</a></div>}
                  </td>
                  <td data-label="input">{trackLabel(run.track)}</td>
                  <td className="num" data-label="progress">{run.progressPct === null ? <span className="faint" aria-label="score unavailable">–</span> : formatProgress(run.progressPct)}</td>
                  <td className="num" data-label="clear time">{formatSeconds(run.clearSeconds) ?? <span className="faint" aria-label="not cleared">–</span>}</td>
                  <td className="num" data-label="cost" title={costTitle(run)}>
                    {formatRunCost(run) ?? <span className="faint" aria-label="cost unknown">–</span>}
                  </td>
                  <td className="num" data-label="decisions">{run.decisions ?? '–'}</td>
                  <td data-label="status">{statusLabel(run)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>}
    </section>
  );
}
