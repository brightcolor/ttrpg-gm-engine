from collections.abc import Callable
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.models import (
    Campaign,
    Character,
    CharacterLog,
    Combat,
    Combatant,
    DiceRoll,
    LoreChunk,
    LoreDocument,
    NPC,
    NPCMemory,
    PendingChange,
    Quest,
    TimelineEvent,
    ToolCallLog,
)
from app.services.dice import roll_dice_expression
from app.services.importer import parse_import_payload
from app.services.rulesets import active_definition, calculate_derived, perform_check, validate_character


class ToolContext(BaseModel):
    campaign_id: str | None = None
    session_id: str | None = None
    llm_provider: str = "unknown"
    model: str = "unknown"


class ToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: dict


TOOL_SCHEMAS: list[ToolDefinition] = [
    ToolDefinition(name="roll_dice", description="Rolls a dice expression and stores an auditable result.", input_schema={"type": "object", "properties": {"expression": {"type": "string"}, "reason": {"type": "string"}, "visibility": {"type": "string", "enum": ["public", "gm", "hidden"]}}, "required": ["expression"]}),
    ToolDefinition(name="get_campaign_state", description="Returns compact campaign state.", input_schema={"type": "object", "properties": {"campaign_id": {"type": "string"}}, "required": ["campaign_id"]}),
    ToolDefinition(name="update_campaign_state", description="Patch campaign world state.", input_schema={"type": "object", "properties": {"campaign_id": {"type": "string"}, "patch": {"type": "object"}, "reason": {"type": "string"}}, "required": ["campaign_id", "patch"]}),
    ToolDefinition(name="create_timeline_event", description="Append immutable campaign event.", input_schema={"type": "object", "properties": {"campaign_id": {"type": "string"}, "title": {"type": "string"}, "description": {"type": "string"}, "involved_entities": {"type": "array"}, "timestamp_mode": {"type": "string"}}, "required": ["campaign_id", "title", "description"]}),
    ToolDefinition(name="get_character", description="Load a character.", input_schema={"type": "object", "properties": {"character_id": {"type": "string"}}, "required": ["character_id"]}),
    ToolDefinition(name="update_character", description="Patch character data and log the delta.", input_schema={"type": "object", "properties": {"character_id": {"type": "string"}, "patch": {"type": "object"}, "reason": {"type": "string"}}, "required": ["character_id", "patch"]}),
    ToolDefinition(name="update_character_inventory", description="Patch character inventory and currency.", input_schema={"type": "object", "properties": {"character_id": {"type": "string"}, "item_changes": {"type": "array"}, "gold_change": {"type": "number"}, "reason": {"type": "string"}}, "required": ["character_id"]}),
    ToolDefinition(name="search_npcs", description="Search NPCs by name, role or summary.", input_schema={"type": "object", "properties": {"query": {"type": "string"}, "location_id": {"type": "string"}, "faction_id": {"type": "string"}}}),
    ToolDefinition(name="create_npc", description="Create an NPC with public and GM data.", input_schema={"type": "object", "properties": {"data": {"type": "object"}}, "required": ["data"]}),
    ToolDefinition(name="add_npc_memory", description="Store an NPC memory.", input_schema={"type": "object", "properties": {"npc_id": {"type": "string"}, "memory": {"type": "string"}, "importance": {"type": "integer"}, "visibility": {"type": "string"}}, "required": ["npc_id", "memory"]}),
    ToolDefinition(name="search_lore", description="Search lore chunks with visibility-aware filters.", input_schema={"type": "object", "properties": {"query": {"type": "string"}, "campaign_id": {"type": "string"}, "filters": {"type": "object"}}, "required": ["query", "campaign_id"]}),
    ToolDefinition(name="create_quest", description="Create a quest or plot thread.", input_schema={"type": "object", "properties": {"data": {"type": "object"}}, "required": ["data"]}),
    ToolDefinition(name="update_quest", description="Patch a quest.", input_schema={"type": "object", "properties": {"quest_id": {"type": "string"}, "patch": {"type": "object"}, "reason": {"type": "string"}}, "required": ["quest_id", "patch"]}),
    ToolDefinition(name="start_combat", description="Start structured combat.", input_schema={"type": "object", "properties": {"campaign_id": {"type": "string"}, "participants": {"type": "array"}, "environment": {"type": "object"}}, "required": ["campaign_id", "participants"]}),
    ToolDefinition(name="advance_combat_turn", description="Advance combat turn order.", input_schema={"type": "object", "properties": {"combat_id": {"type": "string"}}, "required": ["combat_id"]}),
    ToolDefinition(name="get_combat_state", description="Return combat and combatants.", input_schema={"type": "object", "properties": {"combat_id": {"type": "string"}}, "required": ["combat_id"]}),
    ToolDefinition(name="create_pending_change_for_review", description="Queue potentially risky world changes for human review.", input_schema={"type": "object", "properties": {"change": {"type": "object"}}, "required": ["change"]}),
    ToolDefinition(name="get_ruleset", description="Return active campaign ruleset.", input_schema={"type": "object", "properties": {"campaign_id": {"type": "string"}}, "required": ["campaign_id"]}),
    ToolDefinition(name="perform_ruleset_check", description="Perform a ruleset-specific check.", input_schema={"type": "object", "properties": {"character_id": {"type": "string"}, "check_type": {"type": "string"}, "parameters": {"type": "object"}, "reason": {"type": "string"}}, "required": ["character_id", "check_type", "parameters"]}),
    ToolDefinition(name="calculate_derived_values", description="Calculate derived values using active ruleset.", input_schema={"type": "object", "properties": {"character_id": {"type": "string"}, "ruleset_id": {"type": "string"}}, "required": ["character_id", "ruleset_id"]}),
    ToolDefinition(name="validate_character_against_ruleset", description="Validate dynamic character sheet.", input_schema={"type": "object", "properties": {"character_id": {"type": "string"}, "ruleset_id": {"type": "string"}}, "required": ["character_id", "ruleset_id"]}),
]


