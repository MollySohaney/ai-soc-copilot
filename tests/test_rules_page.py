"""Purpose: Verify the Detection Rules page against real seeded data via AppTest.

Script-runs `app/views/rules.py`'s `render()` through Streamlit's `AppTest`,
with `api_state.get_client` monkeypatched to the seeded in-memory API
(`api_client_transport`), so assertions exercise the same seam the real page
uses (`client=api_state.get_client()`) without a live server or a browser.

Known seeded rules (see db/seed.py), in the order the API returns them
(most recently created first, i.e. reverse seed order):
- id 5 "Unusual Outbound Network Connection Volume" (Low, enabled)
- id 4 "SSH Authorized Keys Modification" (Critical, disabled — the only
  disabled seeded rule, a safe fixed point for the enable-toggle test)
- id 3 "Sudo Privilege Escalation" (High, enabled)
- id 2 "Valid Account Login Following Failed Attempts" (High, enabled)
- id 1 "SSH Brute Force Detection" (Medium, enabled)
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from api_client import rules as rules_api
from app.components import api_state

SCRIPT_PATH = str(Path(__file__).parent / "_apptest_scripts" / "rules_script.py")

DISABLED_RULE_ID = 4  # "SSH Authorized Keys Modification"
BRUTE_FORCE_RULE_ID = 1


@pytest.fixture()
def list_app(monkeypatch: pytest.MonkeyPatch, api_client_transport: httpx.Client) -> AppTest:
    """Run the Detection Rules list view against the seeded in-memory API."""
    monkeypatch.setattr(api_state, "get_client", lambda: api_client_transport)
    at = AppTest.from_file(SCRIPT_PATH)
    at.run(timeout=15)
    assert not at.exception
    return at


def _all_markdown(at: AppTest) -> str:
    return "".join(element.value for element in at.markdown)


def test_list_view_renders_all_seeded_rules(list_app: AppTest) -> None:
    """The rules list renders the full seeded set (5 rules)."""
    markup = _all_markdown(list_app)

    assert markup.count("soc-alert-name") == 5
    assert "SSH Brute Force Detection" in markup
    assert "Valid Account Login Following Failed Attempts" in markup
    assert "Sudo Privilege Escalation" in markup
    assert "SSH Authorized Keys Modification" in markup
    assert "Unusual Outbound Network Connection Volume" in markup

    # Exactly one rule (SSH Authorized Keys Modification) is seeded disabled.
    assert markup.count(">Disabled<") == 1
    assert markup.count(">Enabled<") == 4


def test_create_rule_valid_payload_succeeds_and_appears_in_list(
    list_app: AppTest, api_client_transport: httpx.Client
) -> None:
    """A valid Create Rule submission succeeds and the new rule appears in the list."""
    before = rules_api.list_rules(page_size=50, client=api_client_transport)
    assert before.total == 5

    list_app.text_input(key="new_rule_name").set_value("Anomalous DNS Query Volume")
    list_app.text_area(key="new_rule_description").set_value("Flags hosts issuing an unusual volume of DNS queries.")
    list_app.text_input(key="new_rule_source").set_value("custom")
    list_app.selectbox(key="new_rule_language").set_value("sigma")
    list_app.text_area(key="new_rule_query").set_value("event_category:network AND event_action:dns_query | count() by hostname > 500")
    list_app.selectbox(key="new_rule_severity").set_value("medium")
    list_app.number_input(key="new_rule_risk_score").set_value(45)
    list_app.selectbox(key="new_rule_mitre_tactic").set_value("Exfiltration")
    list_app.text_input(key="new_rule_mitre_technique_id").set_value("T1071")
    list_app.text_input(key="new_rule_mitre_technique_name").set_value("Application Layer Protocol")
    list_app.button(key="FormSubmitter:create_rule_form-Create Rule").click()
    list_app.run(timeout=15)

    assert not list_app.exception

    after = rules_api.list_rules(page_size=50, client=api_client_transport)
    assert after.total == 6
    created = next(r for r in after.items if r.name == "Anomalous DNS Query Volume")
    assert created.severity.value == "medium"
    assert created.risk_score == 45
    assert created.mitre_technique_id == "T1071"

    markup = _all_markdown(list_app)
    assert "Anomalous DNS Query Volume" in markup


def test_create_rule_invalid_mitre_technique_id_renders_error_not_crash(
    list_app: AppTest, api_client_transport: httpx.Client
) -> None:
    """An invalid MITRE technique id fails backend validation and shows an error, not a crash."""
    before = rules_api.list_rules(page_size=50, client=api_client_transport)
    assert before.total == 5

    list_app.text_input(key="new_rule_name").set_value("Broken Rule")
    list_app.selectbox(key="new_rule_language").set_value("sigma")
    list_app.text_area(key="new_rule_query").set_value("event_category:network")
    list_app.selectbox(key="new_rule_severity").set_value("low")
    list_app.text_input(key="new_rule_mitre_technique_id").set_value("not-a-valid-id")
    list_app.button(key="FormSubmitter:create_rule_form-Create Rule").click()
    list_app.run(timeout=15)

    assert not list_app.exception
    assert len(list_app.error) >= 1

    after = rules_api.list_rules(page_size=50, client=api_client_transport)
    assert after.total == 5
    assert not any(r.name == "Broken Rule" for r in after.items)


def test_enable_toggle_mutates_and_rerenders_new_state(list_app: AppTest) -> None:
    """Enabling the only disabled seeded rule persists and the rerendered page reflects it."""
    markup_before = _all_markdown(list_app)
    assert markup_before.count(">Disabled<") == 1

    list_app.button(key=f"toggle_rule_{DISABLED_RULE_ID}").click()
    list_app.run(timeout=15)

    assert not list_app.exception
    markup_after = _all_markdown(list_app)
    assert markup_after.count(">Disabled<") == 0
    assert markup_after.count(">Enabled<") == 5

    # The toggle button itself flips from "Enable" to "Disable" on rerender,
    # proving the list re-fetched the rule rather than just leaving stale state.
    refreshed_button = list_app.button(key=f"toggle_rule_{DISABLED_RULE_ID}")
    assert refreshed_button.label == "Disable"


def test_update_rule_edits_field_and_persists_on_rerender(
    list_app: AppTest, api_client_transport: httpx.Client
) -> None:
    """Editing a rule's description via its edit form persists it and it shows on rerender."""
    new_description = "Updated: flags 5+ failed SSH auth attempts from a single source in 3 minutes."

    list_app.text_area(key=f"edit_rule_description_{BRUTE_FORCE_RULE_ID}").set_value(new_description)
    list_app.button(key=f"FormSubmitter:edit_rule_form_{BRUTE_FORCE_RULE_ID}-Save Changes").click()
    list_app.run(timeout=15)

    assert not list_app.exception

    persisted = rules_api.get_rule(BRUTE_FORCE_RULE_ID, client=api_client_transport)
    assert persisted.description == new_description

    # The edit form's own field resets to the persisted value on rerender,
    # proving the list re-fetched the rule rather than just leaving stale state.
    refreshed_description = list_app.text_area(
        key=f"edit_rule_description_{BRUTE_FORCE_RULE_ID}"
    )
    assert refreshed_description.value == new_description
