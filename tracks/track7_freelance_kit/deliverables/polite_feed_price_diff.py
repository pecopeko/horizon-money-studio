"""Freelance Deliverable 1: Polite Feed / Public Catalog Price & Diff Monitor (No Anti-Bot Bypass)."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def compute_catalog_diff(
    previous_items: list[dict[str, Any]],
    current_items: list[dict[str, Any]],
    key_field: str = "handle",
) -> list[dict[str, Any]]:
    """Compute added, removed, price-changed, and stock-changed items between two JSON catalog snapshots."""
    prev_map = {str(it.get(key_field) or ""): it for it in previous_items if it.get(key_field)}
    curr_map = {str(it.get(key_field) or ""): it for it in current_items if it.get(key_field)}

    events: list[dict[str, Any]] = []
    for key in sorted(set(prev_map) | set(curr_map)):
        old = prev_map.get(key)
        new = curr_map.get(key)
        if old is None and new is not None:
            events.append({"key": key, "change": "added", "old_price": None, "new_price": new.get("price_min"), "old_stock": None, "new_stock": new.get("in_stock")})
        elif new is None and old is not None:
            events.append({"key": key, "change": "removed", "old_price": old.get("price_min"), "new_price": None, "old_stock": old.get("in_stock"), "new_stock": None})
        elif old is not None and new is not None:
            p_changed = old.get("price_min") != new.get("price_min")
            s_changed = old.get("in_stock") != new.get("in_stock")
            if p_changed or s_changed:
                events.append(
                    {
                        "key": key,
                        "change": "price_or_stock_changed",
                        "old_price": old.get("price_min"),
                        "new_price": new.get("price_min"),
                        "old_stock": old.get("in_stock"),
                        "new_stock": new.get("in_stock"),
                    }
                )
    return events


def write_diff_csv(events: list[dict[str, Any]], out_csv: str | Path) -> Path:
    """Persist diff events to UTF-8-SIG Excel-friendly CSV."""
    p = Path(out_csv)
    p.parent.mkdir(parents=True, exist_ok=True)
    fields = ["key", "change", "old_price", "new_price", "old_stock", "new_stock"]
    with p.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in events:
            writer.writerow({k: row.get(k) for k in fields})
    return p
