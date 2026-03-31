"""
Literature Pipeline - Main orchestration module
Coordinates search, filtering, deduplication, and Zotero import with topic classification.
"""

import json
import logging
from typing import List, Dict, Set, Any, Optional, Tuple
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path

from semantic_scholar import SemanticScholarClient, Paper, search_multiple_keywords
from zotero_pusher import ZoteroPusher

logger = logging.getLogger(__name__)


class DedupStore:
    """Persistent store for deduplication - tracks already-pushed papers."""
    
    def __init__(self, cache_file: str):
        self.cache_file = Path(cache_file)
        self.paper_ids: Set[str] = set()
        self._load()
    
    def _load(self):
        """Load existing cache from disk."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.paper_ids = set(data.get('paper_ids', []))
                logger.info(f"Loaded dedup cache: {len(self.paper_ids)} papers tracked")
            except Exception as e:
                logger.error(f"Failed to load dedup cache: {e}")
                self.paper_ids = set()
        else:
            logger.info("No dedup cache found, starting fresh")
            self.paper_ids = set()
    
    def _save(self):
        """Save cache to disk."""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'paper_ids': sorted(list(self.paper_ids)),
                    'last_updated': datetime.now().isoformat()
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save dedup cache: {e}")
    
    def is_new(self, paper: Paper) -> bool:
        """Check if paper hasn't been seen before."""
        return paper.paper_id not in self.paper_ids
    
    def mark_as_pushed(self, paper: Paper):
        """Mark paper as pushed (record in cache)."""
        self.paper_ids.add(paper.paper_id)
        self._save()
    
    def mark_multiple_as_pushed(self, papers: List[Paper]):
        """Batch mark papers as pushed."""
        for paper in papers:
            self.paper_ids.add(paper.paper_id)
        self._save()


class TopicClassifier:
    """Classifies papers into topics based on keyword matching."""
    
    def __init__(self, topics_config: Dict[str, Dict]):
        """
        Args:
            topics_config: Dict of topic_id -> {name, keywords, min_impact_factor, required_venues}
        """
        self.topics = topics_config or {}
        self.topic_keywords = {}
        for topic_id, config in self.topics.items():
            self.topic_keywords[topic_id] = {
                'name': config.get('name', topic_id),
                'keywords': [kw.lower() for kw in config.get('keywords', [])],
                'min_impact_factor': config.get('min_impact_factor', 0),
                'required_venues': [v.lower() for v in config.get('required_venues', [])]
            }
    
    def classify(self, paper: Paper) -> List[str]:
        """
        Classify paper into topics.
        Returns list of matching topic_ids.
        """
        text = f"{paper.title} {paper.abstract or ''}".lower()
        matching_topics = []
        
        for topic_id, config in self.topic_keywords.items():
            # Check if any keyword matches
            if any(kw in text for kw in config['keywords']):
                matching_topics.append(topic_id)
        
        return matching_topics
    
    def get_topic_name(self, topic_id: str) -> str:
        """Get display name for a topic."""
        return self.topic_keywords.get(topic_id, {}).get('name', topic_id)


