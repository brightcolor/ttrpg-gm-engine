from pydantic import BaseModel, Field


class CampaignCreate(BaseModel):
    name: str
    description: str = ""
    ruleset_slug: str = "dnd5e"
    mode: str = "solo"


class CharacterCreate(BaseModel):
    campaign_id: str
    name: str
    summary: str = ""
    public_data: dict = Field(default_factory=dict)
    private_data: dict = Field(default_factory=dict)
    ruleset_data: dict = Field(default_factory=dict)


class NPCCreate(BaseModel):
    campaign_id: str
    name: str
    role: str = ""
    location_id: str | None = None
    faction_id: str | None = None
    public_data: dict = Field(default_factory=dict)
    gm_data: dict = Field(default_factory=dict)
    summary: str = ""


class QuestCreate(BaseModel):
    campaign_id: str
    title: str
    description: str = ""
    stakes: str = ""
    visibility: str = "party"
    data: dict = Field(default_factory=dict)


class ChatRequest(BaseModel):
    campaign_id: str
    session_id: str | None = None
    sender_id: str | None = None
    message: str
    stream: bool = False


class ToolRunRequest(BaseModel):
    campaign_id: str | None = None
    session_id: str | None = None
    tool_name: str
    input: dict = Field(default_factory=dict)


class LoreImportRequest(BaseModel):
    campaign_id: str
    filename: str
    content: str
    visibility: str = "gm"


class RulesetCreate(BaseModel):
    slug: str
    name: str
    description: str = ""
    definition: dict
    prompt_addon: str = ""

