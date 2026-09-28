from dataclasses import dataclass
@dataclass(frozen=True)
class AttackerKnowledge: source_epoch:str; facts:frozenset[str]
def retention_by_facts(stale,fresh): return 0. if not fresh.facts else len(stale.facts&fresh.facts)/len(fresh.facts)
