#!/usr/bin/env python3
"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. SPDX-License-Identifier: MIT-0

AWS Shopfloor Connectivity (SFC) log operations module.
Handles log tailing and real-time log monitoring.
"""

import os
import time
import threading
import queue
import select
import sys
from typing import Optional


class SFCLogOperations:
    """Handles log operations for SFC configurations"""

    @staticmethod
    def start_log_tail_thread(
        log_file_path: str,
        log_tail_thread: Optional[threading.Thread],
        log_tail_stop_event: threading.Event,
        log_buffer: queue.Queue,
    ) -> None:
        """Start a thread to tail the SFC log file and keep a buffer of recent log entries

        Args:
            log_file_path: Path to the log file to tail
            log_tail_thread: Current thread reference if one exists
            log_tail_stop_event: Event to signal the thread to stop
            log_buffer: Queue to store the most recent log entries
        """
        # If a thread is already running, stop it before starting a new one
        if log_tail_thread and log_tail_thread.is_alive():
            log_tail_stop_event.set()
            log_tail_thread.join(1)  # Wait up to 1 second for thread to stop

        # Clear any existing stop event
        log_tail_stop_event.clear()

        # Create and start the thread
        new_thread = threading.Thread(
            target=SFCLogOperations.log_tail_worker,
            args=(log_file_path, log_tail_stop_event, log_buffer),
            daemon=True,
        )
        new_thread.start()

        return new_thread

    @staticmethod
    def log_tail_worker(
        log_file_path: str, stop_event: threading.Event, log_buffer: queue.Queue
    ) -> None:
        """Worker thread that continuously reads from the log file and buffers new entries

        Args:
            log_file_path: Path to the log file to tail
            stop_event: Event to signal the thread to stop
            log_buffer: Queue to store the most recent log entries
        """
        try:
            with open(log_file_path, "r") as log_file:
                # Go to the end of the file
                log_file.seek(0, 2)

                while not stop_event.is_set():
                    line = log_file.readline()
                    if line:
                        # If the buffer is full, remove the oldest entry
                        if log_buffer.full():
                            try:
                                log_buffer.get_nowait()
                            except queue.Empty:
                                pass

                        # Add the new log line to the buffer
                        try:
                            log_buffer.put_nowait(line.rstrip())
                        except queue.Full:
                            pass  # Buffer is full, skip this line
                    else:
                        # No new data, wait a bit before checking again
                        time.sleep(0.1)
        except Exception as e:
            # If any error occurs, just print it and exit the thread
            print(f"Log tail thread error: {str(e)}")

    @staticmethod
    def tail_logs(
        current_config_name: str,
        lines: int = 20,
        follow: bool = False,
        log_buffer: Optional[queue.Queue] = None,
    ) -> str:
        """Return the most recent log entries, optionally following in real-time

        Args:
            current_config_name: Name of the current configuration
            lines: Number of recent log lines to show
            follow: If True, continuously display new log lines in real-time
            log_buffer: Queue containing buffered log entries

        Returns:
            String containing log entries or error message
        """
        # Check if there's an active SFC configuration running
        if not current_config_name:
            return "❌ No SFC configuration is currently running"

        # Try to find the log file path
        base_dir = os.getcwd()
        runs_dir = os.path.join(base_dir, ".sfc/runs")
        test_dir = os.path.join(runs_dir, current_config_name)
        log_dir = os.path.join(test_dir, "logs")
        log_file_path = os.path.join(log_dir, "sfc.log")

        if not os.path.exists(log_file_path):
            return f"❌ Log file not found: {log_file_path}"

        # Handle follow mode for real-time log viewing
        if follow:
            print("\n" + "=" * 80)
            print(f"📜 FOLLOW MODE: Showing real-time logs for {current_config_name}")
            print(f"⚠️  TO EXIT: Type 'q' and press Enter")
            print("=" * 80 + "\n")

            # Use a simpler approach that doesn't rely on KeyboardInterrupt
            # First, display the last N lines
            try:
                with open(log_file_path, "r") as file:
                    # Read the last N lines
                    all_lines = file.readlines()
                    last_lines = (
                        all_lines[-lines:] if len(all_lines) > lines else all_lines
                    )

                    # Print the initial lines
                    for line in last_lines:
                        print(line.rstrip())

                # Now enter follow mode with a better exit mechanism

                # Set up non-blocking input checking
                print("\nMonitoring log file... (Type 'q' + Enter to exit)")

                # Open the file for continuous reading
                with open(log_file_path, "r") as file:
                    # Go to the end of the file
                    file.seek(0, 2)

                    # Keep reading new lines as they're added with an exit option
                    while True:
                        # Check if there's user input without blocking
                        if select.select([sys.stdin], [], [], 0)[0]:
                            user_input = sys.stdin.readline().strip()
                            if user_input.lower() == "q":
                                print("\n" + "=" * 80)
                                print(
                                    "Exiting log follow mode. Returning to command mode."
                                )
                                print("=" * 80 + "\n")
                                return "✅ Stopped following logs."

                        # Check for new log content
                        line = file.readline()
                        if line:
                            print(line.rstrip())
                        else:
                            # No new lines, wait a bit before checking again
                            time.sleep(0.1)

            except Exception as e:
                return f"❌ Error following log file: {str(e)}"

        # Standard non-follow mode: Get log entries from the buffer
        log_entries = []

        # Use buffer if provided
        if log_buffer:
            buffer_size = log_buffer.qsize()

            # Try to get requested number of lines from buffer first
            for _ in range(min(lines, buffer_size)):
                try:
                    log_entries.append(log_buffer.get_nowait())
                    log_buffer.task_done()
                except queue.Empty:
                    break

        # If buffer doesn't exist or doesn't have enough entries, read from the file directly
        if not log_buffer or len(log_entries) < lines:
            try:
                with open(log_file_path, "r") as file:
                    all_lines = file.readlines()
                    # Get the last N lines that weren't already in the buffer
                    remaining_lines = lines - len(log_entries)
                    file_lines = [
                        line.rstrip() for line in all_lines[-remaining_lines:]
                    ]
                    log_entries = file_lines + log_entries  # Prepend file lines
            except Exception as e:
                return f"❌ Error reading log file: {str(e)}"

        # Limit to the requested number of lines
        log_entries = log_entries[-lines:]

        # Format the output
        if log_entries:
            return (
                f"📜 Latest log entries for {current_config_name}:\n\n```\n"
                + "\n".join(log_entries)
                + "\n```\n\nUse `tail_logs(50)` to see more lines or `tail_logs(lines=20, follow=True)` to follow logs in real-time."
            )
        else:
            return f"⚠️ No log entries found for {current_config_name}"
