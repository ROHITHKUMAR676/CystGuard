export const clinicianSeed = {
  id: 'DR-2048',
  name: 'Dr. A. Rivera',
  specialty: 'Gastroenterology',
  email: 'doctor@cystguard.health',
  accessCode: 'CG-AR-2486'
};

export const patientSeeds = [
  {
    id: 'CG-1048', name: 'Maya Patel', email: 'maya.patel@example.com', age: 46,
    diagnosis: 'Branch-duct IPMN', doctorId: clinicianSeed.id, lastMri: '18 Sep 2026', nextVisit: '14 Dec 2026',
    symptoms: [{ name: 'Mild abdominal discomfort', severity: 'Mild', date: '2026-10-03', note: 'After meals' }],
    meals: [
      { name: 'Oatmeal, berries and yogurt', date: 'Today', kcal: 385, protein: 19, carbs: 58, confirmed: true },
      { name: 'Lentil soup with whole-grain toast', date: 'Yesterday', kcal: 440, protein: 23, carbs: 62, confirmed: true }
    ]
  },
  {
    id: 'CG-1031', name: 'Jordan Lee', email: 'jordan.lee@example.com', age: 59,
    diagnosis: 'Pancreatic cyst under surveillance', doctorId: clinicianSeed.id, lastMri: '04 Aug 2026', nextVisit: '10 Feb 2027',
    symptoms: [{ name: 'No new symptoms reported', severity: 'Mild', date: '2026-10-01', note: 'Routine check-in' }],
    meals: [
      { name: 'Egg and spinach breakfast wrap', date: 'Today', kcal: 410, protein: 24, carbs: 39, confirmed: true },
      { name: 'Baked salmon, rice and greens', date: 'Yesterday', kcal: 520, protein: 36, carbs: 48, confirmed: true }
    ]
  }
];

export const seededAccessRequests = [
  {
    name: 'Maya Patel', patientId: 'CG-1048', doctorCode: clinicianSeed.accessCode,
    status: 'Pending', reference: 'CG-REQ-2840', createdAt: 'Today · 8:40 AM'
  },
  {
    name: 'Jordan Lee', patientId: 'CG-1031', doctorCode: clinicianSeed.accessCode,
    status: 'Approved', reviewedAt: 'Today · 9:05 AM', reference: 'CG-REQ-2841', createdAt: 'Today · 9:15 AM'
  }
];

const analysisProfiles = [
  { score: 0.72, threshold: 0.50, cystMm: 31, ductMm: 4, profile: 'Higher Risk Profile', evidence: ['Cyst diameter measured at 31 mm', 'Main pancreatic duct measured at 4 mm', 'Model score exceeds the configured review threshold'] },
  { score: 0.38, threshold: 0.50, cystMm: 22, ductMm: 3, profile: 'No / Low Risk Profile', evidence: ['Cyst diameter measured at 22 mm', 'Main pancreatic duct measured at 3 mm', 'Model score is below the configured review threshold'] },
  { score: 0.58, threshold: 0.50, cystMm: 28, ductMm: 6, profile: 'Higher Risk Profile', evidence: ['Cyst diameter measured at 28 mm', 'Main pancreatic duct measured at 6 mm', 'Model score exceeds the configured review threshold'] },
  { score: 0.46, threshold: 0.50, cystMm: 25, ductMm: 4, profile: 'No / Low Risk Profile', evidence: ['Cyst diameter measured at 25 mm', 'Main pancreatic duct measured at 4 mm', 'Model score is below the configured review threshold'] }
];

function stableHash(value) {
  let hash = 2166136261;
  for (const char of String(value)) hash = Math.imul(hash ^ char.charCodeAt(0), 16777619);
  return hash >>> 0;
}

export function resultForUpload(filename, runNumber = 0, patientId = '') {
  const index = (stableHash(`${patientId}:${filename}`) + Math.max(0, runNumber - 1)) % analysisProfiles.length;
  return { ...analysisProfiles[index], date: new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date()) };
}

const mealEstimates = [
  { kcal: 385, protein: 19, carbs: 58, fat: 10, label: 'Balanced grain and fruit meal' },
  { kcal: 460, protein: 27, carbs: 42, fat: 18, label: 'Protein-rich meal' },
  { kcal: 325, protein: 14, carbs: 48, fat: 8, label: 'Light meal with vegetables' },
  { kcal: 520, protein: 32, carbs: 55, fat: 19, label: 'Higher-energy meal' }
];

export function estimateMeal(description, imageName = '', entryCount = 0) {
  const index = (stableHash(`${description}:${imageName}`) + entryCount) % mealEstimates.length;
  return { ...mealEstimates[index], estimated: true };
}
