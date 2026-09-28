def project_ocel(subject_id,experiment_id,epoch_ids,report_digest):
 objects=[{"id":subject_id,"type":"subject"},{"id":experiment_id,"type":"experiment"}]+[{"id":e,"type":"epoch"} for e in epoch_ids]
 return {"objectTypes":["subject","experiment","epoch"],"objects":objects,"events":[{"id":"ptd:evaluate:"+experiment_id,"type":"ptd_evaluation","objects":[x["id"] for x in objects],"attributes":{"report_digest":report_digest}}]}
