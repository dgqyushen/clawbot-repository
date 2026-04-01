"""
Literature Pipeline - Main orchestration module
Coordinates search, filtering, deduplication, and Zotero import with topic classification.
FIXED VERSION: Now properly records papers to database
"""

import json
import logging
from typing import List, Dict, Set, Any, Optional, Tuple
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path

from semantic_scholar import SemanticScholarClient, Paper, search_multiple_keywords
from zotero_pusher import ZoteroPusher
from database import PaperDatabase  # ADDED: Import database

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
    """Filters papers based on journal quality, citation metrics, and content keywords."""
    
    def __init__(
        self,
        journal_whitelist: Optional[List[str]] = None,
        journal_blacklist: Optional[List[str]] = None,
        excluded_keywords: Optional[List[str]] = None,  # ADDED
        min_citations: int = 0,
        citation_filter_age_days: int = 365,
        require_pdf: bool = False
    ):
        self.journal_whitelist = [j.lower() for j in (journal_whitelist or [])]
        self.journal_blacklist = [j.lower() for j in (journal_blacklist or [])]
        self.excluded_keywords = [k.lower() for k in (excluded_keywords or [])]  # ADDED
        self.min_citations = min_citations
        self.citation_filter_age_days = citation_filter_age_days
        self.require_pdf = require_pdf
    
    def is_quality_venue(self, venue: Optional[str]) -> bool:
        """Check if venue is in whitelist or not in blacklist."""
        if not venue:
            return True  # No venue info, can't filter
        
        venue_lower = venue.lower()
        venue_words = set(venue_lower.split())
        
        # Blacklist check first
        for blacklisted in self.journal_blacklist:
            # Check for exact word match or subphrase match
            black_lower = blacklisted.lower()
            if black_lower in venue_lower or black_lower in venue_words:
                logger.debug(f"Venue '{venue}' matches blacklist '{blacklisted}'")
                return False
        
        # Whitelist check (if whitelist exists)
        if self.journal_whitelist:
            for whitelisted in self.journal_whitelist:
                whitelisted_lower = whitelisted.lower()
                # STRICT MATCH: venue must start with whitelisted journal name
                # OR whitelisted journal must be a complete word/phrase in venue
                if venue_lower.startswith(whitelisted_lower):
                    return True
                # Also check if whitelisted is a complete word in venue (for abbreviations like JACS)
                if whitelisted_lower in venue_words:
                    return True
            # Not in whitelist
            logger.debug(f"Venue '{venue}' not in whitelist, filtering out")
            return False
        
        return True
    
    def matches(self, paper: Paper) -> bool:
        """Check if paper passes quality filters."""
        # KEYWORD FILTER: Check title and abstract for excluded keywords
        if self.excluded_keywords:
            text_to_check = (paper.title or "") + " " + (paper.abstract or "")
            text_lower = text_to_check.lower()
            for keyword in self.excluded_keywords:
                if keyword in text_lower:
                    logger.debug(f"Paper '{paper.title[:50]}...' filtered: excluded keyword '{keyword}'")
                    return False
        
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
    NEW: AI review layer before import
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
        self.database: Optional[PaperDatabase] = None  # ADDED: Database instance
        
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
        
        # Merge journal_blacklist with excluded_venues from topics
        journal_blacklist = config.get('journal_blacklist', [])
        excluded_keywords = []  # ADDED: Collect excluded keywords from all topics
        for topic_id, topic_config in self.topics.items():
            excluded_venues = topic_config.get('excluded_venues', [])
            journal_blacklist.extend(excluded_venues)
            # ADDED: Collect excluded keywords
            topic_excluded_keywords = topic_config.get('excluded_keywords', [])
            excluded_keywords.extend(topic_excluded_keywords)
        
        journal_whitelist = config.get('journal_whitelist', [])
        logger.info(f"QualityFilter: whitelist={len(journal_whitelist)} journals, blacklist={len(journal_blacklist)} journals, excluded_keywords={len(excluded_keywords)}")
        
        self.quality_filter = QualityFilter(
            journal_whitelist=journal_whitelist,
            journal_blacklist=list(set(journal_blacklist)) if journal_blacklist else None,  # Remove duplicates
            excluded_keywords=list(set(excluded_keywords)) if excluded_keywords else None,  # ADDED
            min_citations=quality_config.get('min_citations', 0),
            citation_filter_age_days=quality_config.get('citation_filter_age_days', 365),
            require_pdf=quality_config.get('require_pdf', False)
        )
        
        # Deduplication
        cache_file = config.get('data_files', {}).get('dedup_cache', 'data/literature-pushed.json')
        self.dedup = DedupStore(cache_file)
        
        # ADDED: Initialize database
        db_path = config.get('data_files', {}).get('db_path', 'data/papers.db')
        self.database = PaperDatabase(db_path)
        
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
        if not self.dedup or not self.quality_filter or not self.database:  # MODIFIED: Check database
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
        
        # Step 4: Deduplicate against cache AND database
        new_papers = []
        for p in quality_papers:
            # Check both dedup cache and database
            if self.dedup.is_new(p):
                is_dup_db, _ = self.database.is_duplicate(p)
                if not is_dup_db:
                    new_papers.append(p)
                else:
                    logger.debug(f"Paper {p.paper_id} already in database")
        
        results['new_papers_before_limit'] = len(new_papers)
        logger.info(f"{len(new_papers)} papers are new (not in cache or database)")
        
        # ADDED: Record all new papers to database (before importing)
        for paper in new_papers:
            topics = paper_topics.get(paper.paper_id, [])
            self.database.add_paper(paper, topics)
        
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
        
        # NEW Step 5.5: AI Review Layer - Pause for human/AI review before import
        if papers_to_import:
            logger.info("=" * 60)
            logger.info("🤖 AI REVIEW: Please review papers before import")
            logger.info("=" * 60)
            self._generate_review_file(papers_to_import, paper_topics, today_str, results)
            # Return early with papers pending review
            results['status'] = 'pending_review'
            results['pending_import_count'] = len(papers_to_import)
            logger.info("Review file generated. Please confirm import.")
            return results
        
        # If no review needed (empty list), continue to import
        results['status'] = 'no_papers'
        return results
        
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
                        
                        # ADDED: Mark as imported in database
                        self.database.mark_imported(paper.paper_id, item_key)
                        
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
            ""
        ]
        
        if topic_stats:
            lines.append("By topic:")
            for topic_id, count in topic_stats.items():
                if count > 0:
                    topic_name = self.topic_classifier.get_topic_name(topic_id) if self.topic_classifier else topic_id
                    lines.append(f"  - {topic_name}: {count}")
            lines.append("")
        
        if papers:
            lines.append("Top papers:")
            for paper in papers[:5]:
                lines.append(f"  • {paper.title}")
                if paper.venue:
                    lines.append(f"    {paper.venue} ({paper.year})")
        
        return "\n".join(lines)
    
    def _generate_review_file(self, papers: List[Paper], paper_topics: Dict, date_str: str, results: Dict) -> str:
        """Generate a review file for AI/human review before import."""
        import json
        from pathlib import Path
        from datetime import datetime
        
        review_dir = Path("data/reviews")
        review_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        review_file = review_dir / f"review_{date_str}_{timestamp}.json"
        
        review_data = {
            "timestamp": datetime.now().isoformat(),
            "date": date_str,
            "total_papers": len(papers),
            "papers": []
        }
        
        for i, paper in enumerate(papers, 1):
            topics = paper_topics.get(paper.paper_id, [])
            paper_data = {
                "index": i,
                "paper_id": paper.paper_id,
                "title": paper.title,
                "abstract": paper.abstract,
                "authors": paper.authors,
                "venue": paper.venue,
                "year": paper.year,
                "publication_date": paper.publication_date,
                "citation_count": paper.citation_count,
                "pdf_url": paper.pdf_url,
                "topics": topics,
                "proposed_import": True,
                "ai_recommendation": "pending",
                "ai_reasoning": ""
            }
            review_data["papers"].append(paper_data)
        
        # Also generate a human-readable markdown version
        md_file = review_dir / f"review_{date_str}_{timestamp}.md"
        md_lines = [
            f"# Literature Review - {date_str}",
            f"Generated: {datetime.now().isoformat()}",
            f"Total papers to review: {len(papers)}",
            "",
            "## Instructions",
            "1. Review each paper below",
            "2. Edit the JSON file to mark papers for import:",
            "   - Set `\"proposed_import\": true` to import",
            "   - Set `\"proposed_import\": false` to skip",
            "3. Save the JSON file",
            "4. Run: `python src/execute_review.py {review_file}` to import approved papers",
            "",
            "---",
            ""
        ]
        
        for paper_data in review_data["papers"]:
            md_lines.extend([
                f"### [{paper_data['index']}] {paper_data['title']}",
                f"- **Authors**: {', '.join(paper_data['authors'][:3])}{' et al.' if len(paper_data['authors']) > 3 else ''}",
                f"- **Journal**: {paper_data['venue']} ({paper_data['year']})",
                f"- **Citations**: {paper_data['citation_count']}",
                f"- **PDF**: {'Available' if paper_data['pdf_url'] else 'Not available'}",
                "",
                "**Abstract:**",
                f"> {paper_data['abstract'][:300]}..." if paper_data['abstract'] else "> No abstract available",
                "",
                "**AI Assessment:**",
                "- [ ] Relevant to Si-C anode research",
                "- [ ] Not sodium-ion or other chemistry",
                "- [ ] Not environmental/catalysis paper",
                "- [ ] Worth importing",
                "",
                f"**Decision**: `proposed_import`: {str(paper_data['proposed_import']).lower()}",
                "",
                "---",
                ""
            ])
        
        # Save both files
        with open(review_file, 'w', encoding='utf-8') as f:
            json.dump(review_data, f, indent=2, ensure_ascii=False)
        
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(md_lines))
        
        logger.info(f"Review files generated:")
        logger.info(f"  - JSON: {review_file}")
        logger.info(f"  - Markdown: {md_file}")
        
        results['review_file'] = str(review_file)
        results['review_md'] = str(md_file)
        
        return str(review_file)


