# CovaU HA

A custom [Home Assistant](https://www.home-assistant.io/) integration that pulls billing, usage, and tariff data from the [CovaU](https://www.myaccount.covau.com.au) customer portal into Home Assistant sensors.

> **Status:** Early release (v0.1.0). The CovaU portal has no public/documented API — this integration talks to the same internal endpoints the customer web portal uses, reverse-engineered from browser traffic. Endpoints may change without notice.

## Features

- Logs in to the CovaU customer portal using your account number and password (cookie-based session, auto re-authenticates on expiry)
- Automatically discovers all billable sites/services on your account
- Polls every 30 minutes and exposes the following sensors **per service**:

| Sensor | Description | Unit |
|---|---|---|
| Current Cycle Usage | Total usage consumed so far in the current billing cycle | kWh |
| Average Cost Per Day | Average daily cost for the current billing cycle | $ |
| Current Cycle Cost | Cost accrued so far in the current billing cycle | $ |
| Projected Cycle Cost | Projected cost for the full current billing cycle | $ |
| Last Invoice Amount | Amount of the most recent invoice | $ |
| Todays Billing Day | Day number within the current billing cycle (e.g. 12 of 30), whole number | — |
| Period Peak Usage | Total peak usage over the current billing period | kWh |
| Period Off-Peak Usage | Total off-peak usage over the current billing period | kWh |
| Period Standard FiT | Total standard feed-in (solar export) over the current billing period | kWh |
| Period Peak Cost | Total peak cost over the current billing period | $ |
| Period Off-Peak Cost | Total off-peak cost over the current billing period | $ |
| Period Standard FiT Credit | Total solar export credit over the current billing period (negative-or-zero) | $ |
| Period Supply Charge Cost | Total supply charge cost over the current billing period | $ |

The **Todays Billing Day** sensor also exposes `period_days`, `last_invoice_date`, `next_invoice_date`, `warning_message`, and `usage_message` as extra attributes.

The **Current Cycle Usage** sensor also exposes `billing_cycle_day_counter` as an extra attribute — see [Known limitations](#known-limitations) for why this can lag the usage total by roughly a day.

> **Note on the "Period ..." sensors:** these were previously named "Daily ..." (e.g. "Daily Peak Usage"), which was misleading since the values are billing-cycle-to-date totals, not daily figures. If you're upgrading from an earlier version, the old `daily_*` entities will go unavailable after this change and can be deleted from **Settings → Devices & Services → Entities** — the new `period_*` entities are separate, freshly-created ones (different `unique_id`), not renames of the old ones.

## Installation

### Manual

1. Copy the `covau_ha` folder into your Home Assistant `custom_components` directory:
   ```
   custom_components/covau_ha/
   ```
2. Restart Home Assistant.

### HACS (custom repository)

1. In HACS, add this repository as a custom integration repository.
2. Search for "CovaU HA" and install.
3. Restart Home Assistant.

## Configuration

Configuration is done entirely through the Home Assistant UI:

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **CovaU HA**.
3. Enter your CovaU customer portal **account number** and **password** (the same credentials you use at [myaccount.covau.com.au](https://www.myaccount.covau.com.au)).

If you have multiple services/sites on your account, sensors will be created for each one automatically.

## How it works

The integration authenticates against the CovaU portal's `/wp-json/covau/v1/login` endpoint, which sets session cookies used for all subsequent requests — there's no API key or bearer token involved. A `DataUpdateCoordinator` polls the portal every 30 minutes, re-authenticating automatically if the session has expired.

For each discovered service, the integration fetches:
- Current tariff/rate details
- Billing-cycle usage and cost summary
- Recent daily usage readings, broken down by rate category (Peak / Off-Peak / Standard Feed-in), summed into billing-period totals

## Known limitations

- The CovaU login response body and a few endpoints (`customer/billing`, `Customer/transactions`) haven't been fully mapped yet — they're wired up but not yet surfaced as sensors.
- No refresh-token flow is implemented; the integration simply re-logs in with your stored credentials when the session expires.
- **Cycle usage/cost data lags by roughly a day.** CovaU's billing-cycle day counter (**Todays Billing Day**) appears to count today as an elapsed day, but the usage/cost totals only reflect fully finalized meter reads — so on day 3 of your cycle, the totals may only cover 2 days of data. Treat **Current Cycle Usage** and the **Period ...** sensors as "as of the most recently finalized meter day," not "as of right now."
- Since this relies on an undocumented, internal API, a portal-side change could break the integration until it's updated.

## Diagnostics & privacy

Sensitive fields (login credentials, session cookies, and customer PII such as name, address, phone, and email) are redacted before being included in any diagnostics output.

## Disclaimer

This is an unofficial, community-built integration and is not affiliated with or endorsed by CovaU. Use at your own risk.

## License

MIT
