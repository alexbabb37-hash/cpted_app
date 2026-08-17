import pandas as pd

from locivra_privacy import MAX_UPLOAD_BYTES, clear_client_session, csv_safe_value, inspect_client_frame, safe_csv_frame, validate_upload_size


def test_upload_size_limit():
    assert validate_upload_size(MAX_UPLOAD_BYTES) == []
    assert validate_upload_size(MAX_UPLOAD_BYTES + 1)


def test_personal_information_patterns_are_blocked():
    frame = pd.DataFrame({"Location ID": ["A"], "Address": ["100 Queen St"], "Client Notes": ["Call alex@example.com"]})
    audit = inspect_client_frame(frame)
    assert any("email address" in issue for issue in audit["blocking_issues"])


def test_unexpected_and_person_named_columns_are_blocked():
    frame = pd.DataFrame({"Location ID": ["A"], "Employee Name": ["Person"]})
    audit = inspect_client_frame(frame)
    assert audit["blocking_issues"]


def test_formula_like_csv_text_is_escaped():
    assert csv_safe_value("=2+2") == "'=2+2"
    frame = safe_csv_frame(pd.DataFrame({"Client Notes": ["+SUM(A1:A2)", "Normal"]}))
    assert frame.iloc[0, 0].startswith("'")
    assert frame.iloc[1, 0] == "Normal"


def test_clear_client_session_removes_only_locivra_items():
    state = {"locivra_portfolio": 1, "pilot_review_frame": 2, "unrelated": 3}
    removed = clear_client_session(state)
    assert set(removed) == {"locivra_portfolio", "pilot_review_frame"}
    assert state == {"unrelated": 3}
