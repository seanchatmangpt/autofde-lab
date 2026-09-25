"""Passive end-to-end runner for the IEC observation rail."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .engine import IECSession, InverseEcosystemCompiler
from .filesystem import PassiveRepositoryReader
from .inventory import RepositoryInventory, RepositoryInventoryScanner
from .model import RepositorySubject, digest
from .rdf_projection import project_repository
from .receipts import IECReceipt, IECStage, ReceiptChain
from .structural import StructuralDocument, StructuralParserRegistry


@dataclass(frozen=True, slots=True)
class RepositoryInput:
    subject: RepositorySubject
    root: str
    included_paths: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class RepositoryRun:
    subject: RepositorySubject
    inventory: RepositoryInventory
    structural_documents: tuple[tuple[str, StructuralDocument], ...]
    rdf_projection: str

    @property
    def run_id(self) -> str:
        return digest(
            {
                "subject": self.subject,
                "inventory": self.inventory,
                "structural": tuple(
                    (path, document.document_id)
                    for path, document in self.structural_documents
                ),
                "rdf": digest(self.rdf_projection),
            }
        )


@dataclass(frozen=True, slots=True)
class PassiveRunResult:
    session: IECSession
    repositories: tuple[RepositoryRun, ...]
    receipts: tuple[IECReceipt, ...]

    @property
    def run_id(self) -> str:
        return digest(
            {
                "session": self.session.session_id,
                "repositories": tuple(item.run_id for item in self.repositories),
                "receipts": tuple(receipt.receipt_id for receipt in self.receipts),
            }
        )


class PassiveCorpusRunner:
    """Run the non-executing IEC ingest/parse/project path."""

    def __init__(
        self,
        *,
        compiler: InverseEcosystemCompiler | None = None,
        parsers: StructuralParserRegistry | None = None,
    ) -> None:
        self.compiler = compiler or InverseEcosystemCompiler()
        self.parsers = parsers or StructuralParserRegistry()

    def run(self, repositories: Iterable[RepositoryInput]) -> PassiveRunResult:
        inputs = tuple(sorted(repositories, key=lambda item: item.subject.repository))
        if not inputs:
            raise ValueError("at least one repository input is required")

        session = self.compiler.freeze(item.subject for item in inputs)
        receipt_chain = ReceiptChain()
        receipt_chain.append(
            stage=IECStage.CORPUS_FREEZE,
            subject_ids=tuple(item.subject.subject_id for item in inputs),
            input_ids=(),
            output_ids=(session.corpus.revision_id,),
            result="OBSERVED",
        )

        repository_runs: list[RepositoryRun] = []
        for item in inputs:
            inventory = RepositoryInventoryScanner(item.root).scan()
            selected_paths = (
                tuple(sorted(set(item.included_paths)))
                if item.included_paths is not None
                else inventory.text_paths
            )
            reader = PassiveRepositoryReader(item.root)
            files = reader.read_many(selected_paths)
            session = self.compiler.observe(
                session,
                item.subject,
                files,
            )
            analysis = next(
                analysis
                for analysis in session.analyses
                if analysis.subject == item.subject
            )

            structural: list[tuple[str, StructuralDocument]] = []
            file_by_path = {file.path: file for file in files}
            for artifact in analysis.artifacts:
                file = file_by_path[artifact.path]
                document = self.parsers.parse(
                    path=artifact.path,
                    content=file.content,
                    source_digest=artifact.content_digest,
                )
                structural.append((artifact.path, document))

            rdf = project_repository(
                item.subject,
                analysis.artifacts,
                analysis.observations,
            )
            repository_run = RepositoryRun(
                subject=item.subject,
                inventory=inventory,
                structural_documents=tuple(structural),
                rdf_projection=rdf,
            )
            repository_runs.append(repository_run)
            receipt_chain.append(
                stage=IECStage.OBSERVE,
                subject_ids=(item.subject.subject_id,),
                input_ids=(session.corpus.revision_id,),
                output_ids=(
                    analysis.analysis_id,
                    repository_run.run_id,
                ),
                result="OBSERVED",
            )

        return PassiveRunResult(
            session=session,
            repositories=tuple(repository_runs),
            receipts=receipt_chain.receipts(),
        )
