#!/usr/bin/env python3
"""
Quick Zotero diagnostic script - standalone version
"""

import os
import sys
import yaml

try:
    from pyzotero import zotero as pyzotero_lib
except ImportError:
    print("Error: pyzotero not installed. Run: pip install pyzotero pyyaml")
    sys.exit(1)

def main():
    # Load config directly
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'zotero-crawler.yaml')
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    zotero_config = config.get('zotero', {})
    library_id = zotero_config.get('library_id')
    api_key = zotero_config.get('api_key')
    
    if not library_id or not api_key:
        print("❌ Error: Zotero credentials not configured in config/crawler.yaml")
        return 1
    
    print(f"🔍 Connecting to Zotero library: {library_id}")
    zot = pyzotero_lib.Zotero(library_id, 'user', api_key)
    
    # Get all collections
    print("\n📁 Fetching collections...")
    collections = []
    
    def flatten(colls, parent_path="", parent_key=None):
        for c in colls:
            full_name = f"{parent_path}/{c['data']['name']}" if parent_path else c['data']['name']
            collections.append({
                'key': c['key'],
                'name': c['data']['name'],
                'full_name': full_name,
                'parent': c['data'].get('parentCollection'),
            })
            # Recursively get subcollections
            if c.get('children'):
                flatten(c['children'], full_name, c['key'])
    
    top_level = zot.collections()
    flatten(top_level)
    
    print(f"  Total collections found: {len(collections)}")
    
    # Check for OpenClaw specific collections
    print("\n🔎 Looking for 'OpenClaw-Battery-Research'...")
    openclaw_main = [c for c in collections if c['name'] == 'OpenClaw-Battery-Research']
    
    if openclaw_main:
        main_key = openclaw_main[0]['key']
        print(f"  ✅ Found main collection (key: {main_key})")
        
        # Count items in this collection
        items = zot.collection_items(main_key)
        print(f"  📄 Items in main collection: {len(items)}")
        
        # Look for date subfolders
        date_folders = [c for c in collections if c.get('parent') == main_key]
        print(f"  📂 Date subfolders found: {len(date_folders)}")
        for df in date_folders:
            print(f"    ├── {df['name']} (key: {df['key']})")
            
            # Look for topic subfolders
            topic_folders = [c for c in collections if c.get('parent') == df['key']]
            if topic_folders:
                for tf in topic_folders:
                    print(f"    │   └── {tf['name']} (key: {tf['key']})")
                    # Count items in topic folder
                    tf_items = zot.collection_items(tf['key'])
                    if tf_items:
                        print(f"    │       Items: {len(tf_items)}")
                        for item in tf_items[:3]:
                            title = item['data'].get('title', 'No title')[:50]
                            print(f"    │       - {title}...")
            else:
                # Count items directly in date folder
                df_items = zot.collection_items(df['key'])
                if df_items:
                    print(f"        Items: {len(df_items)}")
    else:
        print("  ❌ Main collection 'OpenClaw-Battery-Research' not found!")
        print("\n  Available top-level collections:")
        for c in collections:
            if c['parent'] is None:
                print(f"    - {c['name']}")
    
    # Check all items count
    print(f"\n📊 Library summary:")
    all_items = zot.items()
    print(f"  Total items in library: {len(all_items)}")
    
    # Show recent items with auto-imported tag
    print("\n🏷️  Looking for 'auto-crawler' tag...")
    try:
        tagged_items = zot.items(tag='auto-crawler')
        print(f"  Items with 'auto-crawler' tag: {len(tagged_items)}")
        
        if tagged_items:
            print("\n  Recent auto-imported items (showing collections):")
            for item in tagged_items[:5]:
                title = item['data'].get('title', 'No title')
                date = item['data'].get('dateAdded', 'Unknown')[:10]
                item_key = item['key']
                # Check which collections this item is in
                item_collections = item['data'].get('collections', [])
                coll_names = []
                for ck in item_collections:
                    coll = [c for c in collections if c['key'] == ck]
                    if coll:
                        coll_names.append(coll[0]['full_name'])
                coll_str = ', '.join(coll_names) if coll_names else 'NOT IN ANY COLLECTION (Unfiled)'
                print(f"    - {title[:50]}...")
                print(f"      Collections: {coll_str}")
                print(f"      Item key: {item_key}, Date: {date}")
        
        # Check the date subfolder QINTTZGD specifically
        print("\n🔍 Checking 2026-03-31 folder contents...")
        df_items = zot.collection_items('QINTTZGD')
        print(f"  Items in date folder: {len(df_items)}")
        if df_items:
            for item in df_items[:5]:
                title = item['data'].get('title', 'No title')
                print(f"    - {title[:50]}...")
        
        # Find where "Si-C-Anode" collection actually is
        print("\n🔎 Where is the 'Si-C-Anode' collection?")
        si_c_anode = [c for c in collections if c['name'] == 'Si-C-Anode']
        if si_c_anode:
            for c in si_c_anode:
                parent_info = c.get('parent', 'None')
                parent_name = 'None'
                if parent_info:
                    parent = [x for x in collections if x['key'] == parent_info]
                    if parent:
                        parent_name = parent[0]['full_name']
                print(f"  Found: {c['full_name']} (key: {c['key']}, parent: {parent_name})")
    except Exception as e:
        print(f"  Error checking: {e}")
    
    return 0

