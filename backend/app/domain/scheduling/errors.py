from app.domain.shared.errors import DomainError


class JobNotCancellable(DomainError):
    code = "JOB_NOT_CANCELLABLE"
