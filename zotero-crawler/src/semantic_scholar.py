"""Semantic Scholar API client for academic paper search."""

import httpx
import time
from typing import List, Dict, Any, Optional
from loguru import logger
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Paper:
    """Represents a paper from Semantic Scholar."""
    paper_id: str
    title: str
    authors: List[str]
    year: Optional[int]
    citation_count: int
    publication_date: Optional[str]
    journal: Optional[str]
    abstract: Optional[str]
    doi: Optional[str]
    arxiv_id: Optional[str]
    url: Optional[str]
    open_access_pdf: Optional[str]
    tldr: Optional[str]  # AI-generated summary
    fields_of_study: List[str]
    
    def to_zotero_item(self) -> Dict[str, Any]:
        """Convert to Zotero item format."""
        return {
            "itemType": "journalArticle",
            "title": self.title,
            "creators": [{"creatorType": "author", "name": author} for author in self.authors],
            "date": str(self.year) if self.year else self.publication_date,
            "publicationTitle": self.journal,
            "abstractNote": self.abstract,
            "DOI": self.doi,
            "url": self.url,
            "extra": f"Semantic Scholar ID: {self.paper_id}\nCitations: {self.citation_count}",
        }


class SemanticScholarClient:
    """Client for Semantic Scholar Academic Graph API."""
    
    BASE_URL = "https://api.semanticscholar.org/graph/v1"
    
    def __init__(self, api_key: Optional[str] = None, rate_limit: int = 100):
        """
        Initialize client.
        
        Args:
            api_key: Semantic Scholar API key (optional but recommended)
            rate_limit: Requests per 5 minutes (default 100 for free tier)
        """
        self.api_key = api_key
        self.rate_limit = rate_limit
        self.last_request_time = 0
        self.min_interval = (5 * 60) / rate_limit  # seconds between requests
        
        headers = {}
        if api_key:
            headers["x-api-key"] = api_key
            
        self.client = httpx.Client(
            base_url=self.BASE_URL,
            headers=headers,
            timeout=30.0
        )
        
        logger.info(f"Semantic Scholar client initialized (rate limit: {rate_limit}/5min)")
    
    def _rate_limit(self):
        """Apply rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_interval:
            sleep_time = self.min_interval - elapsed
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        self.last_request_time = time.time()
    
    def search_papers(
        self,
        query: str,
        fields: List[str],
        limit: int = 10,
        min_year: Optional[int] = None,
        sort_by: str = "publicationDate",
    ) -> List[Paper]:
        """
        Search for papers by keyword.
        
        Args:
            query: Search query string
            fields: Fields to retrieve
            limit: Maximum results
            min_year: Minimum publication year
            sort_by: Sort field (citationCount, publicationDate, relevance)
            
        Returns:
            List of Paper objects
        """
        self._rate_limit()
        
        # Build field query string
        field_string = ",".join(fields)
        
        params = {
            "query": query,
            "fields": field_string,
            "limit": limit,
            "sort": sort_by,
        }
        
        if min_year:
            params["minYear"] = min_year
        
        logger.info(f"Searching: '{query}' (limit={limit}, min_year={min_year})")
        
        try:
            response = self.client.get("/paper/search", params=params)
            response.raise_for_status()
            data = response.json()
            
            papers = []
            for item in data.get("data", []):
                paper = self._parse_paper(item)
                if paper:
                    papers.append(paper)
            
            total = data.get("total", 0)
            logger.info(f"Found {len(papers)} papers (total matches: {total})")
            return papers
            
        except httpx.HTTPError as e:
            logger.error(f"API request failed: {e}")
            raise
    
    def _parse_paper(self, data: Dict[str, Any]) -> Optional[Paper]:
        """Parse API response into Paper object."""
        try:
            # Extract authors
            authors = []
            for author in data.get("authors", []):
                name = author.get("name")
                if name:
                    authors.append(name)
            
            # Extract external IDs
            external_ids = data.get("externalIds", {})
            doi = external_ids.get("DOI")
            arxiv_id = external_ids.get("ArXiv")
            
            # Get URL
            url = data.get("openAccessPdf", {}).get("url") if data.get("openAccessPdf") else None
            if not url and doi:
                url = f"https://doi.org/{doi}"
            
            # Get TLDR (AI summary)
            tldr_data = data.get("tldr")
            tldr = tldr_data.get("text") if isinstance(tldr_data, dict) else None
            
            return Paper(
                paper_id=data.get("paperId", ""),
                title=data.get("title", ""),
                authors=authors,
                year=data.get("year"),
                citation_count=data.get("citationCount", 0),
                publication_date=data.get("publicationDate"),
                journal=data.get("journal", {}).get("name") if data.get("journal") else None,
                abstract=data.get("abstract"),
                doi=doi,
                arxiv_id=arxiv_id,
                url=url,
                open_access_pdf=data.get("openAccessPdf", {}).get("url") if data.get("openAccessPdf") else None,
                tldr=tldr,
                fields_of_study=data.get("s2FieldsOfStudy", []),
            )
        except Exception as e:
            logger.warning(f"Failed to parse paper: {e}")
            return None
    
    def get_paper_details(self, paper_id: str, fields: List[str]) -> Optional[Paper]:
        """Fetch detailed information for a specific paper."""
        self._rate_limit()
        
        field_string = ",".join(fields)
        
        try:
            response = self.client.get(f"/paper/{paper_id}", params={"fields": field_string})
            response.raise_for_status()
            data = response.json()
            return self._parse_paper(data)
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch paper details: {e}")
            return None
    
    def close(self):
        """Close HTTP client."""
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