class QualityFilter:
    """Filters papers based on journal quality and citation metrics."""
    
    def __init__(
        self,
        journal_whitelist: Optional[List[str]] = None,
        journal_blacklist: Optional[List[str]] = None,
        min_citations: int = 0,
        citation_filter_age_days: int = 365,
        require_pdf: bool = False
    ):
        self.journal_whitelist = [j.lower() for j in (journal_whitelist or [])]
        self.journal_blacklist = [j.lower() for j in (journal_blacklist or [])]
        self.min_citations = min_citations
        self.citation_filter_age_days = citation_filter_age_days
        self.require_pdf = require_pdf
    
    def is_quality_venue(self, venue: Optional[str]) -> bool:
        """Check if venue is in whitelist or not in blacklist."""
        if not venue:
            return True  # No venue info, can't filter
        
        venue_lower = venue.lower()
        
        # Blacklist check first
        for blacklisted in self.journal_blacklist:
            if blacklisted in venue_lower:
                logger.debug(f"Venue '{venue}' matches blacklist '{blacklisted}'")
                return False
        
        # Whitelist check (if whitelist exists)
        if self.journal_whitelist:
            for whitelisted in self.journal_whitelist:
                if whitelisted in venue_lower:
                    return True
            # Not in whitelist
            logger.debug(f"Venue '{venue}' not in whitelist, filtering out")
            return False
        
        return True
    
    def matches(self, paper: Paper) -> bool:
        """Check if paper passes quality filters."""
        # Venue quality check
        if not self.is_quality_venue(paper.venue):
            logger.debug(f"Paper '{paper.title[:50]}...' filtered: low quality venue '{paper.venue}'")
            return False
        
        # PDF requirement
        if self.require_pdf and not paper.pdf_url:
            logger.debug(f"Paper '{paper.title[:50]}...' filtered: no PDF available")
            return False
        
        # Citation filter (only for older papers)
        if paper.publication_date and self.min_citations > 0:
            try:
                pub_date = datetime.strptime(paper.publication_date, '%Y-%m-%d')
                age_days = (datetime.now() - pub_date).days
                
                if age_days > self.citation_filter_age_days:
                    if paper.citation_count < self.min_citations:
                        logger.debug(f"Paper '{paper.title[:50]}...' filtered: only {paper.citation_count} citations after {age_days} days")
                        return False
            except (ValueError, TypeError):
                pass  # Can't parse date, skip citation filter
        
        return True


