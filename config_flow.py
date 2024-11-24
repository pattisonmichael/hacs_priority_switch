"""Config flow for Priority Switch integration."""

from __future__ import annotations

from abc import ABC, abstractmethod

# from collections.abc import AsyncGenerator
import copy
from dataclasses import fields
import logging
from types import MappingProxyType
from typing import Any, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import websocket_api
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.input_boolean import DOMAIN as INPUT_BOOLEAN_DOMAIN
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    OptionsFlowWithConfigEntry,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowHandler, FlowResult
from homeassistant.exceptions import HomeAssistantError, TemplateError
from homeassistant.helpers import config_validation as cv, selector, template as tp
from homeassistant.helpers.translation import async_get_translations

from .const import DOMAIN
from .data_types import (
    ControlType,
    # InputData,
    InputType,
    PrioritySwitchData,
)
from .schema import (
    ADVANCED_CONFIG_SCHEMA,
    ENTITY_ATTRIBUTES,
    INPUT_SCHEMA_END,
    INPUT_SCHEMA_START,
    INPUT_SCHEMA_SUN,
    SUN_ATTRIBUTES,
    TEMPLATE_ATTRIBUTES,
    VALUE_ATTRIBUTES,
)

_LOGGER = logging.getLogger(__name__)


def insert_and_shift_up(d, new_key, new_value):
    """Insert a key and value into an existing position and shifts other keys by 1."""
    # Assuming that the keys are integer and sorted
    # Get the largest key in the dictionary
    max_key = max(d.keys(), default=int(new_key) - 1)

    # Start from max_key and go down to new_key, shifting values up by one
    for key in range(int(max_key), int(new_key) - 1, -1):
        d[str(key + 1)] = d[str(key)]

    # Insert the new key and value
    d[str(new_key)] = new_value


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


# TODO: Add OutputTarget


def string_to_boolean(s: str):
    """Convert Boolean to String to actual boolean or return None if not boolean."""
    if s.lower() == "true":
        return True
    if s.lower() == "false":
        return False
    return None


