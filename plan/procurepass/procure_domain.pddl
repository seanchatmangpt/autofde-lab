;; ProcurePass: parts procurement + 2-visit scheduling (PDDL 2.1, standalone subset of servengine types)
(define (domain procurepass)
  (:requirements :typing :fluents :durative-actions :negative-preconditions)
  (:types
    physical_locus artifact - object
    site - physical_locus
    work_order visit proposal part_order - artifact
    reactive_wo change_order_wo - work_order)
  (:predicates
    (wo-at-site ?wo - work_order ?s - site)
    (wo-diagnosed ?wo - work_order)
    (wo-linked-parent ?child - work_order ?parent - work_order)
    (wo-complete ?wo - work_order)
    (visit-of-wo ?v - visit ?wo - work_order)
    (proposal-for ?prop - proposal ?wo - work_order)
    (proposal-generated ?prop - proposal ?wo - work_order)
    (proposal-within-nte ?prop - proposal)
    (proposal-over-nte ?prop - proposal)
    (change-order-approved ?co - change_order_wo)
    (proposal-client-accepted ?prop - proposal)
    (part-for ?po - part_order ?wo - work_order)
    (part-ordered ?po - part_order ?wo - work_order)
    (part-delivered ?po - part_order ?s - site)
    (visit-done ?v - visit))
  (:functions
    (wo-nte-limit ?wo - work_order)
    (wo-labor-cost ?wo - work_order)
    (part-cost ?po - part_order)
    (part-lead-time ?po - part_order)
    (part-markup ?po - part_order)   ; integer percent (120 = x1.20); totals scaled x100
    (diagnose-duration ?v - visit)
    (install-duration ?v - visit)
    (calculated-proposal-total ?prop - proposal))

  (:durative-action diagnose-visit
    :parameters (?wo - reactive_wo ?v - visit ?s - site)
    :duration (= ?duration (diagnose-duration ?v))
    :condition (and (at start (visit-of-wo ?v ?wo)) (at start (wo-at-site ?wo ?s))
                    (at start (not (visit-done ?v))))
    :effect (and (at end (wo-diagnosed ?wo)) (at end (visit-done ?v))))

  ;; total = labor + part-cost * markup, must be <= NTE
  (:durative-action propose-parts
    :parameters (?wo - reactive_wo ?prop - proposal ?po - part_order)
    :duration (= ?duration 1)
    :condition (and (at start (wo-diagnosed ?wo)) (at start (proposal-for ?prop ?wo))
                    (at start (part-for ?po ?wo))
                    (at start (<= (+ (* (wo-labor-cost ?wo) 100) (* (part-cost ?po) (part-markup ?po)))
                                  (* (wo-nte-limit ?wo) 100))))
    :effect (and (at end (proposal-generated ?prop ?wo)) (at end (proposal-within-nte ?prop))
                 (at end (assign (calculated-proposal-total ?prop)
                                 (+ (* (wo-labor-cost ?wo) 100) (* (part-cost ?po) (part-markup ?po)))))))

  ;; total > NTE => proposal flagged, change order required
  (:durative-action propose-parts-over-nte
    :parameters (?wo - reactive_wo ?prop - proposal ?po - part_order)
    :duration (= ?duration 1)
    :condition (and (at start (wo-diagnosed ?wo)) (at start (proposal-for ?prop ?wo))
                    (at start (part-for ?po ?wo))
                    (at start (> (+ (* (wo-labor-cost ?wo) 100) (* (part-cost ?po) (part-markup ?po)))
                                 (* (wo-nte-limit ?wo) 100))))
    :effect (and (at end (proposal-generated ?prop ?wo)) (at end (proposal-over-nte ?prop))
                 (at end (assign (calculated-proposal-total ?prop)
                                 (+ (* (wo-labor-cost ?wo) 100) (* (part-cost ?po) (part-markup ?po)))))))

  (:durative-action spawn-change-order
    :parameters (?wo - reactive_wo ?co - change_order_wo ?prop - proposal)
    :duration (= ?duration 1)
    :condition (and (at start (proposal-generated ?prop ?wo)) (at start (proposal-over-nte ?prop)))
    :effect (at end (wo-linked-parent ?co ?wo)))

  (:durative-action approve-change-order
    :parameters (?wo - reactive_wo ?co - change_order_wo)
    :duration (= ?duration 4)
    :condition (at start (wo-linked-parent ?co ?wo))
    :effect (at end (change-order-approved ?co)))

  (:durative-action client-accept-proposal
    :parameters (?wo - reactive_wo ?prop - proposal)
    :duration (= ?duration 2)
    :condition (and (at start (proposal-generated ?prop ?wo)) (at start (proposal-within-nte ?prop)))
    :effect (at end (proposal-client-accepted ?prop)))

  (:durative-action client-accept-change-order-proposal
    :parameters (?wo - reactive_wo ?prop - proposal ?co - change_order_wo)
    :duration (= ?duration 2)
    :condition (and (at start (proposal-generated ?prop ?wo)) (at start (proposal-over-nte ?prop))
                    (at start (wo-linked-parent ?co ?wo)) (at start (change-order-approved ?co)))
    :effect (at end (proposal-client-accepted ?prop)))

  (:durative-action order-part
    :parameters (?wo - reactive_wo ?prop - proposal ?po - part_order)
    :duration (= ?duration 1)
    :condition (and (at start (proposal-client-accepted ?prop)) (at start (proposal-for ?prop ?wo))
                    (at start (part-for ?po ?wo)))
    :effect (at end (part-ordered ?po ?wo)))

  (:durative-action deliver-part-to-site
    :parameters (?wo - reactive_wo ?po - part_order ?s - site)
    :duration (= ?duration (part-lead-time ?po))
    :condition (and (at start (part-ordered ?po ?wo)) (at start (wo-at-site ?wo ?s)))
    :effect (at end (part-delivered ?po ?s)))

  (:durative-action schedule-return-visit
    :parameters (?wo - reactive_wo ?v - visit ?s - site ?po - part_order)
    :duration (= ?duration (install-duration ?v))
    :condition (and (at start (visit-of-wo ?v ?wo)) (at start (wo-at-site ?wo ?s))
                    (at start (wo-diagnosed ?wo)) (at start (part-for ?po ?wo))
                    (at start (part-delivered ?po ?s)) (at start (not (visit-done ?v))))
    :effect (and (at end (wo-complete ?wo)) (at end (visit-done ?v)))))
