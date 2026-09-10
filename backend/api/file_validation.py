"""Centralised, context-aware upload validation.

Every document-upload endpoint funnels its ``request.FILES`` entry through
:func:`validate_upload`, passing the :class:`UploadKind` for that workflow. The
validator is the authoritative check - it never trusts the filename extension,
the browser MIME type, or the frontend:

* size / emptiness
* extension is on the kind's allow-list
* the file *content* matches (PDF magic bytes; images open + report a real
  JPEG/PNG format via Pillow)

Rules per kind:

    PR                    -> pdf, jpg, jpeg, png
    SUPPLIER_REQUIREMENT  -> pdf, jpg, jpeg, png
    COMPLETED_RFQ         -> pdf only
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

# Reuse the single project-wide ceiling rather than inventing a new one.
try:  # pragma: no cover - trivial import shim
    from .supplier_registration import MAX_UPLOAD_SIZE
except ImportError:  # pragma: no cover
    from api.supplier_registration import MAX_UPLOAD_SIZE

MAX_UPLOAD_SIZE_MB = MAX_UPLOAD_SIZE // (1024 * 1024)


class UploadKind:
    """Upload contexts. Use these constants, never bare strings."""

    PR = "pr"
    SUPPLIER_REQUIREMENT = "supplier_requirement"
    COMPLETED_RFQ = "completed_rfq"


_DOC_AND_IMAGE = {".pdf", ".jpg", ".jpeg", ".png"}

_RULES = {
    UploadKind.PR: {
        "extensions": _DOC_AND_IMAGE,
        "type_error": "Unsupported file type. Please upload a PDF, JPG, JPEG, or PNG file.",
    },
    UploadKind.SUPPLIER_REQUIREMENT: {
        "extensions": _DOC_AND_IMAGE,
        "type_error": "Unsupported file type. Please upload a PDF, JPG, JPEG, or PNG file.",
    },
    UploadKind.COMPLETED_RFQ: {
        "extensions": {".pdf"},
        "type_error": "Completed RFQ submissions must be uploaded as a PDF.",
    },
}

_EMPTY_ERROR = "The uploaded file is empty."
_SIZE_ERROR = f"File is too large. Please upload a file no larger than {MAX_UPLOAD_SIZE_MB} MB."
_DAMAGED_ERROR = "The file appears to be damaged or is not a readable document."
_IMAGE_EXTS = {".jpg", ".jpeg", ".png"}


class FileValidationError(Exception):
    """Raised for any rejected upload. ``message`` is safe to show a user."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def allowed_extensions(kind: str) -> list[str]:
    return sorted(_RULES[kind]["extensions"])


def type_error_message(kind: str) -> str:
    return _RULES[kind]["type_error"]


def _extension(file_obj) -> str:
    return Path(getattr(file_obj, "name", "") or "").suffix.lower()


def _read_head(file_obj, size: int = 4096) -> bytes:
    try:
        position = file_obj.tell()
    except (AttributeError, OSError):
        position = 0
    try:
        file_obj.seek(0)
        head = file_obj.read(size) or b""
    except (AttributeError, OSError):
        head = b""
    finally:
        try:
            file_obj.seek(position)
        except (AttributeError, OSError):
            pass
    return head


def _looks_like_pdf(head: bytes) -> bool:
    # The %PDF- marker must appear within the first bytes (a few whitespace /
    # BOM bytes before it are tolerated, per the PDF spec's leniency).
    return b"%PDF-" in head[:1024]


def _image_format(file_obj) -> Optional[str]:
    """Return the real image format ('JPEG' / 'PNG' / ...) or None if unreadable."""
    try:
        from PIL import Image
    except ImportError:  # pragma: no cover - Pillow is a project dependency
        return None
    try:
        position = file_obj.tell()
    except (AttributeError, OSError):
        position = 0
    try:
        file_obj.seek(0)
        with Image.open(file_obj) as image:
            fmt = (image.format or "").upper()
            image.verify()
        return fmt or None
    except Exception:
        return None
    finally:
        try:
            file_obj.seek(position)
        except (AttributeError, OSError):
            pass


def validate_upload(file_obj, kind: str, *, field: Optional[str] = None) -> None:
    """Validate one uploaded file for ``kind``. Raises :class:`FileValidationError`.

    ``field`` is an optional human label used only to prefix messages when the
    caller is validating several files at once.
    """
    if kind not in _RULES:
        raise ValueError(f"Unknown upload kind: {kind!r}")
    rule = _RULES[kind]

    def fail(message: str) -> None:
        raise FileValidationError(f"{field}: {message}" if field else message)

    if file_obj is None:
        fail("A file is required.")

    size = getattr(file_obj, "size", None)
    if size is not None:
        if size <= 0:
            fail(_EMPTY_ERROR)
        if size > MAX_UPLOAD_SIZE:
            fail(_SIZE_ERROR)

    extension = _extension(file_obj)
    if extension not in rule["extensions"]:
        fail(rule["type_error"])

    head = _read_head(file_obj)
    if not head:
        fail(_EMPTY_ERROR)

    if extension == ".pdf":
        if not _looks_like_pdf(head):
            # Wrong content behind a .pdf name - report it as a type problem so
            # the message stays consistent with a plain wrong-extension upload.
            fail(rule["type_error"])
        return

    # Image: it must open AND report a JPEG/PNG format. This rejects renamed
    # binaries and corrupted images alike.
    fmt = _image_format(file_obj)
    if fmt not in {"JPEG", "PNG", "MPO"}:  # MPO = multi-picture JPEG from phones
        if fmt is None:
            fail(_DAMAGED_ERROR)
        fail(rule["type_error"])


def validate_uploads(files: Iterable, kind: str, *, labels: Optional[dict] = None) -> list[str]:
    """Validate many files, returning a list of error messages (empty = all OK)."""
    labels = labels or {}
    errors: list[str] = []
    for index, file_obj in enumerate(files):
        if file_obj is None:
            continue
        label = labels.get(index) or getattr(file_obj, "name", None)
        try:
            validate_upload(file_obj, kind, field=label)
        except FileValidationError as exc:
            errors.append(exc.message)
    return errors
