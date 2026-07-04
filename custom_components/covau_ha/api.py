"""CovaU customer portal API client.

Auth model (confirmed from HAR capture):
    POST /wp-json/covau/v1/login
        body: {"OssLogin": "<account number>", "Password": "<password>", "rememberMe": true}
    On success the portal sets four cookies via Set-Cookie:
        covauToken         (HttpOnly, ~2h)   - session token
        covauRefreshToken  (HttpOnly, ~20h)  - refresh token (refresh endpoint not yet captured)
        seqPartyId         (HttpOnly, ~2h)
        covauRememberMe    (~20h)
    No RSA/captcha step, no bearer/Authorization header - every later call just
    rides on the cookie jar, so a plain aiohttp.ClientSession with its default
    cookie jar handles this without any manual cookie plumbing.

Endpoints confirmed with full response shape:
    GET /wp-json/covau/v1/auth/ping
    GET /wp-json/covau/v1/lookup/customer-account
    GET /wp-json/covau/v1/lookup/customer-parent-child
    GET /wp-json/covau/v1/Customer
    GET /wp-json/covau/v1/utility/rate-details?seqProductItemId=<id>

Endpoints seen but NOT yet confirmed (response body wasn't captured in the
HAR - grab these via DevTools "Copy response" and I'll fill these in):
    GET /wp-json/covau/v1/usage/daily?seqProductItemId=<id>&startDate=YYYY-MM-DD&endDate=YYYY-MM-DD
    GET /wp-json/covau/v1/usage/customer-summary?seqProductItemId=<id>
    GET /wp-json/covau/v1/customer/billing
    GET /wp-json/covau/v1/Customer/transactions
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

import aiohttp

from .const import BASE_URL, DEFAULT_USAGE_DAYS, SENSITIVE_KEYS

_LOGGER = logging.getLogger(__name__)


class CovauApiError(Exception):
    """Base CovaU API error."""


class CovauAuthError(CovauApiError):
    """Authentication failed."""


class CovauSessionExpired(CovauAuthError):
    """The current session is not authorised (token expired)."""


def redact_sensitive(value: Any) -> Any:
    """Redact sensitive portal data for diagnostics."""
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if key in SENSITIVE_KEYS:
                redacted[key] = "**REDACTED**"
            else:
                redacted[key] = redact_sensitive(item)
        return redacted
    return value


def parse_covau_datetime(value: str) -> Any:
    """Parse a CovaU readDatetime string ("MM/DD/YYYY HH:MM:SS").

    Confirmed month-first from the Usage Details page JS (parseDateTimeMDY),
    despite CovaU being an AU site - don't swap to day-first.
    """
    from datetime import datetime

    date_part, _, time_part = value.partition(" ")
    month, day, year = (int(p) for p in date_part.split("/"))
    if time_part:
        hour, minute, second = (int(p) for p in time_part.split(":"))
    else:
        hour = minute = second = 0
    return datetime(year, month, day, hour, minute, second)


def build_daily_usage_summary(
    readings: list[dict[str, Any]] | None,
) -> dict[str, float]:
    """Sum readValue by category for a set of usage/daily readings.

    Categories are normalised to lowercase-alnum before matching, mirroring
    the normalizeCategory() function in the Usage Details page JS, so
    "Off-Peak", "OffPeak", "off peak" etc all collapse to the same key.
    """
    totals: dict[str, float] = {
        "peak": 0.0,
        "off_peak": 0.0,
        "standard_fit": 0.0,
    }
    if not isinstance(readings, list):
        # CovaU returns something other than a JSON array when there's no
        # usage data yet for the account (e.g. a dict like
        # {"success": false, "message": "..."}) rather than an empty [].
        # Treat anything non-list as "no readings" instead of crashing.
        return totals
    for reading in readings:
        if not isinstance(reading, dict):
            continue
        category = "".join(
            ch for ch in str(reading.get("category") or "").lower() if ch.isalnum()
        )
        value = float(reading.get("readValue") or 0)
        if category == "peak":
            totals["peak"] += value
        elif category == "offpeak":
            totals["off_peak"] += value
        elif category == "standardfit":
            totals["standard_fit"] += value
    return totals


class CovauClient:
    """Thin async client for the CovaU customer portal REST API."""

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        """Initialize the client.

        A dedicated ClientSession (with its own cookie jar) is created if one
        isn't supplied, since the whole auth model depends on cookie
        persistence across calls.
        """
        self._session = session or aiohttp.ClientSession()
        self._owns_session = session is None
        self.is_authenticated = False

    async def close(self) -> None:
        """Close the underlying session."""
        if self._owns_session:
            await self._session.close()

    async def _raw_request_json(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Make a request without any auth-retry handling."""
        url = f"{BASE_URL}{path}"
        async with self._session.request(
            method,
            url,
            json=json_body,
            params=params,
            headers={"Accept": "application/json"},
        ) as resp:
            if resp.status in (401, 403):
                raise CovauSessionExpired(f"CovaU session expired ({resp.status})")
            resp.raise_for_status()
            if resp.content_length == 0:
                return None
            return await resp.json(content_type=None)

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Make an authenticated request, re-raising session expiry for the caller to handle."""
        try:
            return await self._raw_request_json(
                method, path, json_body=json_body, params=params
            )
        except CovauSessionExpired:
            self.is_authenticated = False
            raise

    async def authenticate(self, account_no: str, password: str) -> Any:
        """Log in and establish the session cookies."""
        try:
            result = await self._raw_request_json(
                "POST",
                "/wp-json/covau/v1/login",
                json_body={
                    "OssLogin": account_no,
                    "Password": password,
                    "rememberMe": True,
                },
            )
        except aiohttp.ClientResponseError as err:
            if err.status in (401, 403):
                raise CovauAuthError("Invalid CovaU account number or password") from err
            raise CovauApiError(f"CovaU login failed: {err}") from err

        # TODO: confirm the actual shape of the login response body (283
        # bytes observed, not yet captured) - it may carry the seqPartyId or
        # a list of sites worth caching here rather than re-fetching via
        # lookup/customer-account.
        self.is_authenticated = True
        return result

    async def ping(self) -> bool:
        """Check whether the current session is still valid."""
        try:
            result = await self._request_json("GET", "/wp-json/covau/v1/auth/ping")
        except CovauSessionExpired:
            return False
        return bool(isinstance(result, dict) and result.get("success"))

    async def get_customer(self) -> dict[str, Any] | None:
        """Return the customer profile (name, address, contacts)."""
        return await self._request_json("GET", "/wp-json/covau/v1/Customer")

    async def get_customer_accounts(self) -> list[dict[str, Any]] | None:
        """Return the list of billable sites/services on the account.

        Response shape: [{"id": "398522", "code": "", "text": "POWER - <address>"}]
        The "id" here is the seqProductItemId used by usage/rate-details endpoints.
        """
        return await self._request_json(
            "GET", "/wp-json/covau/v1/lookup/customer-account"
        )

    async def get_customer_parent_child(self) -> list[dict[str, Any]] | None:
        """Return the account/contact relationship lookup."""
        return await self._request_json(
            "GET", "/wp-json/covau/v1/lookup/customer-parent-child"
        )

    async def get_rate_details(self, seq_product_item_id: str) -> dict[str, Any] | None:
        """Return the current tariff structure for a site.

        Response shape (confirmed):
        {
          "siteDetails": {"siteId": ..., "tcoDesc": ..., "terms": ...},
          "pricings": [
            {"usageDesc": "Daily Supply Charge", "unitDesc": "c/Day",
             "unitRate": "138.18", "unitRateIncGst": "151.998",
             "startDate": "01/07/2026", "endDate": null},
            ...
          ]
        }
        """
        return await self._request_json(
            "GET",
            "/wp-json/covau/v1/utility/rate-details",
            params={"seqProductItemId": seq_product_item_id},
        )

    async def get_usage_daily(
        self,
        seq_product_item_id: str,
        *,
        days: int = DEFAULT_USAGE_DAYS,
    ) -> list[dict[str, Any]] | None:
        """Return daily usage readings for a site over the given window.

        Response shape (confirmed via the Usage Details page JS):
        [{"readDatetime": "07/03/2026 00:00:00", "readValue": 4.812,
          "category": "Peak"}, ...]
        categories seen: Peak, OffPeak, StandardFiT.
        NOTE: readDatetime is MM/DD/YYYY (US month-first order) despite this
        being an AU site - parse accordingly, don't assume DD/MM/YYYY.
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        return await self._request_json(
            "GET",
            "/wp-json/covau/v1/usage/daily",
            params={
                "seqProductItemId": seq_product_item_id,
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
            },
        )

    async def get_usage_interval(
        self,
        seq_product_item_id: str,
        target_day: date,
    ) -> list[dict[str, Any]] | None:
        """Return hourly interval readings for a single day.

        Same shape as get_usage_daily but finer-grained categories: Peak,
        OffPeakEV, OffPeakFree, StandardFiT. Useful for aligning EV charging
        or battery automations to the actual off-peak windows.
        """
        start_date = target_day
        end_date = target_day + timedelta(days=1)
        return await self._request_json(
            "GET",
            "/wp-json/covau/v1/usage/interval",
            params={
                "seqProductItemId": seq_product_item_id,
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
            },
        )

    async def get_usage_summary(self, seq_product_item_id: str) -> dict[str, Any] | None:
        """Return the billing-cycle usage/cost summary for a site.

        Response shape (confirmed via the Usage Summary page JS):
        {
          "unitsPerDay": 12.4, "uomCode": "kWh", "costPerDay": 3.85,
          "lastInvoiceAmount": 142.10, "currentCost": 58.20,
          "projectedCost": 165.30, "warningMessage": null,
          "periodDays": 30, "currentDays": 12,
          "lastInvoiceDate": "...", "nextInvoiceDate": "..."
        }
        lastInvoiceDate/nextInvoiceDate may arrive as "/Date(1751500800000)/"
        (.NET JSON date format) or a plain date string - handle both.
        """
        return await self._request_json(
            "GET",
            "/wp-json/covau/v1/usage/customer-summary",
            params={"seqProductItemId": seq_product_item_id},
        )

    # -- customer/billing and Customer/transactions are wired to confirmed
    # -- URLs but the response body still hasn't been captured (both showed
    # -- as empty/small in the HAR - 282 and 27 bytes respectively). They
    # -- return raw JSON for now.

    async def get_billing(self) -> Any:
        """Return the customer billing summary."""
        return await self._request_json("GET", "/wp-json/covau/v1/customer/billing")

    async def get_transactions(self) -> Any:
        """Return customer transactions (payments/charges)."""
        return await self._request_json(
            "GET", "/wp-json/covau/v1/Customer/transactions"
        )
