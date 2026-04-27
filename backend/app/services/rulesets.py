from copy import deepcopy
from pathlib import Path
from sqlalchemy.orm import Session
from app.models import Character, Ruleset, RulesetVersion
from app.services.dice import roll_dice_expression


RULESET_DIR = Path(__file__).resolve().parent.parent / "rulesets"


def builtin_ruleset_payloads() -> list[dict]:
    import json

    payloads = []
    for slug in ("dnd5e", "dsa5", "custom"):
        base = RULESET_DIR / slug
        with (base / "definition.json").open("r", encoding="utf-8") as fh:
            definition = json.load(fh)
        prompt_addon = (base / "system_prompt_addon.md").read_text(encoding="utf-8")
        payloads.append({"slug": slug, "definition": definition, "prompt_addon": prompt_addon})
    return payloads


def ensure_builtin_rulesets(db: Session) -> None:
    for payload in builtin_ruleset_payloads():
        existing = db.query(Ruleset).filter(Ruleset.slug == payload["slug"]).one_or_none()
        if existing:
            continue
        definition = payload["definition"]
        ruleset = Ruleset(slug=payload["slug"], name=definition["name"], description=definition.get("description", ""), is_builtin=True)
        db.add(ruleset)
        db.flush()
        version = RulesetVersion(
            ruleset_id=ruleset.id,
            version=definition.get("version", "1.0.0"),
            definition=definition,
            prompt_addon=payload["prompt_addon"],
            change_note="Built-in seed",
        )
        db.add(version)
        db.flush()
        ruleset.active_version_id = version.id
    db.commit()


def active_definition(db: Session, ruleset_id: str) -> dict:
    ruleset = db.get(Ruleset, ruleset_id)
    if not ruleset or not ruleset.active_version_id:
        raise ValueError("ruleset not found")
    version = db.get(RulesetVersion, ruleset.active_version_id)
    if not version:
        raise ValueError("ruleset version not found")
    return deepcopy(version.definition)


def validate_character(db: Session, character: Character, ruleset_id: str) -> dict:
    definition = active_definition(db, ruleset_id)
    required = definition.get("character_schema", {}).get("required", [])
    missing = [field for field in required if field not in character.ruleset_data]
    return {"valid": not missing, "missing": missing, "ruleset": definition["slug"]}


def calculate_derived(character_data: dict, definition: dict) -> dict:
    slug = definition.get("slug")
    if slug == "dnd5e":
        attrs = character_data.get("attributes", {})
        dex = attrs.get("dexterity", 10)
        con = attrs.get("constitution", 10)
        level = int(character_data.get("level", 1))
        return {
            "proficiency_bonus": 2 + max(0, (level - 1) // 4),
            "initiative": (dex - 10) // 2,
            "constitution_modifier": (con - 10) // 2,
        }
    if slug == "dsa5":
        return {
            "life_energy": character_data.get("resources", {}).get("life_energy"),
            "fate_points": character_data.get("resources", {}).get("fate_points"),
        }
    return {"derived": character_data.get("derived", {})}


def perform_check(character_data: dict, definition: dict, check_type: str, parameters: dict) -> dict:
    slug = definition.get("slug")
    if slug == "dnd5e":
        ability = parameters.get("ability")
        skill = parameters.get("skill")
        dc = int(parameters.get("dc", 10))
        attrs = character_data.get("attributes", {})
        modifier = (int(attrs.get(ability, 10)) - 10) // 2 if ability else int(parameters.get("modifier", 0))
        proficient = skill in character_data.get("proficiencies", {}).get("skills", [])
        prof_bonus = calculate_derived(character_data, definition)["proficiency_bonus"] if proficient else 0
        advantage = parameters.get("advantage", "normal")
        rolls = [roll_dice_expression("1d20")["total"]]
        if advantage in ("advantage", "disadvantage"):
            rolls.append(roll_dice_expression("1d20")["total"])
        chosen = max(rolls) if advantage == "advantage" else min(rolls) if advantage == "disadvantage" else rolls[0]
        total = chosen + modifier + prof_bonus + int(parameters.get("bonus", 0))
        return {"ruleset": "dnd5e", "rolls": rolls, "chosen": chosen, "total": total, "dc": dc, "success": total >= dc}
    if slug == "dsa5":
        attributes = parameters.get("attributes", [])
        modifier = int(parameters.get("modifier", 0))
        talent = int(parameters.get("talent_value", 0))
        rolls = [roll_dice_expression("1d20")["total"] for _ in range(3)]
        data_attrs = character_data.get("attributes", {})
        remaining = talent - modifier
        failures = []
        for roll, attr in zip(rolls, attributes, strict=False):
            over = roll - int(data_attrs.get(attr, 8))
            if over > 0:
                remaining -= over
                failures.append({"attribute": attr, "over": over})
        success = remaining >= 0
        quality = max(0, 1 + remaining // 3) if success else 0
        return {"ruleset": "dsa5", "rolls": rolls, "remaining_points": remaining, "quality_level": quality, "success": success, "failures": failures}
    formula = definition.get("checks", {}).get(check_type, {}).get("formula", parameters.get("formula", "1d20"))
    result = roll_dice_expression(formula)
    dc = int(parameters.get("dc", 0))
    return {"ruleset": definition.get("slug", "custom"), "roll": result, "dc": dc, "success": result["total"] >= dc if dc else None}

