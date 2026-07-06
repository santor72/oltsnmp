from __future__ import annotations

from dataclasses import dataclass

from app.core.provider import VendorProvider


@dataclass(frozen=True)
class VendorSelection:
    vendor: str
    provider: VendorProvider


class VendorRegistry:
    def __init__(self, providers: list[VendorProvider], default_vendor: str = "zte") -> None:
        self.providers = providers
        self.default_vendor = default_vendor

    def get(self, vendor: str | None = None) -> VendorSelection:
        selected = (vendor or self.default_vendor).strip().lower()
        for provider in self.providers:
            tags = tuple(tag.strip().lower() for tag in provider.vendor_tags)
            if selected in tags:
                return VendorSelection(vendor=tags[0], provider=provider)
        available = ", ".join(sorted({tag for provider in self.providers for tag in provider.vendor_tags}))
        raise ValueError(f"unsupported vendor '{selected}', available: {available}")
