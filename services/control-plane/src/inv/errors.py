from dataclasses import dataclass


@dataclass
class DomainError(Exception):
    code: str
    detail: str
    status: int = 409
    retryable: bool = False

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"
