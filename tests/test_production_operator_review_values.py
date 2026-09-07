from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_review_profile_fields_use_bound_react_labels_and_normalized_phone():
    import production_operator

    actions = [
        {
            "selector": "#country",
            "operation": "react_select_exact",
            "value": {
                "search_text": "United States",
                "exact_option": "United States +1",
                "selected_option": "+1",
            },
        },
        {
            "selector": "#school",
            "operation": "react_select_exact",
            "value": {
                "search_text": "San Diego",
                "exact_option": "University of California - San Diego",
            },
        },
        {
            "selector": "#phone",
            "operation": "replace_tel_local_digits",
            "value": "(571) 435-5734",
        },
        {
            "selector": "#privacy",
            "operation": "set_checked",
            "value": True,
        },
        {
            "selector": "#resume",
            "operation": "cdp_upload",
            "value": "/safe/Resume.pdf",
        },
    ]

    assert production_operator._review_profile_fields(actions) == {
        "#country": "+1",
        "#school": "University of California - San Diego",
        "#phone": "5714355734",
        "#privacy": True,
    }