def delete_tagged_items():
    """Delete all items with auto-crawler tag."""
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'zotero-crawler.yaml')
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    zotero_config = config.get('zotero', {})
    library_id = zotero_config.get('library_id')
    api_key = zotero_config.get('api_key')
    
    if not library_id or not api_key:
        print("❌ Error: Zotero credentials not configured")
        return 1
    
    print(f"🔍 Connecting to Zotero library: {library_id}")
    zot = pyzotero_lib.Zotero(library_id, 'user', api_key)
    
    # Find all items with auto-crawler tag
    print("\n🏷️  Finding items with 'auto-crawler' tag...")
    tagged_items = zot.items(tag='auto-crawler')
    print(f"  Found {len(tagged_items)} items to delete")
    
    if not tagged_items:
        print("  Nothing to delete.")
        return 0
    
    # Show what will be deleted
    print("\n  Items to delete:")
    for item in tagged_items[:10]:
        title = item['data'].get('title', 'No title')[:50]
        print(f"    - {title}...")
    if len(tagged_items) > 10:
        print(f"    ... and {len(tagged_items) - 10} more")
    
    # Delete items
    print(f"\n🗑️  Deleting {len(tagged_items)} items...")
    deleted = 0
    errors = 0
    
    for item in tagged_items:
        try:
            item_key = item['key']
            zot.delete_item(item)
            deleted += 1
            print(f"  ✓ Deleted: {item['data'].get('title', 'No title')[:40]}...")
        except Exception as e:
            errors += 1
            print(f"  ✗ Error deleting item: {e}")
    
    print(f"\n✅ Deleted {deleted} items, {errors} errors")
    return 0

def create_test_collection():
    """Create a simple test collection."""
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'zotero-crawler.yaml')
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    zotero_config = config.get('zotero', {})
    library_id = zotero_config.get('library_id')
    api_key = zotero_config.get('api_key')
    
    if not library_id or not api_key:
        print("❌ Error: Zotero credentials not configured")
        return 1
    
    print(f"🔍 Connecting to Zotero library: {library_id}")
    zot = pyzotero_lib.Zotero(library_id, 'user', api_key)
    
    # Create test collection
    collection_name = "OpenClaw-Battery-Research"
    print(f"\n📁 Creating collection: '{collection_name}'...")
    
    # Check if already exists
    collections = zot.collections()
    existing = [c for c in collections if c['data']['name'] == collection_name]
    
    if existing:
        print(f"  ⚠️  Collection already exists (key: {existing[0]['key']})")
        return 0
    
    try:
        template = {'name': collection_name, 'parentCollection': None}
        response = zot.create_collection([template])
        
        if response and 'success' in response:
            new_key = response['success']['0']
            print(f"  ✅ Created successfully! Key: {new_key}")
            return 0
        else:
            print(f"  ⚠️  Response: {response}")
            return 1
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return 1

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--delete', action='store_true', help='Delete auto-crawler items')
    parser.add_argument('--create', action='store_true', help='Create test collection')
    args = parser.parse_args()
    
    if args.delete:
        sys.exit(delete_tagged_items())
    elif args.create:
        sys.exit(create_test_collection())
    else:
        sys.exit(main())
