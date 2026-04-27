from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON
from app.db.base import Base
from app.models.base_mixins import TimestampMixin, UUIDMixin


def json_col(default_factory=dict):
    return mapped_column(MutableDict.as_mutable(JSON().with_variant(JSONB, "postgresql")), default=default_factory)


def json_list_col(default_factory=list):
    return mapped_column(MutableList.as_mutable(JSON().with_variant(JSONB, "postgresql")), default=default_factory)


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(40), default="admin")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Ruleset(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "rulesets"
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    active_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class RulesetVersion(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "ruleset_versions"
    ruleset_id: Mapped[str] = mapped_column(ForeignKey("rulesets.id"), index=True)
    version: Mapped[str] = mapped_column(String(40))
    definition: Mapped[dict] = json_col()
    prompt_addon: Mapped[str] = mapped_column(Text, default="")
    change_note: Mapped[str] = mapped_column(Text, default="")


class Campaign(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "campaigns"
    name: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    ruleset_id: Mapped[str | None] = mapped_column(ForeignKey("rulesets.id"), nullable=True)
    mode: Mapped[str] = mapped_column(String(40), default="solo")
    current_scene: Mapped[dict] = json_col()
    world_state: Mapped[dict] = json_col()
    house_rules: Mapped[dict] = json_col()
    llm_settings: Mapped[dict] = json_col()


class CampaignMember(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "campaign_members"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(40), default="player")
    __table_args__ = (UniqueConstraint("campaign_id", "user_id"),)


class Character(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "characters"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    public_data: Mapped[dict] = json_col()
    private_data: Mapped[dict] = json_col()
    ruleset_data: Mapped[dict] = json_col()
    knowledge: Mapped[dict] = json_col()


class CharacterLog(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "character_logs"
    character_id: Mapped[str] = mapped_column(ForeignKey("characters.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text)
    diff: Mapped[dict] = json_col()


class NPC(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "npcs"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    location_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    faction_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    role: Mapped[str] = mapped_column(String(160), default="")
    public_data: Mapped[dict] = json_col()
    gm_data: Mapped[dict] = json_col()
    disposition: Mapped[dict] = json_col()
    summary: Mapped[str] = mapped_column(Text, default="")


class NPCMemory(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "npc_memories"
    npc_id: Mapped[str] = mapped_column(ForeignKey("npcs.id"), index=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    memory: Mapped[str] = mapped_column(Text)
    importance: Mapped[int] = mapped_column(Integer, default=3)
    visibility: Mapped[str] = mapped_column(String(40), default="gm")
    embedding: Mapped[list] = json_list_col()


class Location(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "locations"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    parent_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    type: Mapped[str] = mapped_column(String(80), default="place")
    public_data: Mapped[dict] = json_col()
    gm_data: Mapped[dict] = json_col()
    summary: Mapped[str] = mapped_column(Text, default="")


class Faction(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "factions"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    goals: Mapped[dict] = json_col()
    resources: Mapped[dict] = json_col()
    relationships: Mapped[dict] = json_col()
    secrets: Mapped[dict] = json_col()


class Quest(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "quests"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    title: Mapped[str] = mapped_column(String(220), index=True)
    status: Mapped[str] = mapped_column(String(40), default="open")
    description: Mapped[str] = mapped_column(Text, default="")
    stakes: Mapped[str] = mapped_column(Text, default="")
    visibility: Mapped[str] = mapped_column(String(40), default="party")
    data: Mapped[dict] = json_col()


class QuestStep(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "quest_steps"
    quest_id: Mapped[str] = mapped_column(ForeignKey("quests.id"), index=True)
    title: Mapped[str] = mapped_column(String(220))
    status: Mapped[str] = mapped_column(String(40), default="open")
    data: Mapped[dict] = json_col()


class Clue(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "clues"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    quest_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    text: Mapped[str] = mapped_column(Text)
    visibility: Mapped[str] = mapped_column(String(40), default="gm")
    discovered_by: Mapped[list] = json_list_col()


class Item(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "items"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    type: Mapped[str] = mapped_column(String(80), default="item")
    data: Mapped[dict] = json_col()


class Inventory(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "inventories"
    owner_type: Mapped[str] = mapped_column(String(40), index=True)
    owner_id: Mapped[str] = mapped_column(String(36), index=True)
    items: Mapped[list] = json_list_col()
    currency: Mapped[dict] = json_col()


class Session(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "sessions"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    title: Mapped[str] = mapped_column(String(220), default="Session")
    status: Mapped[str] = mapped_column(String(40), default="active")
    summary: Mapped[str] = mapped_column(Text, default="")
    open_threads: Mapped[list] = json_list_col()


class Message(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "messages"
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    sender_type: Mapped[str] = mapped_column(String(40))
    sender_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    visible_text: Mapped[str] = mapped_column(Text)
    internal: Mapped[dict] = json_col()
    visibility: Mapped[str] = mapped_column(String(40), default="party")


class TimelineEvent(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "timeline_events"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(220))
    description: Mapped[str] = mapped_column(Text)
    event_type: Mapped[str] = mapped_column(String(80), default="story")
    involved_entities: Mapped[list] = json_list_col()
    world_time: Mapped[dict] = json_col()
    immutable: Mapped[bool] = mapped_column(Boolean, default=True)


class DiceRoll(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "dice_rolls"
    campaign_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    expression: Mapped[str] = mapped_column(String(80))
    reason: Mapped[str] = mapped_column(Text, default="")
    visibility: Mapped[str] = mapped_column(String(40), default="public")
    result: Mapped[dict] = json_col()


class Combat(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "combats"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(40), default="active")
    round: Mapped[int] = mapped_column(Integer, default=1)
    turn_index: Mapped[int] = mapped_column(Integer, default=0)
    environment: Mapped[dict] = json_col()
    log: Mapped[list] = json_list_col()


class Combatant(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "combatants"
    combat_id: Mapped[str] = mapped_column(ForeignKey("combats.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    name: Mapped[str] = mapped_column(String(160))
    initiative: Mapped[int] = mapped_column(Integer, default=0)
    hp_current: Mapped[int] = mapped_column(Integer, default=1)
    hp_max: Mapped[int] = mapped_column(Integer, default=1)
    conditions: Mapped[list] = json_list_col()
    data: Mapped[dict] = json_col()


class LoreDocument(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "lore_documents"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    title: Mapped[str] = mapped_column(String(220))
    source_type: Mapped[str] = mapped_column(String(40), default="markdown")
    content: Mapped[str] = mapped_column(Text)
    visibility: Mapped[str] = mapped_column(String(40), default="gm")
    metadata_json: Mapped[dict] = json_col()


class LoreChunk(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "lore_chunks"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("lore_documents.id"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    visibility: Mapped[str] = mapped_column(String(40), default="gm")
    entities: Mapped[list] = json_list_col()
    embedding: Mapped[list] = json_list_col()


class WorldFact(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "world_facts"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    subject: Mapped[str] = mapped_column(String(220), index=True)
    predicate: Mapped[str] = mapped_column(String(120))
    object: Mapped[str] = mapped_column(Text)
    visibility: Mapped[str] = mapped_column(String(40), default="gm")
    confidence: Mapped[int] = mapped_column(Integer, default=100)


class Relationship(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "relationships"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(40))
    source_id: Mapped[str] = mapped_column(String(36), index=True)
    target_type: Mapped[str] = mapped_column(String(40))
    target_id: Mapped[str] = mapped_column(String(36), index=True)
    data: Mapped[dict] = json_col()


class ToolCallLog(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "tool_call_logs"
    campaign_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    llm_provider: Mapped[str] = mapped_column(String(80), default="unknown")
    model: Mapped[str] = mapped_column(String(120), default="unknown")
    tool_name: Mapped[str] = mapped_column(String(120), index=True)
    input: Mapped[dict] = json_col()
    output: Mapped[dict] = json_col()
    status: Mapped[str] = mapped_column(String(40), default="success")
    error: Mapped[str] = mapped_column(Text, default="")
    affected_entities: Mapped[list] = json_list_col()


class LLMRequest(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "llm_requests"
    campaign_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(120))
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_estimate: Mapped[str] = mapped_column(String(80), default="0")
    status: Mapped[str] = mapped_column(String(40), default="success")
    error: Mapped[str] = mapped_column(Text, default="")


class PendingChange(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "pending_changes"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    proposed_by: Mapped[str] = mapped_column(String(80), default="llm")
    change: Mapped[dict] = json_col()
    status: Mapped[str] = mapped_column(String(40), default="pending")


class Secret(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "secrets"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    text: Mapped[str] = mapped_column(Text)
    discovered_by: Mapped[list] = json_list_col()


class VisibilityScope(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "visibility_scopes"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    scope_type: Mapped[str] = mapped_column(String(40))
    members: Mapped[list] = json_list_col()


class Setting(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "settings"
    scope: Mapped[str] = mapped_column(String(80), index=True)
    key: Mapped[str] = mapped_column(String(160), index=True)
    value: Mapped[dict] = json_col()


class RulesetChangeLog(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "ruleset_change_log"
    campaign_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    ruleset_id: Mapped[str] = mapped_column(ForeignKey("rulesets.id"), index=True)
    change: Mapped[dict] = json_col()
    reason: Mapped[str] = mapped_column(Text, default="")

