from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Item(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str = Field(min_length=2, max_length=100)
    category: str = Field(min_length=2, max_length=60)
    estimated_price: float = Field(ge=0)
    rationale: str = Field(default="", max_length=240)
    retailer: str = Field(default="Amazon", max_length=40)
    search_query: str = Field(default="", max_length=120)


class Recommendation(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str = Field(min_length=2, max_length=120)
    summary: str = Field(min_length=2, max_length=500)
    total_budget: float = Field(gt=0)
    total_estimated: float = Field(ge=0)
    currency: Literal["INR"] = "INR"
    items: list[Item] = Field(min_length=1, max_length=12)
    tips: list[str] = Field(default_factory=list, max_length=6)
    caveats: list[str] = Field(default_factory=list, max_length=6)
    source: Literal["AI estimate", "Demo estimate"] = "Demo estimate"

