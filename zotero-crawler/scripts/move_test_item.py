#!/usr/bin/env python3
"""
Check new collection structure and move test item
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
    
    # Find the newest OpenClaw-Battery-Research (highest version = most recently modified)
    print("📁 Finding newest OpenClaw-Battery-Research collection...")
    all_openclaw = []
    for c in zot.collections():
        if c['data']['name'] == 'OpenClaw-Battery-Research':
            all_openclaw.append({
                'key': c['key'],
                'version': c['data']['version'],
                'parent': c['data'].get('parentCollection')
            })
    
    # Sort by version (newest first)
    all_openclaw.sort(key=lambda x: x['version'], reverse=True)
    newest = all_openclaw[0]
    print(f"  Newest: key={newest['key']}, version={newest['version']}")
    
    # Check for subcollections under this one
    print(f"\n📂 Checking subcollections under {newest['key']}...")
    
    def find_subcollections(parent_key, indent=0):
        found = []
        for c in zot.collections():
            if c['data'].get('parentCollection') == parent_key:
                prefix = "  " * indent + "└── "
                print(f"{prefix}{c['data']['name']} (key: {c['key']})")
                found.append({'name': c['data']['name'], 'key': c['key']})
                # Recursively check
                found.extend(find_subcollections(c['key'], indent + 1))
        return found
    
    subcollections = find_subcollections(newest['key'])
    
    # Find Si-C-Anode subcollection
    si_c_anode = [s for s in subcollections if s['name'] == 'Si-C-Anode']
    
    if si_c_anode:
        target_key = si_c_anode[0]['key']
        print(f"\n🎯 Target: Si-C-Anode (key: {target_key})")
        
        # Find test item
        print("\n🔍 Looking for test item I6UIDWS5...")
        try:
            item = zot.item('I6UIDWS5')
            print(f"  Found: {item['data']['title']}")
            
            # Remove from old collection NCVDH7QW
            print("\n🗑️  Removing from old collection NCVDH7QW...")
            try:
                zot.deletefrom_collection('NCVDH7QW', item)
                print("  ✅ Removed from NCVDH7QW")
            except Exception as e:
                print(f"  ⚠️  {e}")
            
            # Add to new Si-C-Anode collection
            print(f"\n➕ Adding to new Si-C-Anode ({target_key})...")
            zot.addto_collection(target_key, item)
            print("  ✅ Added!")
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
    else:
        print("\n❌ Si-C-Anode subcollection not found!")
        print("Available subcollections:", [s['name'] for s in subcollections])

if __name__ == '__main__':
    sys.exit(main())
