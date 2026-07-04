"""Data update coordinator for CovaU HA."""
from __future__ import annotations

import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    CovauApiError,
    CovauClient,
    CovauSessionExpired,
    build_daily_usage_summary,
)
from .const import (
    ACCOUNT_UPDATE_INTERVAL,
    CONF_ACCOUNT_NO,
    CONF_PASSWORD,
    DEFAULT_USAGE_DAYS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class CovauCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for fetching CovaU portal data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=ACCOUNT_UPDATE_INTERVAL,
        )

        self.entry = entry
        self.account_no = entry.data[CONF_ACCOUNT_NO]
        self.password = entry.data[CONF_PASSWORD]
        self.client = CovauClient()

    async def async_shutdown(self) -> None:
        """Close resources."""
        await self.client.close()

    async def _ensure_authenticated(self) -> None:
        """Log in if we don't currently have a valid session.

        The covauToken cookie is only valid for ~2 hours, well inside the
        30-minute poll interval, but a re-login can never hurt - authenticate()
        is idempotent from the coordinator's point of view.
        """
        if self.client.is_authenticated and await self.client.ping():
            return
        await self.client.authenticate(self.account_no, self.password)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch CovaU data, retrying once on session expiry."""
        try:
            return await self._fetch_all()
        except CovauSessionExpired:
            _LOGGER.debug("CovaU session expired mid-cycle, re-authenticating")
            try:
                await self.client.authenticate(self.account_no, self.password)
                return await self._fetch_all()
            except CovauApiError as err:
                raise UpdateFailed(f"Unable to re-authenticate with CovaU: {err}") from err
        except CovauApiError as err:
            raise UpdateFailed(f"Unable to fetch CovaU data: {err}") from err

    async def _fetch_all(self) -> dict[str, Any]:
        await self._ensure_authenticated()

        customer = await self.client.get_customer()
        accounts = await self.client.get_customer_accounts()
        if not isinstance(accounts, list):
            _LOGGER.warning(
                "CovaU lookup/customer-account returned unexpected shape: %r",
                accounts,
            )
            accounts = []

        services: dict[str, dict[str, Any]] = {}
        for account in accounts:
            if not isinstance(account, dict):
                continue
            seq_product_item_id = str(account.get("id") or "")
            if not seq_product_item_id:
                continue

            rate_details = await self.client.get_rate_details(seq_product_item_id)
            usage_summary = await self.client.get_usage_summary(seq_product_item_id)
            daily_readings = await self.client.get_usage_daily(
                seq_product_item_id, days=DEFAULT_USAGE_DAYS
            )

            services[seq_product_item_id] = {
                "account": account,
                "rate_details": rate_details,
                "usage_summary": usage_summary,
                "daily_usage_totals": build_daily_usage_summary(daily_readings),
            }

        return {
            "customer": customer,
            "services": services,
            "last_update": time.time(),
        }
