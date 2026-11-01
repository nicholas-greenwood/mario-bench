# recorded run costs

`cost_usd` is complete, recorded inference spend. non-byok openrouter charges
already include provider inference; adding provider wholesale cost again would
double count it

byok upstream activity figures are list-price estimates, not verified provider
invoices. a complete byok run can expose `cost_estimate_usd` separately, while
`cost_usd` stays null. the website shows estimates with `~`. missing receipts,
billing flags or required components leave both totals unknown

`openrouter_cost_usd` is the complete recorded credit component.
`upstream_cost_usd` is verified direct billing, when available;
`upstream_cost_estimate_usd` is the separate list-price component.
`recorded_openrouter_cost_usd` and `recorded_cost_usd` can retain partial evidence
without claiming a complete total. explicit zero is valid; missing cost is not zero

coverage counts every attempted request, including retries, failed requests,
planner calls and separate timing heads. an interrupted intent without a result
still counts as an attempt with unknown cost. `cost_provenance` records request
coverage, actual coverage, billing basis and a receipt digest without publishing
private request IDs or source paths. inference cost does not affect game scores

## forward pipeline

both public runners retain full response usage in their durable request ledgers
and add receipt aggregates to their summaries. an explicit `usage.is_byok` flag
is used when available. otherwise a verified generation billing receipt is needed
to distinguish byok; positive or zero credit cost alone cannot establish it

`benchmark.public_results.public_native_response` keeps response usage when
building a new portable trace, while removing private request IDs. use this
helper instead of selecting only model/provider/answers

for a standard runner ledger, export an explicitly named public case:

```sh
python -m benchmark.costs benchmark/runs/example/model.jsonl --run-id public-case --episode-id 1-1:seed0:trial000 --output /tmp/run-costs.json
```

the raw ledger can produce only partial evidence if billing flags/components were
not retained. research formats need an audited explicit mapping; do not infer a
public ID or billing coverage from filenames, decisions, token counts or prices

attach a certified report to the public dataset:

```sh
python -m benchmark.public_results results --cost-report /tmp/run-costs.json
```

reports use `{"schema_version":1,"runs":{"public-case":{...cost fields...}}}`.
all IDs must already exist in the public dataset. conflicting audited costs are
rejected. a partial report cannot overwrite an existing complete actual cost or
complete estimate. replay rendering preserves these fields

```sh
python -m benchmark.verify_costs
```

these checks use local synthetic receipts only and make no api calls

## invalidated certificates

complete costs require an explicit source-attempt inventory, not just generation
receipts or successful actions. standalone `request_error`, `api_error` and pending
calls count towards that inventory. an unscoped error cannot be silently dropped
when selecting an episode

for an independently audited correction to an invalid old certificate, use the
explicit replacement path; normal imports continue to preserve complete evidence:

```sh
python -m benchmark.public_results results --cost-report corrected-costs.json --replace-invalidated-costs
```
