import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session as DBSession
from app.core.config import get_settings
from app.db.session import get_db
from app.models import Campaign, Character, LLMRequest, Message, NPC, Quest, Ruleset, RulesetVersion, Session
from app.schemas.api import CampaignCreate, CharacterCreate, ChatRequest, LoreImportRequest, NPCCreate, QuestCreate, RulesetCreate, ToolRunRequest
from app.services.context_builder import build_context
from app.services.llm import provider_for, structured_gm_messages
from app.services.rulesets import ensure_builtin_rulesets
from app.tools import ToolContext, ToolRegistry


router = APIRouter()


def _ruleset_by_slug(db: DBSession, slug: str) -> Ruleset:
    ruleset = db.query(Ruleset).filter(Ruleset.slug == slug).one_or_none()
    if not ruleset:
        raise HTTPException(404, f"ruleset not found: {slug}")
    return ruleset


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "ttrpg-gm-engine"}


@router.post("/seed")
def seed(db: DBSession = Depends(get_db)) -> dict:
    ensure_builtin_rulesets(db)
    dnd = _ruleset_by_slug(db, "dnd5e")
    existing = db.query(Campaign).filter(Campaign.name == "Greifenfurt Demo").one_or_none()
    if existing:
        return {"campaign_id": existing.id, "status": "already_seeded"}
    campaign = Campaign(
        name="Greifenfurt Demo",
        description="Kleine Beispielkampagne mit Dorf, Schmied und alter Muehle.",
        ruleset_id=dnd.id,
        current_scene={"location": "Greifenfurt", "mode": "exploration", "summary": "Die Gruppe erreicht ein regennasses Dorf am Rand des Waldes."},
        world_state={"world_time": {"day": 1, "time": "Abend"}, "open_consequences": []},
        llm_settings={"provider": get_settings().default_llm_provider, "model": get_settings().default_model, "temperature": 0.7},
    )
    db.add(campaign)
    db.flush()
    session = Session(campaign_id=campaign.id, title="Ankunft in Greifenfurt")
    db.add(session)
    hero = Character(
        campaign_id=campaign.id,
        name="Elira",
        summary="Wendige Abenteurerin mit zweifelhaftem Ruf im Dorf.",
        public_data={"inventory": ["Reiserucksack", "Dolch"], "currency": {"gold": 7}},
        ruleset_data={"class": "Rogue", "level": 1, "attributes": {"strength": 8, "dexterity": 16, "constitution": 12, "intelligence": 13, "wisdom": 10, "charisma": 14}, "proficiencies": {"skills": ["stealth", "persuasion"]}, "hp": {"current": 9, "max": 9}, "ac": 14},
    )
    npc = NPC(
        campaign_id=campaign.id,
        name="Alrik",
        role="Dorfschmied",
        public_data={"personality": "direkt, pflichtbewusst", "known_to_players": "Hat nachts Licht bei der alten Muehle gesehen."},
        gm_data={"gm_secret": "Schmiedet heimlich Waffen fuer eine lokale Rebellengruppe."},
        disposition={"party": "vorsichtig freundlich", "Elira": "misstrauisch"},
        summary="Alrik kennt viele Dorfgeruechte und beobachtet Fremde genau.",
    )
    quest = Quest(campaign_id=campaign.id, title="Lichter in der alten Muehle", description="Nachts flackert Licht in der verlassenen Muehle.", stakes="Ein Kult bereitet dort ein Ritual vor.", visibility="party")
    db.add_all([hero, npc, quest])
    db.commit()
    return {"campaign_id": campaign.id, "session_id": session.id, "status": "seeded"}


@router.get("/rulesets")
def list_rulesets(db: DBSession = Depends(get_db)) -> list[dict]:
    ensure_builtin_rulesets(db)
    return [{"id": r.id, "slug": r.slug, "name": r.name, "description": r.description, "is_builtin": r.is_builtin} for r in db.query(Ruleset).order_by(Ruleset.name).all()]


@router.post("/rulesets")
def create_ruleset(payload: RulesetCreate, db: DBSession = Depends(get_db)) -> dict:
    ruleset = Ruleset(slug=payload.slug, name=payload.name, description=payload.description, is_builtin=False)
    db.add(ruleset)
    db.flush()
    version = RulesetVersion(ruleset_id=ruleset.id, version=payload.definition.get("version", "1.0.0"), definition=payload.definition, prompt_addon=payload.prompt_addon, change_note="Initial custom ruleset")
    db.add(version)
    db.flush()
    ruleset.active_version_id = version.id
    db.commit()
    return {"id": ruleset.id, "version_id": version.id}


@router.get("/campaigns")
def list_campaigns(db: DBSession = Depends(get_db)) -> list[dict]:
    return [{"id": c.id, "name": c.name, "description": c.description, "mode": c.mode, "ruleset_id": c.ruleset_id, "current_scene": c.current_scene} for c in db.query(Campaign).order_by(Campaign.created_at.desc()).all()]


@router.post("/campaigns")
def create_campaign(payload: CampaignCreate, db: DBSession = Depends(get_db)) -> dict:
    ensure_builtin_rulesets(db)
    ruleset = _ruleset_by_slug(db, payload.ruleset_slug)
    c = Campaign(name=payload.name, description=payload.description, ruleset_id=ruleset.id, mode=payload.mode, llm_settings={"provider": "mock", "model": "mock-gm"})
    db.add(c)
    db.flush()
    s = Session(campaign_id=c.id, title="Start")
    db.add(s)
    db.commit()
    return {"id": c.id, "session_id": s.id}


