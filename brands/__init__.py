"""Brand configuration module — load brand profiles from brands/<slug>/config.yaml."""

from brands.loader import BrandConfig, brand_config, init_brand, set_brand, load_all_brands

__all__ = ["BrandConfig", "brand_config", "init_brand", "set_brand", "load_all_brands"]
