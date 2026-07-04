
# CovaU HA
 
A custom [Home Assistant](https://www.home-assistant.io/) integration that pulls billing, usage, and tariff data from the [CovaU](https://www.myaccount.covau.com.au) customer portal into Home Assistant sensors.
 
> **Status:** Early release (v0.1.0). The CovaU portal has no public/documented API — this integration talks to the same internal endpoints the customer web portal uses, reverse-engineered from browser traffic. Endpoints may change without notice.
 
## Features
 
- Logs in to the CovaU customer portal using your account number and password (cookie-based session, auto re-authenticates on expiry)
- Automatically discovers all billable sites/services on your account
- Polls every 30 minutes and exposes the following sensors **per service**:
| Sensor | Description | Unit |
|---|---|---|
| Recent Usage Per Day | Average daily usage over the recent billing window | kWh |
| Recent Cost Per Day | Average daily cost over the recent billing window | AUD |
| Current Cycle Cost | Cost accrued so far in the current billing cycle | AUD |
| Projected Cycle Cost | Projected cost for the full current billing cycle | AUD |
| Last Invoice Amount | Amount of the most recent invoice | AUD |
| Billing Cycle Day | Day number within the current billing cycle (e.g. 12 of 30) | — |
| Daily Peak Usage | Total peak usage over the recent daily window | kWh |
| Daily Off-Peak Usage | Total off-peak usage over the recent daily window | kWh |
| Daily Standard FiT | Total standard feed-in (solar export) over the recent daily window | kWh |
 
The **Billing Cycle Day** sensor also exposes `period_days`, `last_invoice_date`, `next_invoice_date`, and `warning_message` as extra attributes.
