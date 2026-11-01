"""Receipt-only inference billing: OpenRouter credits plus explicit direct BYOK cost.

No prices, token estimates, account-wide allocations, request IDs or private paths
are published. A missing receipt/component remains unknown, including on errors.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path

KIND = 'recorded_response_usage'
BASIS = 'all_in_inference'
COST_FIELDS = ('cost_usd', 'recorded_cost_usd', 'openrouter_cost_usd',
               'recorded_openrouter_cost_usd', 'upstream_cost_usd', 'upstream_cost_estimate_usd',
               'cost_estimate_usd', 'cost_provenance')


def amount(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return None
    if not math.isfinite(value) or value < 0:
        return None
    return Decimal(str(value))


def _sum(values):
    known = [value for value in values if value is not None]
    return float(sum(known, Decimal(0))) if known else None


def aggregate_receipts(receipts, *, request_count=None, coverage_complete=False,
                       includes_retries=False, includes_auxiliary_calls=False):
    """Aggregate explicitly normalised receipts, one for EVERY attempted call.

    Each receipt has openrouter_cost_usd from usage.cost/verified total_cost;
    is_byok is an actual explicit billing flag (never inferred from zero cost).
    byok_upstream_actual_cost_usd is an invoice-verified direct component.
    byok_upstream_estimated_cost_usd is a list-price proxy, never exact spend.
    Missing attempted responses must still appear as an empty receipt.
    """
    receipts = list(receipts)
    count = len(receipts) if request_count is None else request_count
    if isinstance(count, bool) or not isinstance(count, int) or count < len(receipts):
        raise ValueError('Request count must enumerate at least every supplied receipt')
    credits, direct, estimates, totals, estimated_totals, safe_receipts = [], [], [], [], [], []
    for receipt in receipts:
        credit = amount(receipt.get('openrouter_cost_usd'))
        byok = receipt.get('is_byok')
        upstream = amount(receipt.get('byok_upstream_actual_cost_usd')) if byok is True else (
            Decimal(0) if byok is False else None)
        estimate = (upstream if upstream is not None else amount(receipt.get('byok_upstream_estimated_cost_usd'))) if byok is True else upstream
        credits.append(credit)
        direct.append(upstream)
        estimates.append(estimate)
        totals.append(credit + upstream if credit is not None and upstream is not None else None)
        estimated_totals.append(credit + estimate if credit is not None and estimate is not None else None)
        safe_receipts.append(dict(credit=str(credit) if credit is not None else None,
                                  is_byok=byok if isinstance(byok, bool) else None,
                                  actual_direct=str(upstream) if upstream is not None else None,
                                  estimated_direct=str(estimate) if estimate is not None else None))
    actual_known = sum(value is not None for value in totals)
    known = sum(value is not None for value in estimated_totals)
    complete_scope = (coverage_complete is True and includes_retries is True
                      and includes_auxiliary_calls is True and len(receipts) == count and count > 0)
    exact = complete_scope and actual_known == count
    estimated_complete = complete_scope and known == count
    canonical = json.dumps(safe_receipts, sort_keys=True, separators=(',', ':')).encode()
    return dict(cost_usd=_sum(totals) if exact else None,
                recorded_cost_usd=_sum(totals),
                cost_estimate_usd=_sum(estimated_totals) if estimated_complete and not exact else None,
                openrouter_cost_usd=_sum(credits) if complete_scope and all(v is not None for v in credits) else None,
                recorded_openrouter_cost_usd=_sum(credits),
                upstream_cost_usd=_sum(direct) if complete_scope and all(v is not None for v in direct) else None,
                upstream_cost_estimate_usd=_sum(estimates) if estimated_complete and not exact else None,
                cost_provenance=dict(kind=KIND, cost_basis=BASIS, request_count=count,
                                     costed_request_count=known, actual_costed_request_count=actual_known,
                                     coverage_complete=bool(estimated_complete),
                                     upstream_cost_basis=('recorded_direct_billing' if exact else (
                                         'openrouter_activity_list_price_estimate' if estimated_complete else 'unknown')),
                                     includes_retries=includes_retries is True,
                                     includes_auxiliary_calls=includes_auxiliary_calls is True,
                                     receipts_sha256=hashlib.sha256(canonical).hexdigest()))


def response_receipt(response, billing=None):
    """Preserve a raw OR component; certify all-in only with explicit billing facts.

    billing is a verified generation receipt: is_byok, total_cost and
    upstream_inference_cost (a list-price estimate, not an invoice).
    Non-BYOK wholesale/upstream values are never added.
    """
    response = response if isinstance(response, dict) else {}
    usage = response.get('usage') if isinstance(response.get('usage'), dict) else {}
    billing = billing if isinstance(billing, dict) else {}
    credit = usage.get('cost')
    if 'total_cost' in billing:
        if amount(credit) is not None and amount(credit) != amount(billing['total_cost']):
            raise ValueError('Response usage.cost conflicts with verified billing total_cost')
        credit = billing['total_cost']
    raw_byok, billed_byok = usage.get('is_byok'), billing.get('is_byok')
    if isinstance(raw_byok, bool) and isinstance(billed_byok, bool) and raw_byok != billed_byok:
        raise ValueError('Response and generation billing BYOK flags conflict')
    byok = billed_byok if isinstance(billed_byok, bool) else raw_byok
    details = usage.get('cost_details') if isinstance(usage.get('cost_details'), dict) else {}
    estimate = billing.get('upstream_inference_cost', details.get('upstream_inference_cost'))
    return dict(openrouter_cost_usd=credit, is_byok=byok,
                byok_upstream_estimated_cost_usd=estimate)


def costs_from_events(events, *, episode_id=None, scope_complete=True):
    """Read the public runners' standard durable intent/result ledger only.

    Auxiliary heads use distinct stage names; retries use distinct attempt values.
    Research-specific formats require an audited explicit normalisation first.
    """
    pending, results = {}, {}
    for event in events:
        if episode_id is not None and event.get('episode_id') != episode_id:
            continue
        kind = event.get('event')
        if kind not in ('request_intent', 'request_result'):
            continue
        key = (event.get('episode_id'), event.get('decision_index'), event.get('stage', 'decision'), event.get('attempt'))
        if kind == 'request_intent':
            if key in pending:
                raise ValueError('Duplicate request intent')
            pending[key] = event
        else:
            if key not in pending or key in results:
                raise ValueError('Request result has no unique matching intent')
            results[key] = event
    receipts = [response_receipt(results.get(key, {}).get('raw_response'), results.get(key, {}).get('billing_receipt'))
                for key in pending]
    return aggregate_receipts(receipts, request_count=len(pending), coverage_complete=scope_complete,
                              includes_retries=True, includes_auxiliary_calls=True)


def validate_public_cost(record):
    """Validate a certified public cost claim; legacy/missing costs stay unknown."""
    for name in COST_FIELDS:
        if name != 'cost_provenance' and record.get(name) is not None and amount(record[name]) is None:
            raise ValueError('Invalid recorded cost component')
    exact_value = record.get('cost_usd')
    value = exact_value if exact_value is not None else record.get('cost_estimate_usd')
    provenance = record.get('cost_provenance')
    if value is None:
        return False
    if amount(value) is None or not isinstance(provenance, dict):
        raise ValueError('Invalid exact cost claim')
    count, known = provenance.get('request_count'), provenance.get('costed_request_count')
    if (provenance.get('kind') != KIND or provenance.get('cost_basis') != BASIS
            or provenance.get('coverage_complete') is not True
            or provenance.get('includes_retries') is not True
            or provenance.get('includes_auxiliary_calls') is not True
            or isinstance(count, bool) or not isinstance(count, int) or count <= 0
            or isinstance(known, bool) or not isinstance(known, int) or count != known):
        raise ValueError('Exact all-in cost requires complete explicit attempt billing provenance')
    actual = provenance.get('actual_costed_request_count')
    if isinstance(actual, bool) or not isinstance(actual, int) or not 0 <= actual <= count:
        raise ValueError('Actual receipt coverage must be explicit')
    if exact_value is not None and actual != count:
        raise ValueError('Estimated BYOK components cannot certify an actual cost')
    if exact_value is None and actual == count:
        raise ValueError('Complete actual receipts must not be labelled as an estimate')
    if exact_value is None and provenance.get('upstream_cost_basis') != 'openrouter_activity_list_price_estimate':
        raise ValueError('An estimate needs its explicit list-price billing basis')
    # Components, when supplied, must reconcile; non-BYOK wholesale cost is never another charge.
    credit = amount(record.get('openrouter_cost_usd'))
    upstream = amount(record.get('upstream_cost_usd' if exact_value is not None else 'upstream_cost_estimate_usd'))
    if credit is None or upstream is None:
        raise ValueError('Complete totals require both explicit billing components')
    if abs(credit + upstream - amount(value)) > Decimal('0.000000000001'):
        raise ValueError('Exact cost components do not reconcile')
    return exact_value is not None


def merge_public_cost(record, evidence):
    """Never downgrade or silently replace an already audited exact cost."""
    current_exact = validate_public_cost(record)
    incoming_exact = validate_public_cost(evidence)
    if current_exact:
        if incoming_exact and amount(record['cost_usd']) != amount(evidence['cost_usd']):
            raise ValueError('Conflicting audited cost; reconcile the receipts explicitly')
        return dict(record)
    if record.get('cost_estimate_usd') is not None and not incoming_exact and evidence.get('cost_estimate_usd') is None:
        return dict(record)
    if (record.get('cost_estimate_usd') is not None and not incoming_exact
            and evidence.get('cost_estimate_usd') is not None
            and amount(record['cost_estimate_usd']) != amount(evidence['cost_estimate_usd'])):
        raise ValueError('Conflicting audited estimate; reconcile the receipts explicitly')
    merged = dict(record)
    merged.update({key: evidence[key] for key in COST_FIELDS if key in evidence})
    validate_public_cost(merged)
    return merged


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('events', type=Path)
    parser.add_argument('--run-id', required=True, help='Explicit public run ID; never inferred from a private path')
    parser.add_argument('--episode-id')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    events = [json.loads(line) for line in args.events.read_text().splitlines() if line]
    report = dict(schema_version=1, runs={args.run_id: costs_from_events(events, episode_id=args.episode_id)})
    encoded = json.dumps(report, indent=2, allow_nan=False) + '\n'
    if args.output:
        args.output.write_text(encoded)
    else:
        print(encoded, end='')


if __name__ == '__main__':
    main()
