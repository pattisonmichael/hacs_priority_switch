"""Dataclasses for PrioritySwitch."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Dict  # noqa: UP035


class ControlType(StrEnum):
    """Types of Controls."""

    TRUE = "True"
    FALSE = "False"
    ENTITY = "Entity"
    TEMPLATE = "Template"
    MANUAL = "Manual"


class InputType(StrEnum):
    """Types of Inputs."""

    FIXED = "Fixed"
    SUN = "Sun"
    ENTITY = "Entity"
    TEMPLATE = "Template"
    MANUAL = "Manual"


@dataclass
class InputData:
    """Dataclass for Input definition."""

    name: str
    priority: int
    control_type: ControlType
    value_type: InputType
    control_template: str | None = None
    control_entity: str | None = None
    auto_on: str | None = None
    auto_off: str | None = None
    value: str | None = None
    value_entity: str | None = None
    value_template: str | None = None
    azimut: int | None = None
    elevation: int | None = None
    building_deviation: int | None = 0
    offset_entry: int | None = 0
    offset_exit: int | None = 0
    update_interval: int | None = 10
    sun_entity: str | None = None
    set_if_in_shadow: bool | None = False
    shadow: int | None = None
    elevation_lt10: int | None = 0
    elevation_10to20: int | None = 0
    elevation_20to30: int | None = 50
    elevation_30to40: int | None = 50
    elevation_40to50: int | None = 50
    elevation_50to60: int | None = 80
    elevation_gt60: int | None = 100
    manual_trigger: str | None = None


@dataclass
class PrioritySwitchData:
    """Dataclass for PrioritySwitch Data definition."""

    inputs: Dict[str, InputData] = field(
        default_factory=lambda: dict()
    )  # dict[str, InputData] = field(default_factory=dict)
    switch_name_friendly: str | None = None
    switch_name: str | None = None
    deadtime: str | None = None
    detect_manual: bool | None = True
    automation_pause: str | None = None
    initial_run: bool | None = True
    output_script: Any | None = None
    output_entity: str | None = None
    only_send_on_change: bool | None = True
