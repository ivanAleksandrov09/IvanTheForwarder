"""Send / withdraw the public profile. Owner: lead.

ASSUMPTION: the central index is ours and does not exist yet, so this is the API it should offer:
  PUT    {NETWORK_URL}/api/v1/companies/{company_uid}   body = PublicCompanyProfile JSON, `Authorization: Bearer {NETWORK_TOKEN}`
  DELETE {NETWORK_URL}/api/v1/companies/{company_uid}   withdraw: the central side must delete everything it holds
With NETWORK_URL empty the profile is written to data/runtime/network/<company_uid>.json instead, so the whole flow can be tried
without a server. Callers must check consent first; this module only transports.
"""

import httpx

from app.core.config import Settings
from app.schemas import PublicCompanyProfile


def _url(s: Settings, uid: str) -> str:
    return f"{s.network_url.rstrip('/')}/api/v1/companies/{uid}"


def _headers(s: Settings) -> dict[str, str]:
    return {"Authorization": f"Bearer {s.network_token}"} if s.network_token else {}


def _check(response: httpx.Response) -> None:
    try:
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"central index request failed: {exc}") from exc


def publish(profile: PublicCompanyProfile, s: Settings) -> str:
    if not s.network_url:
        path = s.runtime_dir / "network" / f"{profile.company_uid}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
        return "published to a local file (no central server configured)"
    try:
        _check(httpx.put(_url(s, profile.company_uid), json=profile.model_dump(mode="json"), headers=_headers(s), timeout=20.0))
    except httpx.HTTPError as exc:
        raise RuntimeError(f"central index unreachable: {exc}") from exc
    return "published to the central index"


def withdraw(uid: str, s: Settings) -> str:
    if not s.network_url:
        (s.runtime_dir / "network" / f"{uid}.json").unlink(missing_ok=True)
        return "withdrawn (local file removed)"
    try:
        _check(httpx.delete(_url(s, uid), headers=_headers(s), timeout=20.0))
    except httpx.HTTPError as exc:
        raise RuntimeError(f"central index unreachable: {exc}") from exc
    return "withdrawn from the central index"