def validate_input(
    step: int, user_input: dict[str, Any], data: dict[str, Any], priority: int = None
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
        # elif int(user_input.get("priority")) != int(priority):
        #     errors.update({"priority": "priority_dup"})
        if user_input.get("control_type") is None:
            errors.update({"control_type": "control_type_req"})
        if user_input.get(
            "control_type"
        ) == ControlType.ENTITY and not cv.valid_entity_id(
            user_input.get("control_entity")
            if user_input.get("control_entity") is not None
            else ""
        ):
            errors.update({"control_entity": "control_entity_req"})
        if user_input.get("control_type") == ControlType.TEMPLATE and (
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


class PrioritySwitchCommonFlow(ABC, FlowHandler):
    """Base class for flows."""

    VERSION = 1
    data: Optional[dict[str, Any]] = {}  # noqa: UP007
    temp_input_priority = None  # to remember original priority of input while editing
    translations = None

    def __init__(self, initial_data=PrioritySwitchData()) -> None:
        """Initialize CommonFlow."""
        self._initial_data = initial_data
        if isinstance(initial_data, MappingProxyType):
            self.cur_data = copy.deepcopy(PrioritySwitchData(**initial_data))
        else:
            self.cur_data = PrioritySwitchData()  # copy.deepcopy(initial_data)
        _LOGGER.debug("initial_data: %s", self.cur_data)

    @abstractmethod
    def finish_flow(self) -> FlowResult:
        """Finish the flow."""

    async def async_step_menu(self, user_input=None):
        """Handle the initial menu selection."""

        if user_input is not None:
            self.cur_data.switch_name_friendly = user_input.get("switch_name_friendly")
            if user_input.get("mainmenu") == "advanced":
                return await self.async_step_advanced()
            if user_input.get("mainmenu") == "add":
                return await self.async_step_add()
            if user_input.get("mainmenu") == "del":
                return await self.async_step_del()
            if user_input.get("mainmenu") == "clone":
                return await self.async_step_clone()
            if user_input.get("mainmenu") == "save":
                self.cur_data.switch_name = cv.slugify(
                    self.cur_data.switch_name_friendly
                )
                return self.finish_flow()
            if user_input.get("mainmenu")[:5] == "input":
                self.temp_input_priority = user_input.get("mainmenu")[5:]
                return await self.async_step_add()

        MAINMENU = [  # pylint: disable=invalid-name
            selector.SelectOptionDict(value="advanced", label="advanced"),
        ]

        MAINMENU.append(selector.SelectOptionDict(value="add", label="add"))
        # if len(self.cur_data.inputs) > 0:
        for val in self.cur_data.inputs.values():
            # for prio in self.cur_data.inputs:
            MAINMENU.append(  # noqa: PERF401
                selector.SelectOptionDict(
                    value="input" + str(val["priority"]),
                    label=self.translations.get(
                        "component.priorityswitch.selector.mainmenu.options.input_"
                        + str(val["priority"])
                    )
                    + str(val["name"]),
                )
            )
        if self.cur_data.switch_name_friendly is None:
            MAINMENU.append(selector.SelectOptionDict(value="clone", label="clone"))

        if self.cur_data.switch_name_friendly is not None:
            MAINMENU.append(selector.SelectOptionDict(value="del", label="del"))
            MAINMENU.append(selector.SelectOptionDict(value="save", label="save"))
            ##
        description_placeholders = {}
        for prio, val in self.cur_data.inputs.items():
            description_placeholders["input_name" + str(prio)] = val["name"]
        return self.async_show_form(
            step_id="menu",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "switch_name_friendly",
                        default=self.cur_data.switch_name_friendly,
                    ): selector.TextSelector(),
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
            last_step=not (
                self.cur_data.switch_name is None or len(self.cur_data.inputs) == 0
            ),
            # last_step=False
            # if self.cur_data.switch_name is None or len(self.cur_data.inputs) == 0
            # else True,
        )

    async def async_step_del(self, user_input=None):
        """Handle the device configuration submenu."""
        if user_input is not None:
            # Process the device configuration input and go back to the menu
            if user_input["menu"] != "back":
                self.cur_data.inputs.pop(str(int(user_input.get("menu")[5:])))
            self.temp_input_priority = None
            return await self.async_step_menu()

        MENU = []  # pylint: disable=invalid-name
        for val in self.cur_data.inputs.values():
            MENU.append(  # noqa: PERF401
                selector.SelectOptionDict(
                    value="input" + str(val["priority"]),
                    label=f"input{val['priority']} {val['name']}",  # pylint: disable=line-too-long
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

    async def async_step_clone(self, user_input=None):
        """Handle the device configuration submenu."""
        if user_input is not None:
            # Process the device configuration input and go back to the menu
            if user_input["clonemenu"] == "abort":
                return self.async_abort(reason="abort")
            # if user_input["clonemenu"] != "back":
            #    self.cur_data.inputs.pop(str(int(user_input.get("menu")[5:])))
            clone = self.hass.config_entries.options.hass.data["entity_platform"][
                "priorityswitch"
            ][int(user_input.get("clonemenu")[6:])]
            name = self.cur_data.switch_name
            friendly_name = self.cur_data.switch_name_friendly
            # print(clone)
            self.cur_data = PrioritySwitchData(**clone.config_entry.data)
            self.cur_data.switch_name = name
            self.cur_data.switch_name_friendly = friendly_name
            # self.temp_input_priority = None
            return await self.async_step_menu()

        MENU = []  # pylint: disable=invalid-name
        for index, val in enumerate(
            self.hass.config_entries.options.hass.data["entity_platform"][
                "priorityswitch"
            ]
        ):
            MENU.append(
                selector.SelectOptionDict(
                    value="clone_" + str(index),
                    label=f"{self.translations.get('component.priorityswitch.selector.clonemenu.options.clone')} {val.config_entry.title}",
                )
            )
        MENU.append(selector.SelectOptionDict(value="abort", label="aback"))
        # Show the device configuration form
        return self.async_show_form(
            step_id="clone",
            last_step=False,
            data_schema=vol.Schema(
                {
                    vol.Required("clonemenu"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=MENU,
                            mode=selector.SelectSelectorMode.LIST,
                            translation_key="clonemenu",
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
            val = validate_input(1, user_input, self.cur_data, self.temp_input_priority)
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
                        self.cur_data.inputs[str(user_input["priority"])].update(
                            user_input
                        )
                    elif self.temp_input_priority is None:  # Add a new one
                        if str(user_input["priority"]) in self.cur_data.inputs:
                            insert_and_shift_up(
                                self.cur_data.inputs,
                                user_input["priority"],
                                user_input,
                            )
                        else:
                            self.cur_data.inputs[str(user_input["priority"])] = (
                                user_input
                            )
                    else:  # Reorder
                        insert_and_shift_up(
                            self.cur_data.inputs,
                            user_input["priority"],
                            user_input,
                        )
                    self.temp_input_priority = user_input["priority"]
                    if user_input["value_type"] == InputType.FIXED:
                        return await self.async_step_add_input_fixed(user_input)
                    if user_input["value_type"] == InputType.ENTITY:
                        return await self.async_step_add_input_entity(user_input)
                    if user_input["value_type"] == InputType.TEMPLATE:
                        return await self.async_step_add_input_template(user_input)
                    if user_input["value_type"] == InputType.SUN:
                        return await self.async_step_add_input_sun(user_input)
                    user_input = await validate_input(
                        self.hass, user_input, self.cur_data
                    )
                    self.temp_input_priority = None
                    return await self.async_step_menu()
            else:
                errors = val.get("errors")

        # i = (
        if not errors:
            user_input = (
                self.cur_data.inputs[self.temp_input_priority]
                if len(self.cur_data.inputs) > 0
                and self.temp_input_priority is not None
                else user_input
                if user_input is not None
                else {
                    "priority": int(max(self.cur_data.inputs, default=0)) + 1,
                    "new": True,
                }
            )
        # if user_input is None:
        #     user_input = {'priority': int(max(self.cur_data.inputs, default=0)) + 1}

        CONTROL_ENTITY_SCHEMA = {}  # pylint: disable=invalid-name
        if (x := user_input.get("control_type")) == ControlType.ENTITY:
            CONTROL_ENTITY_SCHEMA.update(
                {
                    vol.Required(
                        "control_entity",
                        # default=i.get("control_entity")
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

        # Combine the dictionaries
        combined_schema_dict = {
            **INPUT_SCHEMA_START,
            **CONTROL_ENTITY_SCHEMA,
            **INPUT_SCHEMA_END,
        }

        # Create the Schema object with extra=ALLOW_EXTRA
        INPUT_SCHEMA = vol.Schema(combined_schema_dict, extra=vol.ALLOW_EXTRA)  # pylint: disable=invalid-name
        # Show the device configuration form
        data_schema = self.add_suggested_values_to_schema(INPUT_SCHEMA, user_input)
        return self.async_show_form(
            step_id="add",
            last_step=False,
            # data_schema=INPUT_SCHEMA,
            data_schema=data_schema,
            description_placeholders={
                "input_name": self.cur_data.inputs[str(self.temp_input_priority)][
                    "name"
                ]
                if self.temp_input_priority is not None
                else ""
            },
            errors=errors,
            preview="template"
            if user_input.get("control_type") == ControlType.TEMPLATE
            else None,
        )

    async def async_step_add_input_entity(self, user_input=None):
        """Handle the input entity configuration submenu."""
        if user_input.get("value_entity", None) is not None:
            # Process the device configuration input and go back to the menu
            self.cur_data.inputs[str(self.temp_input_priority)].update(user_input)
            self.temp_input_priority = None
            return await self.async_step_menu()

        if self.temp_input_priority is not None:
            user_input = self.cur_data.inputs[str(self.temp_input_priority)]
            # if self.temp_input_priority is None:
            # Define a schema for the "inputs" part of the configuration
            INPUT_SCHEMA = vol.Schema(  # pylint: disable=invalid-name
                {
                    vol.Required("value_entity"): selector.EntitySelector(),
                },
                extra=vol.ALLOW_EXTRA,
            )

        return self.async_show_form(
            step_id="add_input_entity",
            last_step=False,
            data_schema=self.add_suggested_values_to_schema(INPUT_SCHEMA, user_input),
            description_placeholders={
                "input_name": self.cur_data.inputs[str(self.temp_input_priority)][
                    "name"
                ]
            },
        )

    async def async_step_add_input_template(self, user_input=None):
        """Handle the input template configuration submenu."""
        if user_input.get("value_template", None) is not None:
            # Process the device configuration input and go back to the menu
            self.cur_data.inputs[str(self.temp_input_priority)].update(user_input)
            self.temp_input_priority = None
            return await self.async_step_menu()
        if self.temp_input_priority is not None:
            user_input = self.cur_data.inputs[str(self.temp_input_priority)]
            # if self.temp_input_priority is None:
            # Define a schema for the "inputs" part of the configuration
            INPUT_SCHEMA = vol.Schema(  # pylint: disable=invalid-name
                {
                    vol.Required("value_template"): selector.TemplateSelector(),
                },
                extra=vol.ALLOW_EXTRA,
            )

        return self.async_show_form(
            step_id="add_input_template",
            last_step=False,
            data_schema=self.add_suggested_values_to_schema(INPUT_SCHEMA, user_input),
            description_placeholders={
                "input_name": self.cur_data.inputs[str(self.temp_input_priority)][
                    "name"
                ]
            },
            preview="template",
        )

    async def async_step_add_input_sun(self, user_input=None):
        """Handle the input sun configuration submenu."""
        if user_input.get("azimut", None) is not None:
            # Process the device configuration input and go back to the menu
            self.cur_data.inputs[str(self.temp_input_priority)].update(user_input)
            self.temp_input_priority = None
            return await self.async_step_menu()

        i = self.cur_data.inputs[str(self.temp_input_priority)]
        i.update(user_input)
        # i.update_interval=i.get("update_interval", 10)
        user_input = i
        # Define a schema for the "inputs" part of the configuration
        # Show the device configuration form
        return self.async_show_form(
            step_id="add_input_sun",
            last_step=False,
            data_schema=self.add_suggested_values_to_schema(
                INPUT_SCHEMA_SUN, user_input
            ),
            description_placeholders={
                "input_name": self.cur_data.inputs[str(self.temp_input_priority)][
                    "name"
                ]
            },
        )

    async def async_step_add_input_fixed(self, user_input=None):
        """Handle the input fixed configuration submenu."""
        if user_input.get("value", None) is not None:
            # Process the device configuration input and go back to the menu

            self.cur_data.inputs[str(self.temp_input_priority)].update(user_input)
            self.temp_input_priority = None
            return await self.async_step_menu()
        if self.temp_input_priority is not None:
            user_input = self.cur_data.inputs[str(self.temp_input_priority)]
            # if self.temp_input_priority is None:
            # Define a schema for the "inputs" part of the configuration
        INPUT_SCHEMA = vol.Schema(  # pylint: disable=invalid-name
            {
                vol.Required("value"): str,
            },
            extra=vol.ALLOW_EXTRA,
        )

        return self.async_show_form(
            step_id="add_input_fixed",
            last_step=False,
            data_schema=self.add_suggested_values_to_schema(INPUT_SCHEMA, user_input),
            description_placeholders={
                "input_name": self.cur_data.inputs[str(self.temp_input_priority)][
                    "name"
                ]
            },
        )

    async def async_step_advanced(self, user_input=None):
        """Handle the advanced configuration submenu."""
        if user_input is not None:
            # Process the device configuration input and go back to the menu
            # self.cur_data.update(user_input)
            for key, value in user_input.items():
                setattr(self.cur_data, key, value)
            if user_input.get("output_entity", None) is None:
                self.cur_data.output_entity = None
            if user_input.get("output_script", None) is None:
                self.cur_data.output_script = None
            return await self.async_step_menu()

        # user_input = self.cur_data.inputs.get(self.temp_input_priority)
        user_input = {
            field.name: getattr(self.cur_data, field.name)
            for field in fields(self.cur_data)
            if field.name != "inputs"
        }
        # Show the device configuration form
        return self.async_show_form(
            step_id="advanced",
            data_schema=self.add_suggested_values_to_schema(
                ADVANCED_CONFIG_SCHEMA, user_input
            ),
        )

    @staticmethod
    async def async_setup_preview(hass: HomeAssistant) -> None:
        """Set up preview WS API."""
        websocket_api.async_register_command(hass, ws_start_preview)


@config_entries.HANDLERS.register(DOMAIN)
class PrioritySwitchConfigFlow(PrioritySwitchCommonFlow, ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Priority Switch."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> PrioritySwitchOptionsFlow:
        """Get the options flow for this handler."""
        return PrioritySwitchOptionsFlow(config_entry)

    @callback
    def finish_flow(self) -> FlowResult:
        """Create the ConfigEntry."""
        return self.async_create_entry(
            title=self.cur_data.switch_name_friendly, data=self.cur_data.__dict__
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        # errors: dict[str, str] = {}
        self.cur_data.inputs = {}

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


class PrioritySwitchOptionsFlow(PrioritySwitchCommonFlow, OptionsFlowWithConfigEntry):
    """OptionsFlow handler."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize KNX options flow."""
        super().__init__(initial_data=config_entry.data)  # type: ignore[arg-type]
        self._config_entry = config_entry
        # self.cur_data = copy.deepcopy(dict(config_entry.data))
        # self.initial_data = copy.deepcopy(dict(config_entry.data))
        _LOGGER.debug("OptionsFlow Data: %s", self.cur_data)

    @callback
    def finish_flow(self) -> FlowResult:
        """Update the ConfigEntry and finish the flow."""
        # new_data = DEFAULT_ENTRY_DATA | self.initial_data | self.new_entry_data
        # new_data = dict(self.cur_data)
        # self.cur_data = self.initial_data
        data_dict = {
            field.name: getattr(self.cur_data, field.name)
            for field in fields(self.cur_data)
        }
        res = self.hass.config_entries.async_update_entry(
            self.config_entry,
            # data=self.cur_data,
            data=MappingProxyType(data_dict),
            title=self.cur_data.switch_name_friendly,
        )
        # self.async_abort(reason="updated")
        _LOGGER.debug("Config_entry updated: %s", res)
        return self.async_create_entry(title="", data={})

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage KNX options."""

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
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
    if (x := user_input.get("control_template")) is not None or (
        x := user_input.get("value_template")
    ) is not None:
        template_str = x
    else:
        template_str = ""
    _LOGGER.debug("ws_start_preview msg: %s", msg)
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
