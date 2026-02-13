import pytest

from features.chat.utils import agent_router
from features.chat.utils.agent_router import format_group_message


# ---------------------------------------------------------------------------
# format_group_message unit tests
# ---------------------------------------------------------------------------


class TestFormatGroupMessage:
    """Unit tests for format_group_message() — delta-only context."""

    def _base_metadata(self, **overrides):
        meta = {
            "mode": "sequential",
            "agents": ["sherlock", "mycroft"],
            "your_position": 0,
            "accumulated_context": [],
        }
        meta.update(overrides)
        return meta

    def test_first_agent_no_accumulated_context(self):
        """First agent (position 0) with no accumulated context gets clean message."""
        result = format_group_message(
            agent_name="sherlock",
            user_message="What do you think?",
            group_metadata=self._base_metadata(your_position=0),
        )

        assert "[You are sherlock in a group chat" in result
        assert "Mode: sequential" in result
        assert "Other participants: mycroft" in result
        assert "Your speaking position: 0" in result
        assert "What do you think?" in result
        # No transcript for first agent
        assert "Other agents this round" not in result
        assert "Now it's your turn" not in result

    def test_second_agent_sees_first_agent_response(self):
        """Second agent sees first agent's response from accumulated_context."""
        accumulated = [
            {"role": "assistant", "agent": "sherlock", "content": "Elementary, dear Watson."},
        ]
        result = format_group_message(
            agent_name="mycroft",
            user_message="What do you think?",
            group_metadata=self._base_metadata(
                your_position=1,
                accumulated_context=accumulated,
            ),
        )

        assert "[You are mycroft in a group chat" in result
        assert "Your speaking position: 1" in result
        assert "Other agents this round:" in result
        assert "sherlock responded:\nElementary, dear Watson." in result
        assert "User said:\nWhat do you think?" in result
        assert "Now it's your turn to respond." in result

    def test_no_db_history_in_message(self):
        """DB history is NOT included — only accumulated_context matters."""
        # Even if accumulated_context is empty, no old messages appear
        result = format_group_message(
            agent_name="mycroft",
            user_message="New question",
            group_metadata=self._base_metadata(
                your_position=1,
                accumulated_context=[],
            ),
        )

        # No transcript section at all
        assert "Other agents this round" not in result
        assert "responded:" not in result
        # Just the user message
        assert "New question" in result

    def test_sequential_hint_included(self):
        """Sequential hint from group_metadata is included."""
        result = format_group_message(
            agent_name="mycroft",
            user_message="Hello",
            group_metadata=self._base_metadata(
                your_position=1,
                sequential_hint="You are agent 2 of 2. Previous agents: sherlock.",
            ),
        )

        assert "You are agent 2 of 2. Previous agents: sherlock." in result

    def test_first_agent_round2_no_accumulated(self):
        """First agent on round 2 with no accumulated context — clean message."""
        result = format_group_message(
            agent_name="sherlock",
            user_message="Any follow-up?",
            group_metadata=self._base_metadata(your_position=0),
        )

        # Position 0, no accumulated context → just user message
        assert "Any follow-up?" in result
        assert "Now it's your turn" not in result
        assert "Other agents this round" not in result

    def test_multiple_accumulated_responses(self):
        """Multiple agent responses from this round are included."""
        accumulated = [
            {"role": "assistant", "agent": "sherlock", "content": "Clue 1."},
            {"role": "assistant", "agent": "mycroft", "content": "Clue 2."},
        ]
        meta = self._base_metadata(
            agents=["sherlock", "mycroft", "ceo"],
            your_position=2,
            accumulated_context=accumulated,
        )
        result = format_group_message(
            agent_name="ceo",
            user_message="Summary please",
            group_metadata=meta,
        )

        assert "sherlock responded:\nClue 1." in result
        assert "mycroft responded:\nClue 2." in result
        assert "Now it's your turn to respond." in result

    def test_empty_accumulated_context_key_missing(self):
        """Missing accumulated_context key treated as empty list."""
        meta = self._base_metadata()
        del meta["accumulated_context"]
        result = format_group_message(
            agent_name="sherlock",
            user_message="Hello",
            group_metadata=meta,
        )

        assert "[You are sherlock in a group chat" in result
        assert "Hello" in result

    def test_multiple_agents_excluded_from_others(self):
        """Agent name is excluded from 'Other participants' list."""
        meta = self._base_metadata(agents=["sherlock", "mycroft", "ceo"])
        result = format_group_message(
            agent_name="mycroft",
            user_message="Hi",
            group_metadata=meta,
        )

        assert "Other participants: sherlock, ceo" in result

    def test_position_zero_with_accumulated_no_turn_prompt(self):
        """Position 0 agent with accumulated responses does NOT get turn prompt."""
        accumulated = [
            {"role": "assistant", "agent": "mycroft", "content": "Interesting analysis."},
        ]
        result = format_group_message(
            agent_name="sherlock",
            user_message="Thoughts?",
            group_metadata=self._base_metadata(
                your_position=0,
                accumulated_context=accumulated,
            ),
        )

        # Has the transcript
        assert "mycroft responded:" in result
        # But no turn prompt (position 0 goes first)
        assert "Now it's your turn" not in result
        # User message is plain, not prefixed with "User said:"
        assert result.endswith("Thoughts?")


