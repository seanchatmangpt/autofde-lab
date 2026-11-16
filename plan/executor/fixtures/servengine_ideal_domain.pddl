;; DOMAIN: SERVENGINE-CLEAN-SHEET-AUTONOMOUS-FM (PDDL 2.1 baseline from operator spec; lanes repair+validate)
(define (domain servengine-autonomous-fm)
  (:requirements :typing :fluents :durative-actions :timed-initial-literals
                 :negative-preconditions :disjunctive-preconditions :conditional-effects :equality)
  (:types
    organization actor vendor physical_locus artifact taxonomy evidence channel client - object
    tenant_entity dba_brand - organization
    primary_client secondary_client - client
    site asset - physical_locus
    coordinator escalations_officer ap_manager super_admin - actor
    provider - vendor
    w2_tech sub_1099 - provider
    work_order visit proposal invoice ap_payout part_order - artifact
    reactive_wo preventive_wo inspection_wo project_wo recall_wo change_order_wo - work_order
    trade sub_trade state_jurisdiction priority_tier link_kind - taxonomy
    doc_slot media_artifact - evidence
    ss4_doc w9_doc coi_doc license_doc contract_doc - doc_slot
    uniform_photo footwear_photo vehicle_photo before_media during_media after_media model_tag_photo - media_artifact
    delivery_channel - channel)
  (:constants ch_email ch_portal_api ch_edi - delivery_channel
              lk_change_order lk_recall - link_kind)
  (:predicates
    (belongs-to-entity ?dba - dba_brand ?e - tenant_entity)
    (entity-active ?e - tenant_entity)
    (entity-doc-verified ?e - tenant_entity ?d - doc_slot)
    (entity-templates-bound ?e - tenant_entity)
    (client-bound-to-entity ?c - client ?e - tenant_entity)
    (contracted-through ?sec - secondary_client ?pri - primary_client)
    (site-belongs-to ?s - site ?c - client)
    (site-in-state ?s - site ?st - state_jurisdiction)
    (site-in-territory ?s - site ?c - client)
    (asset-at-site ?a - asset ?s - site)
    (client-delivery-mode ?c - client ?ch - delivery_channel)
    (provider-onboarded ?p - provider ?e - tenant_entity)
    (provider-doc-valid ?p - provider ?d - doc_slot)
    (provider-trade-approved ?p - provider ?t - trade ?st - sub_trade)
    (provider-rate-approved ?p - provider ?t - trade)
    (provider-aligned ?p - provider ?e - tenant_entity)
    (provider-blacklisted ?p - provider)
    (eligible-for-wo ?p - provider ?wo - work_order)
    (reactive-hire-triggered ?wo - work_order)
    (wo-at-site ?wo - work_order ?s - site)
    (wo-for-client ?wo - work_order ?c - client)
    (wo-under-entity ?wo - work_order ?e - tenant_entity)
    (wo-requires-trade ?wo - work_order ?t - trade ?st - sub_trade)
    (wo-priority ?wo - work_order ?pr - priority_tier)
    (wo-assigned-coordinator ?wo - work_order ?coord - coordinator)
    (wo-linked-parent ?child - work_order ?parent - work_order)
    (wo-linked ?child - work_order ?parent - work_order ?k - link_kind)
    (territory-flag ?wo - work_order)
    (sales-rep-notified ?wo - work_order)
    (territory-waived ?wo - work_order)
    (wo-territory-cleared ?wo - work_order)
    (reactive-hire-handed-off ?wo - work_order)
    (visit-follow-up ?v - visit ?prior - visit)
    (provider-pay-duration-set ?v - visit)
    (quoted-pay-elected ?wo - work_order)
    (wo-state-intake ?wo - work_order)
    (wo-state-triaged ?wo - work_order)
    (wo-state-dispatched ?wo - work_order)
    (wo-state-on-site ?wo - work_order)
    (wo-state-qa-review ?wo - work_order)
    (wo-state-proposal-pending ?wo - work_order)
    (wo-state-ready-to-invoice ?wo - work_order)
    (wo-state-invoiced ?wo - work_order)
    (wo-state-closed ?wo - work_order)
    (visit-of-wo ?v - visit ?wo - work_order)
    (visit-assigned ?v - visit ?p - provider)
    (geofence-attested ?v - visit ?p - provider ?s - site)
    (device-integrity-attested ?p - provider)
    (internal-checked-in ?v - visit)
    (internal-checked-out ?v - visit)
    (external-checked-in ?v - visit)
    (external-checked-out ?v - visit)
    (media-captured ?v - visit ?m - media_artifact)
    (requires-part-replacement ?wo - work_order ?a - asset)
    (wo-no-part-replacement ?wo - work_order)
    (ai-vision-verified ?v - visit)
    (media-approved-for-client ?v - visit ?m - media_artifact)
    (part-ordered ?po - part_order ?wo - work_order)
    (part-delivered ?po - part_order ?s - site)
    (proposal-generated ?prop - proposal ?wo - work_order)
    (proposal-client-accepted ?prop - proposal)
    (invoice-emitted ?inv - invoice ?wo - work_order)
    (invoice-delivered ?inv - invoice ?ch - delivery_channel)
    (ap-payout-authorized ?pay - ap_payout ?v - visit ?p - provider)
    (ap-payout-settled ?pay - ap_payout))
  (:functions
    (current-clock)
    (wo-onsite-sla ?wo - work_order)
    (wo-complete-sla ?wo - work_order)
    (doc-expiry-time ?p - provider ?d - doc_slot)
    (internal-actual-duration ?v - visit)
    (provider-pay-duration ?v - visit)
    (external-client-duration ?v - visit)
    (proposal-quoted-duration ?wo - work_order)
    (wo-nte-limit ?wo - work_order)
    (client-labor-rate ?c - client ?t - trade)
    (client-payment-terms-days ?c - client)
    (provider-agreed-rate ?p - provider ?t - trade)
    (provider-dispatch-rank ?p - provider ?t - trade)
    (part-cost ?po - part_order)
    (calculated-proposal-total ?prop - proposal)
    (invoice-amount ?inv - invoice)
    (invoice-due-timestamp ?inv - invoice)
    (ap-payout-amount ?pay - ap_payout)
    (coordinator-active-load ?coord - coordinator))

  (:durative-action activate-entity
    :parameters (?e - tenant_entity ?ss4 - ss4_doc ?w9 - w9_doc)
    :duration (= ?duration 1)
    :condition (and (at start (entity-doc-verified ?e ?ss4)) (at start (entity-doc-verified ?e ?w9))
                    (at start (entity-templates-bound ?e)))
    :effect (at end (entity-active ?e)))

  (:durative-action derive-wo-territory-cleared
    :parameters (?wo - work_order ?c - client ?s - site)
    :duration (= ?duration 1)
    :condition (and (at start (wo-for-client ?wo ?c)) (at start (wo-at-site ?wo ?s))
      (at start (or (site-in-territory ?s ?c) (territory-flag ?wo) (territory-waived ?wo))))
    :effect (at end (wo-territory-cleared ?wo)))

  (:durative-action reactive-hire-handoff
    :parameters (?wo - work_order)
    :duration (= ?duration 1)
    :condition (and (at start (wo-state-triaged ?wo)) (at start (reactive-hire-triggered ?wo)))
    :effect (and (at start (not (wo-state-triaged ?wo))) (at end (reactive-hire-handed-off ?wo)) (at end (wo-state-closed ?wo))))

  (:durative-action hold-linked-wo-for-parent
    :parameters (?child - work_order ?parent - work_order ?k - link_kind)
    :duration (= ?duration 1)
    :condition (and (at start (wo-state-triaged ?child)) (at start (wo-linked ?child ?parent ?k))
      (at start (wo-linked-parent ?child ?parent)) (at start (not (wo-state-closed ?parent))))
    :effect (and (at start (not (wo-state-triaged ?child))) (at end (wo-state-proposal-pending ?child))))

  (:durative-action release-linked-wo-after-parent
    :parameters (?child - work_order ?parent - work_order)
    :duration (= ?duration 1)
    :condition (and (at start (wo-state-proposal-pending ?child)) (at start (wo-linked-parent ?child ?parent))
      (at start (wo-state-closed ?parent)))
    :effect (and (at start (not (wo-state-proposal-pending ?child))) (at end (wo-state-triaged ?child))))

  (:durative-action open-follow-up-visit
    :parameters (?wo - work_order ?prior - visit ?v - visit)
    :duration (= ?duration 1)
    :condition (and (at start (visit-of-wo ?prior ?wo)) (at start (visit-of-wo ?v ?wo))
      (at start (internal-checked-out ?prior)))
    :effect (at end (visit-follow-up ?v ?prior)))

  (:durative-action certify-provider-alignment
    :parameters (?p - provider ?e - tenant_entity ?t - trade ?st - sub_trade
                 ?w9 - w9_doc ?coi - coi_doc ?lic - license_doc ?con - contract_doc)
    :duration (= ?duration 5)
    :condition (and (at start (entity-active ?e)) (at start (provider-onboarded ?p ?e))
      (over all (not (provider-blacklisted ?p)))
      (at start (provider-doc-valid ?p ?w9)) (at start (provider-doc-valid ?p ?coi))
      (at start (provider-doc-valid ?p ?lic)) (at start (provider-doc-valid ?p ?con))
      (at start (> (doc-expiry-time ?p ?coi) (current-clock)))
      (at start (> (doc-expiry-time ?p ?lic) (current-clock)))
      (at start (provider-trade-approved ?p ?t ?st)) (at start (provider-rate-approved ?p ?t)))
    :effect (at end (provider-aligned ?p ?e)))

  (:durative-action triage-and-route-work-order
    :parameters (?wo - work_order ?e - tenant_entity ?c - client ?s - site
                 ?t - trade ?st - sub_trade ?coord - coordinator)
    :duration (= ?duration 2)
    :condition (and (at start (wo-state-intake ?wo)) (at start (entity-active ?e))
      (at start (wo-under-entity ?wo ?e)) (at start (wo-for-client ?wo ?c))
      (at start (client-bound-to-entity ?c ?e)) (at start (wo-at-site ?wo ?s))
      (at start (site-belongs-to ?s ?c))
      (at start (or (site-in-territory ?s ?c) (territory-flag ?wo) (territory-waived ?wo)))
      (at start (wo-requires-trade ?wo ?t ?st)) (at start (> (wo-nte-limit ?wo) 0)))
    :effect (and (at start (not (wo-state-intake ?wo))) (at end (wo-state-triaged ?wo))
      (at end (wo-assigned-coordinator ?wo ?coord))
      (at end (increase (coordinator-active-load ?coord) 1))))

  (:durative-action auto-dispatch-aligned-provider
    :parameters (?wo - work_order ?v - visit ?p - provider ?e - tenant_entity
                 ?t - trade ?st - sub_trade ?coi - coi_doc ?lic - license_doc)
    :duration (= ?duration 3)
    :condition (and (at start (wo-state-triaged ?wo)) (at start (wo-under-entity ?wo ?e))
      (at start (wo-requires-trade ?wo ?t ?st)) (at start (visit-of-wo ?v ?wo))
      (at start (provider-aligned ?p ?e)) (over all (not (provider-blacklisted ?p)))
      (at start (> (doc-expiry-time ?p ?coi) (current-clock)))
      (at start (> (doc-expiry-time ?p ?lic) (current-clock)))
      (at start (eligible-for-wo ?p ?wo)))
    :effect (and (at start (not (wo-state-triaged ?wo))) (at end (visit-assigned ?v ?p))
      (at end (wo-state-dispatched ?wo))))

  (:durative-action execute-site-visit
    :parameters (?wo - work_order ?v - visit ?p - provider ?s - site
                 ?u_pic - uniform_photo ?f_pic - footwear_photo ?v_pic - vehicle_photo
                 ?b_med - before_media ?d_med - during_media ?a_med - after_media)
    :duration (= ?duration (internal-actual-duration ?v))
    :condition (and (at start (wo-state-dispatched ?wo)) (at start (wo-at-site ?wo ?s))
      (at start (visit-of-wo ?v ?wo)) (at start (visit-assigned ?v ?p))
      (over all (not (provider-blacklisted ?p)))
      (at start (device-integrity-attested ?p)) (over all (geofence-attested ?v ?p ?s))
      (at start (media-captured ?v ?u_pic)) (at start (media-captured ?v ?f_pic))
      (at start (media-captured ?v ?v_pic))
      (at start (<= (current-clock) (wo-onsite-sla ?wo))))
    :effect (and (at start (not (wo-state-dispatched ?wo))) (at start (wo-state-on-site ?wo))
      (at start (internal-checked-in ?v))
      (at end (media-captured ?v ?b_med)) (at end (media-captured ?v ?d_med))
      (at end (media-captured ?v ?a_med)) (at end (internal-checked-out ?v))
      (at end (not (wo-state-on-site ?wo))) (at end (wo-state-qa-review ?wo))))

  (:durative-action commit-external-client-attendance
    :parameters (?wo - work_order ?v - visit)
    :duration (= ?duration 1)
    :condition (and (at start (visit-of-wo ?v ?wo)) (at start (internal-checked-in ?v))
      (at start (internal-checked-out ?v))
      (at start (= (external-client-duration ?v) (proposal-quoted-duration ?wo))))
    :effect (and (at end (external-checked-in ?v)) (at end (external-checked-out ?v))))

  (:durative-action run-ai-vision-closeout-gate
    :parameters (?wo - work_order ?v - visit ?a - asset
                 ?b_med - before_media ?a_med - after_media ?tag_pic - model_tag_photo)
    :duration (= ?duration 2)
    :condition (and (at start (wo-state-qa-review ?wo)) (at start (visit-of-wo ?v ?wo))
      (at start (media-captured ?v ?b_med)) (at start (media-captured ?v ?a_med))
      (at start (or (not (requires-part-replacement ?wo ?a)) (media-captured ?v ?tag_pic))))
    :effect (and (at end (ai-vision-verified ?v))
      (at end (media-approved-for-client ?v ?b_med)) (at end (media-approved-for-client ?v ?a_med))
      (at end (not (wo-state-qa-review ?wo))) (at end (wo-state-ready-to-invoice ?wo))))

  (:durative-action run-ai-vision-closeout-gate-no-part
    :parameters (?wo - work_order ?v - visit ?b_med - before_media ?a_med - after_media)
    :duration (= ?duration 2)
    :condition (and (at start (wo-state-qa-review ?wo)) (at start (visit-of-wo ?v ?wo))
      (at start (media-captured ?v ?b_med)) (at start (media-captured ?v ?a_med))
      (at start (wo-no-part-replacement ?wo)))
    :effect (and (at end (ai-vision-verified ?v))
      (at end (media-approved-for-client ?v ?b_med)) (at end (media-approved-for-client ?v ?a_med))
      (at end (not (wo-state-qa-review ?wo))) (at end (wo-state-ready-to-invoice ?wo))))

  (:durative-action emit-and-deliver-client-invoice
    :parameters (?wo - work_order ?v - visit ?inv - invoice ?c - client
                 ?e - tenant_entity ?t - trade ?st - sub_trade ?ch - delivery_channel)
    :duration (= ?duration 2)
    :condition (and (at start (wo-state-ready-to-invoice ?wo)) (at start (wo-for-client ?wo ?c))
      (at start (wo-under-entity ?wo ?e)) (at start (wo-requires-trade ?wo ?t ?st))
      (at start (visit-of-wo ?v ?wo)) (at start (ai-vision-verified ?v))
      (at start (external-checked-out ?v)) (at start (entity-templates-bound ?e))
      (at start (client-delivery-mode ?c ?ch))
      (at start (<= (external-client-duration ?v) (wo-complete-sla ?wo))))
    :effect (and
      (at end (assign (invoice-amount ?inv) (* (external-client-duration ?v) (client-labor-rate ?c ?t))))
      (at end (assign (invoice-due-timestamp ?inv) (+ (current-clock) (* (client-payment-terms-days ?c) 1440))))
      (at end (invoice-emitted ?inv ?wo)) (at end (invoice-delivered ?inv ?ch))
      (at end (not (wo-state-ready-to-invoice ?wo))) (at end (wo-state-invoiced ?wo))))

  (:durative-action settle-provider-ap-payout
    :parameters (?wo - work_order ?v - visit ?p - provider ?t - trade ?pay - ap_payout)
    :duration (= ?duration 2)
    :condition (and (at start (wo-state-invoiced ?wo)) (at start (visit-of-wo ?v ?wo))
      (at start (visit-assigned ?v ?p)) (at start (internal-checked-out ?v))
      (at start (ai-vision-verified ?v)) (over all (not (provider-blacklisted ?p))))
    :effect (and
      (at end (assign (ap-payout-amount ?pay) (* (internal-actual-duration ?v) (provider-agreed-rate ?p ?t))))
      (at end (ap-payout-authorized ?pay ?v ?p)) (at end (ap-payout-settled ?pay))
      (at end (not (wo-state-invoiced ?wo))) (at end (wo-state-closed ?wo))))

  (:durative-action record-provider-pay-duration
    :parameters (?wo - work_order ?v - visit)
    :duration (= ?duration 1)
    :condition (and (at start (visit-of-wo ?v ?wo)) (at start (internal-checked-out ?v)))
    :effect (and (at end (assign (provider-pay-duration ?v) (internal-actual-duration ?v)))
      (at end (provider-pay-duration-set ?v))))

  (:durative-action settle-provider-ap-payout-quoted
    :parameters (?wo - work_order ?v - visit ?p - provider ?t - trade ?pay - ap_payout)
    :duration (= ?duration 2)
    :condition (and (at start (wo-state-invoiced ?wo)) (at start (visit-of-wo ?v ?wo))
      (at start (visit-assigned ?v ?p)) (at start (internal-checked-out ?v))
      (at start (ai-vision-verified ?v)) (at start (provider-pay-duration-set ?v))
      (at start (quoted-pay-elected ?wo))
      (over all (not (provider-blacklisted ?p))))
    :effect (and
      (at end (assign (ap-payout-amount ?pay) (* (proposal-quoted-duration ?wo) (provider-agreed-rate ?p ?t))))
      (at end (ap-payout-authorized ?pay ?v ?p)) (at end (ap-payout-settled ?pay))
      (at end (not (wo-state-invoiced ?wo))) (at end (wo-state-closed ?wo)))))
