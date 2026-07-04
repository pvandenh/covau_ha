"""Constants for the CovaU HA integration."""
from __future__ import annotations

from datetime import timedelta

DOMAIN = "covau_ha"

CONF_ACCOUNT_NO = "account_no"
CONF_PASSWORD = "password"

BASE_URL = "https://www.myaccount.covau.com.au"

DEFAULT_USAGE_DAYS = 31

ACCOUNT_UPDATE_INTERVAL = timedelta(minutes=30)

STORAGE_VERSION = 1

# Session cookies set on /wp-json/covau/v1/login. aiohttp's cookie jar
# carries these automatically once set - listed here only for reference
# and for diagnostics redaction.
SESSION_COOKIE_NAMES = {
    "covauToken",
    "covauRefreshToken",
    "seqPartyId",
    "covauRememberMe",
}

SENSITIVE_KEYS = {
    "OssLogin",
    "Password",
    "accountNo",
    "customerName",
    "postalAddress",
    "phoneStd",
    "phoneNo",
    "mobileStd",
    "mobileNo",
    "emailAddress",
    "address",
    "suburb",
    "postCode",
    "siteAddress",
    "contactName",
    "contactFirstName",
    "contactLastName",
    "contactPhoneNo",
    "contactEmailAddress",
    "seqPartyId",
    "covauToken",
    "covauRefreshToken",
    "covauRememberMe",
}
