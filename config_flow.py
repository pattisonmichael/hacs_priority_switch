"""Config flow for Priority Switch integration."""
from __future__ import annotations
from collections.abc import Callable, Coroutine, Mapping
import logging
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.input_boolean import DOMAIN as INPUT_BOOLEAN_DOMAIN
from homeassistant.core import CALLBACK_TYPE

# from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, selector
from homeassistant.helpers import template as tp
from homeassistant.components import websocket_api, template
from homeassistant.const import CONF_NAME, CONF_STATE
from .const import CONF_INPUTS, DOMAIN
from homeassistant.exceptions import TemplateError

_LOGGER = logging.getLogger(__name__)


# def not_in_excluded_values(excluded_values):
#     """Return a validator that checks if value is not in the excluded list."""

#     def validate(value):
#         """Validate that the value is not in the excluded list."""
#         if value in excluded_values:
#             raise vol.Invalid(f"The value {value} is not allowed.")
#         return value

#     return validate


def insert_and_shift_up(d, new_key, new_value):
    # Assuming that the keys are integer and sorted
    # Get the largest key in the dictionary
    max_key = max(d.keys(), default=new_key - 1)

    # Start from max_key and go down to new_key, shifting values up by one
    for key in range(max_key, new_key - 1, -1):
        d[key + 1] = d[key]

    # Insert the new key and value
    d[new_key] = new_value


class PlaceholderHub:
    """Placeholder class to make tests pass.

    TODO Remove this placeholder class and replace with things from your PyPI package.
    """

    def __init__(self, host: str) -> None:
        """Initialize."""
        self.host = host

    async def authenticate(self, username: str, password: str) -> bool:
        """Test if we can authenticate with the host."""
        return True


