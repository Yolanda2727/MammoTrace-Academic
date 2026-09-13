# CBIS-DDSM data card — integration snapshot, 2026-09-13

Source: Sawyer-Lee R, Gimenez F, Hoogi A, Rubin D. TCIA (2016), DOI 10.7937/K9/TCIA.2016.7O02S9CY; dataset description Lee RS et al., Scientific Data (2017), DOI 10.1038/sdata.2017.177. The supplied digest identifies CC BY 3.0. These permissions do not extend to legacy model weights.

The four supplied case-description CSVs are unchanged. `nbia_digest_original.xlsx` is preserved; `digest_export.csv` contains its cell values exported using artifact_tool. `download_manifest.tcia` is a series request list. `metadata_drive_original.csv` is a partial download log, not verified pixel inventory. Original hashes are in `reports/source_provenance_4_1.json`.

Units: 3,568 annotation rows / 1,566 subjects / 2,050 provisional lesion keys / 3,103 full-image series. Repository labels: BENIGN 1,429; BENIGN_WITHOUT_CALLBACK 682; MALIGNANT 1,457. No normal reference group is created. The public labels do not establish the provenance of the historical model's training.

Global train/test overlap: 31 subjects; explicit holdout-priority removes 83 train rows, preserves all 704 official test rows. Train: 2,240 rows/974 subjects; validation: 541/243; test: 704/349. The development validation split is deterministic and not stratified. Target ambiguity exclusions are conservative research design decisions, not proof of annotation error.

There are 17 mixed-binary full-image groups and three discordant provisional lesion keys. The inventory excludes ambiguous targets rather than forcing a label. Metadata-eligible full series: 3,020 (train 1,927, validation 454, test 639). Eligible does not mean locally downloaded or clinically validated.

Manifest and digest: 6,775 unique series; digest declares 10,239 instances, 163,541,759,129 bytes. Partial log: 544 unique series, 837 instances; 544 decimal-comma structural repairs. Actually inspected: three public DICOM instances (full/crop/mask) of P_00038 LEFT CC. Source filenames do not by themselves establish instance role. The crop and mask share a series but have different SOPInstanceUIDs.

P_00038 is marked engineering-exposed. Future blinded evaluation must exclude or explicitly account for this exposure. No all-patient DICOM validation, diagnostic evaluation, patient recruitment, prospective outcome, demographic fairness study or training was performed. Public screening reference data cannot validate the educational guidance rules or transfer directly to a new clinical setting.

Preview transformations: percentile 1–99 with fallback range, aspect-preserving downscale; no new anatomy, generated lesion or AI-predicted segmentation. Original DICOM examples are distributed separately with provenance. Do not mistake previews for native training pixels.
