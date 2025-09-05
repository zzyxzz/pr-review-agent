import hashlib
import hmac
import json

import redis
from fastapi import FastAPI, HTTPException, Request

from app.config import Config, setup_logging

logger = setup_logging()

app = FastAPI()
redis_client = redis.from_url(Config.REDIS_URL)


def verify_signature(payload_body: dict, secret_token: str, signature_header: str):
    if not signature_header:
        raise HTTPException(
            status_code=403, detail="x-hub-signature-256 header is missing!"
        )
    hash_object = hmac.new(
        secret_token.encode("utf-8"), msg=payload_body, digestmod=hashlib.sha256
    )
    expected_signature = "sha256=" + hash_object.hexdigest()
    if not hmac.compare_digest(expected_signature, signature_header):
        raise HTTPException(status_code=403, detail="Request signatures didn't match!")


@app.post("/webhook")
async def github_webhook(request: Request) -> dict:
    payload_bytes = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")

    verify_signature(payload_bytes, Config.GITHUB_WEBHOOK_SECRET, signature)

    event = request.headers.get("X-GitHub-Event")
    if event != "pull_request":
        return {"status": "event ignored", "reason": f"Unhandled event type: {event}"}

    payload = await request.json()

    if payload.get("action") in ["opened", "reopened", "synchronize"]:
        pr_info = {
            "repo_full_name": payload["repository"]["full_name"],
            "pr_number": payload["pull_request"]["number"],
            "head_sha": payload["pull_request"]["head"]["sha"],
            "pr_title": payload["pull_request"]["title"],
            "pr_description": payload["pull_request"]["body"],
        }
        redis_client.lpush("review_tasks", json.dumps(pr_info))
        logger.debug(
            f"Queued task for PR #{pr_info['pr_number']} in {pr_info['repo_full_name']}"
        )
        return {"status": "task queued", "pr": pr_info}

    return {"status": "event ignored", "action": payload.get("action")}


@app.get("/")
def read_root() -> dict:
    return {"Hello": "Webhook Service"}
