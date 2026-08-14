from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AdminLogin(BaseModel):
    token: str


class OpenCodeAccountCreate(BaseModel):
    name: str
    workspace_id: str = "Default"
    auth_cookie: str
    show_rolling: bool = True
    show_weekly: bool = True
    show_monthly: bool = True
    enabled: bool = True


class OpenCodeAccountUpdate(BaseModel):
    name: str | None = None
    workspace_id: str | None = None
    auth_cookie: str | None = None
    show_rolling: bool | None = None
    show_weekly: bool | None = None
    show_monthly: bool | None = None
    enabled: bool | None = None


class OllamaAccountCreate(BaseModel):
    name: str
    session_cookie: str
    show_session: bool = True
    show_weekly: bool = True
    enabled: bool = True


class OllamaAccountUpdate(BaseModel):
    name: str | None = None
    session_cookie: str | None = None
    show_session: bool | None = None
    show_weekly: bool | None = None
    enabled: bool | None = None


class CPAChannelCreate(BaseModel):
    name: str
    url: str
    management_key: str
    enabled: bool = True
    interval_sec: int = Field(default=1800, ge=300)


class CPAChannelUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    management_key: str | None = None
    enabled: bool | None = None
    interval_sec: int | None = Field(default=None, ge=300)


class RefreshSettingsResponse(BaseModel):
    auto_refresh: bool
    interval_sec: int


class UsageSyncSettingsResponse(BaseModel):
    auto_sync: bool
    interval_sec: int
    backfill_pages_per_request: int
    max_pages_per_incremental: int


class RefreshSettingsUpdate(BaseModel):
    auto_refresh: bool | None = None
    interval_sec: int | None = Field(default=None, ge=15)


class QuotaSyncSettingsUpdate(BaseModel):
    auto_sync: bool | None = None
    interval_sec: int | None = Field(default=None, ge=300)


class UsageSyncSettingsUpdate(BaseModel):
    auto_sync: bool | None = None
    interval_sec: int | None = Field(default=None, ge=15)
    backfill_pages_per_request: int | None = Field(default=None, ge=1, le=50)
    max_pages_per_incremental: int | None = Field(default=None, ge=1, le=100)


class OpenCodeSettingsUpdate(BaseModel):
    usage_server_id: str | None = None


class ServiceConfigUpdate(BaseModel):
    refresh: dict[str, RefreshSettingsUpdate] | None = None
    quota_sync: dict[str, QuotaSyncSettingsUpdate] | None = None
    usage_sync: UsageSyncSettingsUpdate | None = None
    opencode: OpenCodeSettingsUpdate | None = None
