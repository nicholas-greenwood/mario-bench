# website data

`results/index.json` is the entry point. the website and README both use
`readPublishedIndex` and `parseDataset`; they resolve the optional
`common_cohort_href` and `common_image_cohort_href` before selecting rows

## common evaluation

`common-state/index.json` contains the frozen state manifest, all prescribed
repeat IDs, actual published trials and all 22 model rows. a model's mean requires
3 valid, independently replayed attempts with matching protocol, provider,
budget and seeds. missing or technical results leave the mean pending

mean progress is the primary score. best clear is the fastest native completion
among the 3 attempts, in frames / 60. completed counts and mean completed time are
separate details. api waiting time affects neither score. only world 1-1 has a
calibrated progress mapping; other world 1 endpoints remain null

the state track uses privileged current-viewport ram terrain and motion, which
can include unrevealed tile ids. the frozen term visible refers to viewport scope,
not rendered pixels. there is no offscreen or future-buffer lookahead or rollout
the separate common image progress baseline uses actual current and past full
frames, fixed 7-frame actions and a seeded temperature-0.05 native probability
sampler. its 16 model rows require three valid prescribed runs each. the earlier
failed calibration gates remain failed; historical clear evidence is not scored
as a final evaluation trial. state and image means use separate frozen protocols

`common_benchmark_status` reports the published cutoff and complete/pending
counts. do not turn pending means into zero or claim that a partial publication
is a finished 22-model ranking

## individual history

`examples`, `observations` and `technical_diagnostics` preserve development
runs and retrospective transport tests. settings differ, so their selected
outcomes are not comparable model averages. original IDs and replay paths stay
stable. repeated evaluation attempts remain distinct even when they produce
identical gameplay

luna's full json-object retest is a separate actual run. its overlapping
stagnation prefix is evidence only and is not another attempt. the original api
error remains in history. fresh common evaluation repeats are separate from all
of these earlier records

## files and paths

- `results/index.json`: entry point, legacy records and optional cohort reference
- `results/common-state/index.json`: frozen state evaluation manifest, trials and means
- `results/common-image/index.json`: separate image baseline, trials and means
- `results/models.json`: model/provider catalogue; compatibility is separate from performance
- `results/traces/` and `results/common-state/traces/`: native answers, actual inputs,
  request/attempt proofs and state/screen hashes
- `results/replays/` and `results/common-state/replays/`: silent native-speed mp4s
- `results/profiles/` and `results/common-state/profiles/`: frozen contracts and source hashes
- `benchmark/common_profiles/` and `benchmark/profiles/`: executable controller definitions
- `results/schema.json`: entry-point and development-record json schema

all asset `*_href` fields use the `results/` root as their base, including fields
inside the nested cohort file. the build copies the complete directory to
`/benchmark-data/`; serve that directory together

```js
const base = '/benchmark-data/';
const index = await fetch(base + 'index.json').then(response => response.json());
const cohort = index.common_cohort_href
  ? await fetch(base + index.common_cohort_href).then(response => response.json())
  : null;
const trial = cohort?.common_benchmark.trials[0];
const replayUrl = trial?.replay_href ? base + trial.replay_href : null;
```

## scores and billing

individual `progress_pct` is normalised furthest valid progress. 100 requires
native completion. `native_frames_to_completion` in cohort trials and
`speedrun_score_native_frames` in development records are null on failure

`cost_usd` is a complete actual total. `cost_estimate_usd` is a separate complete
byok list-price estimate, displayed with `~`. coverage includes every request,
retry and auxiliary stage, with explicit source-attempt counts. missing receipts
or billing components leave totals unknown. a model's mean cost requires all 3
complete scopes; never display missing billing as free or zero

## verification

```sh
.venv/bin/python -m benchmark.common_state_release --verify-public results
.venv/bin/python -m benchmark.public_results
npm --prefix web run check:readme
```

the common verifier reconstructs request hashes and native controls, checks every
recorded frame checkpoint, recomputes outcomes and validates the three-run means
it needs no private ledgers, credentials or model calls. private generation IDs,
request logs and account metadata remain outside the public dataset

see [the common state workflow](common-state-benchmark.md) for a new evaluation
