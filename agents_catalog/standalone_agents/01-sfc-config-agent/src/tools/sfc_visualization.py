#!/usr/bin/env python3
"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. SPDX-License-Identifier: MIT-0

AWS Shopfloor Connectivity (SFC) Data Visualization Module
Provides visualization capabilities for SFC data stored in file targets.
"""

import os
import json
import datetime
from typing import Optional

from src.tools.data_visualizer import visualize_time_series


def visualize_file_target_data(
    config_name: Optional[str],
    minutes: int = None,
    jmespath_expr: str = "value",
    ui_mode: bool = False,
    seconds: int = 15,
) -> str:
    """
    Visualize data from an active SFC configuration with FILE-TARGET

    Args:
        config_name: Name of the currently running configuration (None if no active config)
        minutes: Number of minutes of data to visualize (default: None)
        jmespath_expr: JMESPath expression to extract values (default: "sources.SimulatorSource.values.sinus.value")
        ui_mode: If True, returns a markdown representation instead of using ncurses
        seconds: Seconds parameter for time control (default: 15, overrides minutes when provided)

    Returns:
        Result message or markdown graph
    """
    if config_name is None:
        return "❌ No active SFC configuration is running"

    # Build the path to the configuration directory
    base_dir = os.getcwd()
    run_dir = os.path.join(base_dir, ".sfc/runs", config_name)

    if not os.path.exists(run_dir):
        return f"❌ Configuration directory {run_dir} not found"

    # Find and load the configuration file
    config_file = os.path.join(run_dir, "config.json")
    if not os.path.exists(config_file):
        return f"❌ Configuration file {config_file} not found"

    try:
        with open(config_file, "r") as f:
            config = json.load(f)
    except Exception as e:
        return f"❌ Failed to read configuration file: {str(e)}"

    # Check if this config has a FILE-TARGET
    file_target = None
    file_target_config = None

    if "Targets" in config:
        for target_name, target_config in config["Targets"].items():
            if (
                "TargetType" in target_config
                and target_config["TargetType"] == "FILE-TARGET"
                and target_config.get("Active", False)
            ):
                file_target = target_name
                file_target_config = target_config
                break

    if file_target is None:
        return "❌ No active FILE-TARGET found in the configuration"

    # Get the directory where data files are stored
    data_dir = file_target_config.get("Directory", "./data")

    # If the path is relative, make it absolute relative to the run directory
    if not os.path.isabs(data_dir):
        data_dir = os.path.normpath(os.path.join(run_dir, data_dir))

    if not os.path.exists(data_dir):
        return f"❌ Data directory {data_dir} not found"

    # Filter for files from the last n minutes
    cutoff_time = datetime.datetime.now() - datetime.timedelta(minutes=minutes)

    # Determine the timeframe in seconds
    timeframe_seconds = None
    if seconds is not None:
        timeframe_seconds = seconds
    elif minutes is not None:
        timeframe_seconds = minutes * 60
    else:
        # Default to 15 seconds if neither is provided
        timeframe_seconds = 15

    # Call the data visualizer with UI mode parameter
    result = visualize_time_series(data_dir, jmespath_expr, timeframe_seconds, ui_mode)

    # In UI mode, just return the single visualization without timeframe options
    # This ensures only one visualization is displayed at a time

    return result
