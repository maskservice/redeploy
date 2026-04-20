"""Exceptions for Python-native DSL."""


class DSLException(Exception):
    """Base exception for DSL errors."""
    pass


class StepError(DSLException):
    """Raised when a step fails."""
    def __init__(self, step_name: str, message: str, output: str = ""):
        self.step_name = step_name
        self.output = output
        super().__init__(f"Step '{step_name}' failed: {message}")


class TimeoutError(DSLException):
    """Raised when a step times out."""
    def __init__(self, step_name: str, timeout: int):
        self.step_name = step_name
        self.timeout = timeout
        super().__init__(f"Step '{step_name}' timed out after {timeout}s")


class VerificationError(DSLException):
    """Raised when verification fails."""
    def __init__(self, check_type: str, expected: str, actual: str):
        self.check_type = check_type
        self.expected = expected
        self.actual = actual
        super().__init__(f"{check_type} verification failed: expected '{expected}', got '{actual}'")


class ConnectionError(DSLException):
    """Raised when SSH/connection fails."""
    pass


class RollbackError(DSLException):
    """Raised when rollback fails."""
    def __init__(self, step_name: str, original_error: Exception):
        self.step_name = step_name
        self.original_error = original_error
        super().__init__(f"Rollback for step '{step_name}' failed: {original_error}")
