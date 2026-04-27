from app.models import Campaign, Character, Ruleset
from app.services.rulesets import active_definition, perform_check, validate_character


def test_dnd_character_validation_and_check(db):
    ruleset = db.query(Ruleset).filter(Ruleset.slug == "dnd5e").one()
    campaign = Campaign(name="Test", ruleset_id=ruleset.id)
    db.add(campaign)
    db.flush()
    character = Character(
        campaign_id=campaign.id,
        name="Ada",
        ruleset_data={"level": 1, "attributes": {"dexterity": 16}, "hp": {"current": 8, "max": 8}, "ac": 14, "proficiencies": {"skills": ["stealth"]}},
    )
    db.add(character)
    db.commit()

    validation = validate_character(db, character, ruleset.id)
    assert validation["valid"] is True
    result = perform_check(character.ruleset_data, active_definition(db, ruleset.id), "skill", {"ability": "dexterity", "skill": "stealth", "dc": 10})
    assert "success" in result
    assert result["total"] >= 5


def test_dsa_3d20_check(db):
    ruleset = db.query(Ruleset).filter(Ruleset.slug == "dsa5").one()
    definition = active_definition(db, ruleset.id)
    result = perform_check({"attributes": {"courage": 12, "sagacity": 12, "intuition": 12}}, definition, "talent", {"attributes": ["courage", "sagacity", "intuition"], "talent_value": 8})
    assert len(result["rolls"]) == 3
    assert "quality_level" in result

