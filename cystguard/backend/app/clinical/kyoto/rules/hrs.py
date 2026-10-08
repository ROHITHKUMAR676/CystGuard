from app.clinical.kyoto.evaluation.evaluator import rule_result
from app.clinical.kyoto.schemas import ClinicalContext, RuleCategory, RuleEvaluation, RuleStatus


HRS = RuleCategory.HIGH_RISK_STIGMATA


def evaluate_hrs_01(c: ClinicalContext) -> RuleEvaluation:
    loc, jaundice = c.lesion_location, c.obstructive_jaundice
    evidence = (*loc.evidence, *jaundice.evidence)
    missing = []
    if loc.status.value == "UNKNOWN": missing.append("lesion_location")
    if jaundice.status.value == "UNKNOWN": missing.append("obstructive_jaundice")
    if loc.status.value == "PRESENT" and loc.value.value != "HEAD":
        status, missing = RuleStatus.NOT_TRIGGERED, []
    elif loc.status.value == "ABSENT":
        status, missing = RuleStatus.NOT_TRIGGERED, []
    elif jaundice.status.value == "ABSENT": status, missing = RuleStatus.NOT_TRIGGERED, []
    elif loc.status.value == "PRESENT" and loc.value.value == "HEAD" and jaundice.status.value == "PRESENT": status, missing = RuleStatus.TRIGGERED, []
    else: status = RuleStatus.NOT_EVALUABLE
    return rule_result(code="HRS-01", category=HRS, status=status, criterion="Obstructive jaundice with cystic lesion in pancreatic head", observed={"lesion_location": loc.value.value if loc.value else None, "obstructive_jaundice": jaundice.status.value}, reasons=("HEAD_LESION_WITH_OBSTRUCTIVE_JAUNDICE",) if status is RuleStatus.TRIGGERED else (), evidence=evidence, missing=missing)


def evaluate_hrs_02(c: ClinicalContext) -> RuleEvaluation:
    n, size, solid = c.mural_nodule_enhancing, c.mural_nodule_size, c.solid_component
    reasons, missing, evidence = [], [], [*n.evidence, *size.evidence, *solid.evidence]
    nodule_trigger = n.status.value == "PRESENT" and size.value_mm is not None and size.value_mm >= 5
    if solid.status.value == "PRESENT": reasons.append("SOLID_COMPONENT")
    if nodule_trigger: reasons.append("ENHANCING_MURAL_NODULE_GE_5MM")
    if n.status.value == "PRESENT" and size.value_mm is None: missing.append("mural_nodule.size_mm")
    if n.status.value == "UNKNOWN": missing.append("mural_nodule.enhancing")
    if size.value_mm is None and n.status.value != "ABSENT": missing.append("mural_nodule.size_mm")
    if solid.status.value == "UNKNOWN": missing.append("solid_component")
    status = RuleStatus.TRIGGERED if reasons else (RuleStatus.NOT_EVALUABLE if missing else RuleStatus.NOT_TRIGGERED)
    return rule_result(code="HRS-02", category=HRS, status=status, criterion="Enhancing mural nodule >= 5 mm or solid component", observed={"mural_nodule_enhancing": n.status.value, "mural_nodule_size_mm": size.value_mm, "solid_component": solid.status.value}, threshold={"mural_nodule_size_lower_inclusive_mm": 5.0}, reasons=reasons, evidence=evidence, missing=missing)


def evaluate_hrs_03(c: ClinicalContext) -> RuleEvaluation:
    m = c.mpd_diameter
    status = RuleStatus.NOT_EVALUABLE if m.value_mm is None else RuleStatus.TRIGGERED if m.value_mm >= 10 else RuleStatus.NOT_TRIGGERED
    return rule_result(code="HRS-03", category=HRS, status=status, criterion="MPD >= 10 mm", observed={"mpd_diameter_mm": m.value_mm}, threshold={"lower_inclusive_mm": 10.0}, reasons=("MPD_GE_10MM",) if status is RuleStatus.TRIGGERED else (), evidence=m.evidence, missing=("mpd_diameter_mm",) if m.value_mm is None and m.status.value != "ABSENT" else ())


def evaluate_hrs_04(c: ClinicalContext) -> RuleEvaluation:
    x = c.cytology
    status = RuleStatus.TRIGGERED if x.status.value in ("SUSPICIOUS", "POSITIVE") else RuleStatus.NOT_TRIGGERED if x.status.value == "NEGATIVE" else RuleStatus.NOT_EVALUABLE
    return rule_result(code="HRS-04", category=HRS, status=status, criterion="Suspicious or positive cytology, if performed", observed={"cytology_status": x.status.value}, reasons=(f"CYTOLOGY_{x.status.value}",) if status is RuleStatus.TRIGGERED else (), evidence=x.evidence, missing=("cytology.status",) if status is RuleStatus.NOT_EVALUABLE else (), notes=("Cytology was not performed",) if x.status.value == "NOT_PERFORMED" else ())


HRS_EVALUATORS = (evaluate_hrs_01, evaluate_hrs_02, evaluate_hrs_03, evaluate_hrs_04)
