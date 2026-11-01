# mario bench

give a decision model the controller and watch it try to beat mario

pick a model, show it screenshots or game state, and let it choose every move

[demo](https://mario.nicholasg.com/) · deployment coming soon

![pplx decider v1.2 clearing mario world 1-1](docs/media/first-clear.gif)

*pplx decider v1.2 reaching the flag in a recorded, verified run, replayed at 2x speed*

pplx decider, drex max, mercury decide and liquid d1 ultra have verified 1-1
clears using game state

no model has cleared it from screenshots alone yet

these are separate development runs with different settings, not a leaderboard

[recorded results and replays](results/README.md) · [website data guide](docs/website-data.md)

## try it locally

with python 3.13 and `uv` installed, run from the repository root:

```sh
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python -r requirements.lock.txt
uv pip install --python .venv/bin/python --no-deps -e .
cp .env.example .env
```

add your `OPENROUTER_API_KEY` to `.env`, then start the viewer:

```sh
.venv/bin/python -m prototype.server
```

open [localhost:8765](http://127.0.0.1:8765). choose a model and input mode, then
press **1 decision** or **run 10 decisions**. it starts paused and muted, so
nothing spends api credits until you ask it to play. the key stays server-side

pause to inspect a decision, or reset for a fresh attempt. the viewer runs
locally; you don't need the hosted demo. `--help` lists model and budget options

## run a benchmark

the roster has 22 state models, with 14 currently passing the screenshot checks

see [models.json](benchmark/models.json) for compatible model/provider pairs

```sh
# show the plan without sending requests
.venv/bin/python -m benchmark.run

# exercise the runner without an api key or paid calls
.venv/bin/python -m benchmark.run --policy fake --frames 96 --output benchmark/runs/offline --execute

# run a real model, with 3 attempts declared in advance
.venv/bin/python -m benchmark.run --models perplexity/pplx-decider-v1.2 --trials 3 --output benchmark/runs/pplx-state --execute

# use pixels only
.venv/bin/python -m benchmark.run --track image --output benchmark/runs/pixels

# select all 4 world 1 levels
.venv/bin/python -m benchmark.run --levels 1-1 1-2 1-3 1-4
```

`--execute` makes paid requests when using the default `openrouter` policy

commands without it only print the plan

paid runs use your openrouter credits and account limits. `--models id ...`,
`--frames` and `--trials` let you choose a smaller run before spending credits

results include a frozen `manifest.json`, request and action logs, input images
where applicable, and `summary.json`. repeat the same command and output path to
resume. use a new directory after changing code, models or settings. uncertain
interrupted requests stop for inspection rather than silently spending twice

## how the score works

the headline is **average progress, from 0 to 100**. dying keeps the legitimate
progress already earned; only confirmed native game completion gets 100. average
all declared attempts within each level, then give each level equal weight

world 1-1 has a calibrated start and finish. worlds 1-2, 1-3 and 1-4 run too,
but their progress mappings are still uncalibrated

their incomplete runs show unknown progress, and a combined progress score stays
unavailable until those mappings are validated

clear rate is reported separately. the speedrun score uses native gameplay frames
for completed runs only, with lower being better. it reports the completed-only
median, nominal seconds (`frames / 60`) and attempt counts. failed runs have no
speedrun score. api waiting time and internet speed never affect a game score

this is a public development benchmark. prompts and controls have been tuned on
1-1; verified clears show that the models can do it under their recorded settings

a final shared configuration, repeated evaluation and held-out levels are still
ahead. selected successful attempts aren't an aggregate score

## under the hood

the game freezes while the model thinks. by default, it chooses 1 of 12 complete
controller inputs, held for exactly 4 native frames

the default budget is 6,000 native frames and 1,500 decisions. first death ends
the attempt

- `state` gives the model compact visible geometry, motion and recent positions
  derived from game memory
- `image` gives it pixels only, plus declared buttons, frame number and action
  interval. no memory-derived positions, velocities, terrain or object lists

screenshots are lossless pngs, enlarged from 256x240 to 512x480 with nearest
neighbour sampling. model/provider identity is checked, and each worker owns its
own emulator. malformed model actions count as failed play; infrastructure
failures leave the comparable aggregate unavailable instead of becoming game losses

<details>
<summary>protocol, replay checks and reproducibility</summary>

for 1-1, progress is `100 * (furthest_valid_x - 40) / (3161 - 40)`

valid progress is sampled every native frame and excludes death, falling and
transition animations. unsuccessful attempts are capped at 99.9. unknown route
mappings never reuse another level's denominator

compare models under the same prompts, input mode, controls, starts, cadence and
budgets. don't pick each model's best run. a single deterministic start doesn't
support a general mario ranking, and image transport acceptance doesn't prove
that pixels influenced a decision

run the offline checks and audit a saved run:

```sh
.venv/bin/python -m prototype.verify_paused
.venv/bin/python -m benchmark.verify_scoring
.venv/bin/python -m benchmark.smoke
.venv/bin/python -m benchmark.audit benchmark/runs/offline
```

these cover paused inference, exact stepping, image isolation, score boundaries,
worker isolation, replay hashes and recovery. `benchmark.verify_clear` verifies
recorded development clears against native requests, actions and game frames

export the current development candidate's code, prompts, roster and runtime:

```sh
.venv/bin/python -m benchmark.release --output benchmark/runs/current-candidate/release-manifest.json
```

read the [full protocol](benchmark/PROTOCOL.txt) and
[machine-readable settings](benchmark/protocol.json) for the scoring contract

</details>

## repository

- `prototype/` contains the emulator, decision client and local viewer
- `benchmark/` contains the runner, scoring, protocol and replay tools

`requirements.lock.txt` pins the environment. secrets, environments, run logs,
screenshots and recordings stay ignored. `playground/` is local scratch space

this repository includes no rom files or game binaries; the emulator dependency
supplies its game data

[dependency notices](docs/third-party-notices.md)
