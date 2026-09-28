from .identity import canonical_digest
REQUIRED={"schema","experiment_id","subject_id","epochs","attacks","criteria"}
def validate_manifest(data):
 missing=REQUIRED-data.keys()
 if missing: raise ValueError("missing: "+",".join(sorted(missing)))
 if data["schema"]!="autofde-lab.ptd.campaign/v2": raise ValueError("unsupported PTD schema")
 if len(data["epochs"])<2: raise ValueError("at least two epochs required")
def manifest_digest(data): validate_manifest(data); return canonical_digest(data)
