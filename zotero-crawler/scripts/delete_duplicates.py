#!/usr/bin/env python3
"""
Delete duplicate OpenClaw-Battery-Research collections
Keep only the new one: 87AK5AEQ
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
    
    # Keep this one (user's new collection)
    KEEP_KEY = '87AK5AEQ'
    
    # Find all OpenClaw-Battery-Research collections
    print("📁 Finding duplicate collections...")
    duplicates = []
    for c in zot.collections():
        if c['data']['name'] == 'OpenClaw-Battery-Research' and c['key'] != KEEP_KEY:
            duplicates.append(c['key'])
    
    print(f"  Found {len(duplicates)} duplicates to delete:")
    for key in duplicates:
        print(f"    - {key}")
    
    # Delete duplicates using direct API key approach
    deleted = 0
    errors = 0
    
    # Sort by key to delete in consistent order
    duplicates.sort()
    
    for key in duplicates:
        print(f"\n🗑️  Deleting {key}...")
        try:
            # Build delete URL directly
            import requests
            url = f"https://api.zotero.org/users/{library_id}/collections/{key}"
            headers = {
                'Zotero-API-Key': api_key,
                'Content-Type': 'application/json'
            }
            
            # Get current version first
            resp = requests.get(url, headers=headers)
            if resp.status_code == 200:
                current_version = resp.json()['version']
                headers['If-Unmodified-Since-Version'] = str(current_version)
                
                # Now delete
                del_resp = requests.delete(url, headers=headers)
                if del_resp.status_code in [200, 204]:
                    print(f"  ✅ Deleted")
                    deleted += 1
                else:
                    print(f"  ❌ Delete failed: {del_resp.status_code}")
                    errors += 1
            else:
                print(f"  ❌ Could not get collection: {resp.status_code}")
                errors += 1
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
            errors += 1
    
    print(f"\n✅ Summary: {deleted} deleted, {errors} errors")
    print(f"   Kept: {KEEP_KEY}")

if __name__ == '__main__':
    sys.exit(main())