@router.get("/campaigns/{campaign_id}")
def get_campaign(campaign_id: str, db: DBSession = Depends(get_db)) -> dict:
    c = db.get(Campaign, campaign_id)
    if not c:
        raise HTTPException(404, "campaign not found")
    return {"id": c.id, "name": c.name, "description": c.description, "mode": c.mode, "current_scene": c.current_scene, "world_state": c.world_state, "house_rules": c.house_rules, "llm_settings": c.llm_settings}


@router.get("/campaigns/{campaign_id}/overview")
def campaign_overview(campaign_id: str, db: DBSession = Depends(get_db)) -> dict:
    return {
        "characters": [{"id": c.id, "name": c.name, "summary": c.summary, "public_data": c.public_data, "ruleset_data": c.ruleset_data} for c in db.query(Character).filter(Character.campaign_id == campaign_id).all()],
        "npcs": [{"id": n.id, "name": n.name, "role": n.role, "summary": n.summary, "public_data": n.public_data, "gm_data": n.gm_data} for n in db.query(NPC).filter(NPC.campaign_id == campaign_id).all()],
        "quests": [{"id": q.id, "title": q.title, "status": q.status, "description": q.description, "stakes": q.stakes} for q in db.query(Quest).filter(Quest.campaign_id == campaign_id).all()],
    }


@router.post("/characters")
def create_character(payload: CharacterCreate, db: DBSession = Depends(get_db)) -> dict:
    c = Character(**payload.model_dump())
    db.add(c)
    db.commit()
    return {"id": c.id}


@router.post("/npcs")
def create_npc(payload: NPCCreate, db: DBSession = Depends(get_db)) -> dict:
    n = NPC(**payload.model_dump())
    db.add(n)
    db.commit()
    return {"id": n.id}


@router.post("/quests")
def create_quest(payload: QuestCreate, db: DBSession = Depends(get_db)) -> dict:
    q = Quest(**payload.model_dump())
    db.add(q)
    db.commit()
    return {"id": q.id}


@router.post("/tools/run")
def run_tool(payload: ToolRunRequest, db: DBSession = Depends(get_db)) -> dict:
    registry = ToolRegistry(db, ToolContext(campaign_id=payload.campaign_id, session_id=payload.session_id, llm_provider="manual", model="api"))
    return registry.run(payload.tool_name, payload.input)


@router.get("/tools")
def list_tools(db: DBSession = Depends(get_db)) -> list[dict]:
    return ToolRegistry(db, ToolContext()).definitions()


@router.post("/lore/import")
def import_lore(payload: LoreImportRequest, db: DBSession = Depends(get_db)) -> dict:
    registry = ToolRegistry(db, ToolContext(campaign_id=payload.campaign_id, llm_provider="manual", model="importer"))
    return registry.import_lore_document(payload.campaign_id, payload.filename, payload.content, payload.visibility)


@router.post("/chat")
async def chat(payload: ChatRequest, db: DBSession = Depends(get_db)):
    campaign = db.get(Campaign, payload.campaign_id)
    if not campaign:
        raise HTTPException(404, "campaign not found")
    session_id = payload.session_id
    if not session_id:
        session = Session(campaign_id=campaign.id, title="Session")
        db.add(session)
        db.flush()
        session_id = session.id
    db.add(Message(campaign_id=campaign.id, session_id=session_id, sender_type="player", sender_id=payload.sender_id, visible_text=payload.message))
    db.commit()

    settings = campaign.llm_settings or {}
    provider_name = settings.get("provider", get_settings().default_llm_provider)
    model = settings.get("model", get_settings().default_model)
    context = build_context(db, campaign.id, session_id, payload.message, settings.get("token_budget", 6000))
    system_prompt = (Path(__file__).resolve().parent.parent / "prompts" / "gm_system_prompt.md").read_text(encoding="utf-8")
    messages = structured_gm_messages(system_prompt, context, payload.message)
    registry = ToolRegistry(db, ToolContext(campaign_id=campaign.id, session_id=session_id, llm_provider=provider_name, model=model))

    async def event_stream():
        try:
            result = await provider_for(provider_name).complete(messages, registry.definitions(), settings)
            db.add(LLMRequest(campaign_id=campaign.id, session_id=session_id, provider=provider_name, model=model, prompt_tokens=result.get("usage", {}).get("prompt_tokens", 0), completion_tokens=result.get("usage", {}).get("completion_tokens", 0)))
            msg = Message(campaign_id=campaign.id, session_id=session_id, sender_type="gm", visible_text=result["text"], internal={"tool_calls": result.get("tool_calls", []), "context": context})
            db.add(msg)
            db.commit()
            yield {"event": "message", "data": json.dumps({"session_id": session_id, "message_id": msg.id, "text": result["text"]}, ensure_ascii=False)}
        except Exception as exc:
            yield {"event": "error", "data": json.dumps({"error": str(exc)}, ensure_ascii=False)}

    if payload.stream:
        return EventSourceResponse(event_stream())
    result = await provider_for(provider_name).complete(messages, registry.definitions(), settings)
    db.add(LLMRequest(campaign_id=campaign.id, session_id=session_id, provider=provider_name, model=model, prompt_tokens=result.get("usage", {}).get("prompt_tokens", 0), completion_tokens=result.get("usage", {}).get("completion_tokens", 0)))
    msg = Message(campaign_id=campaign.id, session_id=session_id, sender_type="gm", visible_text=result["text"], internal={"tool_calls": result.get("tool_calls", []), "context": context})
    db.add(msg)
    db.commit()
    return {"session_id": session_id, "message_id": msg.id, "text": result["text"], "tool_calls": result.get("tool_calls", [])}
