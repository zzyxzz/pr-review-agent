review_system_prompt = """
You are a helpful assistant that provides information about code changes.
"""

pull_request_review_instructions = """
Below is the PR details:

PR Title: {pr_title}
PR Description: {pr_description}

Changes:
{changes}
"""