def run_pipeline_from_config(config_path: str) -> Dict[str, Any]:
    """
    Load config and run pipeline.
    
    Args:
        config_path: Path to YAML config file
        
    Returns:
        Pipeline results dict
    """
    import yaml
    from config_loader import load_config
    
    logger.info(f"Loading config from: {config_path}")
    config = load_config(config_path)
    
    # Get API keys from config
    ss_api_key = config.get('api_keys', {}).get('semantic_scholar', '')
    zotero_config = config.get('zotero', {})  # FIX: zotero is top-level, not under api_keys
    zotero_library_id = zotero_config.get('library_id', '')
    zotero_api_key = zotero_config.get('api_key', '')
    zotero_library_type = zotero_config.get('library_type', 'user')
    
    if not ss_api_key or not zotero_api_key:
        raise ValueError("Missing API keys in config. Please set semantic_scholar and zotero api_key.")
    
    # Create and run pipeline
    pipeline = LiteraturePipeline(
        ss_api_key=ss_api_key,
        zotero_library_id=zotero_library_id,
        zotero_api_key=zotero_api_key,
        zotero_library_type=zotero_library_type
    )
    
    pipeline.configure(config)
    return pipeline.run()


if __name__ == "__main__":
    # Test run
    import sys
    import logging
    logging.basicConfig(level=logging.INFO)
    
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    else:
        config_path = "config/zotero-crawler.yaml"
    
    results = run_pipeline_from_config(config_path)
    print("\n" + "="*50)
    print(results.get('summary', 'No summary available'))
    print("="*50)
