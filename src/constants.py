from __future__ import annotations

BASE_URL = "https://agent.superyachtnetwork.com"
LOGIN_URL = f"{BASE_URL}/"
OWNER_REPORT_URL = f"{BASE_URL}/yaycontact/vessel/owners/person/index.htm"

OWNER_DETAIL_URL = (
    f"{BASE_URL}/yaycontact/vessel/owners/person/detail.htm?id={{person_id}}"
)
OWNER_DETAILS_EDIT_URL = (
    f"{BASE_URL}/yaycontact/vessel/owners/person/edit/details.htm"
    "?id={person_id}&channel_id=8"
)
OWNER_SOCIAL_EDIT_URL = (
    f"{BASE_URL}/yaycontact/base-entity/edit/social.htm"
    "?id={person_id}&channel_id=8"
)

SCHEMA_VERSION = 1
DEFAULT_TIMEOUT_SECONDS = 30
HTTP_TIMEOUT_SECONDS = 45
