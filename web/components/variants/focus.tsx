'use client';

import {
  ArenaControls,
  HumanSeat,
  Leaderboard,
  SiteNav,
  ReplayCard,
} from '../benchmark-ui';
import { useBenchmark } from '../benchmark-provider';
import './focus.css';

export default function Focus() {
  const { openPlay } = useBenchmark();

  return (
    <div className="variant-focus">
      <div className="focus-shell">
        <SiteNav />
        <main className="focus-main">
          <section className="focus-stage" id="arena-stage" aria-label="two model replays and your game">
            <div className="focus-model focus-model-left"><ReplayCard side="left" /></div>
            <div className="focus-model focus-model-right"><ReplayCard side="right" /></div>
            <div className="focus-player"><HumanSeat idle={!openPlay} /></div>
            <div className="focus-transport"><ArenaControls /></div>
          </section>
          <section className="focus-results" aria-label="benchmark results">
            <Leaderboard />
          </section>
        </main>
      </div>
    </div>
  );
}
