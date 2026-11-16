;; reactive compressor replacement: diagnose (120m) -> part lead 24h (1440m) -> install (180m); SLA complete 4320m
(define (problem procure-compressor_over_nte)
  (:domain procurepass)
  (:objects site_sbux_0094 - site wo_9001 - reactive_wo co_9001 - change_order_wo
            vis_diag vis_install - visit prop_9001 - proposal po_compressor - part_order)
  (:init
    (wo-at-site wo_9001 site_sbux_0094)
    (visit-of-wo vis_diag wo_9001) (visit-of-wo vis_install wo_9001)
    (proposal-for prop_9001 wo_9001) (part-for po_compressor wo_9001)
    (= (wo-nte-limit wo_9001) 4000) (= (wo-labor-cost wo_9001) 1000)
    (= (part-cost po_compressor) 3500) (= (part-markup po_compressor) 120)
    (= (part-lead-time po_compressor) 1440)
    (= (diagnose-duration vis_diag) 120) (= (install-duration vis_install) 180)
    (= (calculated-proposal-total prop_9001) 0))
  (:goal (wo-complete wo_9001)))
