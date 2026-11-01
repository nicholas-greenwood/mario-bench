# recorded benchmark results

[index.json](index.json) is the entry point. its `common_cohort_href` points to the
fresh, preregistered state evaluation in [common-state/index.json](common-state/index.json)
a model gets a mean only after all 3 prescribed attempts pass native replay;
incomplete models remain unavailable or pending, never zero

`common_image_cohort_href` points to the separate 16-model image progress
baseline. its means require three fresh valid trials; failed calibration gates
remain failed and historical mechanics evidence is not scored.

`examples`, `observations` and
`technical_diagnostics` retain the earlier development runs, including verified
state and pixels clears. those settings differ and their selected outcomes are
not model averages

all asset references use the `results/` root as their base. the
[website data guide](../docs/website-data.md) describes the shared website/README
selector, billing fields and evidence links

verify without a key or model calls:

```sh
.venv/bin/python -m benchmark.common_state_release --verify-public results
.venv/bin/python -m benchmark.public_results
```

the first command checks the published common cohort; the second checks the
legacy development traces. both replay actual native inputs. replays are silent
and exclude api waiting time. failed attempts have no completion-time score
