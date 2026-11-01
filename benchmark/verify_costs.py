"""Offline billing aggregation, coverage and export preservation checks."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile

from benchmark.costs import aggregate_receipts, costs_from_events, merge_public_cost, response_receipt, validate_public_cost
from benchmark.public_results import apply_cost_report, public_native_response


def total(receipts, **kwargs):
    return aggregate_receipts(receipts, coverage_complete=True, includes_retries=True,
                              includes_auxiliary_calls=True, **kwargs)


def receipt(credit, byok=False, estimate=None):
    return response_receipt({'usage': {'cost': credit}},
                            dict(is_byok=byok, total_cost=credit, upstream_inference_cost=estimate))


def main():
    ordinary = total([receipt(.1, False, 99), receipt(.2, False, 88)])
    assert ordinary['cost_usd'] == .3 and ordinary['cost_estimate_usd'] is None
    assert ordinary['upstream_cost_usd'] == 0 and validate_public_cost(ordinary)
    zero = total([receipt(0)])
    assert zero['cost_usd'] == 0 and validate_public_cost(zero)
    byok = total([receipt(0, True, .0000923)])
    assert byok['cost_usd'] is None and byok['cost_estimate_usd'] == .0000923
    assert byok['openrouter_cost_usd'] == 0 and byok['upstream_cost_usd'] is None
    assert not validate_public_cost(byok)
    explicit = total([response_receipt({'usage': {'cost': 0, 'is_byok': True,
                      'cost_details': {'upstream_inference_cost': .2}}})])
    assert explicit['cost_usd'] is None and explicit['cost_estimate_usd'] == .2
    try: response_receipt({'usage': {'cost': 0, 'is_byok': True}}, {'is_byok': False})
    except ValueError: pass
    else: raise AssertionError('Conflicting billing flags accepted')
    missing_actual_count = deepcopy(ordinary)
    missing_actual_count['cost_provenance'].pop('actual_costed_request_count')
    try: validate_public_cost(missing_actual_count)
    except ValueError: pass
    else: raise AssertionError('Actual coverage was inferred')
    mixed = total([receipt(1, False, 42), receipt(.01, True, .2)])
    assert mixed['cost_usd'] is None and mixed['cost_estimate_usd'] == 1.21
    assert mixed['openrouter_cost_usd'] == 1.01
    for partial in ([receipt(.2), {}], [response_receipt({'usage': {'cost': 0}})],
                    [receipt(0, True, None)], [dict(openrouter_cost_usd=False, is_byok=False)],
                    [dict(openrouter_cost_usd=float('nan'), is_byok=False)]):
        value = total(partial)
        assert value['cost_usd'] is None and value['cost_estimate_usd'] is None
    assert total([])['cost_usd'] is None
    assert aggregate_receipts([receipt(1)], coverage_complete=True)['cost_usd'] is None
    assert total([receipt(1)], request_count=2)['cost_usd'] is None

    events = []
    for stage, attempt, value in [('action', 0, .1), ('action', 1, .2), ('duration', 0, .3)]:
        identity = dict(episode_id='episode', decision_index=0, stage=stage, attempt=attempt)
        events += [dict(event='request_intent', **identity),
                   dict(event='request_result', valid=attempt == 1, raw_response={'usage': {'cost': value}},
                        billing_receipt=dict(is_byok=False, total_cost=value), **identity)]
    result = costs_from_events(events)
    assert result['cost_usd'] == .6 and result['cost_provenance']['request_count'] == 3
    incomplete = deepcopy(events)
    incomplete[1].pop('raw_response')
    incomplete[1].pop('billing_receipt')
    unknown = costs_from_events(incomplete)
    assert unknown['cost_usd'] is None and unknown['recorded_openrouter_cost_usd'] == .5
    pending = events + [dict(event='request_intent', episode_id='episode', decision_index=1, attempt=0)]
    assert costs_from_events(pending)['cost_usd'] is None
    for bad in (events + [events[0]], [events[1]]):
        try: costs_from_events(bad)
        except ValueError: pass
        else: raise AssertionError('Ambiguous attempt ledger accepted')
    assert merge_public_cost(ordinary, unknown) == ordinary
    assert merge_public_cost(byok, unknown) == byok
    try: merge_public_cost(ordinary, total([receipt(3)]))
    except ValueError: pass
    else: raise AssertionError('Conflicting audited cost silently replaced')
    invalid = deepcopy(byok)
    invalid['cost_usd'] = invalid['cost_estimate_usd']
    try: validate_public_cost(invalid)
    except ValueError: pass
    else: raise AssertionError('BYOK estimate labelled actual')
    missing_component = deepcopy(ordinary)
    missing_component.pop('upstream_cost_usd')
    try: validate_public_cost(missing_component)
    except ValueError: pass
    else: raise AssertionError('Missing required cost component accepted')
    assert 'private-request-id' not in json.dumps(result)
    raw = dict(model='model', provider='provider', answers={}, id='private-request-id',
               usage=dict(cost=.2, input_tokens=20))
    portable = public_native_response(raw)
    assert portable['usage']['cost'] == .2 and 'id' not in portable

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        index = dict(examples=[dict(id='public-a', **ordinary)], observations=[dict(id='public-a', **ordinary)],
                     technical_diagnostics=[dict(id='public-b')])
        (root / 'index.json').write_text(json.dumps(index))
        report = root / 'costs.json'
        report.write_text(json.dumps(dict(schema_version=1, runs={'public-a': unknown, 'public-b': byok})))
        apply_cost_report(root, report)
        published = json.loads((root / 'index.json').read_text())
        assert published['examples'][0]['cost_usd'] == .3
        assert published['observations'][0]['cost_usd'] == .3
        assert published['technical_diagnostics'][0]['cost_usd'] is None
        assert published['technical_diagnostics'][0]['cost_estimate_usd'] == .0000923
        before = (root / 'index.json').read_bytes()
        report.write_text(json.dumps(dict(schema_version=1, runs={'unknown-private-id': ordinary})))
        try: apply_cost_report(root, report)
        except ValueError: pass
        else: raise AssertionError('Unknown public mapping accepted')
        assert before == (root / 'index.json').read_bytes()
    print('PASS: actual/zero/non-BYOK billing, separate BYOK estimates, no wholesale double count, missing/invalid/aux/retry coverage, safe public mapping and audited-cost preservation; no API calls')


if __name__ == '__main__':
    main()
