from __future__ import annotations

import sys
from pathlib import Path


PROCESSOR_DIR = Path(__file__).resolve().parents[2] / "src" / "processor"
if str(PROCESSOR_DIR) not in sys.path:
    sys.path.insert(0, str(PROCESSOR_DIR))

import xlsx_reader_v2 as xr  # noqa: E402


def test_grid_to_markdown_table_collapses_two_row_merged_header() -> None:
    rows = {
        0: {
            0: {"ref": "A1", "value": "Variants"},
            1: {"ref": "B1", "value": "Metric"},
            2: {"ref": "C1", "value": "ML-1M"},
            3: {"ref": "D1", "value": "ML-1M", "merged_from": "C1"},
            4: {"ref": "E1", "value": "Gowalla"},
            5: {"ref": "F1", "value": "Gowalla", "merged_from": "E1"},
        },
        1: {
            0: {"ref": "A2", "value": "Variants", "merged_from": "A1"},
            1: {"ref": "B2", "value": "Metric", "merged_from": "B1"},
            2: {"ref": "C2", "value": "HR"},
            3: {"ref": "D2", "value": "NDCG"},
            4: {"ref": "E2", "value": "HR"},
            5: {"ref": "F2", "value": "NDCG"},
        },
        2: {
            0: {"ref": "A3", "value": "BD-LRU Only"},
            1: {"ref": "B3", "value": "@10"},
            2: {"ref": "C3", "value": 0.301},
            3: {"ref": "D3", "value": 0.1695},
            4: {"ref": "E3", "value": 0.1199},
            5: {"ref": "F3", "value": 0.0579},
        },
    }

    markdown = xr._grid_to_markdown_table(rows, [0, 1, 2], 0, 5)

    assert "| Variants | Metric | ML-1M HR | ML-1M NDCG | Gowalla HR | Gowalla NDCG |" in markdown
    assert "| Variants | Metric | HR | NDCG | HR | NDCG |" not in markdown
    assert "| BD-LRU Only | @10 | 0.301 | 0.1695 | 0.1199 | 0.0579 |" in markdown
