from datetime import date, timedelta

import pytest
from app.auth.models import PatientDoctorAccess
from app.food.food_provider import FoodAnalysisError, FoodAnalysisResult, FoodProviderUnavailable
from app.food.foodcnn_adapter import FoodCNNAdapter
from app.food.nutrition_rules import meal_context_flags, nutrition_alerts
from app.config import get_settings


class FixedFoodProvider:
    def __init__(self, error=None):
        self.error = error

    def analyze(self, image):
        if self.error:
            raise self.error
        return FoodAnalysisResult(
            provider="FoodCNN", provider_version="test-commit", model_version="test-model",
            nutrition_source="FoodCNN/Nutrition5K", nutrition_source_version=None,
            estimation_method="single-image regression", recognition_confidence=None,
            estimated_portion_grams=250.0,
            nutrients={"calories_kcal": 480.0, "fat_g": 14.0, "carbohydrates_g": 62.0, "protein_g": 22.0},
            raw_output={"Calories (kcal)": 480.0, "Estimated Weight (g)": 250.0},
        )


def register_patient(client, name="Patient One"):
    response = client.post("/api/v1/auth/register", json={
        "email": f"{name.lower().replace(' ', '.')}@example.test",
        "password": "secure-test-password", "role": "PATIENT", "display_name": name,
    })
    assert response.status_code == 201, response.text
    return response.json()


