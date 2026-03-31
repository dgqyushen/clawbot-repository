#!/usr/bin/env python3
"""
Clean up Zotero OpenClaw collections
"""

import os
import sys
import yaml

try:
    from pyzotero import zotero as pyzotero_lib
except ImportError:
    print("Error: pyzotero not installed")
    sys.exit(1)

def main():
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
    
    # Get all collections
    print("\n📁 Fetching collections...")
    collections = []
    
    def flatten(colls, parent_key=None):
        for c in colls:
            collections.append({
                'key': c['key'],
                'name': c['data']['name'],
                'parent': c['data'].get('parentCollection'),
                'children': []
            })
            if c.get('children'):
                flatten(c['children'], c['key'])
    
    top_level = zot.collections()
    flatten(top_level)
    
    # Find OpenClaw-Battery-Research
    openclaw = [c for c in collections if c['name'] == 'OpenClaw-Battery-Research']
    if not openclaw:
        print("❌ OpenClaw-Battery-Research not found")
        return 1
    
    main_key = openclaw[0]['key']
    print(f"✅ Found main collection: {main_key}")
    
    # Find subcollections
    date_folders = [c for c in collections if c.get('parent') == main_key]
    print(f"\n📂 Found {len(date_folders)} date subfolders:")
    
    total_items = 0
    for df in date_folders:
        print(f"  - {df['name']} (key: {df['key']})")
        df_items = zot.collection_items(df['key'])
        print(f"    Items: {len(df_items)}")
        total_items += len(df_items)
        
        # Check for topic subfolders
        topic_folders = [c for c in collections if c.get('parent') == df['key']]
        for tf in topic_folders:
            print(f"    └── {tf['name']} (key: {tf['key']})")
            tf_items = zot.collection_items(tf['key'])
            print(f"        Items: {len(tf_items)}")
            total_items += len(tf_items)
    
    print(f"\n📊 Total items in OpenClaw tree: {total_items}")
    
    # Check auto-crawler tag
    print("\n🏷️  Checking auto-crawler tag...")
    tagged = zot.items(tag='auto-crawler')
    print(f"  Items with auto-crawler tag: {len(tagged)}")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
