#!/usr/bin/env python3
"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. SPDX-License-Identifier: MIT-0

AWS Shopfloor Connectivity (SFC) Module Analyzer
Analyzes SFC configurations to determine required modules
"""

from typing import List, Dict, Any


def analyze_sfc_config_for_modules(config: Dict[str, Any]) -> List[str]:
    """Analyze SFC config to determine required modules

    Args:
        config: SFC configuration dictionary

    Returns:
        List of required module names
    """
    modules = set()

    # Check protocol adapters
    adapter_types = config.get("AdapterTypes", {})
    for adapter_type in adapter_types:
        # Convert adapter type name to lowercase for module name
        adapter_module = adapter_type.lower()
        modules.add(adapter_module)

    # Check for target types
    target_types = config.get("TargetTypes", {})
    for target_type in target_types:
        # Convert target type to module name format
        if target_type.startswith("AWS-"):
            # For AWS targets, use the format "aws-x-target"
            target_module = target_type.lower().replace("-", "-")
            if "-target" not in target_module:
                target_module += "-target"
        else:
            # For other targets
            target_module = target_type.lower()
            if "-target" not in target_module:
                target_module += "-target"

        modules.add(target_module)

    # No longer automatically including core modules
    # modules.add("core")
    # modules.add("metrics")

    return list(modules)
