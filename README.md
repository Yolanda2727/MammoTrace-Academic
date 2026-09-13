# MammoTrace Academic 4.1.0 — public source release

MammoTrace Academic is academic research software for mammography-data exploration, report comprehension, reproducible CBIS-DDSM preparation, and explicitly separated experimental AI components. **It is not diagnostic software, not a validated triage system, and does not establish a safe waiting time for care.**

**Author:** Anderson Díaz Pérez  
**ORCID:** https://orcid.org/0000-0003-2448-0953  
**Version:** 4.1.0  
**Repository:** https://github.com/Yolanda2727/MammoTrace-Academic

## Public-release scope

This repository is the **PUBLICA_SIN_PESOS** source-code edition. It intentionally excludes the historical neural-network weight fragments and does not redistribute bulk CBIS-DDSM DICOM pixels. The historical model was not retrained or clinically validated by the 4.1 CBIS integration.

The 4.1 engineering audit reported 340 core tests passed and 70.79% statement coverage for `mammoapp` and `mammotrace` in the audited development package. Those results are engineering results, not diagnostic-performance estimates. Native Streamlit/browser/cloud acceptance, clinical evaluation, complete CBIS training, and external validation were not part of that reported run.

## What is preserved here

- Streamlit application source (`streamlit_app.py`, `mammoapp/`).
- Research/model infrastructure (`mammotrace/`) without historical weights.
- CBIS-DDSM audit, indexing, and candidate-training scripts.
- Unit and Streamlit acceptance tests.
- Reproducibility-oriented documentation and selected audit summaries.
- Exact hashes of the CBIS-DDSM metadata inputs used in the 4.1 audit.
- Synthetic-example generator; generated binary examples are intentionally not versioned.

## What is intentionally not preserved in the Git tree

- Historical model weights or model fragments.
- Patient uploads, identifiable reports, private DICOMs, credentials, virtual environments, or local caches.
- Bulk third-party CBIS-DDSM metadata snapshots and DICOM pixels. Obtain authorized copies from TCIA and place the required metadata under `data/cbis/` as described in `data/cbis/README.md`.
- Generated example images/PDFs. Recreate them locally with `python scripts/build_examples.py`.

## Install

Prepared for Python 3.13.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/check_environment.py
python scripts/build_examples.py
python -m streamlit run streamlit_app.py
```

Windows helper files `INSTALAR_WINDOWS.bat` and `INICIAR_WINDOWS.bat` are included, but the audited 4.1 run did not constitute a completed Windows acceptance test.

## CBIS-DDSM research workflow

The audited 4.1 integration used four case-description CSVs plus a TCIA manifest/digest snapshot. The reported audit distinguished lesion-view annotations, subjects, full-image series, and actual pixel availability. When the mass and calcification families were combined, 31 subjects crossed the official train/test boundary. The explicit `holdout_priority` policy preserved the official test rows and excluded training rows belonging to subjects in test.

The public source tree does not redistribute those bulk inputs. After obtaining authorized copies from the original dataset source and placing them in `data/cbis/`, run:

```bash
python scripts/audit_cbis.py
python scripts/index_cbis.py --root RUTA_DICOM --out reports/local_index.csv
python training/train_cbis_binary.py --root RUTA_DICOM --index reports/local_index.csv --out runs/cbis_binary
```

The third command is a preflight by default and does not require the optional ML stack. Before an explicit training run, install `requirements-ml.txt`. Training requires the explicit `--execute` flag and suitable authorized image files. No clinical performance claim follows from successfully running it.

Dataset citation:

> Sawyer-Lee R, Gimenez F, Hoogi A, Rubin D. *Curated Breast Imaging Subset of Digital Database for Screening Mammography (CBIS-DDSM).* The Cancer Imaging Archive, 2016. DOI: https://doi.org/10.7937/K9/TCIA.2016.7O02S9CY

The audited metadata snapshot recorded CC BY 3.0 for the dataset. That dataset permission does not grant rights over historical model weights and does not itself license this software.

## Tests

Code-only tests can be run with:

```bash
python -m pip install -r requirements-dev.txt
python scripts/build_examples.py
python -m pytest tests -q
```

The CBIS-specific module is skipped when the required third-party metadata files are not present. Streamlit acceptance tests are also skipped when their required CBIS bundle is unavailable. To reproduce the complete data-dependent audit, first supply the authorized metadata files listed in `data/cbis/README.md`.

## Security and privacy

Do not upload personal health information, credentials, API keys, or private DICOMs to a public deployment. External AI is disabled by default. `secrets.toml` is ignored by Git and only an example template is provided. See `docs/SEGURIDAD_Y_LIMITES.md`.

## License status

No open-source software license is granted by the publication of this repository at this stage. Unless a separate `LICENSE` file is later added by the rights holder, the source remains subject to applicable copyright law. Third-party dependencies and CBIS-DDSM retain their own licenses/terms.

## Citation

Use `CITATION.cff` and cite the exact archived version/SWHID once the Software Heritage snapshot has been created. Do not cite the repository as evidence of clinical validation.
