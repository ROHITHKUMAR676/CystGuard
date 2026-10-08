import { escapeHtml } from '../utils/html.js';

const statusField = (name: string, label: string, current?: string) => `<label>${label}<select name="${name}" required><option value="UNKNOWN" ${!current || current === 'UNKNOWN' ? 'selected' : ''}>Unknown</option><option value="PRESENT" ${current === 'PRESENT' ? 'selected' : ''}>Present</option><option value="ABSENT" ${current === 'ABSENT' ? 'selected' : ''}>Absent</option></select></label>`;

const measurementField = (name: string, label: string, value?: unknown, source?: unknown, verification?: unknown, status?: string) => `
<fieldset class="measurement-field"><legend>${label}</legend>
  <label>Finding status<select name="${name}_status"><option value="UNKNOWN" ${!status || status === 'UNKNOWN' ? 'selected' : ''}>Unknown</option><option value="PRESENT" ${status === 'PRESENT' || (!status && value != null) ? 'selected' : ''}>Present</option><option value="ABSENT" ${status === 'ABSENT' ? 'selected' : ''}>Absent</option></select></label>
  <label>Value (mm)<input name="${name}_value" type="number" min="0" step="0.1" value="${value == null ? '' : escapeHtml(value)}"></label>
  <label>Source<input name="${name}_source" maxlength="256" value="${escapeHtml(source || '')}" placeholder="Report, EUS, or clinician record"></label>
  <label>Verification<select name="${name}_verification"><option value="UNVERIFIED" ${verification === 'VERIFIED' ? '' : 'selected'}>Unverified</option><option value="VERIFIED" ${verification === 'VERIFIED' ? 'selected' : ''}>Verified</option></select></label>
</fieldset>`;

