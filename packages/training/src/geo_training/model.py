"""A ResNet-18-style country classifier, randomly initialised (no pretrained weights)."""

from __future__ import annotations

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