class LiteraturePipeline:
    """
    Main pipeline orchestrating literature search, filtering, and Zotero import.
    Supports topic-based classification and quality filtering.
    """
    
    def __init__(
        self,
        ss_api_key: str,
        zotero_library_id: str,
        zotero_api_key: str,
        zotero_library_type: str = "user"
    ):
        self.ss_client = SemanticScholarClient(api_key=ss_api_key)
        self.zotero = ZoteroPusher(zotero_library_id, zotero_api_key, zotero_library_type)
        
        # Configuration (set via configure())
        self.topics: Dict[str, Dict] = {}
        self.legacy_keywords: List[str] = []
        self.topic_classifier: Optional[TopicClassifier] = None
        self.quality_filter: Optional[QualityFilter] = None
        self.dedup: Optional[DedupStore] = None
        
        self.search_days_back = 7
        self.max_results_per_query = 20
        self.main_collection = "OpenClaw-Battery-Research"
        self.zotero_date_format = "%Y-%m-%d"
        self.enable_topic_subfolders = True
    
    def configure(self, config: Dict):
        """Configure pipeline from dict (loaded from YAML)."""
        # Topic-based keywords (preferred)
        self.topics = config.get('topics', {})
        self.topic_classifier = TopicClassifier(self.topics)
        
        # Legacy keywords (fallback)
        self.legacy_keywords = config.get('keywords', [])
        
        # Quality filtering
        quality_config = config.get('quality_filters', {})
        self.quality_filter = QualityFilter(
            journal_whitelist=config.get('journal_whitelist'),
            journal_blacklist=config.get('journal_blacklist'),
            min_citations=quality_config.get('min_citations', 0),
            citation_filter_age_days=quality_config.get('citation_filter_age_days', 365),
            require_pdf=quality_config.get('require_pdf', False)
        )
        
        # Deduplication
        cache_file = config.get('data_files', {}).get('dedup_cache', 'data/literature-pushed.json')
        self.dedup = DedupStore(cache_file)
        
        # Search parameters
        self.search_days_back = config.get('search_days_back', 7)
        self.max_results_per_query = config.get('max_results_per_query', 20)
        self.daily_import_limit = config.get('daily_import_limit', 5)
        
        # Zotero settings
        zotero_config = config.get('zotero', {})
        self.main_collection = zotero_config.get('main_collection', 'OpenClotero-Battery-Research')
        self.zotero_date_format = zotero_config.get('date_subfolder_format', '%Y-%m-%d')
        self.enable_topic_subfolders = zotero_config.get('enable_topic_subfolders', True)
        
        logger.info(f"Pipeline configured: {len(self.topics)} topics, search {self.search_days_back} days back, daily limit: {self.daily_import_limit}")
    
    def run(self) -> Dict[str, Any]:
        """
        Execute the full pipeline.
        
        Returns:
            Dict with results and statistics
        """
        if not self.dedup or not self.quality_filter:
            raise ValueError("Pipeline not configured. Call configure() first.")
        
        today_str = datetime.now().strftime(self.zotero_date_format)
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'date_folder': today_str,
            'search': {},
            'by_topic': {},
            'quality_filtered': [],
            'new_papers': [],
            'imported': [],
            'errors': []
        }
        
        # Collect all keywords from topics
        all_keywords = []
        keyword_to_topic = {}  # keyword -> list of topic_ids
        
        for topic_id, topic_config in self.topics.items():
            topic_keywords = topic_config.get('keywords', [])
            all_keywords.extend(topic_keywords)
            for kw in topic_keywords:
                if kw not in keyword_to_topic:
                    keyword_to_topic[kw] = []
                keyword_to_topic[kw].append(topic_id)
        
        # Fallback to legacy keywords if no topics defined
        if not all_keywords and self.legacy_keywords:
            all_keywords = self.legacy_keywords
            logger.info(f"Using {len(all_keywords)} legacy keywords (no topics defined)")
        
        # Step 1: Search all keywords
        logger.info(f"Starting search for {len(all_keywords)} keywords across {len(self.topics)} topics...")
        search_results = search_multiple_keywords(
            self.ss_client,
            all_keywords,
            days_back=self.search_days_back,
            limit_per_keyword=self.max_results_per_query
        )
        results['search'] = {kw: len(papers) for kw, papers in search_results.items()}
        
        # Step 2: Aggregate, deduplicate, and classify by topic
        all_papers: Dict[str, Paper] = {}  # paper_id -> Paper
        paper_topics: Dict[str, List[str]] = {}  # paper_id -> [topic_ids]
        
        for kw, papers in search_results.items():
            for paper in papers:
                if paper.paper_id not in all_papers:
                    all_papers[paper.paper_id] = paper
                    paper_topics[paper.paper_id] = []
                
                # Track which topic(s) this keyword belongs to
                for topic_id in keyword_to_topic.get(kw, []):
                    if topic_id not in paper_topics[paper.paper_id]:
                        paper_topics[paper.paper_id].append(topic_id)
        
        logger.info(f"Found {len(all_papers)} unique papers from all keywords")
        results['total_found'] = len(all_papers)
        
        # Step 3: Quality filtering
        quality_papers = [p for p in all_papers.values() if self.quality_filter.matches(p)]
        filtered_out = len(all_papers) - len(quality_papers)
        results['quality_filtered'] = filtered_out
        logger.info(f"Quality filter: {len(quality_papers)}/{len(all_papers)} papers passed ({filtered_out} filtered out)")
        
        # Step 4: Deduplicate against cache
        new_papers = [p for p in quality_papers if self.dedup.is_new(p)]
        results['new_papers_before_limit'] = len(new_papers)
        logger.info(f"{len(new_papers)} papers are new (not in cache)")
        
        if not new_papers:
            logger.info("No new papers to import. Pipeline complete.")
            return results
        
        # Step 5: Rank by quality and apply daily limit
        # Scoring: citations (weighted by age) + venue quality bonus
        def quality_score(paper):
            score = paper.citation_count or 0
            # Bonus for high-quality venues
            if paper.venue:
                venue_lower = paper.venue.lower()
                # Nature/Science family gets high bonus
                if any(v in venue_lower for v in ['nature', 'science', 'joule', 'matter', 'cell']):
                    score += 1000
                # Top energy/materials journals
                elif any(v in venue_lower for v in ['advanced energy', 'advanced materials', 'acs energy', 'nano energy']):
                    score += 500
                # Good journals
                elif any(v in venue_lower for v in ['electrochimica', 'journal of power sources', 'energy storage']):
                    score += 200
            return score
        
        new_papers.sort(key=quality_score, reverse=True)
        
        # Apply daily limit
        papers_to_import = new_papers[:self.daily_import_limit]
        skipped_due_to_limit = len(new_papers) - len(papers_to_import)
        results['new_papers'] = len(papers_to_import)
        results['skipped_due_to_limit'] = skipped_due_to_limit
        
        if skipped_due_to_limit > 0:
            logger.info(f"Daily limit applied: importing top {len(papers_to_import)} papers, skipping {skipped_due_to_limit} lower-quality papers")
        
        # Step 6: Import to Zotero with topic classification
        imported_count = 0
        topic_stats = {tid: 0 for tid in self.topics.keys()}
        
        for paper in papers_to_import:
            topics_for_paper = paper_topics.get(paper.paper_id, [])
            
            if not topics_for_paper:
                # No topic match - import to "Uncategorized" or skip
                topics_for_paper = ['uncategorized']
            
            for topic_id in topics_for_paper:
                topic_name = self.topics.get(topic_id, {}).get('name', topic_id) if topic_id != 'uncategorized' else 'Uncategorized'
                
                try:
                    if self.enable_topic_subfolders:
                        # Three-level: Main/Date/Topic
                        collection_key = self.zotero.ensure_collection_path(
                            self.main_collection,
                            today_str,
                            topic_name
                        )
                    else:
                        # Two-level: Main/Date
                        collection_key = self.zotero.ensure_collection_path(
                            self.main_collection,
                            today_str
                        )
                    
                    # Add paper to the appropriate collection
                    item_key = self.zotero.add_paper_to_collection(paper, collection_key)
                    
                    if item_key:
                        imported_count += 1
                        if topic_id in topic_stats:
                            topic_stats[topic_id] += 1
                        
                        # Only mark as pushed once (even if in multiple topics)
                        if paper.paper_id not in self.dedup.paper_ids:
                            self.dedup.mark_as_pushed(paper)
                        
                        logger.info(f"Imported '{paper.title[:50]}...' to {topic_name}")
                        
                        # Break after first successful import (avoid duplicates across topics)
                        break
                        
                except Exception as e:
                    logger.error(f"Failed to import '{paper.title[:50]}...': {e}")
                    results['errors'].append(f"{paper.paper_id}: {str(e)}")
        
        results['imported_count'] = imported_count
        results['by_topic'] = topic_stats
        
        # Step 6: Generate summary
        summary = self._generate_summary(new_papers, imported_count, topic_stats, today_str)
        results['summary'] = summary
        
        return results
    
    def _generate_summary(self, papers: List[Paper], imported: int, topic_stats: Dict, date_str: str) -> str:
        """Generate human-readable summary for notifications."""
        lines = [
            f"📚 Zotero Literature Update - {date_str}",
            "",
            f"Quality papers found: {len(papers)}",
            f"Successfully imported: {imported}",
            "",
            "By topic:"
        ]
        
        for topic_id, count in topic_stats.items():
            topic_name = self.topics.get(topic_id, {}).get('name', topic_id)
            lines.append(f"  • {topic_name}: {count} papers")
        
        lines.extend(["", "Top papers:"])
        
        # Sort by citation count and show top 5
        sorted_papers = sorted(papers, key=lambda p: p.citation_count, reverse=True)[:5]
        for i, p in enumerate(sorted_papers, 1):
            venue_str = f" ({p.venue})" if p.venue else ""
            topics = self.topic_classifier.classify(p) if self.topic_classifier else []
            topic_str = f" [{', '.join(topics[:2])}]" if topics else ""
            lines.append(f"{i}. {p.title[:60]}{'...' if len(p.title) > 60 else ''}{venue_str}{topic_str}")
            lines.append(f"   Authors: {', '.join(p.authors[:3])}{'...' if len(p.authors) > 3 else ''}")
            lines.append(f"   Citations: {p.citation_count} | Year: {p.year or 'N/A'}")
            lines.append("")
        
        return "\n".join(lines)


def run_pipeline_from_config(config_path: str) -> Dict[str, Any]:
    """
    Convenience function to run pipeline from YAML config.
    """
    import yaml
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # Resolve API keys
    ss_key = config['api_keys']['semantic_scholar']
    zot_lib = config['zotero']['library_id']
    zot_key = config['zotero']['api_key']
    
    # Create and configure pipeline
    pipeline = LiteraturePipeline(
        ss_api_key=ss_key,
        zotero_library_id=zot_lib,
        zotero_api_key=zot_key
    )
    pipeline.configure(config)
    
    # Run
    return pipeline.run()
