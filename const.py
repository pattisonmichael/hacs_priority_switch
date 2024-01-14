"""Constants for the Priority Switch integration."""
from enum import StrEnum

DOMAIN = "priorityswitch"
DOMAIN_FRIENDLY = "Priority Switch"
CONF_INPUTS = "inputs"
ATTR_CONTROL_STATE = "control_state"
ATTR_CONTROL_ENTITY = "control_entity"
ATTR_CONTROL_ENTITY_VALUE = "control_entity_value"
PLATFORMS = ["sensor"]


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
