"""Country classifiers: CountryNet (ResNet-18 style, trained from scratch) and pretrained nets.

A pretrained network has already learned to see from hundreds of millions of photos, so it
needs far fewer GeoGuessr-style images to tell countries apart than a net starting from zero.
"""

from __future__ import annotations

from typing import Any

import torch
from torch import nn


class BasicBlock(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, stride: int) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(in_channels, out_channels, 3, stride, 1, bias=False)
        self.bn1 = nn.BatchNorm2d(out_channels)
        self.conv2 = nn.Conv2d(out_channels, out_channels, 3, 1, 1, bias=False)
        self.bn2 = nn.BatchNorm2d(out_channels)
        self.shortcut: nn.Module = nn.Identity()
        if stride != 1 or in_channels != out_channels:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_channels, out_channels, 1, stride, bias=False),
                nn.BatchNorm2d(out_channels),
            )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = torch.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        return torch.relu(out + self.shortcut(x))


class CountryNet(nn.Module):
    """``width=64`` gives the ResNet-18 layout (~11M parameters); tests use a tiny width."""

    def __init__(self, num_classes: int, width: int = 64, blocks: tuple[int, ...] = (2, 2, 2, 2)):
        super().__init__()
        self.stem = nn.Sequential(
            nn.Conv2d(3, width, 7, 2, 3, bias=False),
            nn.BatchNorm2d(width),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(3, 2, 1),
        )
        layers: list[nn.Module] = []
        channels = width
        for stage, count in enumerate(blocks):
            out_channels = width * 2**stage
            for index in range(count):
                stride = 2 if stage > 0 and index == 0 else 1
                layers.append(BasicBlock(channels, out_channels, stride))
                channels = out_channels
        self.stages = nn.Sequential(*layers)
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.head = nn.Linear(channels, num_classes)
        self._initialise()

    def _initialise(self) -> None:
        for module in self.modules():
            if isinstance(module, nn.Conv2d):
                nn.init.kaiming_normal_(module.weight, mode="fan_out", nonlinearity="relu")
            elif isinstance(module, nn.BatchNorm2d):
                nn.init.ones_(module.weight)
                nn.init.zeros_(module.bias)
        # Zero the last BatchNorm of each residual branch so blocks start as identities.
        for module in self.modules():
            if isinstance(module, BasicBlock):
                nn.init.zeros_(module.bn2.weight)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        features = self.pool(self.stages(self.stem(x))).flatten(1)
        logits: torch.Tensor = self.head(features)
        return logits


# Short names for the pretrained networks the runbook uses. "timm:<name>" picks any other
# timm model (the tests use a tiny untrained one).
BACKBONES = {
    "clip-b16": "vit_base_patch16_clip_224.openai",
    "convnext-t": "convnext_tiny.fb_in22k",
}
# The app feeds every model images normalised with ImageNet's mean and std.
APP_MEAN = (0.485, 0.456, 0.406)
APP_STD = (0.229, 0.224, 0.225)


def timm_name(backbone: str) -> str:
    if backbone.startswith("timm:"):
        return backbone.removeprefix("timm:")
    if backbone not in BACKBONES:
        known = ", ".join(["countrynet", *BACKBONES])
        raise SystemExit(f"Unknown --backbone {backbone!r}; choose one of {known} or timm:<name>.")
    return BACKBONES[backbone]


class PretrainedNet(nn.Module):
    """A pretrained timm network with a fresh country layer on top.

    Inputs arrive normalised the way the app normalises them; a fixed per-channel scale and
    shift turns that into the normalisation the network was pretrained with, so the app and
    its manifest stay the same for every backbone.
    """

    def __init__(self, num_classes: int, backbone: str, pretrained: bool = True) -> None:
        super().__init__()
        import timm

        body = timm.create_model(timm_name(backbone), pretrained=pretrained, num_classes=0)
        config: dict[str, Any] = dict(getattr(body, "pretrained_cfg", {}))
        mean: tuple[float, ...] = tuple(config.get("mean", APP_MEAN))
        std: tuple[float, ...] = tuple(config.get("std", APP_STD))
        features = int(getattr(body, "num_features"))  # noqa: B009
        scale = [a / b for a, b in zip(APP_STD, std, strict=True)]
        shift = [(m0 - m1) / s1 for m0, m1, s1 in zip(APP_MEAN, mean, std, strict=True)]
        self.body: nn.Module = body
        self.scale: torch.Tensor
        self.shift: torch.Tensor
        self.register_buffer("scale", torch.tensor(scale).view(1, 3, 1, 1))
        self.register_buffer("shift", torch.tensor(shift).view(1, 3, 1, 1))
        self.head = nn.Linear(features, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        logits: torch.Tensor = self.head(self.body(x * self.scale + self.shift))
        return logits


def build_model(
    num_classes: int, backbone: str = "countrynet", width: int = 64, pretrained: bool = True
) -> nn.Module:
    """CountryNet for ``backbone="countrynet"``, otherwise a pretrained network."""
    if backbone == "countrynet":
        return CountryNet(num_classes, width=width)
    return PretrainedNet(num_classes, backbone, pretrained=pretrained)
