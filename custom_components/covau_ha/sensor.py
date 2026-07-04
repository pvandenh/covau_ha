"""Sensor platform for CovaU HA."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CovauCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up CovaU sensors from a config entry."""
    coordinator: CovauCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = []

    services = (coordinator.data or {}).get("services", {})
    for seq_product_item_id in services:
        entities.extend(
            [
                CovauCycleUsageTotalSensor(coordinator, entry, seq_product_item_id),
                CovauCostPerDaySensor(coordinator, entry, seq_product_item_id),
                CovauCurrentCycleCostSensor(coordinator, entry, seq_product_item_id),
                CovauProjectedCycleCostSensor(coordinator, entry, seq_product_item_id),
                CovauLastInvoiceAmountSensor(coordinator, entry, seq_product_item_id),
                CovauBillingCycleDaySensor(coordinator, entry, seq_product_item_id),
                CovauDailyPeakUsageSensor(coordinator, entry, seq_product_item_id),
                CovauDailyOffPeakUsageSensor(coordinator, entry, seq_product_item_id),
                CovauDailyStandardFitSensor(coordinator, entry, seq_product_item_id),
                CovauDailyPeakCostSensor(coordinator, entry, seq_product_item_id),
                CovauDailyOffPeakCostSensor(coordinator, entry, seq_product_item_id),
                CovauDailyStandardFitCreditSensor(coordinator, entry, seq_product_item_id),
                CovauDailySupplyChargeCostSensor(coordinator, entry, seq_product_item_id),
            ]
        )

    async_add_entities(entities)


