# Meal analysis and nutrition monitoring

## Provider integration

The image estimator is wrapped by `backend/app/food/foodcnn_adapter.py`; upstream code is not modified. The configured provider interface lives in `backend/app/food/food_provider.py`, so a future provider can replace FoodCNN without changing the meal API.

- Upstream repository: [FoodCNN/FoodCNN](https://github.com/FoodCNN/FoodCNN)
- Inspected upstream revision: `2c944166f988acff4374d131b8b1fe535a64abf6`
- License in the inspected clone: MIT
- Expected checkpoint: `backend/vendor/FoodCNN/best_finetuned_combined_model.pth`
- Optional Python dependencies: `backend/requirements-food.txt`

The pinned upstream inference script resizes an RGB image to 224 × 224 and applies ImageNet channel normalization for its nutrition branch. Its combined model regresses calories, fat, carbohydrates, protein, and estimated portion weight. It does **not** classify foods, return food labels, or provide calibrated recognition confidence. CystGuard therefore stores food names only when entered by the patient and reports recognition confidence as unavailable. The output is an image-level estimate and may be inaccurate for foods, servings, occlusion, or composition outside its training distribution.

Install the optional runtime in the backend environment and make the upstream repository/checkpoint available at the configured path. For a fresh checkout, provision the upstream files at the pinned revision with:

```powershell
git clone https://github.com/FoodCNN/FoodCNN.git backend/vendor/FoodCNN
git -C backend/vendor/FoodCNN checkout 2c944166f988acff4374d131b8b1fe535a64abf6
```

The already-inspected vendor checkout is not modified by CystGuard. Set `FOODCNN_CHECKPOINT_PATH` when the checkpoint is stored elsewhere. The checkpoint is a model artifact and is excluded from normal source tracking; production deployment must provision it explicitly. If the source, checkpoint, or runtime is unavailable, analysis returns a service-unavailable response and saves no estimate.

Each image analysis stores the raw provider output, canonical nutrition estimate, model/provider revision, estimation method, opaque image-storage key, and patient-confirmation state. Files are delivered only through an authenticated endpoint; filesystem paths are not returned. The image itself is not included in API JSON.

## Patient confirmation and intake summaries

Image estimates begin in `AWAITING_CONFIRMATION`. A patient can enter/correct meal identity, portion, and nutrient values before confirmation, or mark the analysis uncertain. The original estimate and raw provider result remain preserved separately from corrections. Confirmed records can be edited later with correction provenance. Pending and uncertain estimates remain visible in history but are excluded from intake totals until confirmed.

The nutrition summary reports daily totals, macro estimates, patient-reported weight, height/BMI context, appetite and reported symptom history, and the source of each meal estimate. A day contributes to calorie-target monitoring only when the patient marks the log complete and there is at least one confirmed image estimate. Meal logging cannot establish total intake when meals or snacks were not recorded.

Only a clinician with an active patient access grant can enter an individualized daily energy or protein target. CystGuard does not calculate a target. Weight and BMI are context, not diagnoses. Rules in `backend/app/food/nutrition_rules.py` produce clinician-review flags from recorded information; they do not diagnose, prescribe, change medication/PERT, or create forbidden-food instructions. Food/symptom context language explicitly avoids claiming causation.

## Clinical context for monitoring rules

The persistent intake rule implements the assessment thresholds described in the [ESPEN practical guideline on clinical nutrition in cancer](https://www.espen.org/files/ESPEN-Guidelines/ESPEN-practical-guideline-clinical-nutrition-in-cancer.pdf): below 50% of an individualized requirement for more than one week, or 50–75% for more than two weeks. It is evaluated only against a clinician-recorded target and complete-day entries. The weight-change flag uses screening thresholds summarized in the [NCI Nutrition in Cancer Care PDQ](https://www.cancer.gov/about-cancer/treatment/side-effects/appetite-loss/nutrition-hp-pdq), and is presented as a review prompt requiring clinical context.

These rules and model outputs have not been clinically validated as CystGuard interventions. They are monitoring support only.

## API endpoints

All routes are under `/api/v1` and require authentication unless stated otherwise.

| Method | Path | Access and purpose |
|---|---|---|
| POST | `/food/meals/analyze` | Patient uploads an image; returns a provider estimate awaiting patient review |
| POST | `/food/meals/{meal_id}/confirm` | Patient confirms/corrects or marks the estimate uncertain |
| PATCH | `/food/meals/{meal_id}` | Patient edits a previously confirmed meal; original provider output is retained |
| GET | `/food/meals/{meal_id}/image` | Patient or doctor with active grant streams the stored image |
| GET | `/patients/{patient_id}/meals` | Patient self or doctor with active grant reads meal history |
| GET | `/patients/{patient_id}/nutrition/summary` | Patient self or doctor with active grant reads estimates and monitoring flags |
| POST | `/patients/{patient_id}/nutrition/observations` | Patient records their own weight, appetite, symptom, and day-completion context |
| POST | `/patients/{patient_id}/nutrition/profile` | Authorized doctor records/updates target and documented context |

Run `alembic upgrade head` before using these endpoints against an existing database. The FoodCNN checkpoint and optional runtime must be separately provisioned.
