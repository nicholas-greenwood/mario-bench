'use client';

import { useMemo, useState } from 'react';
import { useBenchmark } from './benchmark-provider';
import { formatProgress, formatSeconds, trackLabel, type Result } from '../lib/data';

type Value = string | number | null;
type Column = { key: string; label: string; title?: string; numeric?: boolean; first: 'ascending' | 'descending'; value: (run: Result) => Value };

const statusLabel = (run: Result) => run.completed ? 'cleared' : run.status === 'api_abort' ? 'incomplete' : /abort/.test(run.status) ? 'aborted' : /death|game_over/.test(run.status) ? 'not cleared' : run.status.replaceAll('_', ' ');

const COLUMNS: Column[] = [
  { key: 'model', label: 'model', first: 'ascending', value: run => run.name.toLowerCase() },
  { key: 'track', label: 'input', first: 'ascending', value: run => trackLabel(run.track) },
  { key: 'progress', label: 'progress', numeric: true, first: 'descending', value: run => run.progressPct },
  { key: 'clear', label: 'clear time', title: 'native frames to the flag / 60, excluding api waits', numeric: true, first: 'ascending', value: run => run.clearSeconds },
  { key: 'frames', label: 'frames', title: 'native frames played', numeric: true, first: 'ascending', value: run => run.nativeFrames },
  { key: 'decisions', label: 'decisions', numeric: true, first: 'ascending', value: run => run.decisions },
  { key: 'cadence', label: 'cadence', title: 'native frames per decision', numeric: true, first: 'ascending', value: run => run.cadence },
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

export default function ResultsTable() {
  const { runs, dataset, watch, slots, activeSide } = useBenchmark();
  const [view, setView] = useState<'observations' | 'replays'>(dataset.observations.length ? 'observations' : 'replays');
  const results: Result[] = view === 'observations' ? dataset.observations : runs;
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
        <h2 id="results-title" className="section-label">development results</h2>
        <div className="result-views" aria-label="result datasets"><button aria-pressed={view === 'observations'} onClick={() => setView('observations')}>all observations ({dataset.observations.length})</button><button aria-pressed={view === 'replays'} onClick={() => setView('replays')}>replay showcases ({runs.length})</button></div>
        <p className="results-note">{view === 'observations' ? `${dataset.observations.filter(run => run.track === 'state').length} state attempts under a shared input profile; ${dataset.observations.filter(run => run.track === 'image').length} selected pixels runs across different settings. aborted runs retain observed progress; incomplete API runs have no score.` : `${runs.length} selected development replays with different prompts, cadence and image history.`} a development snapshot rather than a ranking. no pixels run has reached the flag yet.</p>
      </div>
      <div className="table-scroll">
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
                  </td>
                  <td>{trackLabel(run.track)}</td>
                  <td className="num">{run.progressPct === null ? <span className="faint" aria-label="score unavailable">–</span> : formatProgress(run.progressPct)}</td>
                  <td className="num">{formatSeconds(run.clearSeconds) ?? <span className="faint" aria-label="not cleared">–</span>}</td>
                  <td className="num">{run.nativeFrames?.toLocaleString('en-GB') ?? '–'}</td>
                  <td className="num">{run.decisions ?? '–'}</td>
                  <td className="num">{run.cadence ?? <span className="faint" aria-label="unknown">–</span>}</td>
                  <td>{statusLabel(run)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="results-hint faint">recorded runs play in pane {activeSide}; other model names open their action trace</p>
    </section>
  );
}