def string_to_boolean(s: str):
    """Convert Boolean to String to actual boolean or return None if not boolean"""
    if s.lower() == "true":
        return True
    elif s.lower() == "false":
        return False
    else:
        return None


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    if data is None:
        return None
    if (
        string_to_boolean(data["control_type"]) is not None
    ):  # remove Control Entity if boolean
        data.pop("control_entity", None)
    sun_attributes = [
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
    entity_attributes = ["value_entity"]
    template_attributes = ["value_template"]
    value_attributes = ["value"]
    if data["value_type"] == "fixed":  # clean not needed keys and validate input
        if data.get("value") is None:
            raise InvalidData
        for key in sun_attributes + entity_attributes + template_attributes:
            data.pop(key, None)
    elif data["value_type"] == "entity":
        if data.get("value_entity") is None:
            raise InvalidData
        for key in sun_attributes + value_attributes + template_attributes:
            data.pop(key, None)
    elif data["value_type"] == "template":
        if data.get("value_template") is None:
            raise InvalidData
        for key in sun_attributes + entity_attributes + value_attributes:
            data.pop(key, None)
    elif data.get("value_type") == "sun":
        for key in sun_attributes:
            if data[key] is None:
                raise InvalidData
        for key in value_attributes + entity_attributes + template_attributes:
            data.pop(key, None)
    return data


@config_entries.HANDLERS.register(DOMAIN)
class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Priority Switch."""

    VERSION = 1
    data: Optional[dict[str, Any]] = {}
    temp_input_priority = None  # to remember original priority of input while editing

    VALUETYPE = [
        selector.SelectOptionDict(value="fixed", label="Fixed Value"),
        selector.SelectOptionDict(value="entity", label="Value Entity"),
        selector.SelectOptionDict(value="template", label="Value Template"),
        selector.SelectOptionDict(value="sun", label="Follow Sun"),
    ]
    CONTROLTYPE = [
        selector.SelectOptionDict(value="True", label="True"),
        selector.SelectOptionDict(value="False", label="False"),
        selector.SelectOptionDict(value="entity", label="Control Entity"),
    ]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        # self.data = user_input
        self.data[CONF_INPUTS] = {}
        # Entry point of the config flow
        # if user_input is not None:
        # try:
        #     await validate_auth(user_input[CONF_ACCESS_TOKEN], self.hass)
        # except ValueError:
        #     errors["base"] = "auth"
        # if not errors:
        # self.data = user_input
        # self.data[CONF_INPUTS] = []
        return await self.async_step_menu()
        return self.async_show_form(
            step_id="menu",
            data_schema=vol.Schema(
                {
                    vol.Required("mainmenu"): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=MAINMENU),
                    )
                },
            ),
            errors=errors,
        )
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        # Check if the user has enabled advanced options
        if self.show_advanced_options:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {**BASE_CONFIG_SCHEMA.schema, **ADVANCED_CONFIG_SCHEMA.schema}
                ),
                errors=errors,
            )
        else:
            return self.async_show_form(
                step_id="user",
                data_schema=BASE_CONFIG_SCHEMA,
                errors=errors,
            )

        # return self.async_show_form(
        #     step_id="user", data_schema=CONFIG_SCHEMA, errors=errors
        # )

    async def async_step_menu(self, user_input=None):
        # Handle the initial menu selection
        if user_input is not None:
            if user_input.get("mainmenu") == "basic":
                return await self.async_step_basic()
            elif user_input.get("mainmenu") == "advanced":
                return await self.async_step_advanced()
            elif user_input.get("mainmenu") == "add":
                return await self.async_step_add()
            elif user_input.get("mainmenu") == "del":
                return await self.async_step_del()
            elif user_input.get("mainmenu") == "save":
                return self.async_create_entry(
                    title=self.data["switch_name"], data=self.data
                )
            elif user_input.get("mainmenu")[:5] == "input":
                self.temp_input_priority = user_input.get("mainmenu")[5:]
                return await self.async_step_add()
        # If no input or not handled, show the menu again
        MAINMENU = [
            selector.SelectOptionDict(value="basic", label="Basic Setup"),
            selector.SelectOptionDict(value="advanced", label="Advance Setup"),
        ]
        MAINMENU.append(selector.SelectOptionDict(value="add", label="Add Input"))
        if len(self.data[CONF_INPUTS]) > 0:
            for prio in self.data[CONF_INPUTS]:
                MAINMENU.append(
                    selector.SelectOptionDict(
                        value="input" + str(self.data[CONF_INPUTS][prio]["priority"]),
                        label="Edit Input "
                        + str(prio)
                        + ": "
                        + str(self.data[CONF_INPUTS][prio]["name"]),
                    )
                )
            MAINMENU.append(
                selector.SelectOptionDict(value="del", label="Delete Input")
            )
            MAINMENU.append(selector.SelectOptionDict(value="save", label="Save"))
        return self.async_show_form(
            step_id="menu",
            data_schema=vol.Schema(
                {
                    vol.Required("mainmenu"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=MAINMENU, mode=selector.SelectSelectorMode.LIST
                        ),
                    )
                }
            ),
            last_step=False
            if self.data.get("name") is None or len(self.data[CONF_INPUTS]) == 0
            else True,
        )

    async def async_step_del(self, user_input=None):
        # Handle the device configuration submenu
        if user_input is not None:
            # Process the device configuration input and go back to the menu
            # self.data.update(user_input)
            if user_input["menu"] != "back":
                self.data[CONF_INPUTS].pop(int(user_input.get("menu")[5:]))
            self.temp_input_priority = None
            return await self.async_step_menu()

        MENU = []
        for prio in self.data[CONF_INPUTS]:
            MENU.append(
                selector.SelectOptionDict(
                    value="input" + str(self.data[CONF_INPUTS][prio]["priority"]),
                    label="Delete Input "
                    + str(prio)
                    + ": "
                    + str(self.data[CONF_INPUTS][prio]["name"]),
                )
            )
        MENU.append(selector.SelectOptionDict(value="back", label="Previous Menu"))
        # Show the device configuration form
        return self.async_show_form(
            step_id="del",
            last_step=False,
            data_schema=vol.Schema(
                {
                    vol.Required("menu"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=MENU, mode=selector.SelectSelectorMode.LIST
                        ),
                    )
                }
            ),
        )

    async def async_step_add(self, user_input=None):
        # Handle the device configuration submenu
        if user_input is not None:
            # Process the device configuration input and go back to the menu
            # self.data.update(user_input)
            if (
                self.temp_input_priority is not None
                and int(self.temp_input_priority) == user_input["priority"]
            ):  # Update existing
                self.data[CONF_INPUTS][user_input["priority"]].update(user_input)
            elif self.temp_input_priority is None:  # Add a new one
                self.data[CONF_INPUTS][user_input["priority"]] = user_input
            else:  # Reorder
                insert_and_shift_up(
                    self.data[CONF_INPUTS], user_input["priority"], user_input
                )
                # self.data[CONF_INPUTS] = newInputs
            self.temp_input_priority = user_input["priority"]
            if user_input["value_type"] == "fixed":
                return await self.async_step_add_input_fixed(user_input)
            elif user_input["value_type"] == "entity":
                return await self.async_step_add_input_entity(user_input)
            elif user_input["value_type"] == "template":
                return await self.async_step_add_input_template(user_input)
            elif user_input["value_type"] == "sun":
                return await self.async_step_add_input_sun(user_input)
            user_input = await validate_input(self.hass, user_input)
            self.temp_input_priority = None
            return await self.async_step_menu()

        i = (
            self.data[CONF_INPUTS][int(self.temp_input_priority)]
            if len(self.data[CONF_INPUTS]) > 0
            else {}
        )
        INPUT_SCHEMA = vol.Schema(
            {
                vol.Required("name", default=i.get("name")): str,
                vol.Required(
                    "priority",
                    default=i.get(
                        "priority", max(self.data[CONF_INPUTS], default=0) + 1
                    ),
                ): vol.All(
                    selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1, max=20, mode=selector.NumberSelectorMode.BOX
                        ),
                    ),
                    vol.Coerce(int),
                    # vol.NotIn(list(self.data[CONF_INPUTS].keys())),
                ),
                vol.Required(
                    "control_type", default=i.get("control_type")
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=self.CONTROLTYPE,
                        mode=selector.SelectSelectorMode.LIST,
                    ),
                ),
                vol.Optional(
                    "control_entity", default=i.get("control_entity")
                ): vol.Any(
                    None,
                    selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=[BINARY_SENSOR_DOMAIN, INPUT_BOOLEAN_DOMAIN]
                        )
                    ),
                ),
                vol.Required(
                    "value_type", default=i.get("value_type")
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=self.VALUETYPE,
                        mode=selector.SelectSelectorMode.LIST,
                    ),
                ),
            },
            extra=vol.ALLOW_EXTRA,
        )
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
        )

    async def async_step_add_input_entity(self, user_input=None):
        # Handle the device configuration submenu
        if user_input.get("value_entity", None) is not None:
            # Process the device configuration input and go back to the menu
            # self.data.update(user_input)

            self.data[CONF_INPUTS][self.temp_input_priority].update(user_input)
            self.temp_input_priority = None
            return await self.async_step_menu()

        if self.temp_input_priority is None:
            # Define a schema for the "inputs" part of the configuration
            INPUT_SCHEMA = vol.Schema(
                {
                    vol.Required("value_entity"): selector.EntitySelector(),
                },
                extra=vol.ALLOW_EXTRA,
            )
        else:  # Get previous Input data as new default
            i = self.data[CONF_INPUTS][int(self.temp_input_priority)]
            INPUT_SCHEMA = vol.Schema(
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
        # Handle the device configuration submenu
        if user_input.get("value_template", None) is not None:
            # Process the device configuration input and go back to the menu
            # self.data.update(user_input)

            self.data[CONF_INPUTS][self.temp_input_priority].update(user_input)
            self.temp_input_priority = None
            return await self.async_step_menu()

        if self.temp_input_priority is None:
            # Define a schema for the "inputs" part of the configuration
            INPUT_SCHEMA = vol.Schema(
                {
                    vol.Required("value_template"): selector.TemplateSelector(),
                },
                extra=vol.ALLOW_EXTRA,
            )
        else:  # Get previous Input data as new default
            i = self.data[CONF_INPUTS][int(self.temp_input_priority)]
            INPUT_SCHEMA = vol.Schema(
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
        # Handle the device configuration submenu
        if user_input.get("azimut", None) is not None:
            # Process the device configuration input and go back to the menu
            # self.data.update(user_input)
            # self.data[CONF_INPUTS][self.temp_input_priority].update(
            #     {"auto_shade": True}
            # )
            self.data[CONF_INPUTS][self.temp_input_priority].update(user_input)
            self.temp_input_priority = None
            return await self.async_step_menu()

        # if self.temp_input_priority is None:
        i = self.data[CONF_INPUTS][int(self.temp_input_priority)]
        # Define a schema for the "inputs" part of the configuration
        INPUT_SCHEMA = vol.Schema(
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
        # Handle the device configuration submenu
        if user_input.get("value", None) is not None:
            # Process the device configuration input and go back to the menu
            # self.data.update(user_input)

            self.data[CONF_INPUTS][self.temp_input_priority].update(user_input)
            self.temp_input_priority = None
            return await self.async_step_menu()

        if self.temp_input_priority is None:
            # Define a schema for the "inputs" part of the configuration
            INPUT_SCHEMA = vol.Schema(
                {
                    vol.Required("value"): str,
                },
                extra=vol.ALLOW_EXTRA,
            )
        else:  # Get previous Input data as new default
            i = self.data[CONF_INPUTS][int(self.temp_input_priority)]
            INPUT_SCHEMA = vol.Schema(
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

    async def async_step_basic(self, user_input=None):
        # Handle the device configuration submenu
        if user_input is not None:
            # Process the device configuration input and go back to the menu
            self.data.update(user_input)
            return await self.async_step_menu()

        BASE_CONFIG_SCHEMA = vol.Schema(
            {
                vol.Required("switch_name", default=self.data.get("switch_name")): str,
                vol.Required("output", default=self.data.get("output")): str,
                vol.Required(
                    "status_entity", default=self.data.get("status_entity")
                ): selector.EntitySelector(),
                vol.Required(
                    "status_entity_icon", default=self.data.get("status_entity")
                ): selector.IconSelector(),
                vol.Optional(
                    "enabled", default=self.data.get("status_entity", True)
                ): selector.BooleanSelector(),
            },
            extra=vol.ALLOW_EXTRA,
        )
        # Show the device configuration form
        return self.async_show_form(
            step_id="basic",
            data_schema=BASE_CONFIG_SCHEMA,
        )

    async def async_step_advanced(self, user_input=None):
        # Handle the device configuration submenu
        ADVANCED_CONFIG_SCHEMA = vol.Schema(
            {
                vol.Required("switch_name", default=self.data.get("switch_name")): str,
                vol.Required("output", default=self.data.get("output")): str,
                vol.Required("output_sequence"): selector.TemplateSelector(),
                vol.Required(
                    "status_entity", default=self.data.get("status_entity")
                ): selector.EntitySelector(),
                vol.Required(
                    "status_entity_icon", default=self.data.get("status_entity")
                ): selector.IconSelector(),
                vol.Optional(
                    "enabled", default=self.data.get("status_entity", True)
                ): selector.BooleanSelector(),
                vol.Optional(
                    "deadtime", default={"hours": 0, "minutes": 0, "seconds": 30}
                ): selector.DurationSelector(),
                vol.Optional("detect_manual", default=True): bool,
                vol.Optional("automation_pause", default=120): int,
                vol.Optional("initial_run", default=True): bool,
                vol.Optional("debug", default=True): bool,
            },
            extra=vol.ALLOW_EXTRA,
        )
        if user_input is not None:
            # Process the device configuration input and go back to the menu
            self.data.update(user_input)
            return await self.async_step_menu()

        # Show the device configuration form
        return self.async_show_form(
            step_id="advanced",
            data_schema=ADVANCED_CONFIG_SCHEMA,
        )

    @staticmethod
    async def async_setup_preview(hass: HomeAssistant) -> None:
        """Set up preview WS API."""
        websocket_api.async_register_command(hass, ws_start_preview)

    # async def async_step_preview(self, user_input):
    #     """Handle the preview step."""
    #     # Normally you would handle the preview logic here
    #     # For this example, we'll just show the form again
    #     return self.async_show_form(step_id="preview", data_schema=CONFIG_SCHEMA)


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

    # @callback
    # def async_preview_updated(
    #     state: str | None,
    #     attributes: Mapping[str, Any] | None,
    #     listeners: dict[str, bool | set[str]] | None,
    #     error: str | None,
    # ) -> CALLBACK_TYPE:
    #     """Forward config entry state events to websocket."""
    #     if error is not None:
    #         connection.send_message(
    #             websocket_api.event_message(
    #                 msg["id"],
    #                 {"error": error},
    #             )
    #         )
    #         return
    #     rendered_template = tp.render_complex(template_str)
    #     connection.send_message(
    #         websocket_api.event_message(
    #             msg["id"],
    #             {
    #                 "attributes": attributes,
    #                 "listeners": listeners,
    #                 "state": rendered_template,
    #             },
    #         )
    #     )

    connection.send_result(msg["id"])


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidData(HomeAssistantError):
    """Error to indicate there is invalid data"""