# ---------------------------------------------------------------------------
# route_to_openclaw_agent integration tests
# ---------------------------------------------------------------------------


def _patch_openclaw(monkeypatch, sent_message, final_response="Response."):
    """Shared OpenClaw monkeypatching."""
    import features.proactive_agent.openclaw.config as oc_config
    import features.proactive_agent.openclaw.session as oc_session

    monkeypatch.setattr(oc_config, "is_openclaw_enabled", lambda: True)

    class FakeAdapter:
        async def send_message(self, **kwargs):
            sent_message.update(kwargs)
            await kwargs["on_stream_end"]("sid", "mid", final_response)
            return "run-1"

    class FakeSessionManager:
        async def get_adapter(self):
            return FakeAdapter()

    async def fake_get_session_manager():
        return FakeSessionManager()

    monkeypatch.setattr(oc_session, "get_openclaw_session_manager", fake_get_session_manager)


@pytest.mark.asyncio
async def test_openclaw_includes_accumulated_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """OpenClaw agent message includes this-round accumulated responses."""
    sent_message = {}
    _patch_openclaw(monkeypatch, sent_message, "Acknowledged.")

    accumulated = [
        {"role": "assistant", "agent": "mycroft", "content": "My analysis suggests..."},
    ]

    response = await agent_router.route_to_openclaw_agent(
        agent_name="sherlock",
        message="What are your thoughts?",
        context=[],
        session_id="chat-session-4",
        user_id=42,
        group_metadata={
            "mode": "sequential",
            "agents": ["sherlock", "mycroft"],
            "your_position": 0,
            "accumulated_context": accumulated,
        },
    )

    assert response == "Acknowledged."
    msg = sent_message["message"]
    assert "mycroft responded:" in msg
    assert "My analysis suggests..." in msg
    assert "What are your thoughts?" in msg


@pytest.mark.asyncio
async def test_openclaw_first_agent_no_accumulated(monkeypatch: pytest.MonkeyPatch) -> None:
    """First OpenClaw agent with no accumulated context gets clean user message."""
    sent_message = {}
    _patch_openclaw(monkeypatch, sent_message, "Elementary.")

    response = await agent_router.route_to_openclaw_agent(
        agent_name="sherlock",
        message="What do you think?",
        context=[],
        session_id="chat-session-5",
        user_id=42,
        group_metadata={
            "mode": "sequential",
            "agents": ["sherlock", "mycroft"],
            "your_position": 0,
            "accumulated_context": [],
        },
    )

    assert response == "Elementary."
    msg = sent_message["message"]
    assert "[You are sherlock in a group chat" in msg
    assert "What do you think?" in msg
    assert "responded:" not in msg
    assert "Now it's your turn" not in msg