export function ClinicalContextForm(props: { assessmentId: string; context?: Record<string, any> | null }): string {
  const context = props.context || {};
  const status = (key: string) => context[key]?.status;
  const measure = (key: string) => context[key] || {};
  const prior = context.longitudinal_measurements?.previous || {};
  const current = context.longitudinal_measurements?.current || {};
  return `<section class="card"><div class="section-title"><div><p class="eyebrow">STRUCTURED CLINICAL INPUT</p><h2>Clinical context for Kyoto 2024</h2></div></div>
    <p class="muted">Unknown is retained unless a clinician records a finding. Submitting runs the backend Kyoto and trust services.</p>
    <form id="clinical-context-form" data-assessment-id="${escapeHtml(props.assessmentId)}"><div class="grid two">
      <label>Cyst type<select name="cyst_type"><option value="UNKNOWN">Unknown</option><option value="IPMN" ${context.cyst_type === 'IPMN' ? 'selected' : ''}>IPMN</option><option value="NON_IPMN" ${context.cyst_type === 'NON_IPMN' ? 'selected' : ''}>Non-IPMN</option></select></label>
      <label>Assessment date<input type="date" name="assessment_date" value="${escapeHtml(context.assessment_date || '')}"></label>
      ${measurementField('cyst_maximum_diameter', 'Maximum cyst diameter', measure('cyst_maximum_diameter').value_mm, measure('cyst_maximum_diameter').source, measure('cyst_maximum_diameter').verification_status, measure('cyst_maximum_diameter').status)}
      ${measurementField('mpd_diameter', 'Main pancreatic duct diameter', measure('mpd_diameter').value_mm, measure('mpd_diameter').source, measure('mpd_diameter').verification_status, measure('mpd_diameter').status)}
      ${measurementField('mural_nodule_size', 'Mural nodule size', measure('mural_nodule_size').value_mm, measure('mural_nodule_size').source, measure('mural_nodule_size').verification_status, measure('mural_nodule_size').status)}
      ${statusField('mural_nodule_presence', 'Mural nodule present', status('mural_nodule_presence'))}
      ${statusField('mural_nodule_enhancing', 'Enhancing mural nodule', status('mural_nodule_enhancing'))}
      ${statusField('solid_component', 'Solid component', status('solid_component'))}
      ${statusField('obstructive_jaundice', 'Obstructive jaundice', status('obstructive_jaundice'))}
      ${statusField('acute_pancreatitis', 'Acute pancreatitis', status('acute_pancreatitis'))}
      ${statusField('cyst_wall_thickened', 'Thickened cyst wall', status('cyst_wall_thickened'))}
      ${statusField('cyst_wall_enhancing', 'Enhancing cyst wall', status('cyst_wall_enhancing'))}
      ${statusField('abrupt_duct_caliber_change', 'Abrupt duct caliber change', status('abrupt_duct_caliber_change'))}
      ${statusField('distal_pancreatic_atrophy', 'Distal pancreatic atrophy', status('distal_pancreatic_atrophy'))}
      ${statusField('lymphadenopathy', 'Lymphadenopathy', status('lymphadenopathy'))}
      <label>Lesion location<select name="lesion_location"><option value="UNKNOWN">Unknown</option>${['HEAD','BODY','TAIL','UNCINATE','OTHER'].map(value => `<option value="${value}" ${context.lesion_location?.value === value ? 'selected' : ''}>${value}</option>`).join('')}</select></label>
      <label>Cytology<select name="cytology"><option value="UNKNOWN">Unknown</option>${['NOT_PERFORMED','NEGATIVE','SUSPICIOUS','POSITIVE'].map(value => `<option ${context.cytology?.status === value ? 'selected' : ''}>${value}</option>`).join('')}</select></label>
      <label>Serum CA19-9 result<select name="ca19_status"><option value="UNKNOWN">Unknown</option><option ${context.serum_ca19_9?.status === 'INCREASED' ? 'selected' : ''}>INCREASED</option><option ${context.serum_ca19_9?.status === 'NORMAL' ? 'selected' : ''}>NORMAL</option></select></label>
      <label>CA19-9 value<input name="ca19_value" type="number" min="0" step="any" value="${escapeHtml(context.serum_ca19_9?.value ?? '')}"></label>
      <label>CA19-9 unit<input name="ca19_unit" value="${escapeHtml(context.serum_ca19_9?.unit || '')}"></label>
      <label>CA19-9 source<input name="ca19_source" value="${escapeHtml(context.serum_ca19_9?.evidence?.[0]?.evidence_reference || '')}"></label>
      <label>CA19-9 verification<select name="ca19_verification"><option value="UNVERIFIED">Unverified</option><option value="VERIFIED" ${context.serum_ca19_9?.evidence?.[0]?.verification_status === 'VERIFIED' ? 'selected' : ''}>Verified</option></select></label>
      ${statusField('new_onset_diabetes', 'New-onset diabetes within past year', context.new_onset_diabetes?.status)}
      <label>New-onset diabetes date<input type="date" name="new_diabetes_date" value="${escapeHtml(context.new_onset_diabetes?.occurred_at || '')}"></label>
      ${statusField('acute_diabetes_exacerbation', 'Acute diabetes exacerbation within past year', context.acute_diabetes_exacerbation?.status)}
      <label>Worsening diabetes date<input type="date" name="worsening_diabetes_date" value="${escapeHtml(context.acute_diabetes_exacerbation?.occurred_at || '')}"></label>
      <h3 class="form-span">Growth assessment measurements</h3>
      ${measurementField('growth_previous', 'Prior cyst size', prior.value_mm, prior.source, prior.verification_status, prior.status)}
      <label>Prior measurement date<input type="date" name="growth_previous_date" value="${escapeHtml(prior.measured_at || '')}"></label>
      ${measurementField('growth_current', 'Current cyst size', current.value_mm, current.source, current.verification_status, current.status)}
      <label>Current measurement date<input type="date" name="growth_current_date" value="${escapeHtml(current.measured_at || '')}"></label>
      <label>Measurements comparable<select name="growth_comparability"><option>UNKNOWN</option><option ${context.longitudinal_measurements?.comparability === 'COMPARABLE' ? 'selected' : ''}>COMPARABLE</option><option ${context.longitudinal_measurements?.comparability === 'INCOMPARABLE' ? 'selected' : ''}>INCOMPARABLE</option></select></label>
    </div><button class="button primary" type="submit">Save context and evaluate</button><p id="clinical-context-error" class="error hidden"></p></form>
  </section>`;
}
