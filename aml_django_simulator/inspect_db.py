import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from simulation.models import Transaction, Customer

def inspect_data():
    print("--- Inspecting Transactions ---")
    tx = Transaction.objects.first()
    if tx:
        print(f"ID: {tx.transaction_id}")
        print(f"Raw Data Type: {type(tx.raw_data)}")
        print(f"Raw Data Content: {tx.raw_data}")
    else:
        print("No transactions found.")

    print("\n--- Inspecting Customers ---")
    cust = Customer.objects.first()
    if cust:
        print(f"ID: {cust.customer_id}")
        print(f"Raw Data Type: {type(cust.raw_data)}")
        print(f"Raw Data Content: {cust.raw_data}")
    else:
        print("No customers found.")

if __name__ == "__main__":
    inspect_data()
