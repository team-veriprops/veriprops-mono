"""The Nigerian states canon (§16.1, D33) — coverage validation, assignment matching and the
frontend map all read this one list, so it must be the 36 states plus the FCT, once each."""
from main.app.domain.config.nigeria_locations import STATE_CODES, is_valid_state, nigeria_locations


def test_lists_the_36_states_and_the_fct_once_each():
    states = nigeria_locations().states

    assert len(states) == 37
    assert len({s.code for s in states}) == 37
    assert {s.code for s in states} == STATE_CODES
    assert "fct" in STATE_CODES


def test_codes_are_lowercase_hyphenated_to_match_the_map_ids():
    for state in nigeria_locations().states:
        assert state.code == state.code.strip().lower()
        assert " " not in state.code


def test_a_state_is_matched_case_and_whitespace_insensitively():
    assert is_valid_state(" Lagos ")
    assert is_valid_state("AKWA-IBOM")


def test_anything_else_is_not_a_state():
    assert not is_valid_state("akwa ibom")
    assert not is_valid_state("london")
    assert not is_valid_state("")
    assert not is_valid_state(None)  # type: ignore[arg-type]
