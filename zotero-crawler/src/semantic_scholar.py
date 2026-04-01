"""
Semantic Scholar API Wrapper
Handles rate limiting, retry logic, and paper metadata extraction.
Rate limit: 1 request per second (cumulative across all endpoints)
"""

import time
import requests
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class Paper:
    """Represents a paper from Semantic Scholar."""
    paper_id: str
    title: str
    abstract: Optional[str]
    authors: List[str]
    year: Optional[int]
    venue: Optional[str]
    url: Optional[str]
    pdf_url: Optional[str]
    citation_count: int
    reference_count: int
    influential_citation_count: int
    publication_date: Optional[str]  # YYYY-MM-DD format
    doi: Optional[str] = None
    fields_of_study: Optional[List[str]] = None
    tldr: Optional[str] = None
    
    # Alias for database compatibility
    @property
    def journal(self) -> Optional[str]:
        """Alias for venue (database compatibility)."""
        return self.venue
    
    @property
    def open_access_pdf(self) -> Optional[str]:
        """Alias for pdf_url (database compatibility)."""
        return self.pdf_url
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "paper_id": self.paper_id,
            "title": self.title,
            "abstract": self.abstract,
            "authors": self.authors,
            "year": self.year,
            "venue": self.venue,
            "url": self.url,
            "pdf_url": self.pdf_url,
            "citation_count": self.citation_count,
            "reference_count": self.reference_count,
            "influential_citation_count": self.influential_citation_count,
            "publication_date": self.publication_date,
            "doi": self.doi,
            "fields_of_study": self.fields_of_study,
            "tldr": self.tldr,
        }


