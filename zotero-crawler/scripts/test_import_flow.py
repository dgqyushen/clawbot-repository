#!/usr/bin/env python3
"""
Test script: Skip search, directly test Zotero import flow.

This simulates having papers from Semantic Scholar and tests:
1. Deduplication (SQLite)
2. Zotero API import
3. Notification
"""

import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from semantic_scholar import Paper
from database import PaperDatabase
from zotero_export import ZoteroClient
from notifier import BarkNotifier
from loguru import logger
import yaml


def setup_logging():
    """Configure logging."""
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(message)s'
    )


def create_mock_papers() -> list:
    """Create mock paper data for testing."""
    import time
    timestamp = int(time.time())
    return [
        Paper(
            paper_id=f"test_{timestamp}_1",
            title="High-Performance Silicon-Carbon Composite Anodes for Lithium-Ion Batteries",
            authors=["Zhang, Wei", "Li, Ming", "Chen, Yu"],
            year=2024,
            citation_count=45,
            publication_date="2024-02-15",
            journal="Journal of Power Sources",
            abstract="This study presents a novel silicon-carbon composite anode material...",
            doi=f"10.1016/j.jpowsour.2024.{timestamp}1",
            arxiv_id=None,
            url="https://doi.org/10.1016/j.jpowsour.2024.mock",
            open_access_pdf=None,
            tldr="Novel Si-C composite improves cycling stability and capacity retention.",
            fields_of_study=["Materials Science", "Chemistry"],
        ),
        Paper(
            paper_id=f"test_{timestamp}_2",
            title="Solid Electrolyte Interphase Engineering in Silicon-Based Anodes",
            authors=["Wang, Jie", "Liu, Hua"],
            year=2023,
            citation_count=32,
            publication_date="2023-11-20",
            journal="Nature Energy",
            abstract="SEI stabilization is critical for silicon anode durability...",
            doi=f"10.1038/s41560-023.{timestamp}2",
            arxiv_id=None,
            url="https://doi.org/10.1038/s41560-023-mock",
            open_access_pdf=None,
            tldr="SEI engineering extends cycle life of Si anodes to over 500 cycles.",
            fields_of_study=["Energy", "Materials Science"],
        ),
    ]


def test_import_flow(config: dict, dry_run: bool = True):
    """
    Test the complete import flow with mock data.
    
    Args:
        config: Configuration dict
        dry_run: If True, don't actually import to Zotero
    """
    logger.info("=" * 60)
    logger.info("Testing Zotero Import Flow (Mock Data)")
    logger.info("=" * 60)
    
    # Get config
    zotero_config = config.get("zotero", {})
    api_config = config.get("api_keys", {})
    zotero_api = api_config.get("zotero", {})
    notification_config = config.get("notification", {})
    
    target_collection = zotero_config.get("target_collection", "Test Import")
    tags = zotero_config.get("tags", ["test"])
    
    bark_key = notification_config.get("bark_key", "")
    bark_url = notification_config.get("bark_url", "https://api.day.app")
    
    # Create mock papers
    mock_papers = create_mock_papers()
    logger.info(f"Created {len(mock_papers)} mock papers for testing")
    
    total_new = 0
    imported_papers = []
    
    try:
        # Initialize database
        with PaperDatabase() as db:
            logger.info("Database initialized")
            
            # Check deduplication for each paper
            for paper in mock_papers:
                is_dup, existing_id = db.is_duplicate(paper)
                if is_dup:
                    logger.warning(f"Duplicate found (ID: {existing_id}): {paper.title[:50]}...")
                    continue
                
                # Add to database
                db.add_paper(paper, keywords_matched=["Si C Anode"])
                total_new += 1
                imported_papers.append(paper)
                logger.info(f"✓ Added to database: {paper.title[:50]}...")
                
                # Import to Zotero (unless dry_run)
                if not dry_run and zotero_api.get("api_key"):
                    try:
                        with ZoteroClient(
                            library_id=zotero_api["library_id"],
                            api_key=zotero_api["api_key"],
                            library_type=zotero_api.get("library_type", "user"),
                        ) as zotero:
                            # Get or create collection
                            collection_key = zotero.get_or_create_collection(target_collection)
                            
                            # Create item
                            item = paper.to_zotero_item()
                            item_key = zotero.create_item(item, collection_key)
                            
                            # Mark as imported in DB
                            db.mark_imported(paper.paper_id, item_key)
                            
                            # Add tags
                            if tags:
                                zotero.add_tags(item_key, tags)
                            
                            # Add note
                            note_text = f"<h3>自动导入信息</h3>\n"
                            note_text += f"<p><b>引用数:</b> {paper.citation_count}</p>\n"
                            if paper.tldr:
                                note_text += f"<p><b>要点:</b> {paper.tldr}</p>\n"
                            zotero.add_note(item_key, note_text)
                            
                            logger.info(f"✓ Imported to Zotero: {item_key}")
                            
                    except Exception as e:
                        logger.error(f"Failed to import to Zotero: {e}")
                else:
                    logger.info(f"  [Dry-run] Would import to Zotero collection: {target_collection}")
            
            # Show database stats
            stats = db.get_stats()
            logger.info("-" * 60)
            logger.info(f"Database stats: {stats}")
        
        # Send notification (if configured and papers were found)
        if bark_key and total_new > 0:
            try:
                with BarkNotifier(bark_key, bark_url) as notifier:
                    date_str = datetime.now().strftime("%Y-%m-%d")
                    notifier.send_literature_summary(
                        date=date_str,
                        total_found=len(mock_papers),
                        new_imported=total_new,
                        papers=imported_papers,
                        max_detail=notification_config.get("max_detail_papers", 5),
                    )
                    logger.info("✓ Notification sent")
            except Exception as e:
                logger.error(f"Failed to send notification: {e}")
        else:
            logger.info("[Notification skipped - no bark_key or no new papers]")
        
        logger.info("=" * 60)
        logger.info(f"Test complete: {total_new} papers processed")
        logger.info("=" * 60)
        return total_new
        
    except Exception as e:
        logger.exception(f"Test failed: {e}")
        raise


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Zotero import flow with mock data")
    parser.add_argument(
        "--config",
        default="/root/.openclaw/workspace/projects/zotero-crawler/config/topics/battery-research.yaml",
        help="Path to config file",
    )
    parser.add_argument(
        "--no-dry-run",
        action="store_true",
        help="Actually import to Zotero (default is dry-run)",
    )
    
    args = parser.parse_args()
    
    # Load config
    with open(args.config, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    # Run test
    dry_run = not args.no_dry_run
    if dry_run:
        logger.info("🧪 DRY RUN MODE - No actual Zotero imports")
    else:
        logger.info("⚠️  LIVE MODE - Will import to real Zotero library!")
    
    count = test_import_flow(config, dry_run=dry_run)
    
    if dry_run:
        logger.info("\n💡 To actually import to Zotero, run with: --no-dry-run")
    
    return 0 if count > 0 else 1


if __name__ == "__main__":
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(message)s'
    )
    sys.exit(main())
