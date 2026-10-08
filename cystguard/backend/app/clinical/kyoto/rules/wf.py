from datetime import date

from app.clinical.kyoto.evaluation.evaluator import rule_result
from app.clinical.kyoto.schemas import ClinicalContext, RuleCategory, RuleEvaluation, RuleStatus

WF = RuleCategory.WORRISOME_FEATURE


def _fact(code: str, criterion: str, fact, field: str) -> RuleEvaluation:
    status = {"PRESENT": RuleStatus.TRIGGERED, "ABSENT": RuleStatus.NOT_TRIGGERED, "UNKNOWN": RuleStatus.NOT_EVALUABLE}[fact.status.value]
    return rule_result(code=code, category=WF, status=status, criterion=criterion, observed={field: fact.status.value}, reasons=(field.upper(),) if status is RuleStatus.TRIGGERED else (), evidence=fact.evidence, missing=(field,) if status is RuleStatus.NOT_EVALUABLE else ())


def evaluate_wf_01(c): return _fact("WF-01", "Acute pancreatitis", c.acute_pancreatitis, "acute_pancreatitis")


def evaluate_wf_02(c):
    x = c.serum_ca19_9
    status = RuleStatus.TRIGGERED if x.status.value == "INCREASED" else RuleStatus.NOT_TRIGGERED if x.status.value == "NORMAL" else RuleStatus.NOT_EVALUABLE
    missing = ("serum_ca19_9.status",) if status is RuleStatus.NOT_EVALUABLE else ()
    return rule_result(code="WF-02", category=WF, status=status, criterion="Increased serum CA19-9", observed={"value": x.value, "unit": x.unit, "reference_range": x.reference_range, "status": x.status.value, "measured_at": x.measured_at.isoformat() if x.measured_at else None}, reasons=("SERUM_CA19_9_INCREASED",) if status is RuleStatus.TRIGGERED else (), evidence=x.evidence, missing=missing, notes=("No numeric threshold is applied by this rule",))


def _one_year_before(d: date) -> date:
    try: return d.replace(year=d.year - 1)
    except ValueError: return d.replace(year=d.year - 1, day=28)


def evaluate_wf_03(c):
    date_ref = c.assessment_date
    events = (("new_onset_diabetes", c.new_onset_diabetes), ("acute_diabetes_exacerbation", c.acute_diabetes_exacerbation))
    missing, reasons, evidence, observations, notes = [], [], [], {}, []
    if date_ref is None: missing.append("assessment_date")
    for field, event in events:
        evidence.extend(event.evidence)
        observations[field] = {"status": event.status.value, "date": event.occurred_at.isoformat() if event.occurred_at else None}
        if event.status.value == "UNKNOWN": missing.append(f"{field}.status")
        elif event.status.value == "PRESENT":
            if event.occurred_at is None: missing.append(f"{field}.date")
            elif date_ref is None: pass
            elif event.occurred_at > date_ref: missing.append(f"{field}.date"); notes.append(f"{field} date is after assessment date")
            elif event.occurred_at >= _one_year_before(date_ref): reasons.append(field.upper())
    status = RuleStatus.TRIGGERED if reasons else RuleStatus.NOT_EVALUABLE if missing else RuleStatus.NOT_TRIGGERED
    return rule_result(code="WF-03", category=WF, status=status, criterion="New-onset or acute exacerbation of diabetes within past year", observed=observations, threshold={"period": "one calendar year preceding assessment_date"}, reasons=reasons, evidence=evidence, missing=missing, notes=notes)


def _measurement_rule(code, criterion, m, lower, upper=None, lower_inclusive=True):
    v = m.value_mm
    if v is None: status = RuleStatus.NOT_EVALUABLE
    else:
        low_ok = v >= lower if lower_inclusive else v > lower
        status = RuleStatus.TRIGGERED if low_ok and (upper is None or v < upper) else RuleStatus.NOT_TRIGGERED
    threshold = {"lower_inclusive_mm" if lower_inclusive else "lower_exclusive_mm": lower}
    if upper is not None: threshold["upper_exclusive_mm"] = upper
    field = {"WF-04": "cyst_maximum_diameter_mm", "WF-07": "mpd_diameter_mm"}.get(code, "measurement_mm")
    return rule_result(code=code, category=WF, status=status, criterion=criterion, observed={field: v}, threshold=threshold, reasons=(code.replace("-", "_") + "_THRESHOLD_MET",) if status is RuleStatus.TRIGGERED else (), evidence=m.evidence, missing=(field,) if v is None and m.status.value != "ABSENT" else ())


def evaluate_wf_04(c): return _measurement_rule("WF-04", "Cyst >= 30 mm", c.cyst_maximum_diameter, 30)


def evaluate_wf_05(c):
    n, m = c.mural_nodule_enhancing, c.mural_nodule_size
    missing = []
    if n.status.value == "UNKNOWN": missing.append("mural_nodule.enhancing")
    if n.status.value != "ABSENT" and m.value_mm is None: missing.append("mural_nodule.size_mm")
    trigger = n.status.value == "PRESENT" and m.value_mm is not None and m.value_mm < 5
    status = RuleStatus.TRIGGERED if trigger else RuleStatus.NOT_EVALUABLE if missing else RuleStatus.NOT_TRIGGERED
    return rule_result(code="WF-05", category=WF, status=status, criterion="Enhancing mural nodule < 5 mm", observed={"mural_nodule_enhancing": n.status.value, "mural_nodule_size_mm": m.value_mm}, threshold={"upper_exclusive_mm": 5.0}, reasons=("ENHANCING_MURAL_NODULE_LT_5MM",) if trigger else (), evidence=(*n.evidence, *m.evidence), missing=missing)


