#!/usr/bin/env python3
"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. SPDX-License-Identifier: MIT-0

AWS Shopfloor Connectivity (SFC) folder operations module.
Handles folder cleaning and management operations.
"""

import os
import shutil
from typing import Optional


class SFCFolderOperations:
    """Handles folder operations for SFC configurations"""

    @staticmethod
    def clean_runs_folder(
        current_config_name: Optional[str] = None,
        last_config_name: Optional[str] = None,
    ) -> str:
        """Clean the runs folder by removing all SFC runs to free up disk space

        Args:
            current_config_name: Name of the current active configuration to preserve
            last_config_name: Name of the last configuration to preserve

        Returns:
            Result message with information about the cleanup operation
        """
        try:
            base_dir = os.getcwd()
            runs_dir = os.path.join(base_dir, ".sfc/runs")

            # Check if runs folder exists
            if not os.path.exists(runs_dir) or not os.path.isdir(runs_dir):
                return "❌ No runs folder found at path: " + runs_dir

            # Get list of run folders
            run_dirs = []
            for entry in os.listdir(runs_dir):
                full_path = os.path.join(runs_dir, entry)
                if os.path.isdir(full_path):
                    run_dirs.append(full_path)

            if not run_dirs:
                return "✅ Runs folder is already empty"

            # Prompt for confirmation
            total_runs = len(run_dirs)
            confirmation_msg = f"⚠️ WARNING: This will delete all {total_runs} run directories in {runs_dir}!\n"
            confirmation_msg += "Do you want to proceed? (y/n): "

            # Ask for confirmation - will need to be implemented by user
            return confirmation_msg

        except Exception as e:
            return f"❌ Error scanning runs folder: {str(e)}"

    @staticmethod
    def confirm_clean_runs_folder(
        confirmation: str,
        current_config_name: Optional[str] = None,
        last_config_name: Optional[str] = None,
    ) -> str:
        """Execute the runs folder cleanup after confirmation

        Args:
            confirmation: User confirmation (y/n)
            current_config_name: Name of the current active configuration to preserve
            last_config_name: Name of the last configuration to preserve

        Returns:
            Result message with information about the cleanup operation
        """
        if confirmation.lower() not in ["y", "yes"]:
            return "❌ Operation canceled by user"

        try:
            base_dir = os.getcwd()
            runs_dir = os.path.join(base_dir, ".sfc/runs")

            # Check if runs folder exists again (in case it was deleted between calls)
            if not os.path.exists(runs_dir) or not os.path.isdir(runs_dir):
                return "❌ No runs folder found at path: " + runs_dir

            # Define helper function to get directory size
            def get_dir_size(path):
                total_size = 0
                for dirpath, _, filenames in os.walk(path):
                    for f in filenames:
                        fp = os.path.join(dirpath, f)
                        if os.path.exists(fp):
                            total_size += os.path.getsize(fp)
                return total_size

            # Track deletion statistics
            deleted_count = 0
            skipped_count = 0
            deleted_size = 0

            # List directories again (might have changed since first scan)
            run_dirs = []
            for entry in os.listdir(runs_dir):
                full_path = os.path.join(runs_dir, entry)
                if os.path.isdir(full_path):
                    run_dirs.append(full_path)

            # Skip active runs
            to_delete = []
            for dir_path in run_dirs:
                dir_name = os.path.basename(dir_path)
                # Skip current and last config directories
                if (current_config_name and dir_name == current_config_name) or (
                    last_config_name and dir_name == last_config_name
                ):
                    skipped_count += 1
                    continue

                to_delete.append(dir_path)

            # Process the directories to delete
            for dir_path in to_delete:
                try:
                    # Calculate directory size before deletion for reporting
                    dir_size = get_dir_size(dir_path)

                    # Delete the directory
                    shutil.rmtree(dir_path)

                    deleted_count += 1
                    deleted_size += dir_size

                except Exception as e:
                    print(f"Error deleting {dir_path}: {str(e)}")
                    skipped_count += 1

            # Format the deleted size for display
            if deleted_size < 1024:
                size_str = f"{deleted_size} bytes"
            elif deleted_size < 1024 * 1024:
                size_str = f"{deleted_size / 1024:.2f} KB"
            elif deleted_size < 1024 * 1024 * 1024:
                size_str = f"{deleted_size / (1024 * 1024):.2f} MB"
            else:
                size_str = f"{deleted_size / (1024 * 1024 * 1024):.2f} GB"

            # Final message
            msg = f"✅ Cleanup completed:\n"
            msg += (
                f"• Deleted: {deleted_count} run{'s' if deleted_count != 1 else ''}\n"
            )
            msg += f"• Freed up: {size_str}\n"

            if skipped_count > 0:
                msg += f"• Skipped: {skipped_count} run{'s' if skipped_count != 1 else ''} (active runs or could not delete)\n"

            return msg

        except Exception as e:
            return f"❌ Error cleaning runs folder: {str(e)}"
