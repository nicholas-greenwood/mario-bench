'use client';

import { Colophon, HumanPane, Intro, Masthead, ReplayPane, Transport } from '../benchmark-ui';
import ResultsTable from '../results-table';
import { BenchmarkProvider } from '../benchmark-provider';
import type { Dataset } from '../../lib/data';
import './focus.css';

export default function Focus({ dataset }: { dataset: Dataset }) {
  return (
    <BenchmarkProvider dataset={dataset}>
      <div className="page">
        <Masthead />
        <main className="layout">
          <Intro />
          <section className="watch" aria-label="2 recorded model runs">
            <div className="pair">
              <ReplayPane side="a" />
              <ReplayPane side="b" />
            </div>
            <Transport />
          </section>
          <HumanPane />
          <ResultsTable />
        </main>
        <Colophon />
      </div>
    </BenchmarkProvider>
  );
}