def evaluate_wf_06(c):
    t, e = c.cyst_wall_thickened, c.cyst_wall_enhancing
    reasons = (["THICKENED_WALL"] if t.status.value == "PRESENT" else []) + (["ENHANCING_WALL"] if e.status.value == "PRESENT" else [])
    missing = (["cyst_wall_thickened"] if t.status.value == "UNKNOWN" else []) + (["cyst_wall_enhancing"] if e.status.value == "UNKNOWN" else [])
    status = RuleStatus.TRIGGERED if reasons else RuleStatus.NOT_EVALUABLE if missing else RuleStatus.NOT_TRIGGERED
    if len(reasons) == 2: reasons.append("BOTH")
    return rule_result(code="WF-06", category=WF, status=status, criterion="Thickened or enhancing cyst wall", observed={"cyst_wall_thickened": t.status.value, "cyst_wall_enhancing": e.status.value}, reasons=reasons, evidence=(*t.evidence, *e.evidence), missing=missing)


def evaluate_wf_07(c): return _measurement_rule("WF-07", "MPD >= 5 mm and < 10 mm", c.mpd_diameter, 5, 10)


def evaluate_wf_08(c):
    a, b = c.abrupt_duct_caliber_change, c.distal_pancreatic_atrophy
    yes = a.status.value == "PRESENT" and b.status.value == "PRESENT"
    missing = (["abrupt_duct_caliber_change"] if a.status.value == "UNKNOWN" else []) + (["distal_pancreatic_atrophy"] if b.status.value == "UNKNOWN" else [])
    status = RuleStatus.TRIGGERED if yes else RuleStatus.NOT_TRIGGERED if "ABSENT" in (a.status.value, b.status.value) else RuleStatus.NOT_EVALUABLE
    return rule_result(code="WF-08", category=WF, status=status, criterion="Abrupt duct caliber change with distal pancreatic atrophy", observed={"abrupt_duct_caliber_change": a.status.value, "distal_pancreatic_atrophy": b.status.value}, reasons=("ABRUPT_CHANGE_WITH_DISTAL_ATROPHY",) if yes else (), evidence=(*a.evidence, *b.evidence), missing=missing if status is RuleStatus.NOT_EVALUABLE else ())


def evaluate_wf_09(c): return _fact("WF-09", "Lymphadenopathy", c.lymphadenopathy, "lymphadenopathy")


def evaluate_wf_10(c):
    pair = c.longitudinal_measurements
    p, n = pair.previous, pair.current
    missing, notes = [], []
    evidence = (*(p.evidence if p else ()), *(n.evidence if n else ()))
    observed = {"previous_mm": p.value_mm if p else None, "previous_date": p.measured_at.isoformat() if p and p.measured_at else None, "current_mm": n.value_mm if n else None, "current_date": n.measured_at.isoformat() if n and n.measured_at else None, "comparability": pair.comparability.value}
    if p is None: missing.append("longitudinal_measurements.previous")
    if n is None: missing.append("longitudinal_measurements.current")
    if p and p.value_mm is None: missing.append("longitudinal_measurements.previous.value_mm")
    if n and n.value_mm is None: missing.append("longitudinal_measurements.current.value_mm")
    if p and p.measured_at is None: missing.append("longitudinal_measurements.previous.measured_at")
    if n and n.measured_at is None: missing.append("longitudinal_measurements.current.measured_at")
    if pair.comparability.value != "COMPARABLE": missing.append("longitudinal_measurements.comparability"); notes.append("Measurements are not established as comparable")
    rate = None
    if not missing:
        elapsed_days = (n.measured_at - p.measured_at).days
        observed["elapsed_days"] = elapsed_days
        if elapsed_days <= 0 or p.value_mm < 0 or n.value_mm < 0:
            notes.append("Invalid longitudinal measurement values or date order")
            missing.append("longitudinal_measurements.validity")
        else:
            rate = (n.value_mm - p.value_mm) / (elapsed_days / 365.2425)
            observed["growth_rate_mm_per_year"] = rate
            observed["calculation_method"] = "delta_mm / (elapsed_days / 365.2425)"
    status = RuleStatus.NOT_EVALUABLE if missing else RuleStatus.TRIGGERED if rate >= 2.5 else RuleStatus.NOT_TRIGGERED
    return rule_result(code="WF-10", category=WF, status=status, criterion="Cyst growth rate >= 2.5 mm/year", observed=observed, threshold={"lower_inclusive_mm_per_year": 2.5}, reasons=("CYST_GROWTH_GE_2_5_MM_PER_YEAR",) if status is RuleStatus.TRIGGERED else (), evidence=evidence, missing=missing, notes=notes)


WF_EVALUATORS = (evaluate_wf_01, evaluate_wf_02, evaluate_wf_03, evaluate_wf_04, evaluate_wf_05, evaluate_wf_06, evaluate_wf_07, evaluate_wf_08, evaluate_wf_09, evaluate_wf_10)
