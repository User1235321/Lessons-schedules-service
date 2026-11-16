from app.domain.shared.errors import DomainError


class JobNotCancellable(DomainError):
    code = "JOB_NOT_CANCELLABLE"


class JobResultsUnavailable(DomainError):
    code = "JOB_RESULTS_UNAVAILABLE"
