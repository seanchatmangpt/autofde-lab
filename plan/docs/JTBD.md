# JTBD

Jobs-to-be-done named by the operator, verified against /Users/sac/tony.txt. Specs live in
`pipeline/tests/jtbd_specs.py`; bounds in `pipeline/tests/jtbd_envelopes.toml`.

| id | job | status | transcript lines |
|----|-----|--------|------------------|
| J1 | out-of-territory work order flagged | UNSUPPORTED[territory flag] | 273-274 |
| J2 | reactive hire, paid, recruiter call | UNSUPPORTED[recruiter_call] | 534-537 |
| J3 | escalation ban vs site exclusion | UNSUPPORTED[escalation event] | 549, 566-567 |
| J4 | margin check at judgment time | UNSUPPORTED[margin predicate] | 395, 432, 442 |
| J5 | compressor model-tag QA | SUPPORTED | 475-476 |

## J1 primary out-of-territory flag
- Transcript: client covers one territory; an out-of-territory work order is not rejected but
  flagged, so the sales rep can call the sender (273-274). Secondary clients differ: taking
  out-of-coverage work is a risk (275).
- Path: work_order -> territory_flag -> sales_rep_notified. Objects: client, site, work_order.
- Store has `site.territory_client` but no flag event or notify kind. Missing: territory_flag.
- Mutation: withhold territory_flag; conformance must break. Ratio: 1 flag per out-of-territory
  work order. No SLA stated.

## J2 reactive hire, paid, recruiter call
- Transcript: dispatcher reactively sources a provider when the network cannot serve; once the
  provider is paid, a recruiter phones them to complete the profile (534-537).
- Path: work_order -> provider -> dispatch -> ... -> ledger_settled -> recruiter_call.
- Objects: provider, work_order, payout. Missing: recruiter_call event.
- Mutation: withhold recruiter_call after ledger_settled. Ratio: 1 call per reactive hire.
  No SLA stated.

## J3 escalation ban vs site exclusion
- Transcript: escalations become tickets and may end in blacklisting or realignment (548-549).
  Invoice left on site is an immediate ban from everything; a clash with a manager excludes
  that site only, not the client (566-567).
- Path: escalation -> provider_blacklist (ban) or provider_filter dim=site mode=exc.
- Store has provider_blacklist and provider_filter but no escalation event to discriminate.
- Mutation: withhold escalation before provider_blacklist. No SLA stated.

## J4 margin check
- Transcript wording differs from the label: there is no "dual clock". Judgment calls weigh
  margin (395), cost versus charge, with NTE-driven cost data "not to be fully trusted" (432),
  and baseline numbers surfaced at decision time (442).
- Path: work_order -> margin_checked -> dispatch. Objects: client_rate, provider rate, NTE.
- Store holds rates and nte_cents but no margin predicate or event.
- Mutation: withhold margin_checked before dispatch. No SLA stated.

## J5 compressor model-tag QA
- Transcript: QA reviews provider photos (475); a compressor photo without the model tag is
  rejected with a request for a new photo (476).
- Path: work_order, plan_dispatched, dispatch, checkin, media:before_media,
  media:model_tag_photo, media:after_media, checkout, plan_closed, ledger_settled
  (model tag may precede before_media).
- Objects: work_order -> media_artifact. Ratio: model_tag_photo per checkout and per-order
  media bounds from the TOML. No SLA stated (empty list).
- Mutation: withhold media:model_tag_photo; token-replay fitness drops below 1.0.
