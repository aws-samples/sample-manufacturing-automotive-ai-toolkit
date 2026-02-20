#!/usr/bin/env python3
"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. SPDX-License-Identifier: MIT-0

AWS Shopfloor Connectivity (SFC) prompt logging module.
Saves agent prompts and responses to S3 and DynamoDB.
No local filesystem storage — all I/O goes to AWS.
"""

import os
import re
import time
import base64
import logging
from typing import List, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

# Reuse the SSM-aware resource resolution from file_operations
from src.tools.file_operations import (
    _resolve_s3_bucket,
    _resolve_ddb_table,
    _get_s3_client,
    _get_ddb_table,
    _hive_partition_prefix,
    _generate_presigned_url,
)

logger = logging.getLogger(__name__)


def _timestamp_prefix() -> str:
    """Generate an ISO timestamp prefix for S3 keys, safe for filenames."""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H-%M-%SZ")


def _iso_timestamp() -> str:
    """Generate a full ISO timestamp for DynamoDB sort keys."""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class ConversationEntry:
    """Represents a single prompt-response pair in a conversation"""

    prompt: str
    response: str
    timestamp: float


class PromptLogger:
    """Handles logging and saving of agent prompts and responses to S3/DynamoDB"""

    def __init__(self, max_history: int = 10, log_dir: str = ".sfc"):
        """Initialize the prompt logger.

        Args:
            max_history: Maximum number of prompt-response pairs to store in memory
            log_dir: Unused (kept for API compatibility), all storage goes to S3/DDB
        """
        self.conversation_history: List[ConversationEntry] = []
        self.max_history = max_history

    def add_entry(self, prompt: str, response: str) -> None:
        """Add a new prompt-response pair to the in-memory conversation history.

        Args:
            prompt: The user's prompt/question
            response: The agent's response
        """
        entry = ConversationEntry(
            prompt=prompt, response=str(response), timestamp=time.time()
        )
        self.conversation_history.append(entry)

        # Maintain history size limit
        if len(self.conversation_history) > self.max_history:
            self.conversation_history.pop(0)

    def _generate_filename(self, prompt: str) -> str:
        """Generate a suitable filename based on the prompt content.

        Args:
            prompt: The prompt text to base the filename on

        Returns:
            A sanitized filename (without timestamp prefix — that's added at save time)
        """
        first_sentence = prompt.split(".")[0].strip()
        if len(first_sentence) > 50:
            first_sentence = first_sentence[:50]

        sanitized = re.sub(r"[^\w\s-]", "", first_sentence)
        sanitized = re.sub(r"[\s]+", "_", sanitized)

        if not sanitized:
            sanitized = "conversation"

        return f"{sanitized}.md"

    def _format_as_markdown(self, entry: ConversationEntry) -> str:
        """Format a conversation entry as markdown.

        Args:
            entry: The conversation entry to format

        Returns:
            Markdown formatted string of the conversation
        """
        formatted_time = datetime.fromtimestamp(entry.timestamp).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        markdown = f"# SFC Agent Conversation - {formatted_time}\n\n"
        markdown += "## User Prompt\n\n"
        markdown += f"```\n{entry.prompt}\n```\n\n"
        markdown += "## Agent Response\n\n"
        markdown += f"```\n{entry.response}\n```\n"

        return markdown

    def _save_to_cloud(self, filename: str, content: str) -> Tuple[bool, str]:
        """Save conversation content to S3 and index in DynamoDB.

        The file is stored under conversations/year=YYYY/month=MM/day=DD/hour=HH/<filename>
        in S3. A pre-signed download URL is returned as a markdown hyperlink.

        Args:
            filename: Base filename for the conversation
            content: Markdown content to save

        Returns:
            Tuple of (success, message)
        """
        partition = _hive_partition_prefix()
        s3_key = f"conversations/{partition}/{filename}"
        bucket = _resolve_s3_bucket()

        # Upload to S3
        s3_ok = False
        if bucket:
            try:
                _get_s3_client().put_object(
                    Bucket=bucket,
                    Key=s3_key,
                    Body=content.encode("utf-8"),
                    ContentType="text/markdown",
                )
                s3_ok = True
                logger.info(f"Conversation uploaded to S3: s3://{bucket}/{s3_key}")
            except ClientError as e:
                logger.error(f"S3 upload failed for conversation {s3_key}: {e}")
        else:
            logger.error("S3 bucket name not available – cannot save conversation")

        # Index in DynamoDB
        ddb_ok = False
        try:
            created_at = _iso_timestamp()
            sort_key = f"{created_at}#{s3_key}"
            content_b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
            file_size = len(content.encode("utf-8"))

            item = {
                "file_type": "conversation",
                "sort_key": sort_key,
                "filename": filename,
                "s3_key": s3_key,
                "created_at": created_at,
                "file_size": file_size,
                "content_type": "text/markdown",
            }

            # Store base64 content if it fits in DDB (< 350KB)
            if len(content_b64) < 350_000:
                item["content_b64"] = content_b64

            _get_ddb_table().put_item(Item=item)
            ddb_ok = True
            logger.info(f"Conversation indexed in DDB: sort_key={sort_key}")
        except ClientError as e:
            logger.error(f"DDB put_item failed for conversation {filename}: {e}")

        # Build result message
        table_name = _resolve_ddb_table()
        if s3_ok and ddb_ok:
            presigned_url = _generate_presigned_url(s3_key)
            download_link = (
                f"[⬇ Download {filename}]({presigned_url})"
                if presigned_url
                else "(pre-signed URL generation failed)"
            )
            return True, (
                f"Conversation saved:\n"
                f"  • S3: `s3://{bucket}/{s3_key}`\n"
                f"  • DynamoDB: {table_name} (conversation/{filename})\n"
                f"  • {download_link}"
            )
        elif s3_ok:
            presigned_url = _generate_presigned_url(s3_key)
            download_link = (
                f"[⬇ Download {filename}]({presigned_url})"
                if presigned_url
                else "(pre-signed URL generation failed)"
            )
            return True, (
                f"Conversation saved to S3: `s3://{bucket}/{s3_key}`\n"
                f"  • {download_link}"
            )
        elif ddb_ok:
            return True, f"Conversation indexed in DynamoDB (S3 upload failed)"
        else:
            return False, "Failed to save conversation to both S3 and DynamoDB"

    def save_last_conversation(self) -> Tuple[bool, str]:
        """Save the most recent conversation entry to S3/DynamoDB.

        Returns:
            Tuple of (success, message)
        """
        if not self.conversation_history:
            return False, "No conversation history to save"

        last_entry = self.conversation_history[-1]
        filename = self._generate_filename(last_entry.prompt)
        content = self._format_as_markdown(last_entry)

        return self._save_to_cloud(filename, content)

    def save_n_conversations(self, n: int = 1) -> Tuple[bool, str]:
        """Save the N most recent conversations to S3/DynamoDB.

        Args:
            n: Number of recent conversations to save (default: 1)

        Returns:
            Tuple of (success, message)
        """
        if not self.conversation_history:
            return False, "No conversation history to save"

        n = min(n, len(self.conversation_history))
        entries_to_save = self.conversation_history[-n:]
        saved_files = []
        errors = []

        for entry in entries_to_save:
            filename = self._generate_filename(entry.prompt)
            content = self._format_as_markdown(entry)

            success, message = self._save_to_cloud(filename, content)
            if success:
                saved_files.append(message)
            else:
                errors.append(message)

        if saved_files and not errors:
            if len(saved_files) == 1:
                return True, saved_files[0]
            return True, f"Saved {len(saved_files)} conversations"
        elif saved_files:
            return True, (
                f"Saved {len(saved_files)} conversations, "
                f"{len(errors)} failed"
            )
        else:
            return False, f"Failed to save conversations: {'; '.join(errors)}"