"""
Lambda Function Mapping Configuration

This module provides mapping between Bedrock agent expected function names
and the actual Lambda function names from the templates.
"""

# Mapping of expected function names from Bedrock agents JSON
LAMBDA_FUNCTION_MAPPING = {
    # From SAM-agent-find-nearestdealership
    'get-dealer-data': 'get-dealer-data',
    
    # From SAM-agent-bookdealerappt  
    'BookAppointmentStar': 'BookAppointmentStar',
    
    # From SAM-agent-finddealeravailability
    'get-dealer-appointment-slots': 'get-dealer-appointment-slots',
    
    # From SAM-agent-parts-availability
    'get-parts-for-dtc': 'get-parts-for-dtc',
    'get-dealer-stock': 'get-dealer-stock', 
    'place-parts-order': 'place-parts-order',
    
    # From SAM-agent-warrantyandrecalls
    'GetWarrantyData': 'GetWarrantyData',
}

# Agent configurations (for CDK deployment - IDs will be generated dynamically)
AGENT_CONFIGURATIONS = {
    'SAM-agent-find-nearestdealership': {
        'lambda_function': 'get-dealer-data',
        'action_group': 'action_group_findnearestdealership'
    },
    'SAM-agent-bookdealerappt': {
        'lambda_function': 'BookAppointmentStar',
        'action_group': 'action_group_dealerappt-starformat'
    },
    'SAM-agent-finddealeravailability': {
        'lambda_function': 'get-dealer-appointment-slots',
        'action_group': 'action_group_finddealerslots'
    },
    'SAM-agent-parts-availability': {
        'lambda_functions': [
            'get-parts-for-dtc',
            'get-dealer-stock', 
            'place-parts-order'
        ]
    },
    'SAM-agent-warrantyandrecalls': {
        'lambda_function': 'GetWarrantyData',
        'action_group': 'action_group_vehiclewarranty'
    }
}

def get_actual_function_name(expected_name: str) -> str:
    """
    Get the actual Lambda function name from templates based on expected name.
    
    Args:
        expected_name: The function name expected by the agent or CDK code
        
    Returns:
        The actual function name from templates, or None if not mapped
    """
    return LAMBDA_FUNCTION_MAPPING.get(expected_name)

def should_create_fallback(expected_name: str, available_functions: dict) -> bool:
    """
    Determine if a fallback function should be created.
    
    Args:
        expected_name: The function name expected by the agent
        available_functions: Dict of functions already created from templates
        
    Returns:
        True if a fallback should be created, False otherwise
    """
    actual_name = get_actual_function_name(expected_name)
    
    # If no mapping exists or mapped to None, create fallback
    if actual_name is None:
        return True
        
    # If the actual function doesn't exist in available functions, create fallback
    return actual_name not in available_functions
