'use client';

import { useState } from 'react';
import { useBenchmark } from './benchmark-provider';

type SortKey = 'score' | 'cost' | 'runs';
type ResultRow = { id: string; name: string; score: number; cost: number; runs: number; player?: boolean };

export default function ResultsTable() {
  const { models, leftModel, rightModel, activeSlot, selectModel, hasPlayed, playerBestScore, playerRuns } = useBenchmark();
  const [sort, setSort] = useState<{ key: SortKey; ascending: boolean }>({ key: 'score', ascending: false });
  const rows: ResultRow[] = models.map(model => ({ id: model.id, name: model.name, score: model.score, cost: model.cost, runs: model.runs.length }));
  if (hasPlayed) rows.push({ id: 'player', name: 'you', score: playerBestScore, cost: 0, runs: playerRuns, player: true });
  const ranked = [...rows].sort((a, b) => b.score - a.score);
  const ranks = new Map(ranked.map((row, index) => [row.id, index + 1]));
  const sorted = [...ranked].sort((a, b) => (a[sort.key] - b[sort.key]) * (sort.ascending ? 1 : -1));
  const changeSort = (key: SortKey) => setSort(current => ({ key, ascending: current.key === key ? !current.ascending : key === 'cost' }));
  const sortDirection = (key: SortKey) => sort.key === key ? sort.ascending ? 'ascending' as const : 'descending' as const : undefined;
  const selectedId = activeSlot === 'left' ? leftModel.id : rightModel.id;

  return <section className="leaderboard" aria-label="results">
    <div className="leaderboard-head"><h2>results</h2><span className="demo-badge">demo data</span></div>
    <div className="table-container"><table className="results-table">
      <thead><tr>
        <th className="rank-cell" scope="col">#</th>
        <th scope="col">model</th>
        <th className="score-cell" scope="col" aria-sort={sortDirection('score')}><button className={sort.key === 'score' ? 'sorted' : ''} onClick={() => changeSort('score')}>score</button></th>
        <th className="cost-column" scope="col" aria-sort={sortDirection('cost')}><button className={sort.key === 'cost' ? 'sorted' : ''} onClick={() => changeSort('cost')}>cost / run</button></th>
        <th className="runs-column" scope="col" aria-sort={sortDirection('runs')}><button className={sort.key === 'runs' ? 'sorted' : ''} onClick={() => changeSort('runs')}>runs</button></th>
      </tr></thead>
      <tbody>{sorted.map(row => <tr key={row.id} className={row.player ? 'player-row' : row.id === selectedId ? 'selected-row' : ''} onClick={row.player ? undefined : () => selectModel(row.id)}>
        <td className="rank-cell">{String(ranks.get(row.id)).padStart(2, '0')}</td>
        <td>{row.player ? <span className="model-cell">you</span> : <button className="model-cell" onClick={event => { event.stopPropagation(); selectModel(row.id); }} aria-label={`watch ${row.name} best replay`}>{row.name}</button>}</td>
        <td className="score-cell">{row.score.toFixed(1)}%</td>
        <td className="cost-column">${row.cost.toFixed(3)}</td>
        <td className="runs-column">{row.runs}</td>
      </tr>)}</tbody>
    </table></div>
  </section>;
}
