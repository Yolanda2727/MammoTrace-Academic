# CBIS-DDSM metadata inputs

The public source-code release does **not** redistribute the bulk CBIS-DDSM metadata snapshot or DICOM pixels.
Obtain authorized source data from the original CBIS-DDSM record in The Cancer Imaging Archive (TCIA):

- Dataset: *Curated Breast Imaging Subset of Digital Database for Screening Mammography (CBIS-DDSM)*
- DOI: https://doi.org/10.7937/K9/TCIA.2016.7O02S9CY
- License recorded in the audited snapshot: CC BY 3.0

For the complete 4.1 audit, the following input filenames were used locally:

- `calc_case_description_test_set.csv`
- `calc_case_description_train_set.csv`
- `mass_case_description_test_set.csv`
- `mass_case_description_train_set.csv`
- `download_manifest.tcia`
- `metadata_drive_original.csv`
- `nbia_digest_original.xlsx`
- `digest_export.csv`

Exact SHA-256 values of the audited inputs are preserved in `reports/source_provenance_4_1.json`.
Place authorized copies in `data/cbis/` before running the full CBIS audit or the data-dependent test module.

The source-code repository intentionally separates software preservation from redistribution of third-party datasets.
