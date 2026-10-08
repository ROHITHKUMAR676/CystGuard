"""Adapter for the unmodified FoodCNN upstream single-image inference model."""

from __future__ import annotations

from io import BytesIO
import importlib.util
import math
from pathlib import Path
from threading import Lock

from app.config import get_settings
from app.food.food_provider import FoodAnalysisError, FoodAnalysisResult, FoodProviderUnavailable


UPSTREAM_URL = "https://github.com/FoodCNN/FoodCNN"
UPSTREAM_COMMIT = "2c944166f988acff4374d131b8b1fe535a64abf6"


class FoodCNNAdapter:
    """Runs FoodCNN's calorie/macronutrient and portion regression on one RGB image.

    FoodCNN does not classify food items and does not output a calibrated confidence.
    Both limitations are preserved as null/absent outputs; no food labels are inferred.
    """

    def __init__(self, checkpoint_path: Path | None = None, model_version: str | None = None):
        settings = get_settings()
        self.checkpoint_path = Path(checkpoint_path or settings.foodcnn_checkpoint_path)
        self.model_version = model_version or settings.foodcnn_model_version
        self._lock = Lock()
        self._runtime = None

    def _load(self):
        if self._runtime is not None:
            return self._runtime
        with self._lock:
            if self._runtime is not None:
                return self._runtime
            predictor_path = self.checkpoint_path.parent / "predict_nutrition.py"
            if not predictor_path.is_file() or not self.checkpoint_path.is_file():
                raise FoodProviderUnavailable("FoodCNN source or checkpoint is not installed.")
            try:
                import torch
                from PIL import Image
                from torchvision import transforms
            except ImportError as exc:
                raise FoodProviderUnavailable(
                    "FoodCNN runtime dependencies are missing; install backend/requirements-food.txt."
                ) from exc

            spec = importlib.util.spec_from_file_location("cystguard_vendor_foodcnn", predictor_path)
            if spec is None or spec.loader is None:
                raise FoodProviderUnavailable("FoodCNN inference source could not be loaded.")
            module = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(module)
                # The checkpoint contains the model weights. Avoid the upstream script's
                # ImageNet weight download by constructing the same architecture uninitialized.
                nutrition_model = module.ResNetFromScratch(num_outputs=4, use_pretrained=False)
                weight_model = module.DeepWeightCNN(num_outputs=1)
                model = module.CombinedSystem(nutrition_model, weight_model)
                state = torch.load(self.checkpoint_path, map_location="cpu", weights_only=True)
                model.load_state_dict(state, strict=True)
                model.to(torch.device("cpu"))
                model.eval()
            except Exception as exc:
                raise FoodProviderUnavailable("FoodCNN checkpoint could not be loaded by its upstream architecture.") from exc

            base_transform = transforms.Compose([
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
            ])
            normalize = transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
            self._runtime = (torch, Image, model, base_transform, normalize)
        return self._runtime

    def analyze(self, image: bytes) -> FoodAnalysisResult:
        torch, Image, model, base_transform, normalize = self._load()
        try:
            with Image.open(BytesIO(image)) as opened:
                rgb = opened.convert("RGB")
            base = base_transform(rgb).unsqueeze(0)
            normalized = normalize(base.squeeze(0)).unsqueeze(0)
            with torch.inference_mode():
                prediction, portion = model(base, normalized)
            values = prediction.detach().cpu().reshape(-1).tolist()
            portion_grams = float(portion.detach().cpu().reshape(-1)[0])
            if len(values) != 4:
                raise FoodAnalysisError("FoodCNN returned an unexpected nutrition structure.")
            calories, fat, carbohydrates, protein = (float(value) for value in values)
            numeric = (calories, fat, carbohydrates, protein, portion_grams)
            if not all(math.isfinite(value) and value >= 0 for value in numeric) or portion_grams == 0:
                raise FoodAnalysisError("FoodCNN returned invalid or non-finite estimates.")
        except FoodAnalysisError:
            raise
        except Exception as exc:
            raise FoodAnalysisError("FoodCNN could not analyze this image.") from exc

        raw = {
            "Calories (kcal)": calories,
            "Fat (g)": fat,
            "Carbohydrates (g)": carbohydrates,
            "Protein (g)": protein,
            "Estimated Weight (g)": portion_grams,
        }
        return FoodAnalysisResult(
            provider="FoodCNN",
            provider_version=UPSTREAM_COMMIT,
            model_version=self.model_version,
            nutrition_source="FoodCNN model trained using Nutrition5K",
            nutrition_source_version=None,
            estimation_method="single-image multi-output regression",
            recognition_confidence=None,
            estimated_portion_grams=portion_grams,
            nutrients={
                "calories_kcal": calories,
                "fat_g": fat,
                "carbohydrates_g": carbohydrates,
                "protein_g": protein,
            },
            raw_output=raw,
        )
