# Public release audit — MammoTrace Academic 4.1.0

Audit date: 2026-09-13

## Publication controls applied

- Removed all historical neural-network weight fragments and model binaries from the public source tree.
- Did not redistribute private/user DICOMs, patient reports, credentials, local environments, or caches.
- Did not redistribute the bulk CBIS-DDSM metadata snapshot or DICOM pixels; preserved input filenames and SHA-256 values for traceability. Large derived audit tables and the full coverage JSON are also omitted from the preservation tree; the concise audit summaries and source code remain.
- Removed direct Google Drive folder/file URLs from the public provenance record; retained the canonical TCIA DOI.
- Removed environment-specific local installation-path content from the public release.
- Harmonized user-visible application/version identifiers to 4.1.0. The internal `mammotrace.guide.4.0` export schema and `reglas_educativas_4.0.0` rule-engine identifiers are retained intentionally as component/schema versions because their semantics were not re-versioned by the CBIS integration.
- Marked the edition as `PUBLICA_SIN_PESOS`.
- Adjusted the CBIS workspace so users can provide the four authorized CSV files without requiring a bundled third-party copy.
- Adjusted data-dependent tests to skip explicitly when the third-party CBIS metadata bundle is intentionally absent.
- Split the public dependency profile from the optional experimental ML stack (`requirements-ml.txt`), so the no-weights interface does not install model runtimes unnecessarily.
- Added deterministic generation of synthetic example assets before CI tests.
- Raised the Linux PDF-worker address-space ceiling from 384 MiB to 768 MiB after the public-release verification environment showed a Python 3.13 baseline virtual-memory size above 384 MiB; the separate-process design, 10 s CPU limit, 15 s parent timeout, 10 MiB input cap, 12-page cap, and 30,000-character cap remain in place.

## Secret scan

A local static scan of the source package found no plaintext OpenAI keys, Google API keys, GitHub tokens, AWS access keys, PEM private keys, or generic credential assignments matching the audit patterns. The only API-key text retained is the commented placeholder in `.streamlit/secrets.toml.example`.

This is a release-preparation audit, not a penetration test, legal opinion, clinical validation, or independent security certification.

## Scientific scope

The archived engineering results describe software tests, data reconciliation, subject-level leakage controls, and a restricted public-DICOM integration check. They do not establish diagnostic accuracy, calibration, clinical safety, effectiveness, or validated triage.
