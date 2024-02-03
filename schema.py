"""Config & OptionsFlow Schema."""
import voluptuous as vol

from homeassistant.helpers import selector

from .data_types import ControlType, InputType

VALUETYPE = [
    selector.SelectOptionDict(value=str(InputType.FIXED), label="fixed"),
    selector.SelectOptionDict(value=str(InputType.ENTITY), label="entity"),
    selector.SelectOptionDict(value=str(InputType.TEMPLATE), label="template"),
    selector.SelectOptionDict(value=str(InputType.SUN), label="sun"),
]
CONTROLTYPE = [
    selector.SelectOptionDict(value=str(ControlType.TRUE), label="True"),
    selector.SelectOptionDict(value=str(ControlType.FALSE), label="False"),
    selector.SelectOptionDict(value=str(ControlType.ENTITY), label="entity"),
    selector.SelectOptionDict(value=str(ControlType.TEMPLATE), label="template"),
]

SUN_ATTRIBUTES = [
    "azimut",
    "elevation",
    "buildingDeviation",
    "offset_entry",
    "offset_exit",
    "updateInterval",
    "sun_entity",
    "setIfInShadow",
    "shadow",
    "elevation_lt10",
    "elevation_10to20",
    "elevation_20to30",
    "elevation_30to40",
    "elevation_40to50",
    "elevation_50to60",
    "elevation_gt60",
]
ENTITY_ATTRIBUTES = ["value_entity"]
TEMPLATE_ATTRIBUTES = ["value_template"]
VALUE_ATTRIBUTES = ["value"]


INPUT_SCHEMA_START = {  # pylint: disable=invalid-name
    vol.Optional(
        "name",
        # default=i.get("name")
    ): vol.Any(
        None,
        selector.TextSelector(),
    ),
    vol.Optional(
        "priority",
        # default=i.get(
        #     "priority", int(max(self.cur_data.inputs, default=0)) + 1
        # ),
    ): vol.All(
        selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1, max=20, mode=selector.NumberSelectorMode.BOX
            ),
        ),
        vol.Coerce(int),
    ),
    vol.Optional(
        "control_type",
        # default=i.get("control_type")
    ): vol.Any(
        None,
        selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=CONTROLTYPE,
                mode=selector.SelectSelectorMode.LIST,
                translation_key="add_input_control",
            ),
        ),
    ),
}

INPUT_SCHEMA_END = {  # pylint: disable=invalid-name
    vol.Required(
        "value_type",
        # default=i.get("value_type")
    ): vol.Any(
        None,
        selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=VALUETYPE,
                mode=selector.SelectSelectorMode.LIST,
                translation_key="add_input_value",
            )
        ),
    ),
    vol.Optional(
        "auto_on",
        # default=user_input.get("auto_on")
    ): vol.Any(None, selector.DurationSelector()),
    vol.Optional(
        "auto_off",
        # default=user_input.get("auto_off")
    ): vol.Any(None, selector.DurationSelector()),
}

ADVANCED_CONFIG_SCHEMA = vol.Schema(  # pylint: disable=invalid-name
    {
        vol.Optional(
            "deadtime",  # default=user_input.get("deadtime")
        ): selector.DurationSelector(),
        vol.Optional(
            "detect_manual",  # default=user_input.get("deadtime", True)
        ): selector.BooleanSelector(),
        vol.Optional(
            "automation_pause",  # default=user_input.get("automation_pause")
        ): selector.DurationSelector(),
        vol.Optional(
            "initial_run",  # default=user_input.get("initial_run", True)
        ): selector.BooleanSelector(),
        vol.Optional(
            "only_send_on_change",  # default=user_input.get("initial_run", True)
        ): selector.BooleanSelector(),
        vol.Optional(
            "output_script",
        ): selector.TargetSelector(
            config=selector.TargetSelectorConfig(
                entity=selector.EntityFilterSelectorConfig(domain="script")
            )
        ),
        vol.Optional(
            "output_entity",
        ): selector.TargetSelector(
            config=selector.TargetSelectorConfig(
                entity=selector.EntityFilterSelectorConfig(
                    domain=["switch", "input_boolean", "light", "cover"]
                )
            )
        ),
    },
    extra=vol.ALLOW_EXTRA,
)

INPUT_SCHEMA_SUN = vol.Schema(  # pylint: disable=invalid-name
    {
        #                    vol.Required("auto_shade"): bool,
        vol.Required(
            "azimut",
            # default=i.get("azimut")
        ): vol.All(
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=360, mode=selector.NumberSelectorMode.BOX
                ),
            ),
            vol.Coerce(int),
        ),
        vol.Required(
            "elevation",
            # default=i.get("elevation")
        ): vol.All(
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=-90, max=90, mode=selector.NumberSelectorMode.SLIDER
                ),
            ),
            vol.Coerce(int),
        ),
        vol.Required("building_deviation", default=0): vol.All(
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=-90, max=90, mode=selector.NumberSelectorMode.SLIDER
                ),
            ),
            vol.Coerce(int),
        ),
        vol.Required("offset_entry", default=0): vol.All(
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=-90, max=0, mode=selector.NumberSelectorMode.SLIDER
                ),
            ),
            vol.Coerce(int),
        ),
        vol.Required("offset_exit", default=0): vol.All(
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=90, mode=selector.NumberSelectorMode.SLIDER
                ),
            ),
            vol.Coerce(int),
        ),
        vol.Required("update_interval", default=10): vol.All(
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=90, mode=selector.NumberSelectorMode.SLIDER
                ),
            ),
            vol.Coerce(int),
        ),
        vol.Required("sun_entity", default="sun.sun"): selector.EntitySelector(),
        vol.Required("set_if_in_shadow", default=False): selector.BooleanSelector(),
        vol.Optional(
            "shadow",
            # default=i.get("shadow")
        ): vol.Any(
            None,
            vol.All(
                selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=100, mode=selector.NumberSelectorMode.SLIDER
                    ),
                ),
                vol.Coerce(int),
            ),
        ),
        vol.Required("elevation_lt10", default=0): vol.All(
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=100, mode=selector.NumberSelectorMode.SLIDER
                ),
            ),
            vol.Coerce(int),
        ),
        vol.Required("elevation_10to20", default=0): vol.All(
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=100, mode=selector.NumberSelectorMode.SLIDER
                ),
            ),
            vol.Coerce(int),
        ),
        vol.Required("elevation_20to30", default=50): vol.All(
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=100, mode=selector.NumberSelectorMode.SLIDER
                ),
            ),
            vol.Coerce(int),
        ),
        vol.Required("elevation_30to40", default=50): vol.All(
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=100, mode=selector.NumberSelectorMode.SLIDER
                ),
            ),
            vol.Coerce(int),
        ),
        vol.Required("elevation_40to50", default=50): vol.All(
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=100, mode=selector.NumberSelectorMode.SLIDER
                ),
            ),
            vol.Coerce(int),
        ),
        vol.Required("elevation_50to60", default=80): vol.All(
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=100, mode=selector.NumberSelectorMode.SLIDER
                ),
            ),
            vol.Coerce(int),
        ),
        vol.Required("elevation_gt60", default=100): vol.All(
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=100, mode=selector.NumberSelectorMode.SLIDER
                ),
            ),
            vol.Coerce(int),
        ),
    },
    extra=vol.ALLOW_EXTRA,
)