class CovauSensorBase(CoordinatorEntity[CovauCoordinator], SensorEntity):
    """Common base for CovaU sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: CovauCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=self._entry.title,
            manufacturer="CovaU",
        )


class CovauServiceSensorBase(CovauSensorBase):
    """Base for sensors scoped to a single service/site (seqProductItemId)."""

    def __init__(
        self,
        coordinator: CovauCoordinator,
        entry: ConfigEntry,
        seq_product_item_id: str,
    ) -> None:
        super().__init__(coordinator, entry)
        self._seq_product_item_id = seq_product_item_id
        # NOTE: unique_id is built from self._key (not self._attr_translation_key).
        # The period_* sensors below deliberately changed _key from the old
        # daily_* naming, so those will show up as new entities and the old
        # daily_* ones will go unavailable/orphaned - delete those manually.
        self._attr_unique_id = (
            f"{entry.entry_id}_{seq_product_item_id}_{self._key}"
        )

    @property
    def _key(self) -> str:
        raise NotImplementedError

    @property
    def _service(self) -> dict[str, Any]:
        return (self.coordinator.data or {}).get("services", {}).get(
            self._seq_product_item_id, {}
        )

    @property
    def _usage_summary(self) -> dict[str, Any]:
        return self._service.get("usage_summary") or {}

    @property
    def _daily_totals(self) -> dict[str, Any]:
        return self._service.get("daily_usage_totals") or {}

    @property
    def available(self) -> bool:
        return super().available and bool(self._service)


class CovauCycleUsageTotalSensor(CovauServiceSensorBase):
    """Total usage consumed so far in the current billing cycle.

    CovaU's API field is misleadingly named "unitsPerDay" but is actually
    a cycle-to-date total, not a per-day rate - confirmed by comparing it
    against currentDays (e.g. 39.16 kWh at currentDays=3 is a plausible
    3-day household total, not a plausible per-day figure).

    This total also lags "currentDays" by roughly one day: on currentDays=3
    the totals reflected only 2 finalized meter-read days, not 3. Treat
    this value as "as of the most recently finalized meter day", not
    "as of right now" - see days_behind_cycle_counter below.
    """

    _attr_translation_key = "cycle_usage_total"
    _key = "cycle_usage_total"

    @property
    def native_value(self) -> float | None:
        return self._usage_summary.get("unitsPerDay")

    @property
    def native_unit_of_measurement(self) -> str | None:
        return self._usage_summary.get("uomCode") or "kWh"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            # CovaU's currentDays counts calendar days elapsed in the
            # billing cycle (including today), but this usage total
            # typically only covers finalized meter-read days, which lags
            # currentDays by roughly one day. Not a guaranteed offset -
            # just a documented observed quirk to watch for.
            "billing_cycle_day_counter": self._usage_summary.get("currentDays"),
        }


class CovauCostPerDaySensor(CovauServiceSensorBase):
    """Average daily cost for the current billing cycle."""

    _attr_translation_key = "cost_per_day"
    _attr_native_unit_of_measurement = "$"
    _key = "cost_per_day"

    @property
    def native_value(self) -> float | None:
        return self._usage_summary.get("costPerDay")


class CovauCurrentCycleCostSensor(CovauServiceSensorBase):
    """Cost accrued so far in the current billing cycle."""

    _attr_translation_key = "current_cycle_cost"
    _attr_native_unit_of_measurement = "$"
    _key = "current_cycle_cost"

    @property
    def native_value(self) -> float | None:
        return self._usage_summary.get("currentCost")


class CovauProjectedCycleCostSensor(CovauServiceSensorBase):
    """Projected cost for the full current billing cycle."""

    _attr_translation_key = "projected_cycle_cost"
    _attr_native_unit_of_measurement = "$"
    _key = "projected_cycle_cost"

    @property
    def native_value(self) -> float | None:
        return self._usage_summary.get("projectedCost")


class CovauLastInvoiceAmountSensor(CovauServiceSensorBase):
    """Amount of the most recent invoice."""

    _attr_translation_key = "last_invoice_amount"
    _attr_native_unit_of_measurement = "$"
    _key = "last_invoice_amount"

    @property
    def native_value(self) -> float | None:
        return self._usage_summary.get("lastInvoiceAmount")


class CovauBillingCycleDaySensor(CovauServiceSensorBase):
    """Day number within the current billing cycle (e.g. 12 of 30)."""

    _attr_translation_key = "todays_billing_day"
    _key = "billing_cycle_day"

    @property
    def native_value(self) -> int | None:
        value = self._usage_summary.get("currentDays")
        if value is None:
            return None
        try:
            return int(round(float(value)))
        except (TypeError, ValueError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "period_days": self._usage_summary.get("periodDays"),
            # "DD Mon" with no year, as returned by the portal.
            "last_invoice_date": self._usage_summary.get("lastInvoiceDate"),
            "next_invoice_date": self._usage_summary.get("nextInvoiceDate"),
            "warning_message": self._usage_summary.get("warningMessage"),
            "usage_message": self._usage_summary.get("usageMessage"),
        }


class CovauDailyPeakUsageSensor(CovauServiceSensorBase):
    """Total peak usage over the current billing period."""

    _attr_translation_key = "period_peak_usage"
    _attr_native_unit_of_measurement = "kWh"
    _key = "period_peak_usage"

    @property
    def native_value(self) -> float | None:
        return self._daily_totals.get("peak")


class CovauDailyOffPeakUsageSensor(CovauServiceSensorBase):
    """Total off-peak usage over the current billing period."""

    _attr_translation_key = "period_off_peak_usage"
    _attr_native_unit_of_measurement = "kWh"
    _key = "period_off_peak_usage"

    @property
    def native_value(self) -> float | None:
        return self._daily_totals.get("off_peak")


class CovauDailyStandardFitSensor(CovauServiceSensorBase):
    """Total standard feed-in (solar export) over the current billing period."""

    _attr_translation_key = "period_standard_fit"
    _attr_native_unit_of_measurement = "kWh"
    _key = "period_standard_fit"

    @property
    def native_value(self) -> float | None:
        return self._daily_totals.get("standard_fit")


class CovauDailyPeakCostSensor(CovauServiceSensorBase):
    """Total peak cost over the current billing period, from netAmount."""

    _attr_translation_key = "period_peak_cost"
    _attr_native_unit_of_measurement = "$"
    _key = "period_peak_cost"

    @property
    def native_value(self) -> float | None:
        return self._daily_totals.get("peak_cost")


class CovauDailyOffPeakCostSensor(CovauServiceSensorBase):
    """Total off-peak cost over the current billing period, from netAmount."""

    _attr_translation_key = "period_off_peak_cost"
    _attr_native_unit_of_measurement = "$"
    _key = "period_off_peak_cost"

    @property
    def native_value(self) -> float | None:
        return self._daily_totals.get("off_peak_cost")


class CovauDailyStandardFitCreditSensor(CovauServiceSensorBase):
    """Total solar export credit over the current billing period.

    Naturally negative-or-zero, since a feed-in credit reduces the bill.
    """

    _attr_translation_key = "period_standard_fit_credit"
    _attr_native_unit_of_measurement = "$"
    _key = "period_standard_fit_credit"

    @property
    def native_value(self) -> float | None:
        return self._daily_totals.get("standard_fit_credit")


class CovauDailySupplyChargeCostSensor(CovauServiceSensorBase):
    """Total supply charge cost over the current billing period."""

    _attr_translation_key = "period_supply_charge_cost"
    _attr_native_unit_of_measurement = "$"
    _key = "period_supply_charge_cost"

    @property
    def native_value(self) -> float | None:
        return self._daily_totals.get("supply_charge_cost")