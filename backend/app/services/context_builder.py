from sqlalchemy.orm import Session
from app.models import Campaign, Character, LoreChunk, Message, NPC, Quest
from app.services.visibility import strip_secret_fields


DEFAULT_BUDGET = {
    "system": 0.15,
    "ruleset": 0.15,
    "scene": 0.10,
    "characters": 0.15,
    "npcs": 0.10,
    "lore": 0.20,
    "chat": 0.15,
}


def rough_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def trim_text(text: str, max_tokens: int) -> str:
    max_chars = max_tokens * 4
    return text if len(text) <= max_chars else text[: max_chars - 20] + "\n[truncated]"


def build_context(db: Session, campaign_id: str, session_id: str | None, user_message: str, token_budget: int = 6000) -> dict:
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise ValueError("campaign not found")
    characters = db.query(Character).filter(Character.campaign_id == campaign_id).limit(8).all()
    npcs = db.query(NPC).filter(NPC.campaign_id == campaign_id).limit(6).all()
    quests = db.query(Quest).filter(Quest.campaign_id == campaign_id, Quest.status != "closed").limit(8).all()
    lore = (
        db.query(LoreChunk)
        .filter(LoreChunk.campaign_id == campaign_id)
        .order_by(LoreChunk.created_at.desc())
        .limit(6)
        .all()
    )
    messages = []
    if session_id:
        messages = (
            db.query(Message)
            .filter(Message.session_id == session_id)
            .order_by(Message.created_at.desc())
            .limit(20)
            .all()
        )
        messages.reverse()

    sections = {
        "scene": strip_secret_fields(campaign.current_scene),
        "characters": [
            {"id": c.id, "name": c.name, "summary": c.summary, "public_data": strip_secret_fields(c.public_data), "ruleset_data": strip_secret_fields(c.ruleset_data)}
            for c in characters
        ],
        "npcs_gm": [
            {"id": n.id, "name": n.name, "role": n.role, "summary": n.summary, "public_data": n.public_data, "gm_data": n.gm_data, "disposition": n.disposition}
            for n in npcs
        ],
        "active_quests": [{"id": q.id, "title": q.title, "status": q.status, "description": q.description, "stakes": q.stakes} for q in quests],
        "lore": [{"id": l.id, "content": l.content, "visibility": l.visibility, "entities": l.entities} for l in lore],
        "recent_messages": [{"sender": m.sender_type, "text": m.visible_text} for m in messages],
        "user_message": user_message,
    }
    trimmed = {}
    for key, value in sections.items():
        raw = str(value)
        max_tokens = int(token_budget * DEFAULT_BUDGET.get(key, 0.1))
        trimmed[key] = trim_text(raw, max_tokens)
    return {"campaign": {"id": campaign.id, "name": campaign.name, "mode": campaign.mode}, "budget": token_budget, "sections": trimmed}

