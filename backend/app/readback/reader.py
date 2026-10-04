from dataclasses import dataclass

from app.adapters.ports import GitHubPort
from app.readback.checks import (
    Finding,
    HeadCheck,
    InputCheck,
    IntegrityCheck,
    ManifestSignatureCheck,
    PropertiesCheck,
    ReadBackCheck,
    ReadBackContext,
    RecordCheck,
    RegenerationCheck,
    RepositoryExistsCheck,
)
from app.readback.manifest import ManifestSigner
from app.readback.subjects import ReadBackSubject


@dataclass(frozen=True)
class ReadBackResult:
    verified: bool
    commit_sha: str | None
    findings: list[Finding]
    design: dict
    request: dict | None

    def as_dict(self) -> dict:
        return {"verified": self.verified, "commit_sha": self.commit_sha,
                "findings": [finding.as_dict() for finding in self.findings], "design": self.design,
                "request": self.request}


class RepositoryReader:
    """Loads a design back from a repository only when the platform generated it and nobody edited it (§21.3)."""

    def __init__(self, github: GitHubPort, owner: str, signer: ManifestSigner, checks: list[ReadBackCheck]):
        self._github = github
        self._owner = owner
        self._signer = signer
        self._checks = checks

    @classmethod
    def default(cls, github: GitHubPort, owner: str, signer: ManifestSigner) -> "RepositoryReader":
        return cls(github, owner, signer, [RepositoryExistsCheck(), PropertiesCheck(), ManifestSignatureCheck(),
                                           RecordCheck(), IntegrityCheck(), InputCheck(), HeadCheck(),
                                           RegenerationCheck()])

    def read(self, subject: ReadBackSubject) -> ReadBackResult:
        context = self._context(subject)
        findings: list[Finding] = []
        for check in self._checks:
            findings += check.run(context)
            if any(finding.blocking for finding in findings):
                break
        verified = not any(finding.blocking for finding in findings)
        return ReadBackResult(verified=verified, commit_sha=context.snapshot.commit_sha if context.snapshot else None,
                              findings=findings, design=subject.identity(),
                              request=context.request if verified else None)

    def _context(self, subject: ReadBackSubject) -> ReadBackContext:
        if not self._github.repository_exists(self._owner, subject.repository):
            return ReadBackContext(subject, self._signer, snapshot=None, properties={})
        return ReadBackContext(subject, self._signer, snapshot=self._github.read_files(self._owner, subject.repository),
                               properties=self._github.repository_properties(self._owner, subject.repository))