def _patch_dict(target: dict, patch: dict) -> dict:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _patch_dict(target[key], value)
        else:
            target[key] = value
    return target


class ToolRegistry:
    def __init__(self, db: Session, context: ToolContext):
        self.db = db
        self.context = context

    def definitions(self) -> list[dict]:
        return [{"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.input_schema}} for t in TOOL_SCHEMAS]

    def run(self, name: str, payload: dict) -> dict:
        handler: Callable[[dict], dict] | None = getattr(self, f"tool_{name}", None)
        if not handler:
            raise ValueError(f"unknown tool: {name}")
        log = ToolCallLog(
            campaign_id=payload.get("campaign_id") or self.context.campaign_id,
            session_id=self.context.session_id,
            llm_provider=self.context.llm_provider,
            model=self.context.model,
            tool_name=name,
            input=payload,
            status="success",
        )
        self.db.add(log)
        try:
            output = handler(payload)
            log.output = output
            log.affected_entities = output.get("affected_entities", [])
            self.db.commit()
            return output
        except Exception as exc:
            self.db.rollback()
            log.status = "error"
            log.error = str(exc)
            self.db.add(log)
            self.db.commit()
            raise

    def tool_roll_dice(self, p: dict) -> dict:
        result = roll_dice_expression(p["expression"])
        roll = DiceRoll(campaign_id=self.context.campaign_id, session_id=self.context.session_id, expression=p["expression"], reason=p.get("reason", ""), visibility=p.get("visibility", "public"), result=result)
        self.db.add(roll)
        self.db.flush()
        return {"dice_roll_id": roll.id, "result": result, "affected_entities": [roll.id]}

    def tool_get_campaign_state(self, p: dict) -> dict:
        c = self.db.get(Campaign, p["campaign_id"])
        return {"id": c.id, "name": c.name, "mode": c.mode, "current_scene": c.current_scene, "world_state": c.world_state}

    def tool_update_campaign_state(self, p: dict) -> dict:
        c = self.db.get(Campaign, p["campaign_id"])
        c.world_state = _patch_dict(c.world_state or {}, p["patch"])
        self.db.add(TimelineEvent(campaign_id=c.id, session_id=self.context.session_id, title="Campaign state updated", description=p.get("reason", ""), event_type="state_change", involved_entities=[c.id]))
        return {"campaign_id": c.id, "world_state": c.world_state, "affected_entities": [c.id]}

    def tool_create_timeline_event(self, p: dict) -> dict:
        event = TimelineEvent(campaign_id=p["campaign_id"], session_id=self.context.session_id, title=p["title"], description=p["description"], involved_entities=p.get("involved_entities", []), world_time={"mode": p.get("timestamp_mode", "now")})
        self.db.add(event)
        self.db.flush()
        return {"event_id": event.id, "affected_entities": [event.id]}

    def tool_get_character(self, p: dict) -> dict:
        c = self.db.get(Character, p["character_id"])
        return {"id": c.id, "name": c.name, "summary": c.summary, "public_data": c.public_data, "ruleset_data": c.ruleset_data, "knowledge": c.knowledge}

    def tool_update_character(self, p: dict) -> dict:
        c = self.db.get(Character, p["character_id"])
        c.ruleset_data = _patch_dict(c.ruleset_data or {}, p["patch"].get("ruleset_data", p["patch"]))
        self.db.add(CharacterLog(character_id=c.id, event_type="patch", description=p.get("reason", ""), diff=p["patch"]))
        return {"character_id": c.id, "ruleset_data": c.ruleset_data, "affected_entities": [c.id]}

    def tool_update_character_inventory(self, p: dict) -> dict:
        c = self.db.get(Character, p["character_id"])
        inv = c.public_data.setdefault("inventory", [])
        inv.extend(p.get("item_changes", []))
        c.public_data.setdefault("currency", {})["gold"] = c.public_data.get("currency", {}).get("gold", 0) + p.get("gold_change", 0)
        self.db.add(CharacterLog(character_id=c.id, event_type="inventory", description=p.get("reason", ""), diff=p))
        return {"character_id": c.id, "inventory": c.public_data["inventory"], "affected_entities": [c.id]}

    def tool_search_npcs(self, p: dict) -> dict:
        query = (p.get("query") or "").lower()
        q = self.db.query(NPC)
        if self.context.campaign_id:
            q = q.filter(NPC.campaign_id == self.context.campaign_id)
        if p.get("location_id"):
            q = q.filter(NPC.location_id == p["location_id"])
        if p.get("faction_id"):
            q = q.filter(NPC.faction_id == p["faction_id"])
        npcs = [n for n in q.limit(50).all() if query in (n.name + n.role + n.summary).lower()]
        return {"results": [{"id": n.id, "name": n.name, "role": n.role, "summary": n.summary, "public_data": n.public_data, "gm_data": n.gm_data} for n in npcs[:10]]}

    def tool_create_npc(self, p: dict) -> dict:
        data = p["data"]
        npc = NPC(campaign_id=data.get("campaign_id") or self.context.campaign_id, name=data["name"], role=data.get("role", ""), location_id=data.get("location_id"), faction_id=data.get("faction_id"), public_data=data.get("public_data", {}), gm_data=data.get("gm_data", {}), disposition=data.get("disposition", {}), summary=data.get("summary", ""))
        self.db.add(npc)
        self.db.flush()
        return {"npc_id": npc.id, "affected_entities": [npc.id]}

    def tool_add_npc_memory(self, p: dict) -> dict:
        npc = self.db.get(NPC, p["npc_id"])
        mem = NPCMemory(npc_id=npc.id, campaign_id=npc.campaign_id, memory=p["memory"], importance=p.get("importance", 3), visibility=p.get("visibility", "gm"))
        self.db.add(mem)
        self.db.flush()
        return {"memory_id": mem.id, "affected_entities": [npc.id, mem.id]}

    def tool_search_lore(self, p: dict) -> dict:
        query = p["query"].lower()
        chunks = self.db.query(LoreChunk).filter(LoreChunk.campaign_id == p["campaign_id"]).limit(100).all()
        scored = []
        for chunk in chunks:
            score = sum(1 for token in query.split() if token in chunk.content.lower())
            if score:
                scored.append((score, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        return {"results": [{"id": c.id, "score": s, "content": c.content, "visibility": c.visibility} for s, c in scored[:8]]}

    def tool_create_quest(self, p: dict) -> dict:
        data = p["data"]
        quest = Quest(campaign_id=data.get("campaign_id") or self.context.campaign_id, title=data["title"], description=data.get("description", ""), stakes=data.get("stakes", ""), visibility=data.get("visibility", "party"), data=data.get("data", {}))
        self.db.add(quest)
        self.db.flush()
        return {"quest_id": quest.id, "affected_entities": [quest.id]}

    def tool_update_quest(self, p: dict) -> dict:
        quest = self.db.get(Quest, p["quest_id"])
        _patch_dict(quest.data, p["patch"].get("data", {}))
        for field in ("title", "status", "description", "stakes", "visibility"):
            if field in p["patch"]:
                setattr(quest, field, p["patch"][field])
        return {"quest_id": quest.id, "status": quest.status, "affected_entities": [quest.id]}

    def tool_start_combat(self, p: dict) -> dict:
        combat = Combat(campaign_id=p["campaign_id"], session_id=self.context.session_id, environment=p.get("environment", {}))
        self.db.add(combat)
        self.db.flush()
        for participant in p["participants"]:
            self.db.add(Combatant(combat_id=combat.id, entity_type=participant.get("entity_type", "npc"), entity_id=participant.get("entity_id"), name=participant["name"], hp_current=participant.get("hp_current", 1), hp_max=participant.get("hp_max", 1), initiative=participant.get("initiative", 0), data=participant))
        return {"combat_id": combat.id, "affected_entities": [combat.id]}

    def tool_advance_combat_turn(self, p: dict) -> dict:
        combat = self.db.get(Combat, p["combat_id"])
        count = self.db.query(Combatant).filter(Combatant.combat_id == combat.id).count()
        if count:
            combat.turn_index = (combat.turn_index + 1) % count
            if combat.turn_index == 0:
                combat.round += 1
        return {"combat_id": combat.id, "round": combat.round, "turn_index": combat.turn_index, "affected_entities": [combat.id]}

    def tool_get_combat_state(self, p: dict) -> dict:
        combat = self.db.get(Combat, p["combat_id"])
        combatants = self.db.query(Combatant).filter(Combatant.combat_id == combat.id).order_by(Combatant.initiative.desc()).all()
        return {"combat": {"id": combat.id, "round": combat.round, "turn_index": combat.turn_index, "status": combat.status}, "combatants": [{"id": c.id, "name": c.name, "initiative": c.initiative, "hp_current": c.hp_current, "conditions": c.conditions} for c in combatants]}

    def tool_create_pending_change_for_review(self, p: dict) -> dict:
        change = PendingChange(campaign_id=self.context.campaign_id or p["change"].get("campaign_id"), change=p["change"])
        self.db.add(change)
        self.db.flush()
        return {"pending_change_id": change.id, "affected_entities": [change.id]}

    def tool_get_ruleset(self, p: dict) -> dict:
        campaign = self.db.get(Campaign, p["campaign_id"])
        return {"ruleset_id": campaign.ruleset_id, "definition": active_definition(self.db, campaign.ruleset_id)}

    def tool_perform_ruleset_check(self, p: dict) -> dict:
        character = self.db.get(Character, p["character_id"])
        campaign = self.db.get(Campaign, character.campaign_id)
        definition = active_definition(self.db, campaign.ruleset_id)
        result = perform_check(character.ruleset_data, definition, p["check_type"], p.get("parameters", {}))
        self.db.add(CharacterLog(character_id=character.id, event_type="ruleset_check", description=p.get("reason", ""), diff=result))
        return {"character_id": character.id, "result": result, "affected_entities": [character.id]}

    def tool_calculate_derived_values(self, p: dict) -> dict:
        character = self.db.get(Character, p["character_id"])
        definition = active_definition(self.db, p["ruleset_id"])
        return {"character_id": character.id, "derived": calculate_derived(character.ruleset_data, definition)}

    def tool_validate_character_against_ruleset(self, p: dict) -> dict:
        character = self.db.get(Character, p["character_id"])
        return validate_character(self.db, character, p["ruleset_id"])

    def import_lore_document(self, campaign_id: str, filename: str, content: str, visibility: str = "gm") -> dict:
        parsed = parse_import_payload(filename, content)
        doc = LoreDocument(campaign_id=campaign_id, title=filename, source_type=filename.rsplit(".", 1)[-1], content=content, visibility=visibility, metadata_json={"injection_warnings": parsed["injection_warnings"]})
        self.db.add(doc)
        self.db.flush()
        for index, chunk in enumerate(parsed["chunks"]):
            self.db.add(LoreChunk(campaign_id=campaign_id, document_id=doc.id, chunk_index=index, content=chunk, visibility=visibility, entities=[]))
        self.db.commit()
        return {"document_id": doc.id, "chunks": len(parsed["chunks"]), "injection_warnings": parsed["injection_warnings"]}

