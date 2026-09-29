"""Approver keys: every approval and every release is signed with the approver's passphrase.

The passphrase is never stored. Each person's key file holds a random salt and a
verifier, so the passphrase can be checked; the signing key is derived from the
passphrase with scrypt each time it is typed. Key files live outside the repo in
HOLDCO_KEYS_DIR (default ~/.holdco/keys), one per business and person, readable
only by their owner.

Without the passphrase nobody, and no agent, can produce a valid signature, so:

* ``send`` refuses an approval whose signature doesn't verify, and
* ``holdco outbox verify`` flags any outbox item that wasn't released with a
  valid signature, or whose files changed after release.

Keep the key store out of any agent's reach (runbook 09). If an agent ever
replaced a key file, the person's real passphrase would stop working: treat
"wrong passphrase" for a passphrase you know is right as an incident.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path

from holdco.config import Business, HoldcoError
from holdco.guard import ExecutionContext, require_human
from holdco.util import canonical_json, now_iso, sha256_file, slugify

SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1}
MIN_LENGTH = 12
_VERIFIER_LABEL = b"holdco:verifier:v1"


def keys_dir() -> Path:
    return Path(os.environ.get("HOLDCO_KEYS_DIR") or Path.home() / ".holdco" / "keys").expanduser()


def key_path(biz: Business, person: str) -> Path:
    return keys_dir() / biz.slug / f"{slugify(person)}.json"


def _derive(passphrase: str, salt: bytes, params: dict) -> bytes:
    return hashlib.scrypt(passphrase.encode("utf-8"), salt=salt, n=params["n"], r=params["r"], p=params["p"],
                          dklen=32, maxmem=64 * 1024 * 1024)


def _verifier(key: bytes) -> str:
    return hmac.new(key, _VERIFIER_LABEL, hashlib.sha256).hexdigest()


def add_key(biz: Business, person: str, passphrase: str, ctx: ExecutionContext,
            old_passphrase: str | None = None) -> dict:
    """Create (or, with the old passphrase, rotate) a person's approval key for one business."""
    require_human(ctx, biz, "keys add", person)
    if len(passphrase or "") < MIN_LENGTH:
        raise HoldcoError(f"Use a passphrase of at least {MIN_LENGTH} characters (a short sentence works well).")
    path = key_path(biz, person)
    if path.exists():
        if old_passphrase is None:
            raise HoldcoError(f"{person} already has a key for {biz.slug}. To change it, rotate it and enter the "
                              "old passphrase.")
        unlock(biz, person, old_passphrase)
    salt = secrets.token_bytes(16)
    verifier = _verifier(_derive(passphrase, salt, SCRYPT))
    record = {"business": biz.slug, "person": person, "created_at": now_iso(), "salt": salt.hex(),
              "scrypt": SCRYPT, "verifier": verifier,
              "key_id": hashlib.sha256(verifier.encode("utf-8")).hexdigest()[:16]}
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2)
        fh.write("\n")
    return record


def load_key(biz: Business, person: str) -> dict:
    path = key_path(biz, person)
    if not path.exists():
        raise HoldcoError(f"{person} has no approval key for {biz.slug}. Set one once, in your own terminal: "
                          f'python3 -m holdco keys add {biz.slug} --by "{person}"')
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def unlock(biz: Business, person: str, passphrase: str | None) -> tuple[bytes, dict]:
    record = load_key(biz, person)
    if not passphrase:
        raise HoldcoError(f"{person}'s passphrase is needed to sign this.")
    key = _derive(passphrase, bytes.fromhex(record["salt"]), record["scrypt"])
    if not hmac.compare_digest(_verifier(key), record["verifier"]):
        raise HoldcoError(f"Wrong passphrase for {person}. Nothing was signed. If you are sure it is right, "
                          "treat it as an incident: the key file may have been replaced (runbook 06).")
    return key, record


def sign(key: bytes, payload: dict) -> str:
    return hmac.new(key, canonical_json(payload).encode("utf-8"), hashlib.sha256).hexdigest()


def verify(key: bytes, payload: dict, signature: str | None) -> bool:
    return bool(signature) and hmac.compare_digest(sign(key, payload), signature)


def list_keys(biz: Business) -> list[dict]:
    folder = keys_dir() / biz.slug
    out = []
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        with open(path, encoding="utf-8") as fh:
            record = json.load(fh)
        out.append({"person": record["person"], "key_id": record["key_id"], "created_at": record["created_at"]})
    return out


def approval_payload(biz: Business, job: dict, approval: dict) -> dict:
    return {"business": biz.slug, "job": job["id"], "sha256": approval["sha256"], "by": approval["by"],
            "at": approval["at"], "draft_version": approval["draft_version"]}


def release_payload(manifest: dict) -> dict:
    return {k: manifest[k] for k in ("business", "job", "client", "approved_by", "approved_at", "sha256",
                                     "approval_signature", "sent_by", "sent_at", "files")}


def file_hashes(folder: Path, names: list[str]) -> dict:
    return {name: sha256_file(folder / name) for name in names}
