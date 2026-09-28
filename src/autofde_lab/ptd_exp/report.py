import hashlib

from .replay import deterministic_report


def seal_report(report):
    out = dict(report)
    out["report_sha256"] = hashlib.sha256(deterministic_report(report)).hexdigest()
    return out


def compare_reports(a, b):
    return [
        k
        for k in sorted(set(a) | set(b))
        if a.get(k) != b.get(k) and k != "report_sha256"
    ]
