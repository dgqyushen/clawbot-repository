"""
Zotero Pusher Module
Handles Zotero integration: collection creation, date-based subfolders, and paper import.
"""

import logging
import re
from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import asdict

try:
    from pyzotero import zotero
except ImportError:
    zotero = None
    logging.warning("pyzotero not installed. Zotero functions will be unavailable.")

logger = logging.getLogger(__name__)


class ZoteroPusher:
    """
    Manages Zotero library operations with automatic date-based folder structure.
    
    Folder structure:
    - OpenClaw-Battery-Research (main collection)
      - 2026-03-31 (subfolder)
      - 2026-04-01 (subfolder)
      - ...
    """
    
    def __init__(self, library_id: str, api_key: str, library_type: str = "user"):
        """
        Initialize Zotero connection.
        
        Args:
            library_id: Zotero library ID (numeric string)
            api_key: Zotero API key
            library_type: "user" or "group"
        """
        if zotero is None:
            raise ImportError("pyzotero is required. Install with: pip install pyzotero")
        
        self.zot = zotero.Zotero(library_id, library_type, api_key)
        self.library_id = library_id
        
        # Cache for collection lookups
        self._collection_cache: Dict[str, str] = {}  # name -> collection_key
        self._collection_item_identity_cache: Dict[str, Dict[str, str]] = {}

    @staticmethod
    def _normalize_doi(doi: Optional[str]) -> Optional[str]:
        return doi.strip().lower() if doi else None

    @staticmethod
    def _extract_semantic_scholar_id(extra: str) -> Optional[str]:
        if not extra:
            return None
        match = re.search(r'^Semantic Scholar ID:\s*(.+)$', extra, re.MULTILINE)
        return match.group(1).strip() if match else None

    def _get_collection_identity_cache(self, collection_key: str) -> Dict[str, str]:
        if collection_key in self._collection_item_identity_cache:
            return self._collection_item_identity_cache[collection_key]

        cache: Dict[str, str] = {}
        items = self.zot.collection_items(collection_key)
        everything = getattr(self.zot, 'everything', None)
        if callable(everything):
            items = everything(items)

        for item in items:
            data = item.get('data', {}) if isinstance(item, dict) else {}
            item_key = item.get('key') if isinstance(item, dict) else None
            paper_id = self._extract_semantic_scholar_id(data.get('extra', ''))
            doi = self._normalize_doi(data.get('DOI'))

            if paper_id and item_key:
                cache[f'paper_id:{paper_id}'] = item_key
            if doi and item_key:
                cache[f'doi:{doi}'] = item_key

        self._collection_item_identity_cache[collection_key] = cache
        return cache
        
    def _refresh_collection_cache(self):
        """Fetch all collections and update cache."""
        collections = []
        
        def flatten(colls, parent_path=""):
            for c in colls:
                full_name = f"{parent_path}/{c['data']['name']}" if parent_path else c['data']['name']
                collections.append({
                    'key': c['key'],
                    'name': c['data']['name'],
                    'full_name': full_name,
                    'parent': c['data'].get('parentCollection'),
                    'version': c['data']['version']
                })
                # Recursively get subcollections
                if c.get('children'):
                    flatten(c['children'], full_name)
        
        top_level = self.zot.collections()
        flatten(top_level)
        
        # Update cache: use "parent_key/name" as key for uniqueness
        self._collection_cache = {}
        for c in collections:
            cache_key = f"{c['parent'] or 'root'}/{c['name']}"
            self._collection_cache[cache_key] = c['key']
        
        return collections
    
    def _get_all_collections(self) -> List[Dict]:
        """Fetch all collections, flattening nested structure."""
        return self._refresh_collection_cache()
    
    def _find_collection_by_name(self, name: str, parent_key: Optional[str] = None) -> Optional[str]:
        """
        Find collection by name (optionally under a specific parent).
        Uses cache to avoid duplicate creation race conditions.
        Returns collection key if found, None otherwise.
        """
        cache_key = f"{parent_key or 'root'}/{name}"
        
        # Check cache first
        if cache_key in self._collection_cache:
            return self._collection_cache[cache_key]
        
        # Refresh cache and try again
        self._refresh_collection_cache()
        return self._collection_cache.get(cache_key)
    
    def _create_collection(self, name: str, parent_key: Optional[str] = None) -> str:
        """
        Create a new collection.
        
        Args:
            name: Collection name
            parent_key: Parent collection key (None for top-level)
            
        Returns:
            New collection key
        """
        collection_template = {
            'name': name,
            'parentCollection': parent_key
        }
        
        try:
            response = self.zot.create_collection([collection_template])
            # Response format varies, extract the key
            if response and 'success' in response:
                new_key = response['success']['0']
                logger.info(f"Created collection '{name}' (key={new_key}, parent={parent_key})")
                return new_key
            else:
                # Try alternative response format
                new_key = response[0]['key'] if isinstance(response, list) else str(response)
                logger.info(f"Created collection '{name}' (key={new_key})")
                return new_key
        except Exception as e:
            logger.error(f"Failed to create collection '{name}': {e}")
            raise
    
    def ensure_collection_path(self, main_name: str, date_folder: str, topic_folder: Optional[str] = None) -> str:
        """
        Ensure the full path exists: main_name/date_folder or main_name/date_folder/topic_folder
        Returns the leaf collection key.
        
        Args:
            main_name: Main collection name (e.g., "OpenClaw-Battery-Research")
            date_folder: Date subfolder (e.g., "2026-03-31")
            topic_folder: Optional topic subfolder (e.g., "Si-C-Anode")
        
        Returns:
            Collection key for the leaf folder
        """
        # Check/create main collection (always at root level)
        main_key = self._find_collection_by_name(main_name, parent_key=None)
        if main_key is None:
            logger.info(f"Main collection '{main_name}' not found, creating...")
            main_key = self._create_collection(main_name)
        else:
            logger.debug(f"Found main collection '{main_name}' (key={main_key})")
        
        # Check/create date subfolder
        date_key = self._find_collection_by_name(date_folder, parent_key=main_key)
        if date_key is None:
            logger.info(f"Date folder '{date_folder}' not found under '{main_name}', creating...")
            date_key = self._create_collection(date_folder, parent_key=main_key)
        else:
            logger.debug(f"Found date folder '{date_folder}' (key={date_key})")
        
        # Check/create topic subfolder (if specified)
        if topic_folder:
            topic_key = self._find_collection_by_name(topic_folder, parent_key=date_key)
            if topic_key is None:
                logger.info(f"Topic folder '{topic_folder}' not found under '{date_folder}', creating...")
                topic_key = self._create_collection(topic_folder, parent_key=date_key)
            else:
                logger.debug(f"Found topic folder '{topic_folder}' (key={topic_key})")
            return topic_key
        
        return date_key
    
    def paper_to_zotero_item(self, paper, auto_imported: bool = True) -> Dict[str, Any]:
        """
        Convert Paper object to Zotero item format.
        
        Args:
            paper: Paper dataclass from semantic_scholar module
            auto_imported: Whether this was auto-imported by the crawler (adds tags/notes)
            
        Returns:
            Zotero item template (journalArticle type)
        """
        # Build creators list
        creators = []
        for author in paper.authors:
            # Try to parse as "First Last" or "Last, First"
            if ',' in author:
                parts = author.split(',', 1)
                last_name = parts[0].strip()
                first_name = parts[1].strip() if len(parts) > 1 else ""
            else:
                parts = author.rsplit(' ', 1)
                if len(parts) == 2:
                    first_name, last_name = parts[0], parts[1]
                else:
                    first_name, last_name = "", parts[0]
            
            creators.append({
                'creatorType': 'author',
                'firstName': first_name,
                'lastName': last_name
            })
        
        # Build extra field with clear auto-import marking
        import_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        extra_lines = [
            f"Semantic Scholar ID: {paper.paper_id}",
            f"Citations: {paper.citation_count}",
            f"PDF: {paper.pdf_url or 'N/A'}"
        ]
        
        if auto_imported:
            extra_lines.insert(0, f"[Auto-Imported by OpenClaw Crawler on {import_timestamp}]")
        
        # Build the item
        # Use full publication date if available, otherwise year
        date_str = paper.publication_date or (str(paper.year) if paper.year else '')
        
        # Use abstract, or tldr as fallback, or empty
        abstract = paper.abstract or paper.tldr or ''
        
        item = {
            'itemType': 'journalArticle',
            'title': paper.title,
            'abstractNote': abstract,
            'creators': creators,
            'date': date_str,
            'publicationTitle': paper.venue or '',
            'url': paper.url or '',
            'extra': '\n'.join(extra_lines),
            'tags': []
        }
        
        # Add auto-import tags for easy filtering
        if auto_imported:
            item['tags'] = [
                {'tag': 'auto-crawler'},
                {'tag': f'imported-{datetime.now().strftime("%Y-%m-%d")}'}
            ]
        
        # Add DOI if available
        if paper.doi:
            item['DOI'] = paper.doi
        
        return item
    
    def add_paper_to_collection(self, paper, collection_key: str) -> Optional[str]:
        """
        Add a paper to a specific collection.
        
        Args:
            paper: Paper object
            collection_key: Target collection key
            
        Returns:
            Item key if successful, None otherwise
        """
        try:
            identity_cache = self._get_collection_identity_cache(collection_key)
            if paper.paper_id:
                existing_key = identity_cache.get(f'paper_id:{paper.paper_id}')
                if existing_key:
                    logger.warning(f"Paper already exists in collection by paper_id, skipping create: {paper.paper_id}")
                    return existing_key

            normalized_doi = self._normalize_doi(getattr(paper, 'doi', None))
            if normalized_doi:
                existing_key = identity_cache.get(f'doi:{normalized_doi}')
                if existing_key:
                    logger.warning(f"Paper already exists in collection by DOI, skipping create: {normalized_doi}")
                    return existing_key

            zotero_item = self.paper_to_zotero_item(paper)
            # Add collection to item - this puts it in the collection on creation
            zotero_item['collections'] = [collection_key]
            
            # Create item (with collection assignment)
            response = self.zot.create_items([zotero_item])
            
            # Debug: log response structure
            logger.debug(f"Zotero create_items response type: {type(response)}, content: {response}")
            
            # Parse response - handle different pyzotero response formats
            item_key = None
            try:
                if isinstance(response, dict):
                    if 'success' in response:
                        success_data = response['success']
                        if isinstance(success_data, dict):
                            item_key = success_data.get('0') or success_data.get(0)
                        elif isinstance(success_data, list) and len(success_data) > 0:
                            item_key = success_data[0]
                    elif '0' in response:
                        item_key = response.get('0')
                    # Also check 'successful' which contains full item data
                    if not item_key and 'successful' in response:
                        successful_data = response['successful']
                        if isinstance(successful_data, dict) and '0' in successful_data:
                            first_item = successful_data['0']
                            if isinstance(first_item, dict):
                                item_key = first_item.get('key')
                elif isinstance(response, list) and len(response) > 0:
                    first_item = response[0]
                    if isinstance(first_item, dict):
                        item_key = first_item.get('key')
            except (TypeError, KeyError, IndexError) as e:
                logger.error(f"Failed to parse Zotero response: {e}, response={response}")
            
            if item_key:
                if paper.paper_id:
                    identity_cache[f'paper_id:{paper.paper_id}'] = item_key
                if normalized_doi:
                    identity_cache[f'doi:{normalized_doi}'] = item_key

                # Try to attach PDF if available
                if paper.pdf_url:
                    try:
                        self._attach_pdf(item_key, paper.pdf_url, paper.title)
                    except Exception as e:
                        logger.warning(f"Could not attach PDF for {paper.title}: {e}")
                
                # Add a child note marking this as auto-imported
                try:
                    self._add_import_note(item_key, paper)
                except Exception as e:
                    logger.warning(f"Could not add import note for {paper.title}: {e}")
                
                logger.info(f"Added paper to Zotero: {paper.title[:50]}...")
                return item_key
            else:
                logger.error(f"Failed to create Zotero item: {response}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to add paper '{paper.title}': {e}")
            return None
    
    def _attach_pdf(self, parent_item_key: str, pdf_url: str, title: str):
        """Attach a PDF link to a Zotero item."""
        # Zotero attachment template
        attachment = {
            'itemType': 'attachment',
            'linkMode': 'linked_url',
            'title': f"{title} - PDF",
            'url': pdf_url,
            'contentType': 'application/pdf',
            'parentItem': parent_item_key
        }
        
        try:
            self.zot.create_items([attachment])
            logger.debug(f"Attached PDF link for: {title}")
        except Exception as e:
            logger.warning(f"Failed to attach PDF link: {e}")
    
    def _add_import_note(self, parent_item_key: str, paper):
        """Add a child note marking this paper as auto-imported by the crawler."""
        import_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        note_content = (
            f"<p><b>🤖 Auto-Imported by OpenClaw Crawler</b></p>\n"
            f"<p>Import time: {import_timestamp}</p>\n"
            f"<p>Source: Semantic Scholar</p>\n"
            f"<p>Paper ID: {paper.paper_id}</p>\n"
            f"<p>Citations: {paper.citation_count}</p>\n"
            f"<hr/>\n"
            f"<p><i>This paper was automatically imported by the OpenClaw literature crawler. "
            f"You can identify auto-imported papers by the tag 'auto-crawler'.</i></p>"
        )
        
        note_item = {
            'itemType': 'note',
            'note': note_content,
            'parentItem': parent_item_key,
            'tags': [{'tag': 'crawler-note'}]
        }
        
        try:
            self.zot.create_items([note_item])
            logger.debug(f"Added import note for: {paper.title}")
        except Exception as e:
            logger.warning(f"Failed to add import note: {e}")
    
    def import_papers_for_today(
        self, 
        papers: List, 
        main_collection: str = "OpenClaw-Battery-Research",
        date_format: str = "%Y-%m-%d"
    ) -> Dict[str, Any]:
        """
        Import papers to today's date folder.
        
        Args:
            papers: List of Paper objects
            main_collection: Main collection name
            date_format: Date folder format (default: "2026-03-31")
            
        Returns:
            Summary dict with counts and keys
        """
        today_str = datetime.now().strftime(date_format)
        
        # Ensure folder structure exists
        date_collection_key = self.ensure_collection_path(main_collection, today_str)
        
        results = {
            'date_folder': today_str,
            'total': len(papers),
            'successful': 0,
            'failed': 0,
            'item_keys': []
        }
        
        for paper in papers:
            key = self.add_paper_to_collection(paper, date_collection_key)
            if key:
                results['successful'] += 1
                results['item_keys'].append(key)
            else:
                results['failed'] += 1
        
        logger.info(f"Import complete: {results['successful']}/{results['total']} papers added to {main_collection}/{today_str}")
        return results