class SemanticScholarClient:
    """
    Semantic Scholar API client with rate limiting.
    https://api.semanticscholar.org/api-docs/
    """
    
    BASE_URL = "https://api.semanticscholar.org/graph/v1"
    
    # Fields to request - optimized for literature tracking
    PAPER_FIELDS = [
        "paperId", "title", "abstract", "authors", "year", "venue",
        "citationCount", "referenceCount", "influentialCitationCount",
        "publicationDate", "openAccessPdf", "externalIds",
        "fieldsOfStudy", "tldr"  # ADDED: New fields
    ]
    
    def __init__(self, api_key: str, rate_limit_rps: float = 1.0):
        """
        Initialize client.
        
        Args:
            api_key: Semantic Scholar API key
            rate_limit_rps: Requests per second limit (default 1 for S2 free tier)
        """
        self.api_key = api_key
        self.rate_limit_delay = 1.0 / rate_limit_rps
        self._last_request_time = 0
        self.session = requests.Session()
        self.session.headers.update({
            "x-api-key": api_key,
            "Accept": "application/json"
        })
        
    def _rate_limited_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Execute request with rate limiting."""
        # Calculate time since last request
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - elapsed
            logger.debug(f"Rate limit: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        try:
            response = self.session.request(method, url, **kwargs)
            self._last_request_time = time.time()
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                logger.warning("Rate limit hit (429), backing off...")
                time.sleep(5)
                return self._rate_limited_request(method, url, **kwargs)
            raise
    
    def search_papers(
        self, 
        query: str, 
        fields: Optional[List[str]] = None,
        limit: int = 20,
        publication_date_or_year: Optional[str] = None,
        sort: str = "relevance"
    ) -> List[Paper]:
        """
        Search for papers using Semantic Scholar search API.
        
        Args:
            query: Search query string
            fields: Paper fields to return (defaults to PAPER_FIELDS)
            limit: Max results (max 100)
            publication_date_or_year: Filter by date range (e.g., "2026-03-01:2026-03-31")
            sort: Sort order ("relevance" or "publicationDate")
            
        Returns:
            List of Paper objects
        """
        url = f"{self.BASE_URL}/paper/search"
        
        params = {
            "query": query,
            "fields": ",".join(fields or self.PAPER_FIELDS),
            "limit": min(limit, 100),
            "sort": sort
        }
        
        if publication_date_or_year:
            params["publicationDateOrYear"] = publication_date_or_year
        
        logger.info(f"Searching: '{query}' (limit={limit}, date_filter={publication_date_or_year})")
        
        response = self._rate_limited_request("GET", url, params=params)
        data = response.json()
        
        papers = []
        for item in data.get("data", []):
            paper = self._parse_paper(item)
            if paper:
                papers.append(paper)
        
        total = data.get("total", 0)
        logger.info(f"Found {len(papers)} papers (total available: {total})")
        return papers
    
    def _parse_paper(self, data: Dict) -> Optional[Paper]:
        """Parse API response into Paper object."""
        try:
            # Extract authors
            authors = []
            for author in data.get("authors", []):
                name = author.get("name")
                if name:
                    authors.append(name)
            
            # Extract PDF URL from openAccessPdf
            pdf_url = None
            oa_pdf = data.get("openAccessPdf")
            if oa_pdf and isinstance(oa_pdf, dict):
                pdf_url = oa_pdf.get("url")
            
            # Build paper URL
            paper_id = data.get("paperId")
            url = f"https://www.semanticscholar.org/paper/{paper_id}" if paper_id else None
            
            # Extract DOI from externalIds
            doi = None
            external_ids = data.get("externalIds", {})
            if external_ids and isinstance(external_ids, dict):
                doi = external_ids.get("DOI")
            
            # Extract fields of study
            fields_of_study = data.get("fieldsOfStudy", [])
            if not isinstance(fields_of_study, list):
                fields_of_study = []
            
            # Extract TLDR
            tldr = None
            tldr_obj = data.get("tldr")
            if tldr_obj and isinstance(tldr_obj, dict):
                tldr = tldr_obj.get("text")
            
            return Paper(
                paper_id=paper_id or "unknown",
                title=data.get("title", "Untitled"),
                abstract=data.get("abstract"),
                authors=authors,
                year=data.get("year"),
                venue=data.get("venue"),
                url=url,
                pdf_url=pdf_url,
                citation_count=data.get("citationCount", 0),
                reference_count=data.get("referenceCount", 0),
                influential_citation_count=data.get("influentialCitationCount", 0),
                publication_date=data.get("publicationDate"),
                doi=doi,
                fields_of_study=fields_of_study,
                tldr=tldr
            )
        except Exception as e:
            logger.error(f"Failed to parse paper: {e}")
            return None
    
    def get_paper_details(self, paper_id: str, fields: Optional[List[str]] = None) -> Optional[Paper]:
        """Get detailed information for a specific paper."""
        url = f"{self.BASE_URL}/paper/{paper_id}"
        params = {"fields": ",".join(fields or self.PAPER_FIELDS)}
        
        try:
            response = self._rate_limited_request("GET", url, params=params)
            data = response.json()
            return self._parse_paper(data)
        except requests.exceptions.HTTPError as e:
            logger.error(f"Failed to get paper details for {paper_id}: {e}")
            return None


# Convenience function for batch searching multiple keywords
def search_multiple_keywords(
    client: SemanticScholarClient,
    keywords: List[str],
    days_back: int = 7,
    limit_per_keyword: int = 20
) -> Dict[str, List[Paper]]:
    """
    Search multiple keywords, return results grouped by keyword.
    
    Args:
        client: Initialized SemanticScholarClient
        keywords: List of search queries
        days_back: How many days back to search
        limit_per_keyword: Max results per keyword
        
    Returns:
        Dict mapping keyword to list of Paper objects
    """
    results = {}
    
    # Build date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    date_range = f"{start_date.strftime('%Y-%m-%d')}:{end_date.strftime('%Y-%m-%d')}"
    
    for keyword in keywords:
        papers = client.search_papers(
            query=keyword,
            limit=limit_per_keyword,
            publication_date_or_year=date_range,
            sort="publicationDate"  # Most recent first
        )
        results[keyword] = papers
    
    return results