def login_header(client, email, password="secure-test-password"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def analyze(client, headers, provider=None):
    if provider is not None:
        client.app.dependency_overrides[
            __import__("app.api.food", fromlist=["get_food_provider"]).get_food_provider
        ] = lambda: provider
    return client.post("/api/v1/food/meals/analyze", headers=headers,
        files={"upload": ("plate.jpg", b"valid test image bytes", "image/jpeg")},
        data={"description": "Dinner"})


def test_image_analysis_persists_estimates_and_provenance(client):
    user = register_patient(client)
    response = analyze(client, login_header(client, user["email"]), FixedFoodProvider())
    assert response.status_code == 201
    assert response.json()["nutrition_estimate"]["calories_kcal"] == 480
    assert response.json()["food_provider"] == "FoodCNN"
    assert response.json()["food_provider_version"] == "test-commit"


def test_foodcnn_output_does_not_invent_food_labels(client):
    user = register_patient(client)
    result = analyze(client, login_header(client, user["email"]), FixedFoodProvider()).json()
    assert result["food_items"] == []


def test_image_recognition_confidence_is_unknown(client):
    user = register_patient(client)
    result = analyze(client, login_header(client, user["email"]), FixedFoodProvider()).json()
    assert result["recognition_confidence"] is None


def test_nutrient_mapping_uses_canonical_fields(client):
    user = register_patient(client)
    result = analyze(client, login_header(client, user["email"]), FixedFoodProvider()).json()
    assert set(result["nutrition_estimate"]) == {"calories_kcal", "fat_g", "carbohydrates_g", "protein_g", "estimated_portion_grams"}


def test_empty_image_is_rejected(client):
    user = register_patient(client)
    response = client.post("/api/v1/food/meals/analyze", headers=login_header(client, user["email"]),
        files={"upload": ("plate.jpg", b"", "image/jpeg")})
    assert response.status_code == 422


def test_unsupported_image_type_is_rejected(client):
    user = register_patient(client)
    response = client.post("/api/v1/food/meals/analyze", headers=login_header(client, user["email"]),
        files={"upload": ("plate.txt", b"x", "text/plain")})
    assert response.status_code == 415


@pytest.mark.parametrize("error,expected", [
    (FoodAnalysisError("bad image"), 422),
    (FoodProviderUnavailable("model unavailable"), 503),
])
def test_provider_failure_does_not_create_meal(client, error, expected):
    user = register_patient(client)
    headers = login_header(client, user["email"])
    response = analyze(client, headers, FixedFoodProvider(error))
    assert response.status_code == expected
    assert client.get(f"/api/v1/patients/{user['id']}/meals", headers=headers).json() == []


def test_patient_confirmation_persists_food_and_final_nutrition(client):
    user = register_patient(client)
    headers = login_header(client, user["email"])
    meal = analyze(client, headers, FixedFoodProvider()).json()
    response = client.post(f"/api/v1/food/meals/{meal['id']}/confirm", headers=headers, json={
        "confirmed": True, "description": "Rice and lentils", "food_items": ["rice", "lentils"],
        "food_context_tags": [],
    })
    assert response.status_code == 200
    assert response.json()["patient_confirmed"] is True
    assert response.json()["final_nutrition"]["calories_kcal"] == 480


def test_uncertain_confirmation_keeps_final_nutrition_unknown(client):
    user = register_patient(client)
    headers = login_header(client, user["email"])
    meal = analyze(client, headers, FixedFoodProvider()).json()
    response = client.post(f"/api/v1/food/meals/{meal['id']}/confirm", headers=headers,
        json={"confirmed": False, "description": "Unsure what this meal contains"})
    assert response.status_code == 200
    assert response.json()["analysis_status"] == "UNCERTAIN"
    assert response.json()["final_nutrition"] is None


def test_patient_can_correct_estimate_on_confirmation(client):
    user = register_patient(client)
    headers = login_header(client, user["email"])
    meal = analyze(client, headers, FixedFoodProvider()).json()
    response = client.post(f"/api/v1/food/meals/{meal['id']}/confirm", headers=headers, json={
        "confirmed": True, "description": "Corrected serving", "food_items": ["rice"],
        "estimated_portion_grams": 200, "nutrition": {"calories_kcal": 400},
    })
    assert response.status_code == 200
    assert response.json()["final_nutrition"]["calories_kcal"] == 400
    assert response.json()["estimated_portion_grams"] == 200


def test_confirmed_meal_patch_keeps_correction_provenance(client):
    user = register_patient(client)
    headers = login_header(client, user["email"])
    meal = analyze(client, headers, FixedFoodProvider()).json()
    client.post(f"/api/v1/food/meals/{meal['id']}/confirm", headers=headers,
        json={"confirmed": True, "description": "Lunch"})
    response = client.patch(f"/api/v1/food/meals/{meal['id']}", headers=headers,
        json={"nutrition": {"calories_kcal": 410}, "food_items": ["pasta"]})
    assert response.status_code == 200
    assert response.json()["final_nutrition"]["calories_kcal"] == 410
    assert response.json()["patient_corrections"]["food_items"] == ["pasta"]


def test_meal_image_requires_authenticated_patient(client):
    user = register_patient(client)
    meal = analyze(client, login_header(client, user["email"]), FixedFoodProvider()).json()
    assert client.get(f"/api/v1/food/meals/{meal['id']}/image").status_code == 401


def test_doctor_cannot_submit_patient_meal(client):
    doctor = client.post("/api/v1/auth/register", json={"email": "meal-doctor@example.test",
        "password": "secure-test-password", "role": "DOCTOR"}).json()
    response = analyze(client, login_header(client, doctor["email"]), FixedFoodProvider())
    assert response.status_code == 403


def test_only_connected_doctor_can_save_nutrition_target(client):
    patient = register_patient(client)
    doctor = client.post("/api/v1/auth/register", json={"email": "target-doctor@example.test",
        "password": "secure-test-password", "role": "DOCTOR"}).json()
    session = client.app.state.test_session_factory()
    session.add(PatientDoctorAccess(patient_user_id=patient["id"], doctor_user_id=doctor["id"], status="ACTIVE"))
    session.commit()
    session.close()
    response = client.post(f"/api/v1/patients/{patient['id']}/nutrition/profile",
        headers=login_header(client, doctor["email"]), json={"target_daily_kcal": 1800})
    assert response.status_code == 200
    assert response.json()["target_daily_kcal"] == 1800


def test_unconnected_doctor_cannot_read_nutrition_summary(client):
    patient = register_patient(client)
    doctor = client.post("/api/v1/auth/register", json={"email": "unconnected@example.test",
        "password": "secure-test-password", "role": "DOCTOR"}).json()
    response = client.get(f"/api/v1/patients/{patient['id']}/nutrition/summary",
        headers=login_header(client, doctor["email"]))
    assert response.status_code == 404


def test_nutrition_summary_has_no_automatically_created_target(client):
    user = register_patient(client)
    summary = client.get(f"/api/v1/patients/{user['id']}/nutrition/summary",
        headers=login_header(client, user["email"])).json()
    assert summary["recorded_target"] == {"daily_kcal": None, "daily_protein_g": None, "source": None}
    assert summary["target_notice"]


def test_nutrition_observation_persists_patient_context(client):
    user = register_patient(client)
    response = client.post(f"/api/v1/patients/{user['id']}/nutrition/observations",
        headers=login_header(client, user["email"]), json={"weight_kg": 64.5, "height_cm": 168,
            "appetite": "FAIR", "reported_symptoms": ["NAUSEA"]})
    assert response.status_code == 201
    assert response.json()["bmi"] == 22.9
    assert response.json()["reported_symptoms"] == ["NAUSEA"]


def test_nutrition_summary_requires_authentication(client):
    assert client.get("/api/v1/patients/1/nutrition/summary").status_code == 401


def test_patient_cannot_read_another_patients_nutrition(client):
    one, two = register_patient(client, "Patient One"), register_patient(client, "Patient Two")
    response = client.get(f"/api/v1/patients/{two['id']}/nutrition/summary",
        headers=login_header(client, one["email"]))
    assert response.status_code == 404


def test_context_flag_is_noncausal_and_requires_symptom_and_tag():
    flags = meal_context_flags(["HIGH_FAT_OR_FRIED"], ["DIARRHEA"])
    assert flags[0]["code"] == "DIARRHEA_MEAL_CONTEXT"
    assert "does not show" in flags[0]["message"]
    assert meal_context_flags(["HIGH_FAT_OR_FRIED"], []) == []


def test_context_rules_do_not_create_forbidden_foods_or_diet_instructions():
    assert meal_context_flags(["ALCOHOL", "SPICY", "HIGH_FAT_OR_FRIED"], []) == []


def test_low_intake_rule_requires_recorded_clinician_target():
    today = date(2026, 10, 9)
    complete = {today - timedelta(days=offset) for offset in range(8)}
    totals = {day: {"calories_kcal": 300.0} for day in complete}
    assert nutrition_alerts(daily_totals=totals, complete_days=complete, observations=[],
        meal_contexts=[], target_daily_kcal=None, today=today) == []


def test_sustained_low_intake_flags_only_review():
    today = date(2026, 10, 9)
    complete = {today - timedelta(days=offset) for offset in range(8)}
    totals = {day: {"calories_kcal": 300.0} for day in complete}
    alerts = nutrition_alerts(daily_totals=totals, complete_days=complete, observations=[],
        meal_contexts=[], target_daily_kcal=2000, today=today)
    assert alerts[0]["code"] == "PERSISTENT_INTAKE_BELOW_RECORDED_TARGET"
    assert "diagnosis" not in alerts[0]["summary"].lower()


def test_recurrent_patient_reported_poor_appetite_creates_review_flag():
    today = date(2026, 10, 9)
    rows = [{"date": today - timedelta(days=offset), "appetite": "POOR", "intake_interfered": True}
        for offset in (0, 2, 4)]
    alerts = nutrition_alerts(daily_totals={}, complete_days=set(), observations=rows,
        meal_contexts=[], target_daily_kcal=None, today=today)
    assert alerts[0]["code"] == "RECURRENT_POOR_APPETITE"


def test_weight_decline_flag_is_contextual_review_not_diagnosis():
    today = date(2026, 10, 9)
    rows = [{"date": today - timedelta(days=20), "weight_kg": 70.0},
        {"date": today, "weight_kg": 66.0}]
    alerts = nutrition_alerts(daily_totals={}, complete_days=set(), observations=rows,
        meal_contexts=[], target_daily_kcal=None, today=today)
    assert alerts[0]["code"] == "RECENT_WEIGHT_DECLINE"
    assert "not a diagnosis" in alerts[0]["summary"]


def test_food_analysis_provider_failure_has_no_persisted_row(client):
    user = register_patient(client)
    headers = login_header(client, user["email"])
    response = analyze(client, headers, FixedFoodProvider(FoodProviderUnavailable("offline")))
    assert response.status_code == 503
    assert client.get(f"/api/v1/patients/{user['id']}/meals", headers=headers).json() == []


def test_unconfirmed_estimate_is_excluded_from_nutrition_totals(client):
    user = register_patient(client)
    headers = login_header(client, user["email"])
    analyze(client, headers, FixedFoodProvider())
    summary = client.get(f"/api/v1/patients/{user['id']}/nutrition/summary", headers=headers).json()
    assert summary["average_per_logged_day"] is None
    assert summary["meals"][0]["nutrition_estimate"]["calories_kcal"] == 480


def test_non_finite_provider_output_is_rejected_without_persistence(client):
    class InvalidProvider(FixedFoodProvider):
        def analyze(self, image):
            result = super().analyze(image)
            return FoodAnalysisResult(**{**result.__dict__, "nutrients": {
                **result.nutrients, "calories_kcal": float("nan")}})
    user = register_patient(client)
    headers = login_header(client, user["email"])
    response = analyze(client, headers, InvalidProvider())
    assert response.status_code == 422
    assert client.get(f"/api/v1/patients/{user['id']}/meals", headers=headers).json() == []


def test_foodcnn_checkpoint_inference_on_synthetic_image():
    checkpoint = get_settings().foodcnn_checkpoint_path
    if not checkpoint.is_file() or not (checkpoint.parent / "predict_nutrition.py").is_file():
        pytest.skip("Pinned FoodCNN source and checkpoint are not provisioned")
    pytest.importorskip("torch")
    pytest.importorskip("torchvision")
    image_module = pytest.importorskip("PIL.Image")
    from io import BytesIO

    stream = BytesIO()
    image_module.new("RGB", (224, 224), (112, 146, 96)).save(stream, format="JPEG")
    result = FoodCNNAdapter().analyze(stream.getvalue())
    assert result.provider == "FoodCNN"
    assert result.provider_version == "2c944166f988acff4374d131b8b1fe535a64abf6"
    assert set(result.nutrients) == {"calories_kcal", "fat_g", "carbohydrates_g", "protein_g"}
    assert all(value >= 0 for value in result.nutrients.values())
    assert result.estimated_portion_grams > 0
    assert result.recognition_confidence is None
