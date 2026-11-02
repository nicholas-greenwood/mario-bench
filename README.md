# mario bench

a benchmark for decision models playing super mario bros. models receive screenshots
or game state and choose controller inputs

[demo](https://mario.nicholasg.com/)

<img src="docs/media/first-clear-1x.gif" alt="pplx decider v1.2 clearing world 1-1" width="512" height="480">

*pplx decider v1.2, state input, replayed at 1x speed*

## results

<!-- BEGIN GENERATED RESULTS -->

mean progress over 3 prespecified evaluation runs per model and input; state and image use separate frozen protocols
pending means the 3 prescribed results are not fully confirmed; best clear is the fastest completed run
mean cost/run requires complete billing for all 3 runs; ~ includes a byok list-price estimate
[protocol and trial evidence](results/common-state/index.json)

5/8 technical continuations independently verified under a separate registered authority; original aborts and proofs remain linked

### state

| model | mean progress | best clear (game s) | mean cost/run (usd) | valid runs | evidence |
| --- | ---: | ---: | ---: | ---: | --- |
| perplexity/pplx-decider-v1.2 | 100.00% | 20.13 | - | 3/3 | [run 1](results/common-state/traces/state-v2-eval-20261101T201131691317Z-perplexity__pplx-decider-v1.2-repeat0.json) · [run 2](results/common-state/traces/state-v2-eval-20261101T201131691317Z-perplexity__pplx-decider-v1.2-repeat1.json) · [run 3](results/common-state/traces/state-v2-eval-20261101T201131691317Z-perplexity__pplx-decider-v1.2-repeat2.json) |
| liquid/d1-ultra | 60.87% | - | $0.00872 | 3/3 | [run 1](results/common-state/traces/state-v2-eval-20261101T201131691317Z-liquid__d1-ultra-repeat0.json) · [run 2](results/common-state/traces/state-v2-eval-20261101T201131691317Z-liquid__d1-ultra-repeat1.json) · [run 3](results/common-state/traces/state-v2-eval-20261101T201131691317Z-liquid__d1-ultra-repeat2.json) |
| respan/span-02 | 55.94% | - | $0.002348 | 3/3 | [run 1](results/common-state/traces/state-v2-eval-20261101T201131691317Z-respan__span-02-repeat0.json) · [run 2](results/common-state/traces/state-v2-eval-20261101T201131691317Z-respan__span-02-repeat1.json) · [run 3](results/common-state/traces/state-v2-eval-20261101T201131691317Z-respan__span-02-repeat2.json) |
| inception/mercury-decide | 51.42% | - | $0.004731 | 3/3 | [run 1](results/common-state/traces/state-v2-eval-20261101T201131691317Z-inception__mercury-decide-repeat0.json) · [run 2](results/common-state/traces/state-v2-eval-20261101T201131691317Z-inception__mercury-decide-repeat1.json) · [run 3](results/common-state/traces/state-v2-eval-20261101T201131691317Z-inception__mercury-decide-repeat2.json) |
| cloudflare/clef | 47.48% | - | $0.050734 | 3/3 | [run 1](results/common-state/traces/state-v2-eval-20261101T201131691317Z-cloudflare__clef-repeat0.json) · [run 2](results/common-state/traces/state-v2-eval-20261101T201131691317Z-cloudflare__clef-repeat1.json) · [run 3](results/common-state/traces/state-v2-eval-20261101T201131691317Z-cloudflare__clef-repeat2.json) |
| nace-ai/drex-max | 46.58% | - | $0.011012 | 3/3 | [run 1](results/common-state/traces/state-v2-eval-20261101T201131691317Z-nace-ai__drex-max-repeat0.json) · [run 2](results/common-state/traces/state-v2-eval-20261101T201131691317Z-nace-ai__drex-max-repeat1.json) · [run 3](results/common-state/traces/state-v2-eval-20261101T201131691317Z-nace-ai__drex-max-repeat2.json) |
| openai/gpt-6-luna-decisions | 34.76% | - | - | 3/3 | [run 1](results/common-state/traces/state-v2-eval-20261101T201131691317Z-openai__gpt-6-luna-decisions-repeat0.json) · [run 2](results/common-state/traces/state-v2-eval-20261101T201131691317Z-openai__gpt-6-luna-decisions-repeat1.json) · [run 3](results/common-state/traces/state-v2-eval-20261101T201131691317Z-openai__gpt-6-luna-decisions-repeat2.json) |
| microsoft/microsoft-decision-1 | 21.24% | - | $0.00315 | 3/3 | [run 1](results/common-state/traces/state-v2-eval-20261101T201131691317Z-microsoft__microsoft-decision-1-repeat0.json) · [run 2](results/common-state/traces/state-v2-eval-20261101T201131691317Z-microsoft__microsoft-decision-1-repeat1.json) · [run 3](results/common-state/traces/state-v2-eval-20261101T201131691317Z-microsoft__microsoft-decision-1-repeat2.json) |
| typesafe/jev-1.13 | 19.14% | - | - | 3/3 | [run 1](results/common-state/traces/state-v2-eval-20261101T201131691317Z-typesafe__jev-1.13-repeat0.json) · [run 2](results/common-state/traces/state-v2-eval-20261101T201131691317Z-typesafe__jev-1.13-repeat1.json) · [run 3](results/common-state/traces/state-v2-eval-20261101T201131691317Z-typesafe__jev-1.13-repeat2.json) |
| typesafe/jev-1.14 | 18.57% | - | - | 3/3 | [run 1](results/common-state/traces/state-v2-eval-20261101T201131691317Z-typesafe__jev-1.14-repeat0.json) · [run 2](results/common-state/traces/state-v2-eval-20261101T201131691317Z-typesafe__jev-1.14-repeat1.json) · [run 3](results/common-state/traces/state-v2-eval-20261101T201131691317Z-typesafe__jev-1.14-repeat2.json) |
| baseten/mammoth-1 | 17.81% | - | - | 3/3 | [run 1](results/common-state/traces/state-v2-eval-20261101T201131691317Z-baseten__mammoth-1-repeat0.json) · [run 2](results/common-state/traces/state-v2-eval-20261101T201131691317Z-baseten__mammoth-1-repeat1.json) · [run 3](results/common-state/recovery/traces/state-v2-eval-20261101T201131691317Z-baseten__mammoth-1-repeat2--technical-recovery-v1.json) |
| cloudflare/clef-omni | 17.81% | - | - | 3/3 | [run 1](results/common-state/traces/state-v2-eval-20261101T201131691317Z-cloudflare__clef-omni-repeat0.json) · [run 2](results/common-state/traces/state-v2-eval-20261101T201131691317Z-cloudflare__clef-omni-repeat1.json) · [run 3](results/common-state/traces/state-v2-eval-20261101T201131691317Z-cloudflare__clef-omni-repeat2.json) |
| nace-ai/drex-v1.5 | 17.81% | - | - | 3/3 | [run 1](results/common-state/traces/state-v2-eval-20261101T201131691317Z-nace-ai__drex-v1.5-repeat0.json) · [run 2](results/common-state/traces/state-v2-eval-20261101T201131691317Z-nace-ai__drex-v1.5-repeat1.json) · [run 3](results/common-state/recovery/traces/state-v2-eval-20261101T201131691317Z-nace-ai__drex-v1.5-repeat2--technical-recovery-v1.json) |
| baseten/elephant-1 | 8.75% | - | $0.001201 | 3/3 | [run 1](results/common-state/traces/state-v2-eval-20261101T201131691317Z-baseten__elephant-1-repeat0.json) · [run 2](results/common-state/traces/state-v2-eval-20261101T201131691317Z-baseten__elephant-1-repeat1.json) · [run 3](results/common-state/traces/state-v2-eval-20261101T201131691317Z-baseten__elephant-1-repeat2.json) |
| baseten/joey-1 | 8.72% | - | $0.000298 | 3/3 | [run 1](results/common-state/traces/state-v2-eval-20261101T201131691317Z-baseten__joey-1-repeat0.json) · [run 2](results/common-state/traces/state-v2-eval-20261101T201131691317Z-baseten__joey-1-repeat1.json) · [run 3](results/common-state/traces/state-v2-eval-20261101T201131691317Z-baseten__joey-1-repeat2.json) |
| liquid/d1.1 | 8.72% | - | $0.000498 | 3/3 | [run 1](results/common-state/traces/state-v2-eval-20261101T201131691317Z-liquid__d1.1-repeat0.json) · [run 2](results/common-state/traces/state-v2-eval-20261101T201131691317Z-liquid__d1.1-repeat1.json) · [run 3](results/common-state/traces/state-v2-eval-20261101T201131691317Z-liquid__d1.1-repeat2.json) |
| perplexity/pplx-decider-flash-v1.2 | 8.72% | - | $0.000292 | 3/3 | [run 1](results/common-state/traces/state-v2-eval-20261101T201131691317Z-perplexity__pplx-decider-flash-v1.2-repeat0.json) · [run 2](results/common-state/traces/state-v2-eval-20261101T201131691317Z-perplexity__pplx-decider-flash-v1.2-repeat1.json) · [run 3](results/common-state/traces/state-v2-eval-20261101T201131691317Z-perplexity__pplx-decider-flash-v1.2-repeat2.json) |
| cloudflare/clef-flash | 8.55% | - | $0.00129 | 3/3 | [run 1](results/common-state/traces/state-v2-eval-20261101T201131691317Z-cloudflare__clef-flash-repeat0.json) · [run 2](results/common-state/traces/state-v2-eval-20261101T201131691317Z-cloudflare__clef-flash-repeat1.json) · [run 3](results/common-state/traces/state-v2-eval-20261101T201131691317Z-cloudflare__clef-flash-repeat2.json) |
| jaredpalmer/kev-4b | 8.20% | - | $0.001558 | 3/3 | [run 1](results/common-state/traces/state-v2-eval-20261101T201131691317Z-jaredpalmer__kev-4b-repeat0.json) · [run 2](results/common-state/traces/state-v2-eval-20261101T201131691317Z-jaredpalmer__kev-4b-repeat1.json) · [run 3](results/common-state/traces/state-v2-eval-20261101T201131691317Z-jaredpalmer__kev-4b-repeat2.json) |
| scaledown/classify-1 | 0.00% | - | - | 3/3 | [run 1](results/common-state/traces/state-v2-eval-20261101T201131691317Z-scaledown__classify-1-repeat0.json) · [run 2](results/common-state/traces/state-v2-eval-20261101T201131691317Z-scaledown__classify-1-repeat1.json) · [run 3](results/common-state/recovery/traces/state-v2-eval-20261101T201131691317Z-scaledown__classify-1-repeat2--technical-recovery-v1.json) |
| upstage/solar-decide-flash | 0.00% | - | - | 3/3 | [run 1](results/common-state/traces/state-v2-eval-20261101T201131691317Z-upstage__solar-decide-flash-repeat0.json) · [run 2](results/common-state/recovery/traces/state-v2-eval-20261101T201131691317Z-upstage__solar-decide-flash-repeat1--technical-recovery-v1.json) · [run 3](results/common-state/recovery/traces/state-v2-eval-20261101T201131691317Z-upstage__solar-decide-flash-repeat2--technical-recovery-v1.json) |
| nace-ai/drex-v2.0 | unavailable | - | - | 0/3 | [run 1](results/common-state/traces/state-v2-eval-20261101T201131691317Z-nace-ai__drex-v2.0-repeat0.json) · [run 2](results/common-state/traces/state-v2-eval-20261101T201131691317Z-nace-ai__drex-v2.0-repeat1.json) · [run 3](results/common-state/traces/state-v2-eval-20261101T201131691317Z-nace-ai__drex-v2.0-repeat2.json) |

<details>
<summary>completed-run timing</summary>

- perplexity/pplx-decider-v1.2: 3/3 completed; mean completed time 20.13 game s
- liquid/d1-ultra: 0/3 completed; mean completed time unavailable
- respan/span-02: 0/3 completed; mean completed time unavailable
- inception/mercury-decide: 0/3 completed; mean completed time unavailable
- cloudflare/clef: 0/3 completed; mean completed time unavailable
- nace-ai/drex-max: 0/3 completed; mean completed time unavailable
- openai/gpt-6-luna-decisions: 0/3 completed; mean completed time unavailable
- microsoft/microsoft-decision-1: 0/3 completed; mean completed time unavailable
- typesafe/jev-1.13: 0/3 completed; mean completed time unavailable
- typesafe/jev-1.14: 0/3 completed; mean completed time unavailable
- baseten/mammoth-1: 0/3 completed; mean completed time unavailable
- cloudflare/clef-omni: 0/3 completed; mean completed time unavailable
- nace-ai/drex-v1.5: 0/3 completed; mean completed time unavailable
- baseten/elephant-1: 0/3 completed; mean completed time unavailable
- baseten/joey-1: 0/3 completed; mean completed time unavailable
- liquid/d1.1: 0/3 completed; mean completed time unavailable
- perplexity/pplx-decider-flash-v1.2: 0/3 completed; mean completed time unavailable
- cloudflare/clef-flash: 0/3 completed; mean completed time unavailable
- jaredpalmer/kev-4b: 0/3 completed; mean completed time unavailable
- scaledown/classify-1: 0/3 completed; mean completed time unavailable
- upstage/solar-decide-flash: 0/3 completed; mean completed time unavailable
- nace-ai/drex-v2.0: unavailable (technical)

</details>

### pixels only

shared image progress baseline; native clears are outcomes. earlier failed calibration gates remain failed; historical mechanics evidence is not a scored final trial
[image protocol and trial evidence](results/common-image/index.json)

| model | mean progress | best clear (game s) | mean cost/run (usd) | valid runs | evidence |
| --- | ---: | ---: | ---: | ---: | --- |
| openai/gpt-6-luna-decisions | 44.31% | - | - | 3/3 | [run 1](results/common-image/traces/image-h7-baseline-evaluation-openai__gpt-6-luna-decisions-repeat0-seed101.json) · [run 2](results/common-image/traces/image-h7-baseline-evaluation-openai__gpt-6-luna-decisions-repeat1-seed102.json) · [run 3](results/common-image/traces/image-h7-baseline-evaluation-openai__gpt-6-luna-decisions-repeat2-seed103.json) |
| perplexity/pplx-decider-v1.2 | 32.76% | - | - | 3/3 | [run 1](results/common-image/traces/image-h7-baseline-evaluation-perplexity__pplx-decider-v1.2-repeat0-seed101.json) · [run 2](results/common-image/traces/image-h7-baseline-evaluation-perplexity__pplx-decider-v1.2-repeat1-seed102.json) · [run 3](results/common-image/traces/image-h7-baseline-evaluation-perplexity__pplx-decider-v1.2-repeat2-seed103.json) |
| nace-ai/drex-max | 30.29% | - | - | 3/3 | [run 1](results/common-image/traces/image-h7-baseline-evaluation-nace-ai__drex-max-repeat0-seed101.json) · [run 2](results/common-image/traces/image-h7-baseline-evaluation-nace-ai__drex-max-repeat1-seed102.json) · [run 3](results/common-image/traces/image-h7-baseline-evaluation-nace-ai__drex-max-repeat2-seed103.json) |
| baseten/mammoth-1 | 26.90% | - | - | 3/3 | [run 1](results/common-image/traces/image-h7-baseline-evaluation-baseten__mammoth-1-repeat0-seed101.json) · [run 2](results/common-image/traces/image-h7-baseline-evaluation-baseten__mammoth-1-repeat1-seed102.json) · [run 3](results/common-image/traces/image-h7-baseline-evaluation-baseten__mammoth-1-repeat2-seed103.json) |
| baseten/elephant-1 | 8.72% | - | - | 3/3 | [run 1](results/common-image/traces/image-h7-baseline-evaluation-baseten__elephant-1-repeat0-seed101.json) · [run 2](results/common-image/traces/image-h7-baseline-evaluation-baseten__elephant-1-repeat1-seed102.json) · [run 3](results/common-image/traces/image-h7-baseline-evaluation-baseten__elephant-1-repeat2-seed103.json) |
| cloudflare/clef | 8.72% | - | - | 3/3 | [run 1](results/common-image/traces/image-h7-baseline-evaluation-cloudflare__clef-repeat0-seed101.json) · [run 2](results/common-image/traces/image-h7-baseline-evaluation-cloudflare__clef-repeat1-seed102.json) · [run 3](results/common-image/traces/image-h7-baseline-evaluation-cloudflare__clef-repeat2-seed103.json) |
| cloudflare/clef-flash | 8.72% | - | - | 3/3 | [run 1](results/common-image/traces/image-h7-baseline-evaluation-cloudflare__clef-flash-repeat0-seed101.json) · [run 2](results/common-image/traces/image-h7-baseline-evaluation-cloudflare__clef-flash-repeat1-seed102.json) · [run 3](results/common-image/traces/image-h7-baseline-evaluation-cloudflare__clef-flash-repeat2-seed103.json) |
| inception/mercury-decide | 8.72% | - | - | 3/3 | [run 1](results/common-image/traces/image-h7-baseline-evaluation-inception__mercury-decide-repeat0-seed101.json) · [run 2](results/common-image/traces/image-h7-baseline-evaluation-inception__mercury-decide-repeat1-seed102.json) · [run 3](results/common-image/traces/image-h7-baseline-evaluation-inception__mercury-decide-repeat2-seed103.json) |
| liquid/d1-ultra | 8.72% | - | - | 3/3 | [run 1](results/common-image/traces/image-h7-baseline-evaluation-liquid__d1-ultra-repeat0-seed101.json) · [run 2](results/common-image/traces/image-h7-baseline-evaluation-liquid__d1-ultra-repeat1-seed102.json) · [run 3](results/common-image/traces/image-h7-baseline-evaluation-liquid__d1-ultra-repeat2-seed103.json) |
| perplexity/pplx-decider-flash-v1.2 | 8.72% | - | - | 3/3 | [run 1](results/common-image/traces/image-h7-baseline-evaluation-perplexity__pplx-decider-flash-v1.2-repeat0-seed101.json) · [run 2](results/common-image/traces/image-h7-baseline-evaluation-perplexity__pplx-decider-flash-v1.2-repeat1-seed102.json) · [run 3](results/common-image/traces/image-h7-baseline-evaluation-perplexity__pplx-decider-flash-v1.2-repeat2-seed103.json) |
| typesafe/jev-1.13 | 8.20% | - | - | 3/3 | [run 1](results/common-image/traces/image-h7-baseline-evaluation-typesafe__jev-1.13-repeat0-seed101.json) · [run 2](results/common-image/traces/image-h7-baseline-evaluation-typesafe__jev-1.13-repeat1-seed102.json) · [run 3](results/common-image/traces/image-h7-baseline-evaluation-typesafe__jev-1.13-repeat2-seed103.json) |
| liquid/d1.1 | 8.14% | - | - | 3/3 | [run 1](results/common-image/traces/image-h7-baseline-evaluation-liquid__d1.1-repeat0-seed101.json) · [run 2](results/common-image/traces/image-h7-baseline-evaluation-liquid__d1.1-repeat1-seed102.json) · [run 3](results/common-image/traces/image-h7-baseline-evaluation-liquid__d1.1-repeat2-seed103.json) |
| respan/span-02 | 8.14% | - | - | 3/3 | [run 1](results/common-image/traces/image-h7-baseline-evaluation-respan__span-02-repeat0-seed101.json) · [run 2](results/common-image/traces/image-h7-baseline-evaluation-respan__span-02-repeat1-seed102.json) · [run 3](results/common-image/traces/image-h7-baseline-evaluation-respan__span-02-repeat2-seed103.json) |
| baseten/joey-1 | 0.00% | - | - | 3/3 | [run 1](results/common-image/traces/image-h7-baseline-evaluation-baseten__joey-1-repeat0-seed101.json) · [run 2](results/common-image/traces/image-h7-baseline-evaluation-baseten__joey-1-repeat1-seed102.json) · [run 3](results/common-image/traces/image-h7-baseline-evaluation-baseten__joey-1-repeat2-seed103.json) |
| cloudflare/clef-omni | 0.00% | - | - | 3/3 | [run 1](results/common-image/traces/image-h7-baseline-evaluation-cloudflare__clef-omni-repeat0-seed101.json) · [run 2](results/common-image/traces/image-h7-baseline-evaluation-cloudflare__clef-omni-repeat1-seed102.json) · [run 3](results/common-image/traces/image-h7-baseline-evaluation-cloudflare__clef-omni-repeat2-seed103.json) |
| typesafe/jev-1.14 | pending | - | - | 2/3 | [run 1](results/common-image/traces/image-h7-baseline-evaluation-typesafe__jev-1.14-repeat0-seed101.json) · [run 2](results/common-image/traces/image-h7-baseline-evaluation-typesafe__jev-1.14-repeat1-seed102.json) · [run 3](results/common-image/traces/image-h7-baseline-evaluation-typesafe__jev-1.14-repeat2-seed103.json) |

<details>
<summary>completed-run timing</summary>

- openai/gpt-6-luna-decisions: 0/3 completed; mean completed time unavailable
- perplexity/pplx-decider-v1.2: 0/3 completed; mean completed time unavailable
- nace-ai/drex-max: 0/3 completed; mean completed time unavailable
- baseten/mammoth-1: 0/3 completed; mean completed time unavailable
- baseten/elephant-1: 0/3 completed; mean completed time unavailable
- cloudflare/clef: 0/3 completed; mean completed time unavailable
- cloudflare/clef-flash: 0/3 completed; mean completed time unavailable
- inception/mercury-decide: 0/3 completed; mean completed time unavailable
- liquid/d1-ultra: 0/3 completed; mean completed time unavailable
- perplexity/pplx-decider-flash-v1.2: 0/3 completed; mean completed time unavailable
- typesafe/jev-1.13: 0/3 completed; mean completed time unavailable
- liquid/d1.1: 0/3 completed; mean completed time unavailable
- respan/span-02: 0/3 completed; mean completed time unavailable
- baseten/joey-1: 0/3 completed; mean completed time unavailable
- cloudflare/clef-omni: 0/3 completed; mean completed time unavailable
- typesafe/jev-1.14: pending

</details>

<details>
<summary>individual runs and development history</summary>


160 published runs, matching the website's all runs view, on world 1-1
individual development runs use different settings; these are not model averages or a ranking

the json retest is a separate retrospective run; its overlapping prefix is evidence only
[serialization diagnostics and prefix](results/diagnostics/openai-state-serialization.json)

cost is usd; ~ includes a byok list-price estimate, and missing billing is shown as -

### state

| model | observed progress | clear time (game s) | cost (usd) | evidence |
| --- | ---: | ---: | ---: | --- |
| perplexity: decider v1.2 | 100.00% | 20.13 | $0.00781 | [replay](results/replays/pplx-state-clear.mp4) · [trace](results/traces/pplx-state-clear.json) · [profile](results/profiles/pplx-state-clear.json) <!-- run:pplx-state-clear --> |
| perplexity: decider v1.2 | 100.00% | 20.13 | $0.00781 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-perplexity__pplx-decider-v1.2-repeat0.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-perplexity__pplx-decider-v1.2-repeat0.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-perplexity__pplx-decider-v1.2-repeat0 --> |
| perplexity: decider v1.2 | 100.00% | 20.13 | - | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-perplexity__pplx-decider-v1.2-repeat1.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-perplexity__pplx-decider-v1.2-repeat1.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-perplexity__pplx-decider-v1.2-repeat1 --> |
| perplexity: decider v1.2 | 100.00% | 20.13 | $0.00781 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-perplexity__pplx-decider-v1.2-repeat2.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-perplexity__pplx-decider-v1.2-repeat2.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-perplexity__pplx-decider-v1.2-repeat2 --> |
| liquidai: d1-ultra | 100.00% | 20.92 | $0.016537 | [replay](results/replays/liquid-state-clear.mp4) · [trace](results/traces/liquid-state-clear.json) · [profile](results/profiles/liquid-state-clear.json) <!-- run:liquid-state-clear --> |
| inception: mercury decide | 100.00% | 22.00 | $0.00706 | [replay](results/replays/mercury-state-clear.mp4) · [trace](results/traces/mercury-state-clear.json) · [profile](results/profiles/mercury-state-clear.json) <!-- run:mercury-state-clear --> |
| nace.ai: drex max | 100.00% | 23.07 | - | [replay](results/replays/drex-state-clear.mp4) · [trace](results/traces/drex-state-clear.json) · [profile](results/profiles/drex-state-clear.json) <!-- run:drex-state-clear --> |
| liquidai: d1-ultra | 77.83% | - | $0.012362 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-liquid__d1-ultra-repeat0.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-liquid__d1-ultra-repeat0.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-liquid__d1-ultra-repeat0 --> |
| inception: mercury decide | 63.57% | - | $0.005427 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-inception__mercury-decide-repeat1.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-inception__mercury-decide-repeat1.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-inception__mercury-decide-repeat1 --> |
| inception: mercury decide | 63.41% | - | $0.005311 | [replay](results/replays/state-c4-inception--mercury-decide.mp4) · [trace](results/traces/state-c4-inception--mercury-decide.json) · [profile](results/profiles/state-c4-inception--mercury-decide.json) <!-- run:state-c4-inception--mercury-decide --> |
| nace.ai: drex max | 63.41% | - | $0.015774 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-nace-ai__drex-max-repeat0.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-nace-ai__drex-max-repeat0.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-nace-ai__drex-max-repeat0 --> |
| nace.ai: drex max | 56.04% | - | $0.012816 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-nace-ai__drex-max-repeat1.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-nace-ai__drex-max-repeat1.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-nace-ai__drex-max-repeat1 --> |
| respan: span-02 | 55.94% | - | $0.002348 | [replay](results/replays/state-c4-respan--span-02.mp4) · [trace](results/traces/state-c4-respan--span-02.json) · [profile](results/profiles/state-c4-respan--span-02.json) <!-- run:state-c4-respan--span-02 --> |
| inception: mercury decide | 55.94% | - | $0.005088 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-inception__mercury-decide-repeat0.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-inception__mercury-decide-repeat0.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-inception__mercury-decide-repeat0 --> |
| respan: span-02 | 55.94% | - | $0.002348 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-respan__span-02-repeat0.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-respan__span-02-repeat0.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-respan__span-02-repeat0 --> |
| respan: span-02 | 55.94% | - | $0.002348 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-respan__span-02-repeat1.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-respan__span-02-repeat1.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-respan__span-02-repeat1 --> |
| respan: span-02 | 55.94% | - | $0.002348 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-respan__span-02-repeat2.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-respan__span-02-repeat2.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-respan__span-02-repeat2 --> |
| liquidai: d1-ultra | 52.45% | - | $0.007242 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-liquid__d1-ultra-repeat1.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-liquid__d1-ultra-repeat1.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-liquid__d1-ultra-repeat1 --> |
| liquidai: d1-ultra | 52.32% | - | $0.006556 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-liquid__d1-ultra-repeat2.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-liquid__d1-ultra-repeat2.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-liquid__d1-ultra-repeat2 --> |
| cloudflare: clef | 47.48% | - | $0.050734 | [replay](results/replays/state-c4-cloudflare--clef.mp4) · [trace](results/traces/state-c4-cloudflare--clef.json) · [profile](results/profiles/state-c4-cloudflare--clef.json) <!-- run:state-c4-cloudflare--clef --> |
| cloudflare: clef | 47.48% | - | $0.050734 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-cloudflare__clef-repeat0.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-cloudflare__clef-repeat0.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-cloudflare__clef-repeat0 --> |
| cloudflare: clef | 47.48% | - | $0.050734 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-cloudflare__clef-repeat1.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-cloudflare__clef-repeat1.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-cloudflare__clef-repeat1 --> |
| cloudflare: clef | 47.48% | - | $0.050734 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-cloudflare__clef-repeat2.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-cloudflare__clef-repeat2.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-cloudflare__clef-repeat2 --> |
| microsoft: microsoft-decision-1 | 44.25% | - | $0.00715 | [replay](results/replays/state-c4-microsoft--microsoft-decision-1.mp4) · [trace](results/traces/state-c4-microsoft--microsoft-decision-1.json) · [profile](results/profiles/state-c4-microsoft--microsoft-decision-1.json) <!-- run:state-c4-microsoft--microsoft-decision-1 --> |
| microsoft: microsoft-decision-1 | 34.80% | - | $0.005554 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-microsoft__microsoft-decision-1-repeat1.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-microsoft__microsoft-decision-1-repeat1.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-microsoft__microsoft-decision-1-repeat1 --> |
| openai: gpt-6 luna decisions (json retest) | 34.76% | - | ~$0.054158 | [replay](results/replays/openai-state-json-object-full-diagnostic.mp4) · [trace](results/traces/openai-state-json-object-full-diagnostic.json) · [profile](results/profiles/openai-state-json-object-full-diagnostic.json) <!-- run:openai-state-json-object-full-diagnostic --> |
| openai: gpt-6 luna decisions | 34.76% | - | ~$0.054158 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-openai__gpt-6-luna-decisions-repeat0.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-openai__gpt-6-luna-decisions-repeat0.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-openai__gpt-6-luna-decisions-repeat0 --> |
| openai: gpt-6 luna decisions | 34.76% | - | ~$0.054158 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-openai__gpt-6-luna-decisions-repeat1.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-openai__gpt-6-luna-decisions-repeat1.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-openai__gpt-6-luna-decisions-repeat1 --> |
| openai: gpt-6 luna decisions | 34.76% | - | - | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-openai__gpt-6-luna-decisions-repeat2.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-openai__gpt-6-luna-decisions-repeat2.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-openai__gpt-6-luna-decisions-repeat2 --> |
| inception: mercury decide | 34.73% | - | $0.003679 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-inception__mercury-decide-repeat2.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-inception__mercury-decide-repeat2.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-inception__mercury-decide-repeat2 --> |
| typesafe: jev 1.13 | 21.88% (aborted) | - | $0.013583 | [replay](results/replays/state-c4-typesafe--jev-1-13.mp4) · [trace](results/traces/state-c4-typesafe--jev-1-13.json) · [profile](results/profiles/state-c4-typesafe--jev-1-13.json) <!-- run:state-c4-typesafe--jev-1-13 --> |
| typesafe: jev 1.13 | 21.88% | - | - | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-typesafe__jev-1.13-repeat1.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-typesafe__jev-1.13-repeat1.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-typesafe__jev-1.13-repeat1 --> |
| liquidai: d1-ultra | 20.47% | - | $0.002905 | [replay](results/replays/state-c4-liquid--d1-ultra.mp4) · [trace](results/traces/state-c4-liquid--d1-ultra.json) · [profile](results/profiles/state-c4-liquid--d1-ultra.json) <!-- run:state-c4-liquid--d1-ultra --> |
| microsoft: microsoft-decision-1 | 20.38% | - | $0.002714 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-microsoft__microsoft-decision-1-repeat0.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-microsoft__microsoft-decision-1-repeat0.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-microsoft__microsoft-decision-1-repeat0 --> |
| nace.ai: drex max | 20.28% | - | $0.004448 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-nace-ai__drex-max-repeat2.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-nace-ai__drex-max-repeat2.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-nace-ai__drex-max-repeat2 --> |
| typesafe: jev 1.14 | 20.22% | - | $0.064601 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-typesafe__jev-1.14-repeat0.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-typesafe__jev-1.14-repeat0.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-typesafe__jev-1.14-repeat0 --> |
| nace.ai: drex max | 20.19% | - | - | [replay](results/replays/state-c4-nace-ai--drex-max.mp4) · [trace](results/traces/state-c4-nace-ai--drex-max.json) · [profile](results/profiles/state-c4-nace-ai--drex-max.json) <!-- run:state-c4-nace-ai--drex-max --> |
| baseten: mammoth 1 | 17.81% (aborted) | - | $0.02235 | [replay](results/replays/state-c4-baseten--mammoth-1.mp4) · [trace](results/traces/state-c4-baseten--mammoth-1.json) · [profile](results/profiles/state-c4-baseten--mammoth-1.json) <!-- run:state-c4-baseten--mammoth-1 --> |
| nace.ai: drex v1.5 | 17.81% (aborted) | - | $0.008571 | [replay](results/replays/state-c4-nace-ai--drex-v1-5.mp4) · [trace](results/traces/state-c4-nace-ai--drex-v1-5.json) · [profile](results/profiles/state-c4-nace-ai--drex-v1-5.json) <!-- run:state-c4-nace-ai--drex-v1-5 --> |
| typesafe: jev 1.14 | 17.81% (aborted) | - | $0.013232 | [replay](results/replays/state-c4-typesafe--jev-1-14.mp4) · [trace](results/traces/state-c4-typesafe--jev-1-14.json) · [profile](results/profiles/state-c4-typesafe--jev-1-14.json) <!-- run:state-c4-typesafe--jev-1-14 --> |
| baseten: mammoth 1 | 17.81% | - | - | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-baseten__mammoth-1-repeat0.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-baseten__mammoth-1-repeat0.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-baseten__mammoth-1-repeat0 --> |
| baseten: mammoth 1 | 17.81% | - | - | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-baseten__mammoth-1-repeat1.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-baseten__mammoth-1-repeat1.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-baseten__mammoth-1-repeat1 --> |
| baseten: mammoth 1 (technical continuation) | 17.81% | - | - | [replay](results/common-state/recovery/replays/state-v2-eval-20261101T201131691317Z-baseten__mammoth-1-repeat2--technical-recovery-v1.mp4) · [trace](results/common-state/recovery/traces/state-v2-eval-20261101T201131691317Z-baseten__mammoth-1-repeat2--technical-recovery-v1.json) · [profile](results/common-state/profiles/protocol.json) · [original abort](results/common-state/traces/state-v2-eval-20261101T201131691317Z-baseten__mammoth-1-repeat2.json) · [proof](results/common-state/recovery/proofs/state-v2-eval-20261101T201131691317Z-baseten__mammoth-1-repeat2--technical-recovery-v1.json) <!-- run:state-v2-eval-20261101T201131691317Z-baseten__mammoth-1-repeat2 --> |
| cloudflare: clef omni | 17.81% | - | $0.292443 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-cloudflare__clef-omni-repeat0.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-cloudflare__clef-omni-repeat0.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-cloudflare__clef-omni-repeat0 --> |
| cloudflare: clef omni | 17.81% | - | - | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-cloudflare__clef-omni-repeat1.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-cloudflare__clef-omni-repeat1.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-cloudflare__clef-omni-repeat1 --> |
| cloudflare: clef omni | 17.81% | - | - | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-cloudflare__clef-omni-repeat2.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-cloudflare__clef-omni-repeat2.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-cloudflare__clef-omni-repeat2 --> |
| nace.ai: drex v1.5 | 17.81% | - | - | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-nace-ai__drex-v1.5-repeat0.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-nace-ai__drex-v1.5-repeat0.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-nace-ai__drex-v1.5-repeat0 --> |
| nace.ai: drex v1.5 | 17.81% | - | - | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-nace-ai__drex-v1.5-repeat1.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-nace-ai__drex-v1.5-repeat1.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-nace-ai__drex-v1.5-repeat1 --> |
| nace.ai: drex v1.5 (technical continuation) | 17.81% | - | - | [replay](results/common-state/recovery/replays/state-v2-eval-20261101T201131691317Z-nace-ai__drex-v1.5-repeat2--technical-recovery-v1.mp4) · [trace](results/common-state/recovery/traces/state-v2-eval-20261101T201131691317Z-nace-ai__drex-v1.5-repeat2--technical-recovery-v1.json) · [profile](results/common-state/profiles/protocol.json) · [original abort](results/common-state/traces/state-v2-eval-20261101T201131691317Z-nace-ai__drex-v1.5-repeat2.json) · [proof](results/common-state/recovery/proofs/state-v2-eval-20261101T201131691317Z-nace-ai__drex-v1.5-repeat2--technical-recovery-v1.json) <!-- run:state-v2-eval-20261101T201131691317Z-nace-ai__drex-v1.5-repeat2 --> |
| typesafe: jev 1.13 | 17.78% | - | - | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-typesafe__jev-1.13-repeat2.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-typesafe__jev-1.13-repeat2.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-typesafe__jev-1.13-repeat2 --> |
| nace.ai: drex v2.0 | 17.75% (aborted) | - | - | [replay](results/replays/state-c4-nace-ai--drex-v2-0.mp4) · [trace](results/traces/state-c4-nace-ai--drex-v2-0.json) · [profile](results/profiles/state-c4-nace-ai--drex-v2-0.json) <!-- run:state-c4-nace-ai--drex-v2-0 --> |
| typesafe: jev 1.13 | 17.75% | - | $0.085937 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-typesafe__jev-1.13-repeat0.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-typesafe__jev-1.13-repeat0.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-typesafe__jev-1.13-repeat0 --> |
| typesafe: jev 1.14 | 17.75% | - | - | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-typesafe__jev-1.14-repeat1.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-typesafe__jev-1.14-repeat1.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-typesafe__jev-1.14-repeat1 --> |
| typesafe: jev 1.14 | 17.75% | - | - | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-typesafe__jev-1.14-repeat2.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-typesafe__jev-1.14-repeat2.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-typesafe__jev-1.14-repeat2 --> |
| cloudflare: clef omni | 13.17% (aborted) | - | $0.05954 | [replay](results/replays/state-c4-cloudflare--clef-omni.mp4) · [trace](results/traces/state-c4-cloudflare--clef-omni.json) · [profile](results/profiles/state-c4-cloudflare--clef-omni.json) <!-- run:state-c4-cloudflare--clef-omni --> |
| baseten: elephant 1 | 8.75% | - | $0.001201 | [replay](results/replays/state-c4-baseten--elephant-1.mp4) · [trace](results/traces/state-c4-baseten--elephant-1.json) · [profile](results/profiles/state-c4-baseten--elephant-1.json) <!-- run:state-c4-baseten--elephant-1 --> |
| baseten: elephant 1 | 8.75% | - | $0.001201 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-baseten__elephant-1-repeat0.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-baseten__elephant-1-repeat0.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-baseten__elephant-1-repeat0 --> |
| baseten: elephant 1 | 8.75% | - | $0.001201 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-baseten__elephant-1-repeat1.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-baseten__elephant-1-repeat1.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-baseten__elephant-1-repeat1 --> |
| baseten: elephant 1 | 8.75% | - | $0.001201 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-baseten__elephant-1-repeat2.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-baseten__elephant-1-repeat2.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-baseten__elephant-1-repeat2 --> |
| baseten: joey 1 | 8.72% | - | $0.000298 | [replay](results/replays/state-c4-perplexity--pplx-decider-flash-v1-2.mp4) · [trace](results/traces/state-c4-baseten--joey-1.json) · [profile](results/profiles/state-c4-baseten--joey-1.json) <!-- run:state-c4-baseten--joey-1 --> |
| liquidai: d1.1 | 8.72% | - | $0.000498 | [replay](results/replays/state-c4-perplexity--pplx-decider-flash-v1-2.mp4) · [trace](results/traces/state-c4-liquid--d1-1.json) · [profile](results/profiles/state-c4-liquid--d1-1.json) <!-- run:state-c4-liquid--d1-1 --> |
| perplexity: decider flash v1.2 | 8.72% | - | $0.000292 | [replay](results/replays/state-c4-perplexity--pplx-decider-flash-v1-2.mp4) · [trace](results/traces/state-c4-perplexity--pplx-decider-flash-v1-2.json) · [profile](results/profiles/state-c4-perplexity--pplx-decider-flash-v1-2.json) <!-- run:state-c4-perplexity--pplx-decider-flash-v1-2 --> |
| baseten: joey 1 | 8.72% | - | $0.000298 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-baseten__joey-1-repeat0.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-baseten__joey-1-repeat0.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-baseten__joey-1-repeat0 --> |
| baseten: joey 1 | 8.72% | - | $0.000298 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-baseten__joey-1-repeat1.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-baseten__joey-1-repeat1.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-baseten__joey-1-repeat1 --> |
| baseten: joey 1 | 8.72% | - | $0.000298 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-baseten__joey-1-repeat2.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-baseten__joey-1-repeat2.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-baseten__joey-1-repeat2 --> |
| liquidai: d1.1 | 8.72% | - | $0.000498 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-liquid__d1.1-repeat0.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-liquid__d1.1-repeat0.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-liquid__d1.1-repeat0 --> |
| liquidai: d1.1 | 8.72% | - | $0.000498 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-liquid__d1.1-repeat1.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-liquid__d1.1-repeat1.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-liquid__d1.1-repeat1 --> |
| liquidai: d1.1 | 8.72% | - | $0.000498 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-liquid__d1.1-repeat2.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-liquid__d1.1-repeat2.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-liquid__d1.1-repeat2 --> |
| perplexity: decider flash v1.2 | 8.72% | - | $0.000292 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-perplexity__pplx-decider-flash-v1.2-repeat0.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-perplexity__pplx-decider-flash-v1.2-repeat0.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-perplexity__pplx-decider-flash-v1.2-repeat0 --> |
| perplexity: decider flash v1.2 | 8.72% | - | $0.000292 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-perplexity__pplx-decider-flash-v1.2-repeat1.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-perplexity__pplx-decider-flash-v1.2-repeat1.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-perplexity__pplx-decider-flash-v1.2-repeat1 --> |
| perplexity: decider flash v1.2 | 8.72% | - | $0.000292 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-perplexity__pplx-decider-flash-v1.2-repeat2.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-perplexity__pplx-decider-flash-v1.2-repeat2.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-perplexity__pplx-decider-flash-v1.2-repeat2 --> |
| cloudflare: clef flash | 8.55% | - | $0.00129 | [replay](results/replays/state-c4-cloudflare--clef-flash.mp4) · [trace](results/traces/state-c4-cloudflare--clef-flash.json) · [profile](results/profiles/state-c4-cloudflare--clef-flash.json) <!-- run:state-c4-cloudflare--clef-flash --> |
| cloudflare: clef flash | 8.55% | - | $0.00129 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-cloudflare__clef-flash-repeat0.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-cloudflare__clef-flash-repeat0.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-cloudflare__clef-flash-repeat0 --> |
| cloudflare: clef flash | 8.55% | - | $0.00129 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-cloudflare__clef-flash-repeat1.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-cloudflare__clef-flash-repeat1.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-cloudflare__clef-flash-repeat1 --> |
| cloudflare: clef flash | 8.55% | - | $0.00129 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-cloudflare__clef-flash-repeat2.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-cloudflare__clef-flash-repeat2.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-cloudflare__clef-flash-repeat2 --> |
| microsoft: microsoft-decision-1 | 8.55% | - | $0.001182 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-microsoft__microsoft-decision-1-repeat2.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-microsoft__microsoft-decision-1-repeat2.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-microsoft__microsoft-decision-1-repeat2 --> |
| jared palmer: kev 4b | 8.20% | - | $0.001558 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-jaredpalmer__kev-4b-repeat0.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-jaredpalmer__kev-4b-repeat0.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-jaredpalmer__kev-4b-repeat0 --> |
| jared palmer: kev 4b | 8.20% | - | $0.001558 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-jaredpalmer__kev-4b-repeat1.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-jaredpalmer__kev-4b-repeat1.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-jaredpalmer__kev-4b-repeat1 --> |
| jared palmer: kev 4b | 8.20% | - | $0.001558 | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-jaredpalmer__kev-4b-repeat2.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-jaredpalmer__kev-4b-repeat2.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-jaredpalmer__kev-4b-repeat2 --> |
| scaledown: classify-1 | 0.00% (aborted) | - | $0.008584 | [replay](results/replays/state-c4-scaledown--classify-1.mp4) · [trace](results/traces/state-c4-scaledown--classify-1.json) · [profile](results/profiles/state-c4-scaledown--classify-1.json) <!-- run:state-c4-scaledown--classify-1 --> |
| upstage: solar decide flash | 0.00% (aborted) | - | $0.009052 | [replay](results/replays/state-c4-upstage--solar-decide-flash.mp4) · [trace](results/traces/state-c4-upstage--solar-decide-flash.json) · [profile](results/profiles/state-c4-upstage--solar-decide-flash.json) <!-- run:state-c4-upstage--solar-decide-flash --> |
| scaledown: classify-1 | 0.00% | - | - | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-scaledown__classify-1-repeat0.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-scaledown__classify-1-repeat0.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-scaledown__classify-1-repeat0 --> |
| scaledown: classify-1 | 0.00% | - | - | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-scaledown__classify-1-repeat1.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-scaledown__classify-1-repeat1.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-scaledown__classify-1-repeat1 --> |
| scaledown: classify-1 (technical continuation) | 0.00% | - | - | [replay](results/common-state/recovery/replays/state-v2-eval-20261101T201131691317Z-scaledown__classify-1-repeat2--technical-recovery-v1.mp4) · [trace](results/common-state/recovery/traces/state-v2-eval-20261101T201131691317Z-scaledown__classify-1-repeat2--technical-recovery-v1.json) · [profile](results/common-state/profiles/protocol.json) · [original abort](results/common-state/traces/state-v2-eval-20261101T201131691317Z-scaledown__classify-1-repeat2.json) · [proof](results/common-state/recovery/proofs/state-v2-eval-20261101T201131691317Z-scaledown__classify-1-repeat2--technical-recovery-v1.json) <!-- run:state-v2-eval-20261101T201131691317Z-scaledown__classify-1-repeat2 --> |
| upstage: solar decide flash | 0.00% | - | - | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-upstage__solar-decide-flash-repeat0.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-upstage__solar-decide-flash-repeat0.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-upstage__solar-decide-flash-repeat0 --> |
| upstage: solar decide flash (technical continuation) | 0.00% | - | - | [replay](results/common-state/recovery/replays/state-v2-eval-20261101T201131691317Z-upstage__solar-decide-flash-repeat1--technical-recovery-v1.mp4) · [trace](results/common-state/recovery/traces/state-v2-eval-20261101T201131691317Z-upstage__solar-decide-flash-repeat1--technical-recovery-v1.json) · [profile](results/common-state/profiles/protocol.json) · [original abort](results/common-state/traces/state-v2-eval-20261101T201131691317Z-upstage__solar-decide-flash-repeat1.json) · [proof](results/common-state/recovery/proofs/state-v2-eval-20261101T201131691317Z-upstage__solar-decide-flash-repeat1--technical-recovery-v1.json) <!-- run:state-v2-eval-20261101T201131691317Z-upstage__solar-decide-flash-repeat1 --> |
| upstage: solar decide flash (technical continuation) | 0.00% | - | - | [replay](results/common-state/recovery/replays/state-v2-eval-20261101T201131691317Z-upstage__solar-decide-flash-repeat2--technical-recovery-v1.mp4) · [trace](results/common-state/recovery/traces/state-v2-eval-20261101T201131691317Z-upstage__solar-decide-flash-repeat2--technical-recovery-v1.json) · [profile](results/common-state/profiles/protocol.json) · [original abort](results/common-state/traces/state-v2-eval-20261101T201131691317Z-upstage__solar-decide-flash-repeat2.json) · [proof](results/common-state/recovery/proofs/state-v2-eval-20261101T201131691317Z-upstage__solar-decide-flash-repeat2--technical-recovery-v1.json) <!-- run:state-v2-eval-20261101T201131691317Z-upstage__solar-decide-flash-repeat2 --> |
| jared palmer: kev 4b | api error | - | - | [trace](results/traces/state-c4-jaredpalmer--kev-4b.json) · [profile](results/profiles/state-c4-jaredpalmer--kev-4b.json) <!-- run:state-c4-jaredpalmer--kev-4b --> |
| openai: gpt-6 luna decisions | api error | - | - | [replay](results/replays/state-c4-openai--gpt-6-luna-decisions.mp4) · [trace](results/traces/state-c4-openai--gpt-6-luna-decisions.json) · [profile](results/profiles/state-c4-openai--gpt-6-luna-decisions.json) <!-- run:state-c4-openai--gpt-6-luna-decisions --> |
| nace.ai: drex v2.0 | incomplete | - | - | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-nace-ai__drex-v2.0-repeat0.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-nace-ai__drex-v2.0-repeat0.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-nace-ai__drex-v2.0-repeat0 --> |
| nace.ai: drex v2.0 | incomplete | - | - | [replay](results/common-state/replays/state-v2-eval-20261101T201131691317Z-nace-ai__drex-v2.0-repeat1.mp4) · [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-nace-ai__drex-v2.0-repeat1.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-nace-ai__drex-v2.0-repeat1 --> |
| nace.ai: drex v2.0 | incomplete | - | - | [trace](results/common-state/traces/state-v2-eval-20261101T201131691317Z-nace-ai__drex-v2.0-repeat2.json) · [profile](results/common-state/profiles/protocol.json) <!-- run:state-v2-eval-20261101T201131691317Z-nace-ai__drex-v2.0-repeat2 --> |

### pixels only

| model | observed progress | clear time (game s) | cost (usd) | evidence |
| --- | ---: | ---: | ---: | --- |
| perplexity: decider v1.2 | 100.00% | 31.18 | $0.0069 | [replay](results/replays/pplx-pixels-sampled-clear-t005-seed0.mp4) · [trace](results/traces/pplx-pixels-sampled-clear-t005-seed0.json) · [profile](results/profiles/pplx-pixels-sampled-clear-t005-seed0.json) <!-- run:pplx-pixels-sampled-clear-t005-seed0 --> |
| baseten: mammoth 1 | 100.00% | 31.93 | $0.122228 | [replay](results/replays/mammoth-pixels-first-clear.mp4) · [trace](results/traces/mammoth-pixels-first-clear.json) · [profile](results/profiles/mammoth-pixels-first-clear.json) <!-- run:mammoth-pixels-first-clear --> |
| inception: mercury decide (crop-only) | 100.00% | 39.22 | - | [replay](results/replays/mercury-pixels-planner-sampled-clear-t02-seed0.mp4) · [trace](results/traces/mercury-pixels-planner-sampled-clear-t02-seed0.json) · [profile](results/profiles/mercury-pixels-planner-sampled-clear-t02-seed0.json) <!-- run:mercury-pixels-planner-sampled-clear-t02-seed0 --> |
| baseten: mammoth 1 | 81.83% (aborted) | - | - | [replay](results/replays/pixels-best-baseten--mammoth-1.mp4) · [trace](results/traces/pixels-best-baseten--mammoth-1.json) · [profile](results/profiles/pixels-best-baseten--mammoth-1.json) <!-- run:pixels-best-baseten--mammoth-1 --> |
| openai: gpt-6 luna decisions | 77.86% | - | ~$0.052339 | [replay](results/replays/pixels-best-openai--gpt-6-luna-decisions.mp4) · [trace](results/traces/pixels-best-openai--gpt-6-luna-decisions.json) · [profile](results/profiles/pixels-best-openai--gpt-6-luna-decisions.json) <!-- run:pixels-best-openai--gpt-6-luna-decisions --> |
| perplexity: decider v1.2 | 77.83% | - | $0.004782 | [replay](results/replays/pplx-pixels-partial.mp4) · [trace](results/traces/pplx-pixels-partial.json) · [profile](results/profiles/pplx-pixels-partial.json) <!-- run:pplx-pixels-partial --> |
| baseten: mammoth 1 | 63.28% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-baseten__mammoth-1-repeat0-seed101.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-baseten__mammoth-1-repeat0-seed101.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-baseten__mammoth-1-repeat0-seed101 --> |
| baseten: elephant 1 | 61.39% | - | - | [replay](results/replays/pixels-best-baseten--elephant-1.mp4) · [trace](results/traces/pixels-best-baseten--elephant-1.json) · [profile](results/profiles/pixels-best-baseten--elephant-1.json) <!-- run:pixels-best-baseten--elephant-1 --> |
| inception: mercury decide | 56.30% | - | - | [replay](results/replays/mercury-pixels-partial.mp4) · [trace](results/traces/mercury-pixels-partial.json) · [profile](results/profiles/mercury-pixels-partial.json) <!-- run:mercury-pixels-partial --> |
| nace.ai: drex max | 56.30% | - | - | [replay](results/replays/pixels-best-nace-ai--drex-max.mp4) · [trace](results/traces/pixels-best-nace-ai--drex-max.json) · [profile](results/profiles/pixels-best-nace-ai--drex-max.json) <!-- run:pixels-best-nace-ai--drex-max --> |
| baseten: mammoth 1 | 56.01% | - | $0.033988 | [replay](results/replays/mammoth-pixels-partial.mp4) · [trace](results/traces/mammoth-pixels-partial.json) · [profile](results/profiles/mammoth-pixels-partial.json) <!-- run:mammoth-pixels-partial --> |
| perplexity: decider v1.2 | 52.23% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-perplexity__pplx-decider-v1.2-repeat2-seed103.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-perplexity__pplx-decider-v1.2-repeat2-seed103.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-perplexity__pplx-decider-v1.2-repeat2-seed103 --> |
| typesafe: jev 1.14 | 51.94% | - | - | [replay](results/replays/jev-pixels-partial.mp4) · [trace](results/traces/jev-pixels-partial.json) · [profile](results/profiles/jev-pixels-partial.json) <!-- run:jev-pixels-partial --> |
| nace.ai: drex max | 44.38% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-nace-ai__drex-max-repeat0-seed101.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-nace-ai__drex-max-repeat0-seed101.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-nace-ai__drex-max-repeat0-seed101 --> |
| openai: gpt-6 luna decisions | 44.31% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-openai__gpt-6-luna-decisions-repeat0-seed101.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-openai__gpt-6-luna-decisions-repeat0-seed101.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-openai__gpt-6-luna-decisions-repeat0-seed101 --> |
| openai: gpt-6 luna decisions | 44.31% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-openai__gpt-6-luna-decisions-repeat1-seed102.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-openai__gpt-6-luna-decisions-repeat1-seed102.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-openai__gpt-6-luna-decisions-repeat1-seed102 --> |
| openai: gpt-6 luna decisions | 44.31% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-openai__gpt-6-luna-decisions-repeat2-seed103.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-openai__gpt-6-luna-decisions-repeat2-seed103.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-openai__gpt-6-luna-decisions-repeat2-seed103 --> |
| perplexity: decider flash v1.2 | 44.31% | - | $0.002803 | [replay](results/replays/pixels-best-perplexity--pplx-decider-flash-v1-2.mp4) · [trace](results/traces/pixels-best-perplexity--pplx-decider-flash-v1-2.json) · [profile](results/profiles/pixels-best-perplexity--pplx-decider-flash-v1-2.json) <!-- run:pixels-best-perplexity--pplx-decider-flash-v1-2 --> |
| typesafe: jev 1.13 | 34.80% | - | - | [replay](results/replays/pixels-best-typesafe--jev-1-13.mp4) · [trace](results/traces/pixels-best-typesafe--jev-1-13.json) · [profile](results/profiles/pixels-best-typesafe--jev-1-13.json) <!-- run:pixels-best-typesafe--jev-1-13 --> |
| cloudflare: clef | 34.76% | - | $0.00553 | [replay](results/replays/pixels-best-cloudflare--clef.mp4) · [trace](results/traces/pixels-best-cloudflare--clef.json) · [profile](results/profiles/pixels-best-cloudflare--clef.json) <!-- run:pixels-best-cloudflare--clef --> |
| cloudflare: clef flash | 34.76% | - | - | [replay](results/replays/pixels-best-cloudflare--clef-flash.mp4) · [trace](results/traces/pixels-best-cloudflare--clef-flash.json) · [profile](results/profiles/pixels-best-cloudflare--clef-flash.json) <!-- run:pixels-best-cloudflare--clef-flash --> |
| liquidai: d1-ultra | 27.49% | - | $0.007572 | [replay](results/replays/pixels-best-liquid--d1-ultra.mp4) · [trace](results/traces/pixels-best-liquid--d1-ultra.json) · [profile](results/profiles/pixels-best-liquid--d1-ultra.json) <!-- run:pixels-best-liquid--d1-ultra --> |
| perplexity: decider v1.2 | 25.79% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-perplexity__pplx-decider-v1.2-repeat0-seed101.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-perplexity__pplx-decider-v1.2-repeat0-seed101.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-perplexity__pplx-decider-v1.2-repeat0-seed101 --> |
| nace.ai: drex max | 25.66% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-nace-ai__drex-max-repeat2-seed103.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-nace-ai__drex-max-repeat2-seed103.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-nace-ai__drex-max-repeat2-seed103 --> |
| baseten: joey 1 | 20.92% | - | - | [replay](results/replays/pixels-best-baseten--joey-1.mp4) · [trace](results/traces/pixels-best-baseten--joey-1.json) · [profile](results/profiles/pixels-best-baseten--joey-1.json) <!-- run:pixels-best-baseten--joey-1 --> |
| nace.ai: drex max | 20.83% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-nace-ai__drex-max-repeat1-seed102.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-nace-ai__drex-max-repeat1-seed102.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-nace-ai__drex-max-repeat1-seed102 --> |
| respan: span-02 | 20.38% | - | - | [replay](results/replays/pixels-best-respan--span-02.mp4) · [trace](results/traces/pixels-best-respan--span-02.json) · [profile](results/profiles/pixels-best-respan--span-02.json) <!-- run:pixels-best-respan--span-02 --> |
| perplexity: decider v1.2 | 20.25% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-perplexity__pplx-decider-v1.2-repeat1-seed102.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-perplexity__pplx-decider-v1.2-repeat1-seed102.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-perplexity__pplx-decider-v1.2-repeat1-seed102 --> |
| cloudflare: clef omni | 20.25% | - | - | [replay](results/replays/pixels-best-cloudflare--clef-omni.mp4) · [trace](results/traces/pixels-best-cloudflare--clef-omni.json) · [profile](results/profiles/pixels-best-cloudflare--clef-omni.json) <!-- run:pixels-best-cloudflare--clef-omni --> |
| liquidai: d1.1 | 12.66% (aborted) | - | $0.00878 | [replay](results/replays/pixels-best-liquid--d1-1.mp4) · [trace](results/traces/pixels-best-liquid--d1-1.json) · [profile](results/profiles/pixels-best-liquid--d1-1.json) <!-- run:pixels-best-liquid--d1-1 --> |
| baseten: elephant 1 | 8.72% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-baseten__elephant-1-repeat0-seed101.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-baseten__elephant-1-repeat0-seed101.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-baseten__elephant-1-repeat0-seed101 --> |
| baseten: elephant 1 | 8.72% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-baseten__elephant-1-repeat1-seed102.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-baseten__elephant-1-repeat1-seed102.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-baseten__elephant-1-repeat1-seed102 --> |
| baseten: elephant 1 | 8.72% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-baseten__elephant-1-repeat2-seed103.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-baseten__elephant-1-repeat2-seed103.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-baseten__elephant-1-repeat2-seed103 --> |
| baseten: mammoth 1 | 8.72% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-baseten__mammoth-1-repeat1-seed102.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-baseten__mammoth-1-repeat1-seed102.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-baseten__mammoth-1-repeat1-seed102 --> |
| baseten: mammoth 1 | 8.72% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-baseten__mammoth-1-repeat2-seed103.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-baseten__mammoth-1-repeat2-seed103.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-baseten__mammoth-1-repeat2-seed103 --> |
| cloudflare: clef flash | 8.72% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-cloudflare__clef-flash-repeat0-seed101.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-cloudflare__clef-flash-repeat0-seed101.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-cloudflare__clef-flash-repeat0-seed101 --> |
| cloudflare: clef flash | 8.72% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-cloudflare__clef-flash-repeat1-seed102.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-cloudflare__clef-flash-repeat1-seed102.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-cloudflare__clef-flash-repeat1-seed102 --> |
| cloudflare: clef flash | 8.72% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-cloudflare__clef-flash-repeat2-seed103.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-cloudflare__clef-flash-repeat2-seed103.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-cloudflare__clef-flash-repeat2-seed103 --> |
| cloudflare: clef | 8.72% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-cloudflare__clef-repeat0-seed101.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-cloudflare__clef-repeat0-seed101.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-cloudflare__clef-repeat0-seed101 --> |
| cloudflare: clef | 8.72% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-cloudflare__clef-repeat1-seed102.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-cloudflare__clef-repeat1-seed102.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-cloudflare__clef-repeat1-seed102 --> |
| cloudflare: clef | 8.72% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-cloudflare__clef-repeat2-seed103.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-cloudflare__clef-repeat2-seed103.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-cloudflare__clef-repeat2-seed103 --> |
| inception: mercury decide | 8.72% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-inception__mercury-decide-repeat0-seed101.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-inception__mercury-decide-repeat0-seed101.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-inception__mercury-decide-repeat0-seed101 --> |
| inception: mercury decide | 8.72% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-inception__mercury-decide-repeat1-seed102.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-inception__mercury-decide-repeat1-seed102.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-inception__mercury-decide-repeat1-seed102 --> |
| inception: mercury decide | 8.72% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-inception__mercury-decide-repeat2-seed103.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-inception__mercury-decide-repeat2-seed103.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-inception__mercury-decide-repeat2-seed103 --> |
| liquidai: d1-ultra | 8.72% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-liquid__d1-ultra-repeat0-seed101.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-liquid__d1-ultra-repeat0-seed101.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-liquid__d1-ultra-repeat0-seed101 --> |
| liquidai: d1-ultra | 8.72% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-liquid__d1-ultra-repeat1-seed102.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-liquid__d1-ultra-repeat1-seed102.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-liquid__d1-ultra-repeat1-seed102 --> |
| liquidai: d1-ultra | 8.72% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-liquid__d1-ultra-repeat2-seed103.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-liquid__d1-ultra-repeat2-seed103.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-liquid__d1-ultra-repeat2-seed103 --> |
| perplexity: decider flash v1.2 | 8.72% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-perplexity__pplx-decider-flash-v1.2-repeat0-seed101.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-perplexity__pplx-decider-flash-v1.2-repeat0-seed101.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-perplexity__pplx-decider-flash-v1.2-repeat0-seed101 --> |
| perplexity: decider flash v1.2 | 8.72% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-perplexity__pplx-decider-flash-v1.2-repeat1-seed102.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-perplexity__pplx-decider-flash-v1.2-repeat1-seed102.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-perplexity__pplx-decider-flash-v1.2-repeat1-seed102 --> |
| perplexity: decider flash v1.2 | 8.72% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-perplexity__pplx-decider-flash-v1.2-repeat2-seed103.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-perplexity__pplx-decider-flash-v1.2-repeat2-seed103.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-perplexity__pplx-decider-flash-v1.2-repeat2-seed103 --> |
| typesafe: jev 1.14 | 8.72% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-typesafe__jev-1.14-repeat2-seed103.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-typesafe__jev-1.14-repeat2-seed103.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-typesafe__jev-1.14-repeat2-seed103 --> |
| typesafe: jev 1.14 | 8.43% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-typesafe__jev-1.14-repeat0-seed101.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-typesafe__jev-1.14-repeat0-seed101.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-typesafe__jev-1.14-repeat0-seed101 --> |
| typesafe: jev 1.13 | 8.20% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-typesafe__jev-1.13-repeat0-seed101.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-typesafe__jev-1.13-repeat0-seed101.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-typesafe__jev-1.13-repeat0-seed101 --> |
| typesafe: jev 1.13 | 8.20% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-typesafe__jev-1.13-repeat1-seed102.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-typesafe__jev-1.13-repeat1-seed102.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-typesafe__jev-1.13-repeat1-seed102 --> |
| typesafe: jev 1.13 | 8.20% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-typesafe__jev-1.13-repeat2-seed103.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-typesafe__jev-1.13-repeat2-seed103.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-typesafe__jev-1.13-repeat2-seed103 --> |
| liquidai: d1.1 | 8.14% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-liquid__d1.1-repeat0-seed101.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-liquid__d1.1-repeat0-seed101.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-liquid__d1.1-repeat0-seed101 --> |
| liquidai: d1.1 | 8.14% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-liquid__d1.1-repeat1-seed102.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-liquid__d1.1-repeat1-seed102.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-liquid__d1.1-repeat1-seed102 --> |
| liquidai: d1.1 | 8.14% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-liquid__d1.1-repeat2-seed103.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-liquid__d1.1-repeat2-seed103.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-liquid__d1.1-repeat2-seed103 --> |
| respan: span-02 | 8.14% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-respan__span-02-repeat0-seed101.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-respan__span-02-repeat0-seed101.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-respan__span-02-repeat0-seed101 --> |
| respan: span-02 | 8.14% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-respan__span-02-repeat1-seed102.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-respan__span-02-repeat1-seed102.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-respan__span-02-repeat1-seed102 --> |
| respan: span-02 | 8.14% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-respan__span-02-repeat2-seed103.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-respan__span-02-repeat2-seed103.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-respan__span-02-repeat2-seed103 --> |
| baseten: joey 1 | 0.00% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-baseten__joey-1-repeat0-seed101.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-baseten__joey-1-repeat0-seed101.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-baseten__joey-1-repeat0-seed101 --> |
| baseten: joey 1 | 0.00% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-baseten__joey-1-repeat1-seed102.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-baseten__joey-1-repeat1-seed102.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-baseten__joey-1-repeat1-seed102 --> |
| baseten: joey 1 | 0.00% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-baseten__joey-1-repeat2-seed103.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-baseten__joey-1-repeat2-seed103.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-baseten__joey-1-repeat2-seed103 --> |
| cloudflare: clef omni | 0.00% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-cloudflare__clef-omni-repeat0-seed101.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-cloudflare__clef-omni-repeat0-seed101.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-cloudflare__clef-omni-repeat0-seed101 --> |
| cloudflare: clef omni | 0.00% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-cloudflare__clef-omni-repeat1-seed102.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-cloudflare__clef-omni-repeat1-seed102.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-cloudflare__clef-omni-repeat1-seed102 --> |
| cloudflare: clef omni | 0.00% | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-cloudflare__clef-omni-repeat2-seed103.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-cloudflare__clef-omni-repeat2-seed103.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-cloudflare__clef-omni-repeat2-seed103 --> |
| typesafe: jev 1.14 | incomplete | - | - | [replay](results/common-image/replays/image-h7-baseline-evaluation-typesafe__jev-1.14-repeat1-seed102.mp4) · [trace](results/common-image/traces/image-h7-baseline-evaluation-typesafe__jev-1.14-repeat1-seed102.json) · [profile](results/common-image/profiles/protocol.json) <!-- run:image-h7-baseline-evaluation-typesafe__jev-1.14-repeat1-seed102 --> |

</details>

<!-- END GENERATED RESULTS -->

state uses privileged current-viewport ram terrain and motion, which can include
unrevealed tile ids. the frozen term visible refers to viewport scope, not rendered
pixels. pixels (`image` track) uses
screenshots, crops and past screens where configured, plus rules, controls and timing
every pixels request was audited for the absence of memory-derived game state

clear time is native gameplay frames divided by 60, excluding api waiting time
and available only for completed runs

[results and traces](results/README.md) · [public 22-model roster](results/models.json) · [website data guide](docs/website-data.md)

<details>
<summary>run locally</summary>

### website

with node.js 24 installed, run from the repository checkout:

```sh
cd web
npm ci
npm run dev
```

open [localhost:3100](http://127.0.0.1:3100). the build prepares the game asset
and published results automatically. no python installation or api key is needed

### model viewer

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

### run a benchmark

the roster has 22 state models, with 14 currently passing the screenshot checks

see the [runner configuration](benchmark/models.json) for compatible model/provider pairs

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

### run a common state evaluation

see [the common state workflow](docs/common-state-benchmark.md) for the frozen
22-model protocol, offline evidence checks and a new 3-repeat evaluation. common
image calibration is pending

### rerun a frozen development controller

these explicit profiles run the controllers used by all 7 published clears:

```sh
# plans only; each profile pins its own model, provider, inputs and controller
.venv/bin/python -m benchmark.run --profile pplx-state-clear
.venv/bin/python -m benchmark.run --profile mercury-state-clear
.venv/bin/python -m benchmark.run --profile drex-state-clear
.venv/bin/python -m benchmark.run --profile liquid-state-clear
.venv/bin/python -m benchmark.run --profile mammoth-pixels-first-clear
.venv/bin/python -m benchmark.run --profile pplx-pixels-sampled-clear-t005-seed0
.venv/bin/python -m benchmark.run --profile mercury-pixels-planner-sampled-clear-t02-seed0

# add --execute for a new paid attempt, or use --policy fake for an offline check
.venv/bin/python -m benchmark.run --profile mammoth-pixels-first-clear --policy fake --max-native-frames 24 --output benchmark/runs/profile-offline --execute
.venv/bin/python -m benchmark.audit benchmark/runs/profile-offline

# verify all 4 historical profiles and native clears from public traces
.venv/bin/python -m benchmark.verify_profiles
```

the state profile holds inputs for 4 frames. mammoth uses pixels and its own
control history to enable model-selected 2/4/6/8-frame holds. the sampled pplx
profile uses pixels at cadence 7 and all 12 native probabilities with temperature
0.05 and seed 0. the provider's original choice stays in the log alongside the
sampled choice, draw and weights

mercury uses 2 calls per action: a native landing plan and duration, then sampled
motor inputs at temperature 0.2 and seed 0. it sees 3 matching lower-gameplay
crops, including the current view; areas outside that crop are unknown

fresh runs have a strict 6,000-native-frame cap; `--max-native-frames` changes it
before starting. the decision cap is derived from the shortest allowed hold.
the last hold stops at the remaining frame budget, death or native completion;
logs distinguish its requested and actual duration

the frozen controller and the fresh run envelope have separate hashes. historical
research budgets differed, so these commands do not recreate an identical whole
experiment or guarantee another clear. the 7 profiles also differ from each other
and from the common runner. changing a profile, source or envelope requires a new
output directory; resume cannot extend the budget

see [profile constraints](benchmark/profiles/README.md) for the exact contracts

</details>

<details>
<summary>methodology, verification and notices</summary>

update the tables with `npm --prefix web run update:readme` after changing published
results. `npm --prefix web run check:readme` checks the same run selection as the
website; website builds fail if the tables are stale

the aggregate score is **average progress, from 0 to 100**, unavailable for these
selected runs. average all declared attempts within each level, then weight levels
equally. dying keeps legitimate progress; only confirmed game completion gets 100

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

### inputs and controls

the game freezes while the model thinks. by default, it chooses 1 of 12 complete
controller inputs, held for exactly 4 native frames

the default budget is 6,000 native frames and 1,500 decisions. first death ends
the attempt

- `state` gives the model privileged current-viewport ram terrain, motion and recent
  positions, including tile ids that may not yet be rendered or revealed
- `image` gives it pixels only, plus declared buttons, frame number and action
  interval. no memory-derived positions, velocities, terrain or object lists

screenshots are lossless pngs, enlarged from 256x240 to 512x480 with nearest
neighbour sampling. model/provider identity is checked, and each worker owns its
own emulator. malformed model actions count as failed play; infrastructure
failures leave the comparable aggregate unavailable instead of becoming game losses

### replay checks and reproducibility

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

### repository

- `prototype/` contains the emulator, decision client and local viewer
- `benchmark/` contains the runner, scoring, protocol and replay tools
- `web/` contains the website and browser-local human game
- `results/` contains public development examples, profiles, action traces and replays

`requirements.lock.txt` pins the environment. secrets, environments, run logs,
screenshots and recordings stay ignored. `playground/` is local scratch space

this repository includes no rom files or game binaries; the emulator dependency
supplies its game data

[dependency notices](docs/third-party-notices.md)

</details>
