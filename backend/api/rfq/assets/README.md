# RFQ assets

## signature.png

E-signature block for the BAC Secretariat signatory, embedded in every
generated RFQ PDF in place of the typed name/role.

The current file was copied from `src/assets/eSignature.png` and already
contains the signature strokes **plus** the printed name and role
("LURIZA L. PRESBITERO" / "Member, BAC Secretariat"). Replace this file to
change the signature; the template renders the image as-is.

If the file is missing, the template falls back to a blank signature line
with `SIGNATORY_NAME` / `SIGNATORY_ROLE` (see
`api/rfq/services/rfq_generator.py`) typed below it.

Recommended: PNG, transparent background, ~2:1 width-to-height
(scaled to 190pt x 95pt in the PDF).
