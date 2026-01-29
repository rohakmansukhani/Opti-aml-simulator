"""
Field Mapper - Column mapping utility for flexible data ingestion (Django Native)
"""

from typing import Dict, Optional, List

def apply_field_mappings(data_dict: Dict, mappings: Optional[Dict[str, str]]) -> Dict:
    """
    Applies field mappings to a dictionary (for JSON data).
    
    Args:
        data_dict: Original data with user's field names
        mappings: Dict mapping system fields -> user columns
                  Example: {'transaction_amount': 'tx_amt'}
                  
    Returns:
        Dictionary with renamed fields.
    """
    if not mappings:
        return data_dict
    
    # Reverse mapping: User Column -> System Field
    reverse_map = {v: k for k, v in mappings.items()}
    
    # Apply mappings
    mapped_dict = {}
    for key, value in data_dict.items():
        new_key = reverse_map.get(key, key)  # Use mapped name or keep original
        mapped_dict[new_key] = value
    
    return mapped_dict

def get_required_fields(entity_type: str) -> List[str]:
    """
    Returns required fields for a given entity type.
    
    Args:
        entity_type: 'transaction' or 'customer'
        
    Returns:
        List of required field names
    """
    if entity_type == 'transaction':
        return [
            'transaction_id',
            'customer_id',
            'transaction_date',
            'transaction_amount'
        ]
    elif entity_type == 'customer':
        return [
            'customer_id',
            'customer_name'
        ]
    return []

def validate_field_mappings(mappings: Dict[str, str], entity_type: str) -> tuple[bool, List[str]]:
    """
    Validates that all required fields are mapped.
    
    Args:
        mappings: Field mapping dictionary
        entity_type: 'transaction' or 'customer'
        
    Returns:
        (is_valid, missing_fields)
    """
    required = get_required_fields(entity_type)
    mapped_system_fields = set(mappings.keys())
    
    missing = [field for field in required if field not in mapped_system_fields]
    
    return (len(missing) == 0, missing)
