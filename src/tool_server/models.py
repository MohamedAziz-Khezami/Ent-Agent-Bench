# models.py — one hand-written Pydantic request model per CRM tool. These
# models (their fields, types, and this module's docstrings via the routes
# in server.py) are the source of truth for the tool catalog: read directly
# by the SDKs (as plain JSON bodies) and by fastapi-mcp (auto-generated MCP
# tool schemas). The TS executor's typed tool signatures
# (executors/ts_executor/tools.d.ts) are hand-maintained separately and
# must be kept in sync with these models by hand, not derived from them.
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

Stage = Literal["prospecting", "qualification", "proposal",
                 "negotiation", "closing", "won", "lost"]
LeadStatus = Literal["new", "qualified", "unqualified", "converted"]
LeadSource = Literal["webform", "referral", "event", "cold_call", "inbound_email"]
FollowupStatus = Literal["open", "done"]
ActivityType = Literal["call", "email", "meeting", "note"]


class FindContactsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid") #to prevent malformed extra arguments

    name: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    rep_id: Optional[int] = None


class GetByIdArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int


class FindLeadsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contact_id: Optional[int] = None
    rep_id: Optional[int] = None
    status: Optional[LeadStatus] = None
    min_score: Optional[int] = None


class FindDealsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lead_id: Optional[int] = None
    stage: Optional[Stage] = None
    rep_id: Optional[int] = None
    min_value: Optional[float] = None


class GetActivitiesArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deal_id: Optional[int] = None
    contact_id: Optional[int] = None


class GetFollowupsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deal_id: Optional[int] = None
    rep_id: Optional[int] = None
    status: Optional[FollowupStatus] = None


class CreateContactArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    email: str
    rep_id: int
    company: Optional[str] = None
    phone: Optional[str] = None


class UpdateContactArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    rep_id: Optional[int] = None


class CreateLeadArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contact_id: int
    source: LeadSource
    score: Optional[int] = None
    rep_id: Optional[int] = None


class UpdateLeadArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    status: Optional[LeadStatus] = None
    score: Optional[int] = None
    source: Optional[LeadSource] = None


class CreateDealArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lead_id: int
    name: str
    value: float
    stage: Optional[Stage] = None
    close_date: Optional[str] = None


class UpdateDealArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    stage: Optional[Stage] = None
    value: Optional[float] = None
    close_date: Optional[str] = None


class LogActivityArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: ActivityType
    subject: str
    deal_id: Optional[int] = None
    contact_id: Optional[int] = None


class ScheduleFollowupArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deal_id: int
    due_date: str
    note: Optional[str] = None


class UpdateFollowupArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    status: Optional[FollowupStatus] = None
    due_date: Optional[str] = None
    note: Optional[str] = None
