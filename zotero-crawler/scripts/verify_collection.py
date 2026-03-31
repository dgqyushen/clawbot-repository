#!/usr/bin/env python3
"""
Verify Zotero collection ownership
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
    
    print(f"🔍 Library ID: {library_id}")
    print(f"🔑 API Key (last 4): ...{api_key[-4:]}")
    
    zot = pyzotero_lib.Zotero(library_id, 'user', api_key)
    
    # Get library info
    print("\n📚 Library Info:")
    try:
        # Try to get user info
        user_info = zot.key_info()
        print(f"  User ID: {user_info.get('userID', 'N/A')}")
        print(f"  Username: {user_info.get('username', 'N/A')}")
    except Exception as e:
        print(f"  Could not get user info: {e}")
    
    # Check specific collection
    print(f"\n📁 Checking collection NCVDH7QW:")
    try:
        # Try to get the collection directly
        collection = zot.collection('NCVDH7QW')
        print(f"  ✅ Collection found!")
        print(f"  Name: {collection['data']['name']}")
        print(f"  Parent: {collection['data'].get('parentCollection', 'None (top-level)')}")
        print(f"  Version: {collection['data']['version']}")
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    # Check QINTTZGD
    print(f"\n📁 Checking collection QINTTZGD:")
    try:
        collection = zot.collection('QINTTZGD')
        print(f"  ✅ Collection found!")
        print(f"  Name: {collection['data']['name']}")
        print(f"  Parent: {collection['data'].get('parentCollection', 'None')}")
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    # Compare working collection vs non-working
    print(f"\n🔍 Comparing accessible (9CVEDEPW) vs non-accessible (NCVDH7QW):")
    try:
        c_working = zot.collection('9CVEDEPW')
        c_broken = zot.collection('NCVDH7QW')
        
        print(f"\n  Working (9CVEDEPW):")
        print(f"    Name: {c_working['data']['name']}")
        print(f"    Parent: {c_working['data'].get('parentCollection', 'None')}")
        print(f"    Version: {c_working['data']['version']}")
        
        print(f"\n  Non-working (NCVDH7QW):")
        print(f"    Name: {c_broken['data']['name']}")
        print(f"    Parent: {c_broken['data'].get('parentCollection', 'None')}")
        print(f"    Version: {c_broken['data']['version']}")
    except Exception as e:
        print(f"  Error comparing: {e}")
    
    # Import test item
    print(f"\n🧪 Importing test item to NCVDH7QW...")
    try:
        test_item = {
            'itemType': 'journalArticle',
            'title': '[Test Import] OpenClaw Zotero Integration Test',
            'creators': [{'creatorType': 'author', 'firstName': 'OpenClaw', 'lastName': 'Bot'}],
            'date': '2026',
            'extra': '[Auto-Imported by OpenClaw Crawler on 2026-03-31]',
            'tags': [{'tag': 'auto-crawler'}, {'tag': 'test-import'}]
        }
        response = zot.create_items([test_item])
        if response and 'successful' in response:
            item_key = response['successful']['0']['key']
            print(f"  ✅ Item created: {item_key}")
            
            # Add to collection
            zot.addto_collection('NCVDH7QW', response['successful']['0'])
            print(f"  ✅ Added to collection NCVDH7QW")
        else:
            print(f"  ⚠️  Response: {response}")
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    # List all top-level collections
    print(f"\n📂 All top-level collections in library {library_id}:")
    try:
        collections = zot.collections()
        for c in collections:
            if not c['data'].get('parentCollection'):
                print(f"  - {c['data']['name']} (key: {c['key']})")
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
