"""Backward-compatible storage facade for the books domain."""

from .services.storage import delete_library_asset, is_managed_asset_url, save_library_asset

__all__ = ["save_library_asset", "delete_library_asset", "is_managed_asset_url"]
