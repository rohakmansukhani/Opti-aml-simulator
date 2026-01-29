/**
 * Utility functions for handling customer and account IDs
 * 
 * Backend prefixes IDs with upload_id to ensure uniqueness across users.
 * These utilities extract the original IDs for display purposes.
 */

/**
 * Extract original customer ID from raw_data or parse from prefixed ID
 * @param customer - Customer object with customer_id and optional raw_data
 * @returns Original customer ID without prefix
 */
export function getDisplayCustomerId(customer: any): string {
    // Try to get from raw_data first (most reliable)
    if (customer?.raw_data?.original_customer_id) {
        return customer.raw_data.original_customer_id;
    }

    // Fallback: Parse from prefixed ID (format: "prefix_originalId")
    if (customer?.customer_id && typeof customer.customer_id === 'string') {
        const parts = customer.customer_id.split('_');
        if (parts.length > 1) {
            // Remove the first part (prefix) and join the rest
            return parts.slice(1).join('_');
        }
        return customer.customer_id;
    }

    return customer?.customer_id || 'Unknown';
}

/**
 * Extract original account ID from raw_data or parse from prefixed ID
 * @param account - Account object with account_id and optional raw_data
 * @returns Original account ID without prefix
 */
export function getDisplayAccountId(account: any): string {
    // Try to get from raw_data first
    if (account?.raw_data?.original_account_id) {
        return account.raw_data.original_account_id;
    }

    // Fallback: Parse from prefixed ID
    if (account?.account_id && typeof account.account_id === 'string') {
        const parts = account.account_id.split('_');
        if (parts.length > 1) {
            return parts.slice(1).join('_');
        }
        return account.account_id;
    }

    return account?.account_id || 'Unknown';
}

/**
 * Extract original customer ID from a simple string ID
 * Useful for alerts and other objects that only have the ID string
 */
export function parseCustomerId(customerId: string): string {
    if (!customerId) return 'Unknown';

    const parts = customerId.split('_');
    if (parts.length > 1) {
        return parts.slice(1).join('_');
    }
    return customerId;
}
