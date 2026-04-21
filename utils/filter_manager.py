"""IMPROVEMENT 5: Smart Filter Save & Recall"""
import pandas as pd
from db.database import (
    save_filter_preset, get_filter_preset, list_filter_presets,
    delete_filter_preset, get_connection
)


class FilterManager:
    def __init__(self):
        self.current_filters = {}

    def save_preset(self, preset_name: str, carriers: list = None, sizes: list = None,
                   statuses: list = None, search_text: str = None) -> bool:
        """Save current filter as preset."""
        config = {
            "carriers": carriers or [],
            "sizes": sizes or [],
            "statuses": statuses or [],
            "search_text": search_text or "",
        }
        return save_filter_preset(preset_name, config)

    def load_preset(self, preset_name: str) -> dict | None:
        """Load saved filter preset."""
        return get_filter_preset(preset_name)

    def apply_filters(self, df: pd.DataFrame, carriers: list = None, sizes: list = None,
                     statuses: list = None, search_text: str = None) -> pd.DataFrame:
        """Apply filters to dataframe."""
        filtered = df.copy()

        if carriers:
            filtered = filtered[
                filtered["Compagnie maritime"].isin(carriers) |
                filtered["Compagnie maritime"].isna()
            ]

        if sizes:
            filtered = filtered[
                filtered["Container size"].isin(sizes) |
                filtered["Container size"].isna()
            ]

        if statuses:
            filtered = filtered[
                filtered["Statut Container"].isin(statuses) |
                filtered["Statut Container"].isna()
            ]

        if search_text:
            p = search_text.lower()
            filtered = filtered[
                filtered["N° Container"].fillna("").str.lower().str.contains(p) |
                filtered["N° TAN"].fillna("").str.lower().str.contains(p) |
                filtered["Item"].fillna("").str.lower().str.contains(p)
            ]

        return filtered

    def get_available_values(self, df: pd.DataFrame) -> dict:
        """Get all unique values for filter options."""
        return {
            "carriers": sorted([c for c in df["Compagnie maritime"].dropna().unique()]),
            "sizes": sorted([s for s in df["Container size"].dropna().unique()]),
            "statuses": sorted([s for s in df["Statut Container"].dropna().unique()]),
        }

    def list_presets(self) -> list:
        """List all saved presets."""
        return list_filter_presets()

    def delete_preset(self, preset_name: str):
        """Delete a saved preset."""
        delete_filter_preset(preset_name)


# Quick filter functions for use in streamlit pages

def get_container_options(df: pd.DataFrame) -> dict:
    """Get filter options from containers view."""
    manager = FilterManager()
    return manager.get_available_values(df)


def apply_container_filters(df: pd.DataFrame, carriers: list = None, sizes: list = None,
                           statuses: list = None, search_text: str = None) -> pd.DataFrame:
    """Apply filters to containers dataframe."""
    manager = FilterManager()
    return manager.apply_filters(df, carriers, sizes, statuses, search_text)


def apply_shipment_filters(df: pd.DataFrame, carriers: list = None, statuses: list = None,
                          search_text: str = None) -> pd.DataFrame:
    """Apply filters to shipments dataframe."""
    filtered = df.copy()

    if carriers:
        filtered = filtered[filtered["carrier"].isin(carriers) | filtered["carrier"].isna()]

    if statuses:
        filtered = filtered[filtered["status"].isin(statuses)]

    if search_text:
        p = search_text.lower()
        filtered = filtered[
            filtered["tan"].fillna("").str.lower().str.contains(p) |
            filtered["vessel"].fillna("").str.lower().str.contains(p) |
            filtered["item"].fillna("").str.lower().str.contains(p)
        ]

    return filtered
