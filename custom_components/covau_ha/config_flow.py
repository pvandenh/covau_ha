"""Config flow for CovaU HA."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .api import CovauAuthError, CovauClient
from .const import CONF_ACCOUNT_NO, CONF_PASSWORD, DOMAIN

_LOGGER = logging.getLogger(__name__)


class CovauConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for CovaU HA."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            account_no = str(user_input[CONF_ACCOUNT_NO]).strip()
            password = str(user_input[CONF_PASSWORD])

            await self.async_set_unique_id(account_no)
            self._abort_if_unique_id_configured()

            client = CovauClient()
            try:
                await client.authenticate(account_no, password)
            except CovauAuthError:
                errors["base"] = "invalid_auth"
            except Exception as err:  # noqa: BLE001 - HA config flow maps this.
                _LOGGER.exception("Unexpected CovaU setup failure: %s", err)
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"CovaU ({account_no})",
                    data={
                        CONF_ACCOUNT_NO: account_no,
                        CONF_PASSWORD: password,
                    },
                )
            finally:
                await client.close()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACCOUNT_NO): str,
                    vol.Required(CONF_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    ),
                }
            ),
            errors=errors,
        )
