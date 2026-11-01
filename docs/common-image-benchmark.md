# common image progress baseline

the published image track uses a frozen 16-model, 48-slot schedule. each model
has three prescribed local sampler seeds: 101, 102 and 103. each attempt starts
world 1-1 from reset with one life and a 6000-native-frame budget

models receive actual current and past full-frame pixels and their own declared
controller history. no ram observations are sent. the controller holds each
choice for 7 native frames, stopping at native episode termination. all 12 native
action probabilities are transformed with temperature 0.05, without masks, then
sampled once per valid action. api waiting time never advances the game

this is an explicit progress baseline. three earlier positive-clear calibration
gates failed and remain negative evidence. the historical seed-0 mechanics clear
is not a scored final trial. a model mean requires three fresh valid, native-
replayed trials; technical failures and missing trials leave its mean pending

## reproduce

the executable sources and evidence are included in the package. source hashes,
provider pins, rom hash, exact trial ids and controls are in the public protocol

```sh
.venv/bin/python -m benchmark.verify_common_image_final_results
.venv/bin/python -m benchmark.verify_common_image_final_release
.venv/bin/python -m benchmark.common_image_final_run --help
```

the separate release adapter audits copied closed logs and preserves all 48
registered slots. it does not change the frozen worker or send model requests

```sh
.venv/bin/python -m benchmark.common_image_final_release --snapshot SNAPSHOT --preflight PREFLIGHT --destination EXPORT --jobs 4
```

`results/common-image/index.json` contains the published cutoff, all 16 rows and
actual trial evidence. replay files run at native 60 fps without audio. billing
is separate: missing receipts or incomplete attempt coverage stay unknown
