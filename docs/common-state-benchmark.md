# common state benchmark

the state cohort uses privileged current-viewport ram terrain and motion, including
tile ids that may not yet be rendered or revealed. the frozen term visible refers
to viewport scope. no offscreen or future-buffer lookahead or rollout is provided

all 22 models receive one frozen compact observation, the same 12 native button
choices and a 4-frame hold for all 22 model/provider pairs. each has 3 fresh
prespecified attempts on world 1-1, with a 6,000-native-frame cap and 1 life

only a complete set of 3 independently replayed, valid attempts gets a mean
progress score. missing or technical results leave the model pending. a native
flag is required for 100%; death animation and invalid coordinates cannot add
progress. best clear is the fastest completed attempt, in native frames / 60;
completed counts and mean completed time are shown separately. api waits do not
enter game time or progress

common image calibration is pending. image development runs and the earlier
selected state clears remain available as history, outside these means

## check the published evidence offline

run these from a source checkout after the main README setup. they make no model
calls and need no key or private experiment files

```sh
.venv/bin/python -m benchmark.common_state_release --verify-public results
.venv/bin/python -m benchmark.verify_common_state_release
.venv/bin/python -m benchmark.verify_common_state_v2
```

the public check rebuilds the actual request hashes, validates native responses,
replays every recorded input and frame checkpoint, and recomputes the scores and
three-run means. the controller definition is
[common_profiles/state-compact-v2.json](../benchmark/common_profiles/state-compact-v2.json)

## run a new evaluation

these commands create a new registration and new results. they do not extend or
replace the published cohort. `plan`, `audit` and `select` make no model calls;
`execute` makes paid requests using `OPENROUTER_API_KEY`

```sh
# freeze and check every model's input contract before gameplay
.venv/bin/python -m benchmark.common_state_run_v2 plan --phase preflight --output benchmark/runs/common-preflight
.venv/bin/python -m benchmark.common_state_run_v2 execute --output benchmark/runs/common-preflight
.venv/bin/python -m benchmark.common_state_run_v2 audit --output benchmark/runs/common-preflight

# independently check the fixed four-model calibration and its native-clear gate
.venv/bin/python -m benchmark.common_state_run_v2 plan --phase pilot --preflight benchmark/runs/common-preflight/summary.json --output benchmark/runs/common-pilot
.venv/bin/python -m benchmark.common_state_run_v2 execute --output benchmark/runs/common-pilot
.venv/bin/python -m benchmark.common_state_run_v2 audit --output benchmark/runs/common-pilot
.venv/bin/python -m benchmark.common_state_run_v2 select --output benchmark/runs/common-pilot

# freeze all 66 fresh attempts before making their requests
.venv/bin/python -m benchmark.common_state_evaluation plan --output benchmark/runs/common-evaluation --calibration benchmark/runs/common-pilot --preflight benchmark/runs/common-preflight
.venv/bin/python -m benchmark.common_state_evaluation execute --output benchmark/runs/common-evaluation
.venv/bin/python -m benchmark.common_state_evaluation audit --output benchmark/runs/common-evaluation
```

the roster, provider pins, controller sources, native budget and exact repeat IDs
are locked before execution. the emulator seed is 0 for each attempt; repeat IDs
are separate attempts on the same level. state actions use the provider's native
choice directly. models requiring a json object receive the same observation text
inside `observation_text`

use the same command and output directory to resume. an uncertain interrupted
request stops for inspection and is never silently resent. changing a source,
provider, registration or budget requires a fresh output directory. run the full
audit after the workers have finished

## export and billing

for a complete, audited new cohort:

```sh
.venv/bin/python -m benchmark.common_state_results --output benchmark/runs/common-evaluation --destination /tmp/mario-common-export
```

the separate release adapter for the published cohort can project a captured
subset of closed, audited attempts without changing its frozen worker or counting
pilot results. it retains all 22 prescribed rows and leaves incomplete means null

billing enrichment is separate and uses read-only generation metadata:

```sh
.venv/bin/python -m benchmark.common_billing --output benchmark/runs/common-evaluation --completed-only
```

complete actual charges and complete byok list-price estimates have separate
fields. estimates are marked `~`; a missing receipt or required billing component
leaves the total unknown. retries count as attempts. private ledgers and generation
metadata stay outside the published dataset
