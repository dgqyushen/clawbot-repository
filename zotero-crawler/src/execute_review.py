#!/usr/bin/env python3
"""
Execute reviewed papers import - Import papers that passed AI/human review.

Usage:
    python src/execute_review.py data/reviews/review_2026-04-01_023045.json
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any
import logging

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from literature_pipeline import LiteraturePipeline, run_pipeline_from_config
from semantic_scholar import Paper
from config_loader import load_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_review_file(review_path: str) -> Dict[str, Any]:
    """Load review JSON file."""
    with open(review_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def execute_import(review_path: str, config_path: str = "config/zotero-crawler.yaml") -> Dict[str, Any]:
    """
    Import papers that were approved in review.
    
    Args:
        review_path: Path to review JSON file
        config_path: Path to crawler config
        
    Returns:
        Import results
    """
    # Load review data
    review_data = load_review_file(review_path)
    
    logger.info(f"Executing review from: {review_path}")
    logger.info(f"Total papers in review: {review_data['total_papers']}")
    
    # Filter approved papers
    approved_papers = [p for p in review_data['papers'] if p.get('proposed_import', False)]
    skipped_papers = [p for p in review_data['papers'] if not p.get('proposed_import', False)]
    
    logger.info(f"Approved for import: {len(approved_papers)}")
    logger.info(f"Skipped: {len(skipped_papers)}")
    
    if not approved_papers:
        logger.info("No papers approved for import.")
        return {
            'imported': 0,
            'skipped': len(skipped_papers),
            'message': 'No papers approved for import'
        }
    
    # Load config and create pipeline
    config = load_config(config_path)
    
    ss_api_key = config.get('api_keys', {}).get('semantic_scholar', '')
    zotero_config = config.get('zotero', {})
    zotero_library_id = zotero_config.get('library_id', '')
    zotero_api_key = zotero_config.get('api_key', '')
    zotero_library_type = zotero_config.get('library_type', 'user')
    
    if not ss_api_key or not zotero_api_key:
        raise ValueError("Missing API keys in config")
    
    pipeline = LiteraturePipeline(
        ss_api_key=ss_api_key,
        zotero_library_id=zotero_library_id,
        zotero_api_key=zotero_api_key,
        zotero_library_type=zotero_library_type
    )
    pipeline.configure(config)
    
    # Import approved papers
    from datetime import datetime
    
    today_str = review_data.get('date', datetime.now().strftime("%Y-%m-%d"))
    imported_count = 0
    topic_stats = {}
    
    for paper_data in approved_papers:
        # Reconstruct Paper object
        paper = Paper(
            paper_id=paper_data['paper_id'],
            title=paper_data['title'],
            abstract=paper_data.get('abstract'),
            authors=paper_data['authors'],
            venue=paper_data['venue'],
            year=paper_data['year'],
            publication_date=paper_data.get('publication_date'),
            citation_count=paper_data.get('citation_count', 0),
            reference_count=0,  # Not stored in review
            influential_citation_count=0,  # Not stored in review
            pdf_url=paper_data.get('pdf_url'),
            url=f"https://semanticscholar.org/paper/{paper_data['paper_id']}",
            doi=None,
            fields_of_study=[],
            tldr=None
        )
        
        topics = paper_data.get('topics', [])
        
        for topic_id in topics if topics else ['uncategorized']:
            topic_name = pipeline.topics.get(topic_id, {}).get('name', topic_id) if topic_id != 'uncategorized' else 'Uncategorized'
            
            try:
                if pipeline.enable_topic_subfolders:
                    collection_key = pipeline.zotero.ensure_collection_path(
                        pipeline.main_collection,
                        today_str,
                        topic_name
                    )
                else:
                    collection_key = pipeline.zotero.ensure_collection_path(
                        pipeline.main_collection,
                        today_str
                    )
                
                item_key = pipeline.zotero.add_paper_to_collection(paper, collection_key)
                
                if item_key:
                    imported_count += 1
                    topic_stats[topic_id] = topic_stats.get(topic_id, 0) + 1
                    
                    pipeline.dedup.mark_as_pushed(paper)
                    pipeline.database.mark_imported(paper.paper_id, item_key)
                    
                    logger.info(f"✅ Imported: {paper.title[:60]}...")
                    break
                    
            except Exception as e:
                logger.error(f"❌ Failed to import '{paper.title[:50]}...': {e}")
    
    # Generate summary
    summary = f"""
{'='*50}
📚 Import Complete - {today_str}
{'='*50}

Approved: {len(approved_papers)}
Successfully imported: {imported_count}

By topic:
"""
    for topic_id, count in topic_stats.items():
        topic_name = pipeline.topic_classifier.get_topic_name(topic_id) if pipeline.topic_classifier else topic_id
        summary += f"  - {topic_name}: {count}\n"
    
    summary += f"""
Skipped during review: {len(skipped_papers)}
{'='*50}
"""
    
    logger.info(summary)
    
    return {
        'imported': imported_count,
        'approved': len(approved_papers),
        'skipped_review': len(skipped_papers),
        'by_topic': topic_stats,
        'summary': summary
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python src/execute_review.py <review_json_file>")
        print("Example: python src/execute_review.py data/reviews/review_2026-04-01_023045.json")
        sys.exit(1)
    
    review_file = sys.argv[1]
    config_file = sys.argv[2] if len(sys.argv) > 2 else "config/zotero-crawler.yaml"
    
    results = execute_import(review_file, config_file)
    print("\n" + results.get('summary', 'No summary'))
