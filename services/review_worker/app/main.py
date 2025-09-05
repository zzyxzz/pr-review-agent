import json
import time

import redis

from app.config import Config, setup_logging
from app.graph import build_graph
from app.tools import GithubClient, prepare_diff_context

logger = setup_logging()


def main():
    logger.info("Starting Review Worker...")
    redis_client = redis.from_url(Config.REDIS_URL)
    logger.info("Connected to Redis.")
    github_client = GithubClient(Config.GITHUB_TOKEN)

    graph = build_graph()

    while True:
        try:
            _, task_data = redis_client.brpop("review_tasks")
            task = json.loads(task_data)
            logger.debug(f"Received task: {task}")

            pr_data = prepare_diff_context(task, github_client)
            logger.debug(
                f"Processing PR #{task.get('pr_number')} in {task.get('repo_full_name')}..."
            )
            response = graph.invoke(pr_data)
            github_client.post_pr_summary(
                task.get("repo_full_name"), task.get("pr_number"), response["summary"]
            )
            github_client.post_pr_file_comments(
                task.get("repo_full_name"),
                task.get("pr_number"),
                response.get("reviews", []),
            )
            logger.debug("Task finished.")

        except Exception as e:
            logger.error(f"An error occurred: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
