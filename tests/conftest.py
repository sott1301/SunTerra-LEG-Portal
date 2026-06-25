import pytest

from sunterra_leg_portal import main as portal


@pytest.fixture(autouse=True)
def isolate_document_consent_state() -> None:
    portal.DOCUMENT_VERSIONS.clear()
    portal.CONSENT_EVIDENCE.clear()
    portal.NETWORK_TOPOLOGY_ENTRIES.clear()
    portal.PASSWORD_RESET_TOKENS.clear()
    portal.PILOT_FEEDBACK.clear()
    portal.INTEREST_RECORDS.clear()
    portal.PILOT_ALLOWLIST.clear()
