import os
import django
from django.apps import apps

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

def describe_all_models():
    print("=" * 60)
    print(f"{'DATABASE SCHEMA OVERVIEW':^60}")
    print("=" * 60)

    # Filter for relevant apps to avoid system/internal tables unless desired
    target_apps = ['core', 'simulation'] 

    for model in apps.get_models():
        app_label = model._meta.app_label
        if app_label not in target_apps:
            continue

        print(f"\nTABLE: {model._meta.db_table} (Model: {model.__name__})")
        print("-" * 60)
        print(f"{'Field':25} | {'Type':20} | {'Null'}")
        print("-" * 60)

        for field in model._meta.get_fields():
            # Skip reverse relations
            if not hasattr(field, 'get_internal_type'):
                continue
                
            name = field.name
            field_type = field.get_internal_type()
            is_null = "Yes" if field.null else "No"
            
            print(f"{name:25} | {field_type:20} | {is_null}")
            
    print("\n" + "=" * 60)

if __name__ == "__main__":
    describe_all_models()
