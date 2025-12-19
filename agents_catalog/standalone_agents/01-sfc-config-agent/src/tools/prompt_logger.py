#!/usr/bin/env python3
"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. SPDX-License-Identifier: MIT-0

AWS Shopfloor Connectivity (SFC) prompt logging module.
Saves agent prompts and responses as markdown files.
"""

import os
import re
import time
from typing import List, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ConversationEntry:
    """Represents a single prompt-response pair in a conversation"""

    prompt: str
    response: str
    timestamp: float


class PromptLogger:
    """Handles logging and saving of agent prompts and responses"""

    def __init__(self, max_history: int = 10, log_dir: str = ".sfc"):
        """Initialize the prompt logger

        Args:
            max_history: Maximum number of prompt-response pairs to store in memory
            log_dir: Directory where conversation logs will be saved
        """
        self.conversation_history: List[ConversationEntry] = []
        self.max_history = max_history
        self.log_dir = log_dir

        # Create log directory if it doesn't exist
        os.makedirs(self.log_dir, exist_ok=True)

    def add_entry(self, prompt: str, response: str) -> None:
        """Add a new prompt-response pair to the conversation history

        Args:
            prompt: The user's prompt/question
            response: The agent's response
        """
        # Create a new entry with current timestamp
        entry = ConversationEntry(
            prompt=prompt, response=response, timestamp=time.time()
        )

        # Add to history
        self.conversation_history.append(entry)

        # Maintain history size limit
        if len(self.conversation_history) > self.max_history:
            self.conversation_history.pop(0)

    def _generate_filename(self, prompt: str) -> str:
        """Generate a suitable filename based on the prompt content

        Args:
            prompt: The prompt text to base the filename on

        Returns:
            A sanitized filename with .md extension
        """
        # Extract the first sentence or up to 50 chars, whichever is shorter
        first_sentence = prompt.split(".")[0].strip()
        if len(first_sentence) > 50:
            first_sentence = first_sentence[:50]

        # Remove special characters and replace spaces with underscores
        sanitized = re.sub(r"[^\w\s-]", "", first_sentence)
        sanitized = re.sub(r"[\s]+", "_", sanitized)

        # Add timestamp to ensure uniqueness
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        return f"{sanitized}_{timestamp}.md"

    def _format_as_markdown(self, entry: ConversationEntry) -> str:
        """Format a conversation entry as markdown

        Args:
            entry: The conversation entry to format

        Returns:
            Markdown formatted string of the conversation
        """
        # Format the timestamp
        formatted_time = datetime.fromtimestamp(entry.timestamp).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # Create markdown content
        markdown = f"# SFC Agent Conversation - {formatted_time}\n\n"
        markdown += "## User Prompt\n\n"
        markdown += f"```\n{entry.prompt}\n```\n\n"
        markdown += "## Agent Response\n\n"
        markdown += f"```\n{entry.response}\n```\n"

        return markdown

    def save_last_conversation(self) -> Tuple[bool, str]:
        """Save the most recent conversation entry as a markdown file

        Returns:
            Tuple of (success, message)
        """
        if not self.conversation_history:
            return False, "No conversation history to save"

        # Get the last entry
        last_entry = self.conversation_history[-1]

        # Generate filename and format content
        filename = self._generate_filename(last_entry.prompt)
        content = self._format_as_markdown(last_entry)

        # Save the file
        try:
            filepath = os.path.join(self.log_dir, filename)
            with open(filepath, "w") as f:
                f.write(content)
            return True, f"Conversation saved to {filepath}"
        except Exception as e:
            return False, f"Error saving conversation: {str(e)}"

    def save_n_conversations(self, n: int = 1) -> Tuple[bool, str]:
        """Save the N most recent conversations as markdown files

        Args:
            n: Number of recent conversations to save (default: 1)

        Returns:
            Tuple of (success, message)
        """
        if not self.conversation_history:
            return False, "No conversation history to save"

        # Limit n to available history
        n = min(n, len(self.conversation_history))

        # Get the last n entries
        entries_to_save = self.conversation_history[-n:]
        saved_files = []

        for entry in entries_to_save:
            filename = self._generate_filename(entry.prompt)
            content = self._format_as_markdown(entry)

            try:
                filepath = os.path.join(self.log_dir, filename)
                with open(filepath, "w") as f:
                    f.write(content)
                saved_files.append(filepath)
            except Exception as e:
                return False, f"Error saving conversation: {str(e)}"

        if len(saved_files) == 1:
            return True, f"Conversation saved to {saved_files[0]}"
        else:
            return True, f"Saved {len(saved_files)} conversations"
