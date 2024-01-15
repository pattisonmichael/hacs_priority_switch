"""Config flow for Priority Switch integration."""
from __future__ import annotations

import logging
from typing import Any, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import websocket_api
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.input_boolean import DOMAIN as INPUT_BOOLEAN_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError, TemplateError
from homeassistant.helpers import config_validation as cv, selector, template as tp
from homeassistant.helpers.translation import async_get_translations

from .const import CONF_INPUTS, DOMAIN, ControlType, InputType

_LOGGER = logging.getLogger(__name__)


def insert_and_shift_up(d, new_key, new_value):
    """Insert a key and value into an existing position and shifts other keys by 1."""
    # Assuming that the keys are integer and sorted
    # Get the largest key in the dictionary
    max_key = max(d.keys(), default=new_key - 1)

    # Start from max_key and go down to new_key, shifting values up by one
    for key in range(max_key, new_key - 1, -1):
        d[key + 1] = d[key]

    # Insert the new key and value
    d[new_key] = new_value


# class PlaceholderHub:
#     """Placeholder class to make tests pass.

#     TO DO Remove this placeholder class and replace with things from your PyPI package.
#     """

#     def __init__(self, host: str) -> None:
#         """Initialize."""
#         self.host = host

#     async def authenticate(self, username: str, password: str) -> bool:
#         """Test if we can authenticate with the host."""
#         return True


def string_to_boolean(s: str):
    """Convert Boolean to String to actual boolean or return None if not boolean."""
    if s.lower() == "true":
        return True
    elif s.lower() == "false":
        return False
    else:
        return None


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


def validate_input(
    step: int, user_input: dict[str, Any], data: dict[str, Any]
) -> dict[str, Any]:
    """Validate Input data for Step 1 & 2."""
    if user_input is None:
        return {"user_input": None, "errors": {"base": "missing_data"}}
    errors = {}
    if step is None or step == 1:
        if user_input.get("name", "") == "":
            errors.update({"name": "input_name_req"})
        if user_input.get("priority") is None:
            errors.update({"priority": "priority_req"})
        elif int(user_input.get("priority")) in data[CONF_INPUTS]:
            errors.update({"priority": "priority_dup"})
        if user_input.get("control_type") is None:
            errors.update({"control_type": "control_type_req"})
        if user_input.get("control_type") == "entity" and not cv.valid_entity_id(
            user_input.get("control_entity")
            if user_input.get("control_entity") is not None
            else ""
        ):
            errors.update({"control_entity": "control_entity_req"})
        if user_input.get("control_type") == "template" and (
            user_input.get("control_template") is None
            or not cv.template(user_input.get("control_template"))
        ):
            errors.update({"control_template": "control_template_req"})
        if user_input.get("value_type") is None:
            errors.update({"value_type": "value_type_req"})

    else:
        if (
            string_to_boolean(user_input["control_type"]) is not None
        ):  # remove Control Entity if boolean
            user_input.pop("control_entity", None)

        if (
            user_input["value_type"] == InputType.FIXED
        ):  # clean not needed keys and validate input
            if user_input.get("value") is None:
                errors.update({"value": "fixed_value_req"})
            for key in SUN_ATTRIBUTES + ENTITY_ATTRIBUTES + TEMPLATE_ATTRIBUTES:
                user_input.pop(key, None)
        elif user_input["value_type"] == InputType.ENTITY:
            if user_input.get("value_entity") is None:
                errors.update({"value_entity": "value_entity_req"})
            for key in SUN_ATTRIBUTES + VALUE_ATTRIBUTES + TEMPLATE_ATTRIBUTES:
                user_input.pop(key, None)
        elif user_input["value_type"] == InputType.TEMPLATE:
            if user_input.get("value_template") is None:
                errors.update({"value_template": "template_value_req"})
            for key in SUN_ATTRIBUTES + ENTITY_ATTRIBUTES + VALUE_ATTRIBUTES:
                user_input.pop(key, None)
        elif user_input.get("value_type") == InputType.SUN:
            for key in SUN_ATTRIBUTES:
                if user_input[key] is None:
                    errors.update({key: "required"})
            for key in VALUE_ATTRIBUTES + ENTITY_ATTRIBUTES + TEMPLATE_ATTRIBUTES:
                user_input.pop(key, None)
    return {"user_input": user_input, "errors": errors}


