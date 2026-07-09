"""Chat-message state machine (§4.7): the fast lane, the held path, and terminal states."""
import pytest

from main.app.core.state.machine import chat_message_state_machine
from main.app.core.state.status import ChatMessageState
from main.appodus_utils.exception.exceptions import IllegalStateTransitionException

_S = ChatMessageState


@pytest.mark.parametrize(
    "current,target",
    [
        (_S.PENDING_SCAN.value, _S.DELIVERED.value),  # fast lane
        (_S.PENDING_SCAN.value, _S.HELD.value),       # flagged → held
        (_S.HELD.value, _S.DELIVERED.value),          # admin approves
        (_S.HELD.value, _S.BLOCKED.value),            # admin rejects
    ],
)
def test_allowed_transitions(current, target):
    chat_message_state_machine.assert_can_transition(current, target, resource="ChatMessage")


@pytest.mark.parametrize(
    "current,target",
    [
        (_S.DELIVERED.value, _S.BLOCKED.value),   # delivered is terminal
        (_S.BLOCKED.value, _S.DELIVERED.value),   # blocked is terminal
        (_S.PENDING_SCAN.value, _S.BLOCKED.value),  # cannot block without holding first
    ],
)
def test_illegal_transitions_rejected(current, target):
    with pytest.raises(IllegalStateTransitionException):
        chat_message_state_machine.assert_can_transition(current, target, resource="ChatMessage")


def test_delivered_and_blocked_are_terminal():
    assert chat_message_state_machine.is_terminal(_S.DELIVERED.value)
    assert chat_message_state_machine.is_terminal(_S.BLOCKED.value)
    assert not chat_message_state_machine.is_terminal(_S.HELD.value)
