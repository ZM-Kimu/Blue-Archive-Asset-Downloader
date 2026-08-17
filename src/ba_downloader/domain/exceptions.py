from enum import StrEnum
from typing import ClassVar


class ErrorCode(StrEnum):
    internal = "INTERNAL_ERROR"
    config_invalid = "CONFIG_INVALID"
    dispatch_duplicate = "DISPATCH_DUPLICATE"
    dispatch_unhandled = "DISPATCH_UNHANDLED"
    network_failed = "NETWORK_FAILED"
    catalog_failed = "CATALOG_FAILED"
    download_failed = "DOWNLOAD_FAILED"
    extraction_decode_failed = "EXTRACTION_DECODE_FAILED"
    extraction_failed = "EXTRACTION_FAILED"
    schema_failed = "SCHEMA_FAILED"
    recovery_failed = "RECOVERY_FAILED"
    storage_failed = "STORAGE_FAILED"
    external_tool_failed = "EXTERNAL_TOOL_FAILED"
    cancelled = "CANCELLED"


class BAError(Exception):
    """Base application error."""

    code: ClassVar[ErrorCode] = ErrorCode.internal


class ConfigError(BAError):
    """Invalid configuration."""

    code = ErrorCode.config_invalid


class DispatchError(BAError):
    """Application message registration or dispatch failure."""


class DuplicateMessageRegistrationError(DispatchError):
    """The same message type was registered more than once."""

    code = ErrorCode.dispatch_duplicate


class UnhandledMessageError(DispatchError):
    """No handler was registered for an application message."""

    code = ErrorCode.dispatch_unhandled


class NetworkError(BAError):
    """Network failure while fetching remote content."""

    code = ErrorCode.network_failed


class DownloadError(BAError):
    """Download workflow failed to complete all requested resources."""

    code = ErrorCode.download_failed


class DecodeError(BAError):
    """Resource decoding failure."""

    code = ErrorCode.extraction_decode_failed


class ExtractError(BAError):
    """Resource extraction failure."""

    code = ErrorCode.extraction_failed


class ExternalToolError(BAError):
    """External command or SDK failure."""

    code = ErrorCode.external_tool_failed


class ProcessExecutionError(ExternalToolError):
    """External process exited with a nonzero status."""

    def __init__(
        self,
        argv: tuple[str, ...],
        returncode: int,
        stdout: str,
        stderr: str,
    ) -> None:
        self.argv = argv
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        detail = stderr.strip() or stdout.strip() or "No process output was captured."
        super().__init__(f"External process exited with status {returncode}: {detail}")


class OperationCancelledError(BAError):
    """Application operation was cancelled."""

    code = ErrorCode.cancelled
