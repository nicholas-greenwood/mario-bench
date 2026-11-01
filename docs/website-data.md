# website data

`results/index.json` is the entry point for real recorded gameplay
it includes both `state` and strictly pixels-only `image` examples, with a model
catalogue, exact action traces and silent mp4 replays

this is a development checkpoint, not a leaderboard. the examples were selected
from many experiments with different prompts, controls, cadence and image history
`data_class` is `selected_development_examples`, `matched_cohort` is false, and
`comparable_aggregate` is null. show those limits with the results

## expanded observations

`observations` contains 22 common-profile state attempts and 16 best-observed
pixels-only development runs. `examples` preserves the original 8 replay showcases
and their stable ids. use `observations` for expanded tables; new records have
compact traces and profiles, with null replay links where no video was exported
api-aborted state attempts have null scores and separate observed progress
stagnation stops are explicitly aborted. no comparable aggregate is supplied

## files

- `results/index.json`: website cards, per-run progress, completion, speedrun,
  experiment settings, verification and asset references
- `results/models.json`: 22 state models and 14 currently image-compatible
  model/provider pairs. compatibility is separate from game performance
- `results/traces/*.json`: exact native answers, button sequences, prompt/action
  contracts and state/screen hashes for offline replay
- `results/replays/*.mp4`: silent gameplay at native game speed, with api waiting
  removed. pixel enlarging uses nearest neighbour
- `results/profiles/*.json`: byte-stable prompt, controller and observation settings
- `benchmark/profiles/`: frozen pure observation/controller adapters for these profiles
- `results/schema.json`: the version 1 index format

all `*_href` fields resolve relative to the directory containing `index.json`
serve the complete directory together, or rewrite these references in your adapter
this repository doesn't mount these assets on the website automatically

```js
// after publishing results/ at your chosen static base path
const base = '/benchmark-data/';
const data = await fetch(base + 'index.json').then(response => response.json());
const example = data.examples[0];
const replayUrl = base + example.replay_href;
```

## card fields

| field | meaning |
| --- | --- |
| `id` | stable example identifier |
| `model_id`, `display_name` | model catalogue key and label |
| `returned_model`, `provider` | identities actually returned by the api |
| `mode` | `state` or pixels-only `image` |
| `progress_pct` | this episode's normalised furthest valid progress |
| `completed` | native completion flag, required for 100 |
| `native_frames`, `decisions` | gameplay frames and model decisions |
| `speedrun_score_native_frames` | native frames to completion, lower is better; null on failure |
| `nominal_game_seconds_to_completion` | completion frames / 60; null on failure |
| `experiment_config` | exact profile, cadence, history, seed and contract hash |
| `controls`, `trace_href` | controller adapter and full action trace |
| `replay_href`, `replay_sha256` | recorded gameplay and its file hash |
| `source_hashes`, `verified`, `input_audit` | source provenance, native replay and input audit |

render null as unavailable, never as zero. each selected attempt has its own
progress and completion clock; these are not a model average or a speedrun median
research attempt counts are disclosed separately in `search_context`, with each
search's scope and snapshot. don't derive a win rate from the selected examples

for a matched benchmark cohort, the primary score averages every declared repeat
within a level, then gives each level equal weight. speedrun uses the median
native completion frames per level, accompanied by attempt and completion counts
failures have no speedrun value. neither measure uses api latency or internet speed

only 1-1 has a calibrated progress mapping. the other world 1 levels keep null
endpoints and cannot supply a comparable progress aggregate yet

## verification

```sh
.venv/bin/python -m benchmark.public_results
```

this checks provider identities and native choice distributions, expands those
choices directly to controls, and replays every native frame. all recorded state
and screen hashes must match, along with completion, valid progress and speedrun
there are no api calls. the image input audits also checked the original requests
against actual screenshots; private requests and memory snapshots stay local

`--render` recreates the mp4s from the public actions. it never asks a model to
play again. the hashes in `index.json` identify the checked-in replay files

## technical retests

`technical_diagnostics` retains transport corrections separately from `observations`
luna's json-object retest preserves the same evidence text, rules and questions
the old api-aborted row stays unchanged. its retrospective stagnation prefix has
null final progress and 17.81% observed progress; the longer full diagnostic reached
34.76% and is not comparable with that prefix. both have null speedrun values
