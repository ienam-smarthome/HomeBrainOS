from pydantic import BaseModel, Field
from typing import Any


class Device(BaseModel):
    id: str
    name: str
    label: str
    category: str = 'device'
    attributes: dict[str, Any] = Field(default_factory=dict)
    switch: str | None = None
    temperature: float | str | None = None
    humidity: float | str | None = None
    power: float | str | None = None
    energy: float | str | None = None
    battery: float | str | None = None
