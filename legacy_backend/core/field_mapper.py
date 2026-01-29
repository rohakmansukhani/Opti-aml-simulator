import pandas as pd
from typing import Dict, Optional

def apply_field_mappings_to_df(df: pd.DataFrame, mappings: Optional[Dict[str, str]]) -> pd.DataFrame:
    """
    Renames DataFrame columns based on mapping configuration.
    
    Args:
        df: Original DataFrame with user's column names
        mappings: Dict mapping scenario fields -> actual DB columns
                  Example: {'transaction_amount': 'tx_amt'}
                  
    Returns:
        DataFrame with renamed columns.
        If mappings is None or empty, returns original DataFrame.
    """
    if not mappings:
        return df
    
    # The 'mappings' dict is typically: { 'system_field': 'user_column' }
    # e.g. { 'transaction_amount': 'amount_usd', 'customer_id': 'cust_id' }
    # But check the direction. 
    # Usually: Application expects 'transaction_amount'.
    # User provides CSV with 'amount_usd'.
    # So we want to rename 'amount_usd' -> 'transaction_amount'.
    
    # Reverse mapping: User Column -> System Field
    reverse_map = {v: k for k, v in mappings.items()}
    
    # Only rename columns that exist in the DataFrame
    # This prevents errors if a mapping key doesn't exist in the specific DF (e.g. if partial)
    rename_dict = {col: reverse_map[col] for col in df.columns if col in reverse_map}
    
    if rename_dict:
        # Create a copy to avoid modifying original
        df_mapped = df.copy()
        
        # Drop target columns if they already exist (to prevent duplicates)
        target_cols = list(rename_dict.values())
        existing_targets = [col for col in target_cols if col in df_mapped.columns]
        if existing_targets:
            print(f"[FIELD_MAPPER] Dropping existing columns to prevent duplicates: {existing_targets}")
            df_mapped = df_mapped.drop(columns=existing_targets)
        
        # Now safely rename
        df_mapped = df_mapped.rename(columns=rename_dict)
        return df_mapped
        
    return df