@config_entries.HANDLERS.register(DOMAIN)
class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Priority Switch."""

    VERSION = 1
    data: Optional[dict[str, Any]] = {}
    temp_input_priority = None  # to remember original priority of input while editing
    translations = None
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

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        # errors: dict[str, str] = {}
        self.data[CONF_INPUTS] = {}

        # get translastions
        if self.translations is None:
            language = self.hass.config.language
            self.translations = await async_get_translations(
                self.hass,
                language=language,
                integrations=[DOMAIN],
                category="selector",
                config_flow=True,
            )
        res = await self.async_step_menu()
        return res

    async def async_step_menu(self, user_input=None):
        """Handle the initial menu selection."""

        if user_input is not None:
            # if user_input.get("mainmenu") == "basic":
            #     return await self.async_step_basic()
            self.data["switch_name_friendly"] = user_input.get("switch_name_friendly")
            # self.data["enabled"] = user_input.get("enabled")
            if user_input.get("mainmenu") == "advanced":
                return await self.async_step_advanced()
            elif user_input.get("mainmenu") == "add":
                return await self.async_step_add()
            elif user_input.get("mainmenu") == "del":
                return await self.async_step_del()
            elif user_input.get("mainmenu") == "save":
                self.data["switch_name"] = cv.slugify(self.data["switch_name_friendly"])
                return self.async_create_entry(
                    title=self.data["switch_name_friendly"], data=self.data
                )
            elif user_input.get("mainmenu")[:5] == "input":
                self.temp_input_priority = user_input.get("mainmenu")[5:]
                return await self.async_step_add()
        # If no input or not handled, show the menu again
        #########

        # Use translated state names
        # for state in all_states:
        #     device_class = state.attributes.get("device_class", "_")
        #     key = f"component.{state.domain}.entity_component.{device_class}.state.{state.state}"
        #     state.state = translations.get(key, state.state)

        #########
        MAINMENU = [  # pylint: disable=invalid-name
            selector.SelectOptionDict(value="advanced", label="advanced"),
        ]

        MAINMENU.append(selector.SelectOptionDict(value="add", label="add"))
        if len(self.data[CONF_INPUTS]) > 0:
            for prio in self.data[CONF_INPUTS]:
                MAINMENU.append(
                    selector.SelectOptionDict(
                        value="input" + str(self.data[CONF_INPUTS][prio]["priority"]),
                        label=self.translations.get(
                            "component.priorityswitch.selector.mainmenu.options.input_"
                            + str(self.data[CONF_INPUTS][prio]["priority"])
                        )
                        + str(self.data[CONF_INPUTS][prio]["name"]),
                    )
                )
            MAINMENU.append(selector.SelectOptionDict(value="del", label="del"))
            if self.data.get("switch_name_friendly") is not None:
                MAINMENU.append(selector.SelectOptionDict(value="save", label="save"))
        description_placeholders = {}
        for prio in self.data[CONF_INPUTS]:
            description_placeholders["input_name" + str(prio)] = self.data[CONF_INPUTS][
                prio
            ]["name"]
        return self.async_show_form(
            step_id="menu",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "switch_name_friendly",
                        default=self.data.get("switch_name_friendly"),
                    ): selector.TextSelector(),
                    # vol.Optional(
                    #     "enabled", default=self.data.get("enabled", True)
                    # ): selector.BooleanSelector(),
                    vol.Required("mainmenu", default="add"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=MAINMENU,
                            mode=selector.SelectSelectorMode.LIST,
                            translation_key="mainmenu",
                        ),
                    ),
                }
            ),
            description_placeholders=description_placeholders,
            last_step=False
            if self.data.get("name") is None or len(self.data[CONF_INPUTS]) == 0
            else True,
        )

    async def async_step_del(self, user_input=None):
        """Handle the device configuration submenu."""
        if user_input is not None:
            # Process the device configuration input and go back to the menu
            # self.data.update(user_input)
            if user_input["menu"] != "back":
                self.data[CONF_INPUTS].pop(int(user_input.get("menu")[5:]))
            self.temp_input_priority = None
            return await self.async_step_menu()

        MENU = []  # pylint: disable=invalid-name
        for prio in self.data[CONF_INPUTS]:
            MENU.append(
                selector.SelectOptionDict(
                    value="input" + str(self.data[CONF_INPUTS][prio]["priority"]),
                    label="input" + str(self.data[CONF_INPUTS][prio]["priority"]),
                )
            )
        MENU.append(selector.SelectOptionDict(value="back", label="back"))
        # Show the device configuration form
        return self.async_show_form(
            step_id="del",
            last_step=False,
            data_schema=vol.Schema(
                {
                    vol.Required("menu"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=MENU,
                            mode=selector.SelectSelectorMode.LIST,
                            translation_key="menu",
                        ),
                    )
                }
            ),
        )

    async def async_step_add(self, user_input=None):
        """Handle the input configuration submenu."""
        errors = {}
        if user_input is not None:
            # Process the device configuration input and go back to the menu
            val = validate_input(1, user_input, self.data)
            if len(val.get("errors", {})) == 0:
                if (
                    user_input.get("control_type")
                    in [ControlType.TRUE, ControlType.FALSE]
                    or (
                        user_input.get("control_type") == ControlType.ENTITY
                        and user_input.get("control_entity") is not None
                    )
                    or (
                        user_input.get("control_type") == ControlType.TEMPLATE
                        and user_input.get("control_template") is not None
                    )
                ):  # validate if control_entity is required
                    if (
                        self.temp_input_priority is not None
                        and int(self.temp_input_priority) == user_input["priority"]
                    ):  # Update existing
                        self.data[CONF_INPUTS][user_input["priority"]].update(
                            user_input
                        )
                    elif self.temp_input_priority is None:  # Add a new one
                        self.data[CONF_INPUTS][user_input["priority"]] = user_input
                    else:  # Reorder
                        insert_and_shift_up(
                            self.data[CONF_INPUTS], user_input["priority"], user_input
                        )
                        # self.data[CONF_INPUTS] = newInputs
                    self.temp_input_priority = user_input["priority"]
                    if user_input["value_type"] == InputType.FIXED:
                        return await self.async_step_add_input_fixed(user_input)
                    elif user_input["value_type"] == InputType.ENTITY:
                        return await self.async_step_add_input_entity(user_input)
                    elif user_input["value_type"] == InputType.TEMPLATE:
                        return await self.async_step_add_input_template(user_input)
                    elif user_input["value_type"] == InputType.SUN:
                        return await self.async_step_add_input_sun(user_input)
                    user_input = await validate_input(self.hass, user_input, self.data)
                    self.temp_input_priority = None
                    return await self.async_step_menu()
            else:
                errors = val.get("errors")

        i = (
            self.data[CONF_INPUTS][int(self.temp_input_priority)]
            if len(self.data[CONF_INPUTS]) > 0 and self.temp_input_priority is not None
            else user_input
            if user_input is not None
            else {}
        )
        if user_input is None:
            user_input = {}

        CONTROL_ENTITY_SCHEMA = {}  # pylint: disable=invalid-name
        if (x := user_input.get("control_type")) == ControlType.ENTITY:
            CONTROL_ENTITY_SCHEMA.update(
                {
                    vol.Required(
                        "control_entity", default=i.get("control_entity")
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=[BINARY_SENSOR_DOMAIN, INPUT_BOOLEAN_DOMAIN]
                        )
                    ),
                }
            )
        elif x == ControlType.TEMPLATE:
            CONTROL_ENTITY_SCHEMA.update(
                {
                    vol.Required("control_template"): selector.TemplateSelector(),
                }
            )

        INPUT_SCHEMA_START = {  # pylint: disable=invalid-name
            vol.Optional("name", default=i.get("name")): vol.Any(
                None,
                selector.TextSelector(),
            ),
            vol.Optional(
                "priority",
                default=i.get("priority", max(self.data[CONF_INPUTS], default=0) + 1),
            ): vol.All(
                selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=20, mode=selector.NumberSelectorMode.BOX
                    ),
                ),
                vol.Coerce(int),
            ),
            vol.Optional("control_type", default=i.get("control_type")): vol.Any(
                None,
                selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=self.CONTROLTYPE,
                        mode=selector.SelectSelectorMode.LIST,
                        translation_key="add_input_control",
                    ),
                ),
            ),
        }

        INPUT_SCHEMA_END = {  # pylint: disable=invalid-name
            vol.Required("value_type", default=i.get("value_type")): vol.Any(
                None,
                selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=self.VALUETYPE,
                        mode=selector.SelectSelectorMode.LIST,
                        translation_key="add_input_value",
                        # msg="Type of Input is required!",
                    )
                ),
            ),
            vol.Optional("auto_on", default=user_input.get("auto_on")): vol.Any(
                None, selector.DurationSelector()
            ),
            vol.Optional("auto_off", default=user_input.get("auto_off")): vol.Any(
                None, selector.DurationSelector()
            ),
        }
        # Combine the dictionaries
        combined_schema_dict = {
            **INPUT_SCHEMA_START,
            **CONTROL_ENTITY_SCHEMA,
            **INPUT_SCHEMA_END,
        }

        # Create the Schema object with extra=ALLOW_EXTRA
        INPUT_SCHEMA = vol.Schema(combined_schema_dict, extra=vol.ALLOW_EXTRA)  # pylint: disable=invalid-name
        # Show the device configuration form
        return self.async_show_form(
            step_id="add",
            last_step=False,
            data_schema=INPUT_SCHEMA,
            description_placeholders={
                "input_name": self.data[CONF_INPUTS][int(self.temp_input_priority)][
                    "name"
                ]
                if self.temp_input_priority is not None
                else ""
            },
            errors=errors,
        )

    async def async_step_add_input_entity(self, user_input=None):
        """Handle the input entity configuration submenu."""
        if user_input.get("value_entity", None) is not None:
            # Process the device configuration input and go back to the menu
            # self.data.update(user_input)

            self.data[CONF_INPUTS][self.temp_input_priority].update(user_input)
            self.temp_input_priority = None
            return await self.async_step_menu()

        if self.temp_input_priority is None:
            # Define a schema for the "inputs" part of the configuration
            INPUT_SCHEMA = vol.Schema(  # pylint: disable=invalid-name
                {
                    vol.Required("value_entity"): selector.EntitySelector(),
                },
                extra=vol.ALLOW_EXTRA,
            )
        else:  # Get previous Input data as new default
            i = self.data[CONF_INPUTS][int(self.temp_input_priority)]
            INPUT_SCHEMA = vol.Schema(  # pylint: disable=invalid-name
                {
                    vol.Required(
                        "value_entity", default=i.get("value_entity", "")
                    ): selector.EntitySelector(),
                },
                extra=vol.ALLOW_EXTRA,
            )
        # Show the device configuration form
        return self.async_show_form(
            step_id="add_input_entity",
            last_step=False,
            data_schema=INPUT_SCHEMA,
            description_placeholders={
                "input_name": self.data[CONF_INPUTS][int(self.temp_input_priority)][
                    "name"
                ]
            },
        )

    async def async_step_add_input_template(self, user_input=None):
        """Handle the input template configuration submenu."""
        if user_input.get("value_template", None) is not None:
            # Process the device configuration input and go back to the menu
            # self.data.update(user_input)

            self.data[CONF_INPUTS][self.temp_input_priority].update(user_input)
            self.temp_input_priority = None
            return await self.async_step_menu()

        if self.temp_input_priority is None:
            # Define a schema for the "inputs" part of the configuration
            INPUT_SCHEMA = vol.Schema(  # pylint: disable=invalid-name
                {
                    vol.Required("value_template"): selector.TemplateSelector(),
                },
                extra=vol.ALLOW_EXTRA,
            )
        else:  # Get previous Input data as new default
            i = self.data[CONF_INPUTS][int(self.temp_input_priority)]
            INPUT_SCHEMA = vol.Schema(  # pylint: disable=invalid-name
                {
                    vol.Required(
                        "value_template", default=i.get("value_template")
                    ): selector.TemplateSelector(),
                },
                extra=vol.ALLOW_EXTRA,
            )
        # Show the device configuration form
        return self.async_show_form(
            step_id="add_input_template",
            last_step=False,
            data_schema=INPUT_SCHEMA,
            description_placeholders={
                "input_name": self.data[CONF_INPUTS][int(self.temp_input_priority)][
                    "name"
                ]
            },
            preview="template",
        )

    async def async_step_add_input_sun(self, user_input=None):
        """Handle the input sun configuration submenu."""
        if user_input.get("azimut", None) is not None:
            # Process the device configuration input and go back to the menu
            # self.data.update(user_input)
            # self.data[CONF_INPUTS][self.temp_input_priority].update(
            #     {"auto_shade": True}
            # )
            self.data[CONF_INPUTS][self.temp_input_priority].update(user_input)
            self.temp_input_priority = None
            return await self.async_step_menu()

        i = self.data[CONF_INPUTS][int(self.temp_input_priority)]
        # Define a schema for the "inputs" part of the configuration
        INPUT_SCHEMA = vol.Schema(  # pylint: disable=invalid-name
            {
                #                    vol.Required("auto_shade"): bool,
                vol.Required("azimut", default=i.get("azimut")): vol.All(
                    selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0, max=360, mode=selector.NumberSelectorMode.BOX
                        ),
                    ),
                    vol.Coerce(int),
                ),
                vol.Required("elevation", default=i.get("elevation")): vol.All(
                    selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=-90, max=90, mode=selector.NumberSelectorMode.SLIDER
                        ),
                    ),
                    vol.Coerce(int),
                ),
                vol.Required(
                    "buildingDeviation", default=i.get("buildingDeviation", 0)
                ): vol.All(
                    selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=-90, max=90, mode=selector.NumberSelectorMode.SLIDER
                        ),
                    ),
                    vol.Coerce(int),
                ),
                vol.Required("offset_entry", default=i.get("offset_entry", 0)): vol.All(
                    selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=-90, max=0, mode=selector.NumberSelectorMode.SLIDER
                        ),
                    ),
                    vol.Coerce(int),
                ),
                vol.Required("offset_exit", default=i.get("offset_exit", 0)): vol.All(
                    selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0, max=90, mode=selector.NumberSelectorMode.SLIDER
                        ),
                    ),
                    vol.Coerce(int),
                ),
                vol.Required(
                    "updateInterval", default=i.get("updateInterval", 10)
                ): vol.All(
                    selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1, max=90, mode=selector.NumberSelectorMode.SLIDER
                        ),
                    ),
                    vol.Coerce(int),
                ),
                vol.Required(
                    "sun_entity", default=i.get("sun_entity", "sun.sun")
                ): selector.EntitySelector(),
                vol.Required(
                    "setIfInShadow", default=i.get("setIfInShadow", False)
                ): selector.BooleanSelector(),
                vol.Optional("shadow", default=i.get("shadow")): vol.Any(
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
                vol.Required(
                    "elevation_lt10", default=i.get("elevation_lt10", 0)
                ): vol.All(
                    selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0, max=100, mode=selector.NumberSelectorMode.SLIDER
                        ),
                    ),
                    vol.Coerce(int),
                ),
                vol.Required(
                    "elevation_10to20", default=i.get("elevation_10to20", 0)
                ): vol.All(
                    selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0, max=100, mode=selector.NumberSelectorMode.SLIDER
                        ),
                    ),
                    vol.Coerce(int),
                ),
                vol.Required(
                    "elevation_20to30", default=i.get("elevation_20to30", 50)
                ): vol.All(
                    selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0, max=100, mode=selector.NumberSelectorMode.SLIDER
                        ),
                    ),
                    vol.Coerce(int),
                ),
                vol.Required(
                    "elevation_30to40", default=i.get("elevation_30to40", 50)
                ): vol.All(
                    selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0, max=100, mode=selector.NumberSelectorMode.SLIDER
                        ),
                    ),
                    vol.Coerce(int),
                ),
                vol.Required(
                    "elevation_40to50", default=i.get("elevation_40to50", 50)
                ): vol.All(
                    selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0, max=100, mode=selector.NumberSelectorMode.SLIDER
                        ),
                    ),
                    vol.Coerce(int),
                ),
                vol.Required(
                    "elevation_50to60", default=i.get("elevation_50to60", 80)
                ): vol.All(
                    selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0, max=100, mode=selector.NumberSelectorMode.SLIDER
                        ),
                    ),
                    vol.Coerce(int),
                ),
                vol.Required(
                    "elevation_gt60", default=i.get("elevation_gt60", 100)
                ): vol.All(
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

        # Show the device configuration form
        return self.async_show_form(
            step_id="add_input_sun",
            last_step=False,
            data_schema=INPUT_SCHEMA,
            description_placeholders={
                "input_name": self.data[CONF_INPUTS][int(self.temp_input_priority)][
                    "name"
                ]
            },
        )

    async def async_step_add_input_fixed(self, user_input=None):
        """Handle the input fixed configuration submenu."""
        if user_input.get("value", None) is not None:
            # Process the device configuration input and go back to the menu

            self.data[CONF_INPUTS][self.temp_input_priority].update(user_input)
            self.temp_input_priority = None
            return await self.async_step_menu()

        if self.temp_input_priority is None:
            # Define a schema for the "inputs" part of the configuration
            INPUT_SCHEMA = vol.Schema(  # pylint: disable=invalid-name
                {
                    vol.Required("value"): str,
                },
                extra=vol.ALLOW_EXTRA,
            )
        else:  # Get previous Input data as new default
            i = self.data[CONF_INPUTS][int(self.temp_input_priority)]
            INPUT_SCHEMA = vol.Schema(  # pylint: disable=invalid-name
                {
                    vol.Required("value", default=i.get("value")): str,
                },
                extra=vol.ALLOW_EXTRA,
            )
        # Show the device configuration form
        return self.async_show_form(
            step_id="add_input_fixed",
            last_step=False,
            data_schema=INPUT_SCHEMA,
            description_placeholders={
                "input_name": self.data[CONF_INPUTS][int(self.temp_input_priority)][
                    "name"
                ]
            },
        )

    async def async_step_advanced(self, user_input=None):
        """Handle the advanced configuration submenu."""
        if user_input is not None:
            # Process the device configuration input and go back to the menu
            self.data.update(user_input)
            return await self.async_step_menu()

        user_input = self.data[CONF_INPUTS].get(self.temp_input_priority)
        ADVANCED_CONFIG_SCHEMA = vol.Schema(  # pylint: disable=invalid-name
            {
                vol.Optional(
                    "deadtime", default=user_input.get("deadtime")
                ): selector.DurationSelector(),
                vol.Optional(
                    "detect_manual", default=user_input.get("deadtime", True)
                ): selector.BooleanSelector(),
                vol.Optional(
                    "automation_pause", default=user_input.get("automation_pause")
                ): selector.DurationSelector(),
                vol.Optional(
                    "initial_run", default=user_input.get("initial_run", True)
                ): selector.BooleanSelector(),
            },
            extra=vol.ALLOW_EXTRA,
        )
        # Show the device configuration form
        return self.async_show_form(
            step_id="advanced",
            data_schema=ADVANCED_CONFIG_SCHEMA,
        )

    @staticmethod
    async def async_setup_preview(hass: HomeAssistant) -> None:
        """Set up preview WS API."""
        websocket_api.async_register_command(hass, ws_start_preview)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "template/start_preview",
        vol.Required("flow_id"): str,
        vol.Required("flow_type"): vol.Any("config_flow", "options_flow"),
        vol.Required("user_input"): dict,
    }
)
@callback
def ws_start_preview(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Generate a preview based on the template provided in user input."""
    user_input = msg["user_input"]
    template_str = user_input.get("value_template")

    try:
        # Render the template with the provided string
        if template_str is not None and tp.is_template_string(template_str):
            tmpl = tp.Template(template_str, hass)

            rendered_template = tmpl.async_render()
            connection.send_message(
                websocket_api.event_message(
                    msg["id"],
                    {
                        "state": rendered_template,
                        "attributes": {"friendly_name": "Template Preview:"},
                    },
                )
            )

    except TemplateError as ex:
        # If there is an error in rendering the template, send the error message back
        connection.send_message(
            websocket_api.error_message(
                msg["id"], "template_error", f"Error rendering template: {ex}"
            )
        )

    connection.send_result(msg["id"])


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidData(HomeAssistantError):
    """Error to indicate there is invalid data."""
