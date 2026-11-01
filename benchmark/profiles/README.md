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
factored native-choice composition. these are functions for reproducing the
contracts, not additional `benchmark.run --profile` options

817 historical image-profile requests, 269 edgezoom requests and 996 state-profile
requests reproduced their original body hashes exactly. their native choices also
expanded to the recorded controls. jev's early adapter was reconstructed from its
immutable payloads and verified by exact round trips; it isn't presented as an
archived historical source file

future experiments should use a new profile version instead of editing these
