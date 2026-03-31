#!/usr/bin/env python3
"""
Create subcollections and move test item
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
    
    zot = pyzotero_lib.Zotero(library_id, 'user', api_key)
    
    # New main collection
    MAIN_KEY = '87AK5AEQ'
    print(f"📁 Using main collection: {MAIN_KEY}")
    
    # Create date subfolder
    DATE_NAME = '2026-04-01'
    print(f"\n📂 Creating date subfolder: {DATE_NAME}...")
    try:
        template = {'name': DATE_NAME, 'parentCollection': MAIN_KEY}
        response = zot.create_collection([template])
        if 'success' in response:
            date_key = response['success']['0']
            print(f"  ✅ Created: {date_key}")
        else:
            # Check if already exists
            for c in zot.collections():
                if c['data']['name'] == DATE_NAME and c['data'].get('parentCollection') == MAIN_KEY:
                    date_key = c['key']
                    print(f"  ℹ️  Already exists: {date_key}")
                    break
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return 1
    
    # Create topic subfolder
    TOPIC_NAME = 'Si-C-Anode'
    print(f"\n📂 Creating topic subfolder: {TOPIC_NAME}...")
    try:
        template = {'name': TOPIC_NAME, 'parentCollection': date_key}
        response = zot.create_collection([template])
        if 'success' in response:
            topic_key = response['success']['0']
            print(f"  ✅ Created: {topic_key}")
        else:
            for c in zot.collections():
                if c['data']['name'] == TOPIC_NAME and c['data'].get('parentCollection') == date_key:
                    topic_key = c['key']
                    print(f"  ℹ️  Already exists: {topic_key}")
                    break
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return 1
    
    # Add test item to new collection
    print(f"\n🔄 Adding test item to new collection...")
    try:
        # Re-fetch fresh item data
        item = zot.item('I6UIDWS5')
        
        # Add to new collection
        zot.addto_collection(topic_key, item)
        print(f"  ✅ Added to new Si-C-Anode collection ({topic_key})")
        
        # Try to remove from old (may fail if already removed, that's ok)
        try:
            item = zot.item('I6UIDWS5')  # Re-fetch after add
            zot.deletefrom_collection('NCVDH7QW', item)
            print("  ✅ Removed from old collection (NCVDH7QW)")
        except Exception as e:
            print(f"  ℹ️  Old collection removal: {e}")
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    print(f"\n✅ Structure created:")
    print(f"  OpenClaw-Battery-Research ({MAIN_KEY})")
    print(f"    └── {DATE_NAME} ({date_key})")
    print(f"        └── {TOPIC_NAME} ({topic_key})")
    print(f"  Test item: I6UIDWS5")

if __name__ == '__main__':
    sys.exit(main())
