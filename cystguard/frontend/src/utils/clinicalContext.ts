type FormDataValues = Record<string, FormDataEntryValue>;

export function buildClinicalContextPayload(form: HTMLFormElement): Record<string, unknown> {
  const values = Object.fromEntries(new FormData(form)) as FormDataValues;
  const get = (key: string) => String(values[key] ?? '');
  const evidence = (source: string, verification: string, field: string) => [{
    source_type: 'CLINICAL_HISTORY', source_id: 'clinician-entered', field,
    evidence_reference: source || null, verification_status: verification || 'UNVERIFIED',
  }];
  const fact = (key: string) => ({ status: get(key) || 'UNKNOWN', evidence: evidence('Clinician-entered assessment', 'UNVERIFIED', key) });
  const measurement = (key: string, valueKey = `${key}_value`, dateKey = '') => {
    const rawValue = get(valueKey);
    let status = get(`${key}_status`) || (rawValue ? 'PRESENT' : 'UNKNOWN');
    if (rawValue && status === 'UNKNOWN') status = 'PRESENT';
    const source = get(`${key}_source`);
    const verification = get(`${key}_verification`) || 'UNVERIFIED';
    return {
      status,
      value_mm: rawValue ? Number(rawValue) : null,
      unit: 'mm',
      measured_at: dateKey ? get(dateKey) || null : get('assessment_date') || null,
      measurement_method: 'Clinician-entered',
      source: source || null,
      verification_status: verification,
      evidence: evidence(source, verification, key),
    };
  };
  const location = get('lesion_location') || 'UNKNOWN';
  const cytology = get('cytology') || 'UNKNOWN';
  const caStatus = get('ca19_status') || 'UNKNOWN';
  const previous = measurement('growth_previous', 'growth_previous_value', 'growth_previous_date');
  const current = measurement('growth_current', 'growth_current_value', 'growth_current_date');
  return {
    cyst_type: get('cyst_type') || 'UNKNOWN',
    clinical_context: {
      evaluated_at: new Date().toISOString(),
      assessment_date: get('assessment_date') || null,
      lesion_location: { status: location === 'UNKNOWN' ? 'UNKNOWN' : 'PRESENT', value: location === 'UNKNOWN' ? null : location, evidence: evidence('Clinician-entered assessment', 'UNVERIFIED', 'lesion_location') },
      obstructive_jaundice: fact('obstructive_jaundice'),
      mural_nodule_presence: fact('mural_nodule_presence'),
      mural_nodule_enhancing: fact('mural_nodule_enhancing'),
      mural_nodule_size: measurement('mural_nodule_size'),
      solid_component: fact('solid_component'),
      mpd_diameter: measurement('mpd_diameter'),
      cytology: { status: cytology, evidence: evidence('Clinician-entered assessment', 'UNVERIFIED', 'cytology') },
      acute_pancreatitis: fact('acute_pancreatitis'),
      serum_ca19_9: {
        status: caStatus, value: get('ca19_value') ? Number(get('ca19_value')) : null,
        unit: get('ca19_unit') || null, reference_range: null, reference_upper_limit: null,
        measured_at: null, evidence: evidence(get('ca19_source'), get('ca19_verification'), 'serum_ca19_9'),
      },
      diabetes_status: { status: 'UNKNOWN', evidence: [] },
      new_onset_diabetes: { status: get('new_onset_diabetes') || 'UNKNOWN', occurred_at: get('new_diabetes_date') || null, evidence: evidence('Clinician-entered assessment', 'UNVERIFIED', 'new_onset_diabetes') },
      acute_diabetes_exacerbation: { status: get('acute_diabetes_exacerbation') || 'UNKNOWN', occurred_at: get('worsening_diabetes_date') || null, evidence: evidence('Clinician-entered assessment', 'UNVERIFIED', 'acute_diabetes_exacerbation') },
      cyst_maximum_diameter: measurement('cyst_maximum_diameter'),
      cyst_wall_thickened: fact('cyst_wall_thickened'),
      cyst_wall_enhancing: fact('cyst_wall_enhancing'),
      abrupt_duct_caliber_change: fact('abrupt_duct_caliber_change'),
      distal_pancreatic_atrophy: fact('distal_pancreatic_atrophy'),
      lymphadenopathy: fact('lymphadenopathy'),
      longitudinal_measurements: {
        previous: previous.value_mm == null && previous.status === 'UNKNOWN' ? null : previous,
        current: current.value_mm == null && current.status === 'UNKNOWN' ? null : current,
        comparability: get('growth_comparability') || 'UNKNOWN',
      },
    },
  };
}
