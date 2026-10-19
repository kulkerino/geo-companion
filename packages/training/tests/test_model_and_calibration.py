from __future__ import annotations

import random

import pytest
import torch
from geo_training.calibration import choose_threshold, expected_calibration_error, fit_temperature
from geo_training.model import CountryNet
from geo_training.preprocess import eval_array, train_array
from PIL import Image


def test_full_width_model_is_resnet18_sized_and_maps_to_classes() -> None:
    model = CountryNet(num_classes=200)
    parameters = sum(p.numel() for p in model.parameters())
    assert 11_000_000 < parameters < 11_400_000
    assert model(torch.zeros(2, 3, 64, 64)).shape == (2, 200)


def test_models_start_from_random_initialisation() -> None:
    torch.manual_seed(1)
    first = CountryNet(3, width=8).head.weight.clone()
    torch.manual_seed(2)
    assert not torch.equal(first, CountryNet(3, width=8).head.weight)


def test_preprocessing_shapes_and_eval_determinism() -> None:
    image = Image.new("RGB", (120, 80), (10, 20, 30))
    assert eval_array(image, 32).shape == (3, 32, 32)
    assert (eval_array(image, 32) == eval_array(image, 32)).all()
    assert train_array(image, 32, random.Random(0)).shape == (3, 32, 32)


def test_train_augmentation_never_mirrors_the_image() -> None:
    # Left half dark, right half bright: a horizontal flip would swap them.
    image = Image.new("RGB", (64, 64), (0, 0, 0))
    image.paste((255, 255, 255), (32, 0, 64, 64))
    for seed in range(20):
        array = train_array(image, 32, random.Random(seed))
        assert array[:, :, :8].mean() <= array[:, :, -8:].mean()


def test_temperature_recovers_known_overconfidence() -> None:
    generator = torch.Generator().manual_seed(0)
    true_logits = torch.randn(4000, 5, generator=generator) * 2
    labels = torch.distributions.Categorical(logits=true_logits).sample()
    # The "model" is three times too confident; temperature scaling should undo it.
    temperature = fit_temperature(true_logits * 3, labels)
    assert 2.5 < temperature < 3.5
    raw = expected_calibration_error((true_logits * 3).softmax(1), labels)
    fixed = expected_calibration_error((true_logits * 3 / temperature).softmax(1), labels)
    assert fixed < raw


def test_threshold_reaches_target_on_the_answered_subset() -> None:
    probs = torch.tensor([[0.9, 0.1], [0.8, 0.2], [0.6, 0.4], [0.55, 0.45]])
    labels = torch.tensor([0, 0, 1, 0])
    result = choose_threshold(probs, labels, target=0.75)
    assert result.threshold == pytest.approx(0.55)
    assert result.coverage == 1.0
    strict = choose_threshold(probs, labels, target=1.0)
    assert strict.threshold == pytest.approx(0.8) and strict.coverage == 0.5


def test_threshold_abstains_everywhere_when_target_is_unreachable() -> None:
    probs = torch.tensor([[0.9, 0.1]])
    result = choose_threshold(probs, torch.tensor([1]), target=0.5)
    assert result.threshold > 1 and result.coverage == 0.0
