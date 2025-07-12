"""
Custom exceptions for the VPR system.
"""


class VPRException(Exception):
    """Base exception for all VPR errors."""

    pass


class NavigationError(VPRException):
    """Raised when navigation fails."""

    pass


class ElementNotFoundError(VPRException):
    """Raised when an element cannot be found."""

    pass


class TimeoutError(VPRException):
    """Raised when an operation times out."""

    pass


class RecordingError(VPRException):
    """Raised when recording fails."""

    pass


class WorkflowError(VPRException):
    """Raised when workflow execution fails."""

    pass
