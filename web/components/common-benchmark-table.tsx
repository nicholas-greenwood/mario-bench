'use client';

import { useState } from 'react';
import { DATA_BASE, formatRunCost, formatSeconds, trackLabel } from '../lib/data';
import type { CommonBenchmark, CommonResult } from '../lib/common-benchmark';
import { useBenchmark } from './benchmark-provider';

type Column = { key: string; label: string; numeric?: boolean; value: (row: CommonResult) => string | number | null };
const columns: Column[] = [
  { key: 'model', label: 'model', value: row => row.name.toLowerCase() },
  { key: 'track', label: 'input', value: row => trackLabel(row.track) },
  { key: 'score', label: 'mean progress', numeric: true, value: row => row.meanProgressPct },
  { key: 'speed', label: 'best clear (game s)', numeric: true, value: row => row.bestClearSeconds },
  { key: 'cost', label: 'mean cost/run', numeric: true, value: row => row.meanCostUsd ?? row.meanCostEstimateUsd },
  { key: 'coverage', label: 'valid runs', numeric: true, value: row => row.validTrials },
];

export default function CommonBenchmarkTable({ cohort, showRuns }: { cohort: CommonBenchmark; showRuns: (ids: string[]) => void }) {
  const { runs, watch } = useBenchmark();
  const [sort, setSort] = useState({ key: 'score', ascending: false });
  const column = columns.find(candidate => candidate.key === sort.key)!;
  const rows = [...cohort.rows].sort((a, b) => {
    const av = column.value(a), bv = column.value(b);
    if (av === null && bv !== null) return 1;
    if (bv === null && av !== null) return -1;
    const value = av === null || bv === null ? 0 : typeof av === 'string' || typeof bv === 'string' ? String(av).localeCompare(String(bv)) : av - bv;
    return value * (sort.ascending ? 1 : -1) || a.name.localeCompare(b.name) || a.track.localeCompare(b.track);
  });
  return (
    <div className="table-scroll">
      <table className="runs" data-common-benchmark data-common-protocol={cohort.protocolSha256}>
        <caption className="visually-hidden">mean progress over 3 prespecified evaluation runs per model and input</caption>
        <thead><tr>
          {columns.map(item => <th key={item.key} className={item.numeric ? 'num' : undefined} scope="col" aria-sort={sort.key === item.key ? sort.ascending ? 'ascending' : 'descending' : 'none'}>
            <button onClick={() => setSort(current => ({ key: item.key, ascending: current.key === item.key ? !current.ascending : item.key !== 'score' }))} data-sorted={sort.key === item.key || undefined}>
              {item.label}<span className="sort-mark" aria-hidden="true">{sort.key === item.key && sort.ascending ? '↑' : '↓'}</span>
            </button>
          </th>)}
          <th scope="col">evidence</th>
        </tr></thead>
        <tbody>{rows.map(row => {
          const representative = runs.find(run => run.id === row.representativeRunId);
          return <tr key={row.id} data-common-model={row.modelId} data-track={row.track}>
            <td><span className="run-name"><span>{row.name}</span><span className="run-id mono">{row.modelId}</span></span></td>
            <td data-label="input">{trackLabel(row.track)}</td>
            <td className="num" data-label="mean progress">{row.meanProgressPct === null ? <span className="faint">pending</span> : `${row.meanProgressPct.toFixed(2)}%`}</td>
            <td className="num" data-label="best clear (game s)">{formatSeconds(row.bestClearSeconds) ?? '–'}</td>
            <td className="num" data-label="mean cost/run">{formatRunCost({ costUsd: row.meanCostUsd, costEstimateUsd: row.meanCostEstimateUsd }) ?? '–'}</td>
            <td className="num" data-label="valid runs">{row.validTrials}/3</td>
            <td data-label="evidence">
              <button onClick={() => showRuns(row.recordedTrialIds)} disabled={!row.recordedTrialIds.length}>{row.recordedTrialIds.length} runs</button>
              <details><summary>details</summary>
                <p>{row.coverageComplete ? `${row.nCompleted}/3 completed; mean completed time ${formatSeconds(row.meanCompletedSeconds) ?? 'unavailable'}` : 'mean pending until all 3 prescribed results are fully confirmed'}</p>
                {representative && <button onClick={() => watch(representative.id)}>watch representative demo</button>}
                {row.recordedTrialIds.map(id => {
                  const trial = cohort.trials.find(candidate => candidate.id === id);
                  const lineage = trial?.recovery_lineage as { originalTraceHref: string; proofHref: string } | undefined;
                  return typeof trial?.trace_href === 'string' ? <p key={id}><a href={DATA_BASE + trial.trace_href} target="_blank" rel="noreferrer">{id}{lineage ? ' (technical continuation)' : ''}</a>{lineage && <> · <a href={DATA_BASE + lineage.originalTraceHref} target="_blank" rel="noreferrer">original abort</a> · <a href={DATA_BASE + lineage.proofHref} target="_blank" rel="noreferrer">proof</a></>}</p> : null;
                })}
              </details>
            </td>
          </tr>;
        })}</tbody>
      </table>
    </div>
  );
}
