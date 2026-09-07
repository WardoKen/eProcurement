"""Controlled list of procurement modes offered during RFQ preparation.

This is the single source of truth for the "Mode of Procurement" field on an
RFQ. To add a mode, append an entry; to retire one, set ``is_active`` to
``False`` (existing RFQs that already reference it keep rendering correctly).
Nothing else needs to change - the RFQ preparation dropdown, the backend
validation and the PDF generator all read from here.

Each entry:
    code        internal reference (e.g. the IRR section shown on the form);
                may be blank when no official code applies. Not invented -
                only fill this in from an authoritative source.
    label       human-readable name of the procurement procedure.
    is_active   whether admins may pick it for new RFQs.

The value stored on ``RFQ.mode_of_procurement`` and printed on the RFQ PDF is
the *display string* produced by :func:`mode_display` - e.g.
``"26.h) Small Value Procurement"`` or, when there is no code, just
``"Shopping"``.
"""

PROCUREMENT_MODES = [
    # From the supplied sample RFQ document.
    {"code": "", "label": "Small Value Procurement", "is_active": True},
    {"code": "", "label": "Shopping", "is_active": True},
    {"code": "", "label": "Negotiated Procurement", "is_active": True},
    {"code": "", "label": "Competitive Bidding", "is_active": True},
]

# Display strings for modes that older RFQs may already have stored, mapped to
# the current canonical display string. Keeps drafts created before this list
# existed valid and editable.
_LEGACY_ALIASES = {
    "26.h) small value procurement": "Small Value Procurement",
}


def mode_display(entry):
    """Return the combined display string for a PROCUREMENT_MODES entry."""
    label = (entry.get("label") or "").strip()
    code = (entry.get("code") or "").strip()
    return f"{code}) {label}" if code else label


def active_procurement_modes():
    return [m for m in PROCUREMENT_MODES if m.get("is_active", True)]


def procurement_mode_choices():
    """Ordered list of selectable display strings, for the API / dropdown."""
    return [mode_display(m) for m in active_procurement_modes()]


def allowed_procurement_modes():
    """Set of display strings accepted by validation (active list only)."""
    return {mode_display(m) for m in active_procurement_modes()}


def normalize_procurement_mode(value):
    """Trim, and map a known legacy label to its current canonical form."""
    candidate = (value or "").strip()
    if not candidate:
        return ""
    if candidate in allowed_procurement_modes():
        return candidate
    return _LEGACY_ALIASES.get(candidate.lower(), candidate)


def is_valid_procurement_mode(value):
    """True when ``value`` (after normalization) is in the active list."""
    return normalize_procurement_mode(value) in allowed_procurement_modes()
