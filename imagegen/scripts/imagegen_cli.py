#!/usr/bin/env python3
"""Subscription-backed image generation CLI reusing the Codex ChatGPT login.

Zero dependencies (Python 3.10+ stdlib only). Generates or edits images via the
Codex backend's hosted image_generation tool, billed against the user's ChatGPT
subscription instead of the OpenAI API. This route is undocumented and may
change; failures surface as clear errors rather than falling back to API billing.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import mimetypes
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CODEX_BASE_URL = "https://chatgpt.com/backend-api/codex"
OAUTH_TOKEN_URL = "https://auth.openai.com/oauth/token"
OAUTH_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
DEFAULT_MODEL = "gpt-5.5"
MAX_REFERENCES = 5
DEFAULT_TIMEOUT = 300.0
MAX_REFERENCE_BYTES = 50 * 1024 * 1024

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class ImagegenError(Exception):
    pass


def die(message: str, code: int = 1) -> None:
    print(f"Error: {message}", file=sys.stderr)
    raise SystemExit(code)


# ---------------------------------------------------------------------------
# OAuth
# ---------------------------------------------------------------------------


def _jwt_claims(token: str | None) -> dict[str, Any]:
    if not token or token.count(".") < 2:
        return {}
    payload = token.split(".")[1]
    padded = payload + "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        claims = json.loads(decoded)
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return {}
    return claims if isinstance(claims, dict) else {}


def _account_id_from_id_token(id_token: Any) -> str | None:
    if not isinstance(id_token, str):
        return None
    claim = _jwt_claims(id_token).get("https://api.openai.com/auth")
    if isinstance(claim, dict):
        value = claim.get("chatgpt_account_id")
        return value if isinstance(value, str) and value else None
    return None


def _token_expiring(access_token: str, leeway_seconds: int = 300) -> bool:
    exp = _jwt_claims(access_token).get("exp")
    if not isinstance(exp, (int, float)):
        return False
    return exp <= time.time() + leeway_seconds


def _auth_file_path(auth_file: str | None) -> Path:
    if auth_file:
        return Path(auth_file).expanduser()
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        return Path(codex_home).expanduser() / "auth.json"
    return Path.home() / ".codex" / "auth.json"


def _load_auth(auth_file: str | None) -> dict[str, Any]:
    path = _auth_file_path(auth_file)
    try:
        data = json.loads(path.read_text("utf-8"))
    except FileNotFoundError:
        raise ImagegenError(
            f"Codex auth file not found: {path}. Run `codex login` and choose ChatGPT."
        ) from None
    except json.JSONDecodeError:
        raise ImagegenError(f"Codex auth file is not valid JSON: {path}") from None
    if not isinstance(data, dict):
        raise ImagegenError(f"Codex auth file must contain a JSON object: {path}")
    return data


def _write_auth_atomic(auth_file: str | None, auth: dict[str, Any]) -> None:
    path = _auth_file_path(auth_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(auth, indent=2) + "\n")
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _refresh_tokens(refresh_token: str, timeout: float) -> dict[str, Any]:
    body = json.dumps(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": OAUTH_CLIENT_ID,
            "scope": "openid profile email offline_access",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        OAUTH_TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=min(timeout, 60)) as resp:
            refreshed = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise ImagegenError(
            f"Token refresh failed (HTTP {exc.code}): {detail}. Run `codex login` again."
        ) from None
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        raise ImagegenError(f"Token refresh failed: {exc}") from None
    if not isinstance(refreshed, dict) or not isinstance(refreshed.get("access_token"), str):
        raise ImagegenError("Token refresh did not return an access token.")
    return refreshed


def oauth_headers(auth_file: str | None, timeout: float) -> dict[str, str]:
    auth = _load_auth(auth_file)
    tokens = auth.get("tokens")
    if not isinstance(tokens, dict):
        raise ImagegenError("Codex ChatGPT auth not found. Run `codex login` and choose ChatGPT.")

    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")
    id_token = tokens.get("id_token")
    account_id = tokens.get("account_id") or _account_id_from_id_token(id_token)

    if not isinstance(access_token, str) or not access_token:
        raise ImagegenError("Codex access token not found. Run `codex login` and choose ChatGPT.")

    if _token_expiring(access_token):
        if not isinstance(refresh_token, str) or not refresh_token:
            raise ImagegenError("Codex refresh token not found. Run `codex login` again.")
        refreshed = _refresh_tokens(refresh_token, timeout)
        tokens["access_token"] = refreshed["access_token"]
        if isinstance(refreshed.get("refresh_token"), str) and refreshed["refresh_token"]:
            tokens["refresh_token"] = refreshed["refresh_token"]
        if isinstance(refreshed.get("id_token"), str) and refreshed["id_token"]:
            tokens["id_token"] = refreshed["id_token"]
        account_id = _account_id_from_id_token(refreshed.get("id_token")) or account_id
        if account_id:
            tokens["account_id"] = account_id
        auth["last_refresh"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        _write_auth_atomic(auth_file, auth)
        access_token = tokens["access_token"]

    if not account_id:
        raise ImagegenError("Codex account id not found. Run `codex login` and choose ChatGPT.")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "ChatGPT-Account-Id": account_id,
        "OpenAI-Beta": "responses=experimental",
    }
    claim = _jwt_claims(id_token if isinstance(id_token, str) else None).get(
        "https://api.openai.com/auth"
    )
    if isinstance(claim, dict) and claim.get("chatgpt_account_is_fedramp"):
        headers["X-OpenAI-Fedramp"] = "true"
    return headers


# ---------------------------------------------------------------------------
# Reference images
# ---------------------------------------------------------------------------


def _reference_data_url(path_str: str) -> str:
    path = Path(path_str).expanduser()
    if not path.is_file():
        raise ImagegenError(f"Reference image not found: {path}")
    size = path.stat().st_size
    if size == 0:
        raise ImagegenError(f"Reference image is empty: {path}")
    if size > MAX_REFERENCE_BYTES:
        raise ImagegenError(f"Reference image exceeds 50MB: {path}")
    data = path.read_bytes()
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    if not mime.startswith("image/"):
        raise ImagegenError(f"Reference file is not an image: {path}")
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


# ---------------------------------------------------------------------------
# Codex Responses request
# ---------------------------------------------------------------------------


def build_payload(args: argparse.Namespace, references: list[str]) -> dict[str, Any]:
    content: list[dict[str, Any]] = [{"type": "input_text", "text": args.prompt}]
    for path_str in references:
        content.append({"type": "input_image", "image_url": _reference_data_url(path_str)})

    tool: dict[str, Any] = {
        "type": "image_generation",
        "output_format": "png",
        "quality": args.quality,
    }
    if args.size != "auto":
        tool["size"] = args.size

    return {
        "model": args.model,
        "instructions": (
            "You are an image generation assistant running inside the Codex backend. "
            "Always satisfy the request by invoking the image_generation tool exactly once. "
            "Do not respond with text only."
        ),
        "input": [{"role": "user", "content": content}],
        "tools": [tool],
        "tool_choice": {"type": "image_generation"},
        "stream": True,
        "store": False,
    }


def parse_sse_image_result(stream: bytes) -> str:
    last_event: dict[str, Any] | None = None
    for raw_line in stream.decode("utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line.startswith("data:"):
            continue
        data = line[len("data:"):].strip()
        if data == "[DONE]":
            break
        try:
            event = json.loads(data)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        event_type = event.get("type")
        if event_type in {"response.failed", "response.incomplete"}:
            last_event = event
        item = event.get("item")
        if isinstance(item, dict) and item.get("type") == "image_generation_call":
            result = item.get("result")
            if isinstance(result, str) and result:
                return result
    if last_event is not None:
        response = last_event.get("response")
        error = response.get("error") if isinstance(response, dict) else None
        if isinstance(error, dict):
            code = error.get("code") or "error"
            message = error.get("message") or "image generation failed"
            raise ImagegenError(f"Codex backend returned {code}: {message}")
    raise ImagegenError("Codex backend stream ended without an image result.")


def call_codex(args: argparse.Namespace, references: list[str]) -> bytes:
    payload = build_payload(args, references)
    headers = oauth_headers(args.auth_file, args.timeout)
    headers["Content-Type"] = "application/json"
    headers["Accept"] = "text/event-stream"
    headers["originator"] = "imagegen-skill"

    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    req = urllib.request.Request(
        f"{args.base_url.rstrip('/')}/responses",
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=args.timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:600]
        if exc.code == 401:
            detail = "authentication failed; run `codex login` again. " + detail
        raise ImagegenError(f"Codex backend request failed (HTTP {exc.code}): {detail}") from None
    except urllib.error.URLError as exc:
        raise ImagegenError(f"Codex backend request failed: {exc.reason}") from None

    result_b64 = parse_sse_image_result(raw)
    try:
        image = base64.b64decode(result_b64, validate=True)
    except (binascii.Error, ValueError):
        raise ImagegenError("Codex backend returned invalid base64 image data.") from None
    if not image.startswith(PNG_MAGIC):
        raise ImagegenError("Codex backend returned data that is not a valid PNG.")
    return image


# ---------------------------------------------------------------------------
# Output handling
# ---------------------------------------------------------------------------


def pick_output_path(requested: Path, force: bool) -> Path:
    if force or not requested.exists():
        return requested
    stem, suffix = requested.stem, requested.suffix
    for n in range(2, 1000):
        candidate = requested.with_name(f"{stem}-v{n}{suffix}")
        if not candidate.exists():
            return candidate
    raise ImagegenError(f"Could not find a non-conflicting filename for {requested}")


def png_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 24 or not data.startswith(PNG_MAGIC):
        return None
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


# ---------------------------------------------------------------------------
# Size validation
# ---------------------------------------------------------------------------


def validate_size(size: str) -> None:
    if size == "auto":
        return
    parts = size.lower().split("x")
    if len(parts) != 2 or not all(p.isdigit() and int(p) > 0 for p in parts):
        raise ImagegenError("size must be auto or WIDTHxHEIGHT, e.g. 1536x1024.")
    width, height = int(parts[0]), int(parts[1])
    if max(width, height) > 3840:
        raise ImagegenError("size max edge must be <= 3840px.")
    if width % 16 or height % 16:
        raise ImagegenError("size width and height must be multiples of 16px.")
    if max(width, height) / min(width, height) > 3:
        raise ImagegenError("size long-to-short ratio must not exceed 3:1.")
    pixels = width * height
    if not (655_360 <= pixels <= 8_294_400):
        raise ImagegenError("size total pixels must be between 655,360 and 8,294,400.")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_generate(args: argparse.Namespace) -> int:
    if args.prompt_file:
        prompt_path = Path(args.prompt_file).expanduser()
        if not prompt_path.is_file():
            raise ImagegenError(f"Prompt file not found: {prompt_path}")
        args.prompt = prompt_path.read_text("utf-8").strip()
    if not args.prompt:
        raise ImagegenError("Missing prompt. Use --prompt or --prompt-file.")
    validate_size(args.size)

    references = args.reference or []
    if len(references) > MAX_REFERENCES:
        raise ImagegenError(f"At most {MAX_REFERENCES} reference images are supported.")

    out = Path(args.out).expanduser()
    if out.suffix.lower() != ".png":
        out = out.with_suffix(".png")

    if args.dry_run:
        result = {
            "dry_run": True,
            "out": str(out),
            "model": args.model,
            "quality": args.quality,
            "size": args.size,
            "references": references,
            "prompt_chars": len(args.prompt),
        }
        print(json.dumps(result, indent=2))
        return 0

    started = time.time()
    image = call_codex(args, references)
    elapsed = time.time() - started

    saved = pick_output_path(out, args.force)
    saved.parent.mkdir(parents=True, exist_ok=True)
    saved.write_bytes(image)

    dims = png_dimensions(image)
    result = {
        "status": "completed",
        "out": str(saved.resolve()),
        "versioned": saved != out,
        "mime": "image/png",
        "bytes": len(image),
        "width": dims[0] if dims else None,
        "height": dims[1] if dims else None,
        "references": len(references),
        "billing": "chatgpt-subscription",
        "elapsed_seconds": round(elapsed, 1),
    }
    print(json.dumps(result, indent=2))
    return 0


def cmd_auth_status(args: argparse.Namespace) -> int:
    path = _auth_file_path(args.auth_file)
    if not path.exists():
        print(json.dumps({"authenticated": False, "auth_file": str(path)}, indent=2))
        return 1
    try:
        headers = oauth_headers(args.auth_file, 30.0)
    except ImagegenError as exc:
        print(json.dumps({"authenticated": False, "auth_file": str(path), "error": str(exc)}, indent=2))
        return 1
    result = {
        "authenticated": True,
        "auth_file": str(path),
        "account_id_present": bool(headers.get("ChatGPT-Account-Id")),
        "plan_hint": "codex login uses ChatGPT OAuth; generation requires a paid plan",
    }
    print(json.dumps(result, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="imagegen",
        description="Generate images via the Codex ChatGPT image backend (no API key).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="Generate an image from a prompt, optionally with references.")
    gen.add_argument("--prompt")
    gen.add_argument("--prompt-file")
    gen.add_argument("--reference", action="append", help="Reference image path (repeatable, max 5).")
    gen.add_argument("--out", required=True, help="Output PNG path.")
    gen.add_argument("--quality", choices=["low", "medium", "high", "auto"], default="auto")
    gen.add_argument("--size", default="auto", help="auto or WIDTHxHEIGHT (gpt-image-2 constraints).")
    gen.add_argument("--model", default=os.environ.get("IMAGEGEN_MODEL", DEFAULT_MODEL),
                     help="Codex orchestration model (default: gpt-5.5).")
    gen.add_argument("--base-url", default=os.environ.get("IMAGEGEN_BASE_URL", CODEX_BASE_URL))
    gen.add_argument("--auth-file", help="Override Codex auth.json path.")
    gen.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    gen.add_argument("--force", action="store_true", help="Allow overwriting the output file.")
    gen.add_argument("--dry-run", action="store_true", help="Print the planned request without calling the backend.")
    gen.set_defaults(func=cmd_generate)

    status = sub.add_parser("auth-status", help="Check Codex ChatGPT authentication state.")
    status.add_argument("--auth-file", help="Override Codex auth.json path.")
    status.set_defaults(func=cmd_auth_status)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except ImagegenError as exc:
        die(str(exc))
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
