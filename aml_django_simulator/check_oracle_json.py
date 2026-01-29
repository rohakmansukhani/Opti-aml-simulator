"""
Check Oracle table structure to see if JSON fields are CLOB or JSON type
"""
import oracledb

# Connect to Oracle
connection = oracledb.connect(
    user='system',
    password='oracle',
    dsn='localhost:1521/FREEPDB1'
)

cursor = connection.cursor()

# Query to check column data types for tables with JSON fields
query = """
SELECT 
    table_name, 
    column_name, 
    data_type,
    data_length
FROM user_tab_columns
WHERE table_name IN ('TRANSACTIONS', 'CUSTOMERS', 'ACCOUNTS', 'ALERTS', 
                     'SCENARIOS_CONFIG', 'SIMULATION_RUNS', 'DATA_UPLOADS',
                     'FIELD_METADATA', 'FIELD_VALUE_INDEX', 'DATA_QUALITY_METRICS',
                     'AUDIT_LOGS', 'COMPARISON_REPORTS', 'SCENARIO_VERSIONS',
                     'SIMULATION_COMPARISONS', 'ALERT_EXCLUSION_LOGS')
AND column_name LIKE '%DATA%' OR column_name LIKE '%JSON%' OR column_name LIKE '%CONFIG%'
OR column_name LIKE '%DETAILS%' OR column_name LIKE '%SNAPSHOT%' OR column_name LIKE '%FLAGS%'
OR column_name LIKE '%ISSUES%' OR column_name LIKE '%INFO%' OR column_name LIKE '%VALUES%'
OR column_name LIKE '%OPERATORS%'
ORDER BY table_name, column_name
"""

print("=" * 80)
print("ORACLE JSON/CLOB FIELD ANALYSIS")
print("=" * 80)

cursor.execute(query)
results = cursor.fetchall()

current_table = None
for row in results:
    table_name, column_name, data_type, data_length = row
    
    if current_table != table_name:
        print(f"\n📋 Table: {table_name}")
        print("-" * 80)
        current_table = table_name
    
    # Highlight JSON-like fields
    if data_type == 'CLOB':
        status = "⚠️  CLOB (Should be JSON)"
    elif data_type == 'JSON':
        status = "✅ JSON"
    else:
        status = f"ℹ️  {data_type}"
    
    print(f"  {column_name:30} → {status}")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

# Count CLOB vs JSON
cursor.execute("""
    SELECT data_type, COUNT(*) 
    FROM user_tab_columns
    WHERE (column_name LIKE '%DATA%' OR column_name LIKE '%JSON%' 
           OR column_name LIKE '%CONFIG%' OR column_name LIKE '%DETAILS%'
           OR column_name LIKE '%SNAPSHOT%' OR column_name LIKE '%FLAGS%'
           OR column_name LIKE '%ISSUES%' OR column_name LIKE '%INFO%'
           OR column_name LIKE '%VALUES%' OR column_name LIKE '%OPERATORS%')
    AND data_type IN ('CLOB', 'JSON')
    GROUP BY data_type
""")

summary = cursor.fetchall()
for data_type, count in summary:
    print(f"{data_type}: {count} columns")

cursor.close()
connection.close()

print("\n✅ Analysis complete!")
