"""Zotero export functionality - API client and RDF export."""

import httpx
from typing import List, Dict, Any, Optional
from loguru import logger


class ZoteroClient:
    """Client for Zotero API."""
    
    BASE_URL = "https://api.zotero.org"
    
    def __init__(self, library_id: str, api_key: str, library_type: str = "user"):
        """
        Initialize Zotero client.
        
        Args:
            library_id: Zotero user or group ID
            api_key: Zotero API key
            library_type: "user" or "group"
        """
        self.library_id = library_id
        self.api_key = api_key
        self.library_type = library_type
        
        self.client = httpx.Client(
            headers={
                "Zotero-API-Version": "3",
                "Zotero-API-Key": api_key,
            },
            timeout=30.0,
        )
        
        logger.info(f"Zotero client initialized ({library_type} library: {library_id})")
    
    def get_or_create_collection(self, name: str, parent_key: Optional[str] = None) -> str:
        """
        Get collection by name, or create if not exists.
        
        Returns:
            Collection key
        """
        # Search existing collections
        collections = self._get_collections()
        for coll in collections:
            if coll.get("data", {}).get("name") == name:
                logger.debug(f"Found existing collection: {name} ({coll['key']})")
                return coll["key"]
        
        # Create new collection
        return self._create_collection(name, parent_key)
    
    def _get_collections(self) -> List[Dict[str, Any]]:
        """Get all collections."""
        url = f"{self.BASE_URL}/{self.library_type}s/{self.library_id}/collections"
        
        try:
            response = self.client.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get collections: {e}")
            return []
    
    def _create_collection(self, name: str, parent_key: Optional[str] = None) -> str:
        """Create a new collection."""
        url = f"{self.BASE_URL}/{self.library_type}s/{self.library_id}/collections"
        
        # Zotero API requires JSON array for collections
        data = [{"name": name}]
        if parent_key:
            data[0]["parentCollection"] = parent_key
        
        try:
            response = self.client.post(url, json=data)
            response.raise_for_status()
            
            # Zotero returns 201 with Location header
            location = response.headers.get("Location", "")
            key = location.split("/")[-1] if location else response.json().get("key")
            
            logger.info(f"Created collection: {name} ({key})")
            return key
            
        except httpx.HTTPError as e:
            logger.error(f"Failed to create collection: {e}")
            raise
    
    def create_item(self, item: Dict[str, Any], collection_key: Optional[str] = None) -> str:
        """
        Create a new item in Zotero library.
        
        Args:
            item: Item data (use Paper.to_zotero_item())
            collection_key: Optional collection to add item to
            
        Returns:
            Item key
        """
        url = f"{self.BASE_URL}/{self.library_type}s/{self.library_id}/items"
        
        # Zotero API requires JSON array for items
        data = [item]
        
        if collection_key:
            url += f"?collection={collection_key}"
        
        try:
            response = self.client.post(url, json=data)
            response.raise_for_status()
            
            # Zotero returns 200 with successful object
            result = response.json()
            
            # The response is typically a dictionary with "success", "failed", "unchanged"
            if isinstance(result, dict) and "success" in result:
                success_keys = list(result["success"].keys())
                if success_keys:
                    item_key = success_keys[0]
                    logger.debug(f"Created item: {item.get('title', 'Unknown')[:50]}... ({item_key})")
                    return item_key
            
            # If response is a list, extract first item key
            if isinstance(result, list) and len(result) > 0:
                first_item = result[0]
                if isinstance(first_item, dict) and "key" in first_item:
                    return first_item["key"]
            
            logger.warning(f"Unexpected response format: {result}")
            return None
                
        except httpx.HTTPError as e:
            logger.error(f"Failed to create item: {e}")
            raise
    
    def add_tags(self, item_key: str, tags: List[str]):
        """Add tags to an item."""
        url = f"{self.BASE_URL}/{self.library_type}s/{self.library_id}/items/{item_key}/tags"
        
        try:
            for tag in tags:
                response = self.client.post(url, json={"tag": tag})
                if response.status_code not in (200, 201, 204):
                    logger.warning(f"Failed to add tag '{tag}': {response.status_code}")
        except httpx.HTTPError as e:
            logger.error(f"Failed to add tags: {e}")
    
    def add_note(self, item_key: str, note_text: str):
        """Add a child note to an item."""
        url = f"{self.BASE_URL}/{self.library_type}s/{self.library_id}/items"
        
        note_item = {
            "itemType": "note",
            "note": note_text,
            "parentItem": item_key,
        }
        
        try:
            response = self.client.post(url, json=note_item)
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"Failed to add note: {e}")
    
    def close(self):
        """Close HTTP client."""
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def export_to_csv(papers: List[Any], output_path: str):
    """Export papers to CSV for manual Zotero import."""
    import csv
    
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Title", "Authors", "Year", "Journal", "DOI", "URL", "Abstract"])
        
        for paper in papers:
            writer.writerow([
                paper.title,
                "; ".join(paper.authors),
                paper.year,
                paper.journal,
                paper.doi,
                paper.url,
                paper.abstract,
            ])
    
    logger.info(f"Exported {len(papers)} papers to CSV: {output_path}")
