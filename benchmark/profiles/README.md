# frozen development profiles

these snapshots preserve the current clears and selected pixels-only near misses
alongside [the public results](../../results/README.md). they are separate from
the runner's shared `joint-visible-v1` default and aren't a comparable leaderboard

- `state_v1.py`: frozen compact, phase and exposed-surface observers used by the
  4 state clears. each `*-state-clear.json` contains its exact rules, questions,
  cadence and controller adapter
- `image_v1.py`: exact pixels-only input and controller builders for pplx edges,
  jev's four questions, luna's fixed crop and pplx's declared A-duration variant
- `edgezoom_v1.py`: exact current-first, fixed-crop image builder and controller
  for the mercury and mammoth partial runs
- `verification.json`: recorded request/choice round-trip counts and source hashes

all builders are pure: they don't access an emulator, credentials or the network
state builders accept the current observation; image builders accept only actual
screen pixels and declared control history. A-duration memory counts the model's
own button choices, with no hidden game-state signal

```python
from benchmark.profiles import load_profile, state_text

profile = load_profile('liquid-state-clear')
# current_state is supplied by the caller; this doesn't advance the game
text = state_text(profile, current_state)
questions = profile['contract']['questions']
```

use `image_v1.profile_request` and `decode_profile_response` for its named frozen
profiles, or `edgezoom_v1.build_request` and `decode_response` for edgezoom
`benchmark.public_results.decode_answers` preserves the state profiles' joint or
factored native-choice composition

## executable profiles

`benchmark.run --profile` supports these 3 selected controllers:

| profile | input and controller | model/provider |
| --- | --- | --- |
| `pplx-state-clear` | compact state, joint 12-choice controller, cadence 4 | dated pplx v1.2 / perplexity |
| `mammoth-pixels-first-clear` | `memoryfinish240-v1`, current screen/crops and 1 past screen; initial cadence 6, then model-selected 2/4/6/8 | dated mammoth 1 / baseten |
| `pplx-pixels-sampled-clear-t005-seed0` | `pixels-edge-pplx-c7-v1`, current and 1 past screen; cadence 7; native probability sampling at temperature 0.05, seed 0 | dated pplx v1.2 / perplexity |

each pins world 1-1, its original serialization, exact request model and provider
with fallbacks disabled. `--track`, `--cadence`, `--models` and custom rosters
cannot replace the frozen contract. other profile files remain pure builder or
historical evidence snapshots, without a runnable cli adapter

```sh
python -m benchmark.run --profile pplx-state-clear
python -m benchmark.run --profile mammoth-pixels-first-clear
python -m benchmark.run --profile pplx-pixels-sampled-clear-t005-seed0
```

these print a plan. add `--execute` to make paid requests with
`OPENROUTER_API_KEY` from the environment or repository `.env`. `--trials N`
declares repeated attempts in advance; each starts the same deterministic level
and resets the sampler to seed 0. they sample model variability, not new layouts

mammoth's duration question appears after any prior uninterrupted identical
model input has lasted at least 120 native frames. the generic finish rule appears
after such a sequence reaches 240 frames. these gates use the full declared
control history, without positions, contact sensors, progress or future state

the sampled profile validates all 12 native probabilities before any draw or
native step. it preserves the original response and samples the frozen
`p**(1/T)` distribution in alphabetical choice order with python's seeded rng.
no actions are masked. request retries consume no draws. replay reconstructs
prior draws and declared controls; a committed response can recover its next
draw without another request

the default fresh envelope is 6,000 native frames, 1 life per attempt, and
`ceil(frame_budget / minimum_hold)` decisions. use `--max-native-frames N` or
`--frames N` to declare another native cap. the last hold executes
`min(chosen_hold, remaining_budget)` frames, stopping sooner on death or flag.
the ledger records chosen duration, bounded duration and actual native frames

the controller/profile and the fresh envelope are hashed separately in
`manifest.json`. historical winning episodes used research envelopes that can
differ: mammoth's was 18,000 frames and 1,600 decisions. the new derived cap for
18,000 frames is 9,000 decisions. this preserves the original requests and
native choices through its 1,916-frame clear, without claiming identical whole
experiment settings or guaranteed repeat success

the 3 controllers are selected development profiles, not one matched benchmark
configuration. continue a run only with the identical source, profile and
envelope. extending a budget or changing any setting requires a new output
directory. an interrupted request without a committed result is marked
infrastructure-incomplete and is never silently resent

## offline checks

```sh
python -m benchmark.verify_profiles
python -m benchmark.run --profile mammoth-pixels-first-clear --policy fake --max-native-frames 24 --output benchmark/runs/profile-offline --execute
python -m benchmark.audit benchmark/runs/profile-offline
```

the verification uses only public traces and the local emulator. it checks all
302 state, 467 mammoth and 268 sampled pplx request hashes, native choices,
sampler draws, every action's state/screen hashes and actual flag completion.
it also checks malformed distributions, bounded holds and safe resume at
response/action/checkpoint boundaries. it makes no paid or network requests

817 historical image-profile requests, 269 edgezoom requests and 996 state-profile
requests reproduced their original body hashes exactly. their native choices also
expanded to the recorded controls. jev's early adapter was reconstructed from its
immutable payloads and verified by exact round trips; it isn't presented as an
archived historical source file

future experiments should use a new profile version instead of editing these
