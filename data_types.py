"""Dataclasses for PrioritySwitch."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Optional, Dict


class ControlType(StrEnum):
    """Types of Controls."""

    TRUE = "True"
    FALSE = "False"
    ENTITY = "Entity"
    TEMPLATE = "Template"


class InputType(StrEnum):
    """Types of Inputs."""

    FIXED = "Fixed"
    SUN = "Sun"
    ENTITY = "Entity"
    TEMPLATE = "Template"


@dataclass
class InputData:
    """Dataclass for Input definition."""

    name: str
    priority: int
    control_type: ControlType
    value_type: InputType
    control_template: Optional[str] = None
    control_entity: Optional[str] = None
    auto_on: Optional[str] = None
    auto_off: Optional[str] = None
    value: Optional[str] = None
    value_entity: Optional[str] = None
    value_template: Optional[str] = None
    azimut: Optional[int] = None
    elevation: Optional[int] = None
    building_deviation: Optional[int] = 0
    offset_entry: Optional[int] = 0
    offset_exit: Optional[int] = 0
    update_interval: Optional[int] = 10
    sun_entity: Optional[str] = None
    set_if_in_shadow: Optional[bool] = False
    shadow: Optional[int] = None
    elevation_lt10: Optional[int] = 0
    elevation_10to20: Optional[int] = 0
    elevation_20to30: Optional[int] = 50
    elevation_30to40: Optional[int] = 50
    elevation_40to50: Optional[int] = 50
    elevation_50to60: Optional[int] = 80
    elevation_gt60: Optional[int] = 100


@dataclass
class PrioritySwitchData:
    """Dataclass for PrioritySwitch Data definition."""

    inputs: Dict[str, InputData] = field(
        default_factory=lambda: dict()
    )  # dict[str, InputData] = field(default_factory=dict)
    switch_name_friendly: Optional[str] = None
    switch_name: Optional[str] = None
    deadtime: Optional[str] = None
    detect_manual: Optional[bool] = True
    automation_pause: Optional[str] = None
    initial_run: Optional[bool] = True
