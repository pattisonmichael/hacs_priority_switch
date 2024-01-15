"""Constants for the Priority Switch integration."""
from enum import StrEnum

DOMAIN = "priorityswitch"
DOMAIN_FRIENDLY = "Priority Switch"
CONF_INPUTS = "inputs"
ATTR_CONTROL_STATE = "control_state"
ATTR_CONTROL_ENTITY = "control_entity"
ATTR_CONTROL_ENTITY_VALUE = "control_entity_value"
ATTR_CONTROL_TEMPLATE = "control_template"
ATTR_CONTROL_TEMPLATE_VALUE = "control_template_value"
ATTR_CONTROL_TYPE = "control_type"
ATTR_VALUE = "value"
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
