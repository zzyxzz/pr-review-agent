import logging

import requests
from langchain.chat_models import init_chat_model

from app.schema import Reviews

logger = logging.getLogger(__name__)


class ChatModel:
    _instances = {}

    @classmethod
    def get_model(cls, model_name: str, structured_output=None, **kwargs):
        key = f"{model_name}_{structured_output.__name__}"
        if key not in cls._instances:
            cls._instances[key] = init_chat_model(
                model_name, **kwargs
            ).with_structured_output(structured_output)
        return cls._instances[key]


class GithubClient:
    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        self.base_url = "https://api.github.com"

    def fetch_pr_files(self, repo_full_name: str, pr_number: int):
        url = f"{self.base_url}/repos/{repo_full_name}/pulls/{pr_number}/files"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def post_pr_summary(self, repo_full_name: str, pr_number: int, summary: str):
        url = f"{self.base_url}/repos/{repo_full_name}/issues/{pr_number}/comments"
        payload = {"body": f"### 🤖 AI Code Review Summary\n\n{summary}"}
        response = requests.post(url, headers=self.headers, json=payload)
        response.raise_for_status()
        return response.json()

    def post_pr_file_comments(
        self, repo_full_name: str, pr_number: int, reviews: list[Reviews]
    ):
        """
        reviews: list[Reviews]
        """
        url = f"{self.base_url}/repos/{repo_full_name}/pulls/{pr_number}"
        pr_resp = requests.get(url, headers=self.headers)
        pr_resp.raise_for_status()
        latest_commit_id = pr_resp.json()["head"]["sha"]

        for review in reviews:
            for c in review.comments:
                comment_payload = {
                    "body": f"**{c.issue_header}**\n\n{c.issue_content}",
                    "path": review.filename,
                    "line": c.end_line,
                    "side": "LEFT" if c.end_sign == "-" else "RIGHT",
                    "commit_id": latest_commit_id,
                }
                if c.start_line != c.end_line:
                    comment_payload["start_line"] = c.start_line
                    comment_payload["start_side"] = (
                        "LEFT" if c.start_sign == "-" else "RIGHT"
                    )

                url = (
                    f"{self.base_url}/repos/{repo_full_name}/pulls/{pr_number}/comments"
                )
                logger.debug(
                    f"Posting comment to {url} with payload: {comment_payload}"
                )
                resp = requests.post(url, headers=self.headers, json=comment_payload)

                if resp.status_code >= 400:
                    logger.error(
                        "❌ Failed to post comment:", resp.status_code, resp.text
                    )
                else:
                    logger.info(f"✅ Comment posted to {review.filename}:{c.end_line}")


def parse_patch(patch: str):
    """
    Parse a GitHub patch string into a structured format.
    """
    lines = patch.splitlines()
    old_line_start = None
    new_line_start = None
    results = []
    for line in lines:
        if line.startswith("@@"):
            import re

            m = re.match(r"@@ -(\d+),?(\d+)? \+(\d+),?(\d+)? @@", line)
            if m:
                old_line_start = int(m.group(1))
                new_line_start = int(m.group(3))
                results.append(
                    {"old_line": None, "new_line": None, "content": line, "sign": "@@"}
                )
        elif line.startswith(" "):
            results.append(
                {
                    "old_line": old_line_start,
                    "new_line": new_line_start,
                    "content": line[1:],
                    "sign": "",
                }
            )
            old_line_start += 1
            new_line_start += 1
        elif line.startswith("+"):
            results.append(
                {
                    "old_line": None,
                    "new_line": new_line_start,
                    "content": line[1:],
                    "sign": "+",
                }
            )
            new_line_start += 1
        elif line.startswith("-"):
            results.append(
                {
                    "old_line": old_line_start,
                    "new_line": None,
                    "content": line[1:],
                    "sign": "-",
                }
            )
            old_line_start += 1
        else:
            continue

    return results


def prepare_diff_context(task: dict, github_client: GithubClient = None):
    """
    Prepare diff + small context for AI review.
    Extracts context_lines before and after each change in the patch.
    """
    context_data = []
    pr_files = github_client.fetch_pr_files(task["repo_full_name"], task["pr_number"])

    for f in pr_files:
        patch = f.get("patch")
        if not patch:
            continue

        parsed_lines = parse_patch(patch)
        context_data.append(
            {
                "filename": f["filename"],
                "previous_filename": f.get("previous_filename", f["filename"]),
                "status": f["status"],
                "patch_snippet": parsed_lines,
            }
        )

    return {
        "pr_title": task["pr_title"],
        "pr_description": task["pr_description"],
        "context_data": context_data,
    }
