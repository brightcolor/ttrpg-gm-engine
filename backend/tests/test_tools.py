from app.models import Campaign, Character, Ruleset
from app.tools import ToolContext, ToolRegistry


def test_tool_roll_is_audited(db):
    registry = ToolRegistry(db, ToolContext(llm_provider="test", model="test"))
    result = registry.run("roll_dice", {"expression": "1d6", "reason": "test"})
    assert result["result"]["total"] >= 1


def test_character_patch_logs_delta(db):
    ruleset = db.query(Ruleset).filter(Ruleset.slug == "dnd5e").one()
    campaign = Campaign(name="Patch", ruleset_id=ruleset.id)
    db.add(campaign)
    db.flush()
    character = Character(campaign_id=campaign.id, name="Ada", ruleset_data={"hp": {"current": 10, "max": 10}})
    db.add(character)
    db.commit()
    registry = ToolRegistry(db, ToolContext(campaign_id=campaign.id, llm_provider="test", model="test"))
    result = registry.run("update_character", {"character_id": character.id, "patch": {"hp": {"current": 6}}, "reason": "damage"})
    assert result["ruleset_data"]["hp"]["current"] == 6

