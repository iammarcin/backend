"""Tests for group member update planning."""

import pytest

from features.chat.services.group_service import (
    GroupMemberInfo,
    _plan_group_member_update,
    MAX_GROUP_MEMBERS,
)


def test_add_members_success():
    current = [
        GroupMemberInfo(agent_name="sherlock", position=0),
        GroupMemberInfo(agent_name="bugsy", position=1),
    ]
    plan = _plan_group_member_update(
        current_members=current,
        leader_agent="sherlock",
        add_agents=["mycroft"],
        remove_agents=None,
        validate_agent=None,
    )

    assert plan.add_agents == ["mycroft"]
    assert plan.remove_agents == []
    assert len(plan.remaining_members) == 2
    assert plan.next_position == 2


def test_remove_members_success():
    current = [
        GroupMemberInfo(agent_name="sherlock", position=0),
        GroupMemberInfo(agent_name="bugsy", position=1),
        GroupMemberInfo(agent_name="mycroft", position=2),
    ]
    plan = _plan_group_member_update(
        current_members=current,
        leader_agent="sherlock",
        add_agents=None,
        remove_agents=["bugsy"],
        validate_agent=None,
    )

    assert plan.add_agents == []
    assert plan.remove_agents == ["bugsy"]
    assert [member.agent_name for member in plan.remaining_members] == ["sherlock", "mycroft"]
    assert plan.next_position == 3


def test_remove_leader_fails():
    current = [GroupMemberInfo(agent_name="sherlock", position=0)]
    with pytest.raises(ValueError, match="Leader agent cannot be removed"):
        _plan_group_member_update(
            current_members=current,
            leader_agent="sherlock",
            add_agents=None,
            remove_agents=["sherlock"],
            validate_agent=None,
        )


def test_add_beyond_max_fails():
    current = [
        GroupMemberInfo(agent_name=f"agent_{i}", position=i)
        for i in range(MAX_GROUP_MEMBERS)
    ]
    with pytest.raises(ValueError, match="Group cannot exceed"):
        _plan_group_member_update(
            current_members=current,
            leader_agent="agent_0",
            add_agents=["extra_agent"],
            remove_agents=None,
            validate_agent=None,
        )


def test_remove_below_min_fails():
    current = [GroupMemberInfo(agent_name="bugsy", position=0)]
    with pytest.raises(ValueError, match="Group must have at least"):
        _plan_group_member_update(
            current_members=current,
            leader_agent="sherlock",
            add_agents=None,
            remove_agents=["bugsy"],
            validate_agent=None,
        )


def test_add_and_remove_same_request_works():
    current = [
        GroupMemberInfo(agent_name="sherlock", position=0),
        GroupMemberInfo(agent_name="bugsy", position=1),
        GroupMemberInfo(agent_name="mycroft", position=2),
    ]
    plan = _plan_group_member_update(
        current_members=current,
        leader_agent="sherlock",
        add_agents=["ceo"],
        remove_agents=["bugsy"],
        validate_agent=None,
    )

    assert plan.add_agents == ["ceo"]
    assert plan.remove_agents == ["bugsy"]
    assert [member.agent_name for member in plan.remaining_members] == ["sherlock", "mycroft"]
    assert plan.next_position == 3
