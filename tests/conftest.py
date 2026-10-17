"""Fixtures for the Madeira Fuel Prices tests."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let Home Assistant load the integration from custom_components."""
    return


# The feed as it was on Saturday 3 October 2026 (see docs/feed.md).
FEED = {
    "updated_at": "2026-10-03T14:40:25Z",
    "warnings": [],
    "current": {
        "valid_from": "2026-09-28",
        "petrol_95": 2.029,
        "diesel": 2.148,
        "coloured_diesel": 1.7,
        "portaria": "25/2022",
        "source": "https://joram.madeira.gov.pt/joram/2serie/Ano%20de%202026/IISerie-174-2026-09-25Supl3.pdf",
    },
    "next": {
        "valid_from": "2026-10-05",
        "petrol_95": 2.021,
        "diesel": 2.12,
        "coloured_diesel": 1.672,
        "portaria": "25/2022",
        "source": "https://joram.madeira.gov.pt/joram/2serie/Ano%20de%202026/IISerie-179-2026-10-02Supl.pdf",
    },
}
