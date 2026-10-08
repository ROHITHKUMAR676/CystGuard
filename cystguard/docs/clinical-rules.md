# Clinical rules

## Kyoto 2024 deterministic findings

The independent Phase 3 engine evaluates caller-supplied structured facts for IPMN-related Kyoto 2024 high-risk stigmata (HRS) and worrisome features (WF). It reports findings and missing data; it does not diagnose cancer, estimate cancer probability, or recommend treatment. Clinician review and decision remain required. The engine has no database, API, Cyst-X, or external-service dependency.

### High-risk stigmata

- **HRS-01:** obstructive jaundice with a cystic lesion in the pancreatic head.
- **HRS-02:** enhancing mural nodule at least 5 mm, or a solid component. A solid component does not require a measured nodule size.
- **HRS-03:** main pancreatic duct (MPD) diameter at least 10 mm.
- **HRS-04:** suspicious or positive cytology, if performed.

### Worrisome features

- **WF-01:** acute pancreatitis.
- **WF-02:** increased serum CA19-9, based on explicit laboratory interpretation; the engine applies no numeric cutoff.
- **WF-03:** explicitly documented new-onset diabetes or acute exacerbation within the year preceding the assessment date. Diabetes alone does not trigger this criterion.
- **WF-04:** cyst maximum diameter at least 30 mm.
- **WF-05:** enhancing mural nodule under 5 mm. At exactly 5 mm WF-05 does not trigger; HRS-02 applies when enhancement is present.
- **WF-06:** thickened or enhancing cyst wall, preserving which finding(s) are present.
- **WF-07:** MPD at least 5 mm and under 10 mm. At 10 mm WF-07 does not trigger; HRS-03 applies.
- **WF-08:** abrupt duct caliber change together with distal pancreatic atrophy.
- **WF-09:** lymphadenopathy.
- **WF-10:** cyst growth rate at least 2.5 mm/year, calculated from explicitly supplied comparable measurements and dates as `delta_mm / (elapsed_days / 365.2425)`.

Thresholds are inclusive/exclusive as written above: WF-04 includes 30.0 mm; WF-05 excludes 5.0 mm; WF-07 includes 5.0 and excludes 10.0 mm; WF-10 includes 2.50 mm/year. Each rule is evaluated independently, so a missing field does not invalidate unrelated rules.

### Unknown data and provenance

Omitted findings default to `UNKNOWN`, never `ABSENT`. Rules requiring unavailable facts return `NOT_EVALUABLE` with field paths in `missing_data`. Explicit negative findings return `NOT_TRIGGERED` when sufficient to exclude that rule. Cytology marked `NOT_PERFORMED` remains distinct from a negative result. For WF-03 the engine uses only explicit event status/date and the supplied assessment date; it does not infer diabetes onset/exacerbation. Events after the assessment date are unresolved. Growth is not calculated for missing, invalid, or incomparable measurements.

Each structured input may carry source type, source identifier, page, field, timestamp, and evidence reference. Triggered findings retain their input provenance; assessment evidence is deduplicated while preserving encounter order. No provenance is fabricated.

### Reproducibility and versioning

Each result records guideline `KYOTO` version `2024`, rule engine name/version `CystGuard Kyoto Rule Engine` / `1.0.0`, caller-supplied timezone-aware evaluation timestamp, and assessment date. The deterministic engine remains persistence-agnostic; when invoked through a stored MRI assessment, the API persists its inputs and output on that assessment record.

### Longitudinal data boundary

Longitudinal comparisons are factual only. Growth is calculated only from verified, comparable measurements with explicit dates and safely normalizable units. The service does not convert growth into malignancy or independently declare a Kyoto feature; Kyoto criteria remain evaluated only by the Kyoto engine. Cyst-X raw scores remain non-probabilistic historical outputs.

### Source

Ohtsuka T, Fernandez-del Castillo C, Furukawa T, et al. International evidence-based Kyoto guidelines for the management of intraductal papillary mucinous neoplasm of the pancreas. *Pancreatology*. 2024;24(2):255–270. doi:10.1016/j.pan.2023.12.009. This implementation follows the Phase 3 CystGuard rule specification; no local `CystGuard_Kyoto_2024_Implementation_Reference.md` was present in the repository at implementation time.
