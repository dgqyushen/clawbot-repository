#!/usr/bin/env python3
"""
Daily literature crawler - main entry point.

Fetches papers from Semantic Scholar, checks for duplicates,
and imports metadata to Zotero.
"""

import sys
import yaml
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from semantic_scholar import SemanticScholarClient, Paper
from database import PaperDatabase
from zotero_export import ZoteroClient, export_to_csv
from notifier import BarkNotifier


def setup_logging():
    """Configure logging."""
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO",
    )
    log_dir = Path("/root/.openclaw/workspace/projects/zotero-crawler/logs")
    log_dir.mkdir(exist_ok=True)
    logger.add(
        log_dir / "crawler_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="30 days",
        level="DEBUG",
    )


def load_config(config_path: str) -> dict:
    """Load YAML configuration."""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_crawl(config: dict, dry_run: bool = False, since: str = None):
    """
    Main crawl workflow.
    
    Args:
        config: Loaded configuration
        dry_run: If True, don't import to Zotero
        since: Only fetch papers published after this date (YYYY-MM-DD)
    """
    setup_logging()
    logger.info(f"Starting literature crawl (dry_run={dry_run})")
    
    # Parse config
    api_config = config.get("api_keys", {})
    ss_api_key = api_config.get("semantic_scholar", "")
    zotero_config = api_config.get("zotero", {})
    
    keywords_config = config.get("keywords", {})
    primary_keywords = keywords_config.get("primary", [])
    secondary_keywords = keywords_config.get("secondary", [])
    all_keywords = primary_keywords + secondary_keywords
    
    search_config = config.get("search", {})
    fields = search_config.get("fields", [])
    limit_per_keyword = search_config.get("max_results_per_keyword", 10)
    min_year = search_config.get("min_year")
    sort_by = search_config.get("sort_by", "publicationDate")
    
    zotero_export_config = config.get("zotero", {})
    target_collection = zotero_export_config.get("target_collection", "Daily Auto-Import")
    tags = zotero_export_config.get("tags", ["auto-import"])
    
    notification_config = config.get("notification", {})
    bark_key = notification_config.get("bark_key")
    bark_url = notification_config.get("bark_url", "https://api.day.app")
    max_detail = notification_config.get("max_detail_papers", 5)
    
    # Override min_year if since is provided
    if since:
        since_year = int(since.split("-")[0])
        min_year = max(min_year or 0, since_year)
    
    total_found = 0
    total_new = 0
    imported_papers = []
    errors = []
    
    try:
        # Initialize components
        with SemanticScholarClient(api_key=ss_api_key) as ss_client, \
             PaperDatabase() as db, \
             BarkNotifier(bark_key, bark_url) as notifier if bark_key else None as notifier:
            
            # Initialize Zotero client if not dry_run
            zotero = None
            if not dry_run and zotero_config.get("api_key"):
                zotero = ZoteroClient(
                    library_id=zotero_config["library_id"],
                    api_key=zotero_config["api_key"],
                    library_type=zotero_config.get("library_type", "user"),
                )
                # Get or create target collection
                collection_key = zotero.get_or_create_collection(target_collection)
            else:
                collection_key = None
            
            # Search all keywords
            for keyword in all_keywords:
                logger.info(f"Searching keyword: '{keyword}'")
                
                try:
                    papers = ss_client.search_papers(
                        query=keyword,
                        fields=fields,
                        limit=limit_per_keyword,
                        min_year=min_year,
                        sort_by=sort_by,
                    )
                    
                    keyword_new = 0
                    for paper in papers:
                        total_found += 1
                        
                        # Check for duplicates
                        is_dup, _ = db.is_duplicate(paper)
                        if is_dup:
                            logger.debug(f"Skipping duplicate: {paper.title[:50]}...")
                            continue
                        
                        # Add to database
                        db.add_paper(paper, keywords_matched=[keyword])
                        total_new += 1
                        keyword_new += 1
                        imported_papers.append(paper)
                        
                        # Import to Zotero if not dry_run
                        if zotero and collection_key:
                            try:
                                item = paper.to_zotero_item()
                                item_key = zotero.create_item(item, collection_key)
                                db.mark_imported(paper.paper_id, item_key)
                                
                                # Add tags
                                if tags:
                                    zotero.add_tags(item_key, tags)
                                
                                # Add note with citation count and TLDR
                                note_text = f"<h3>自动导入信息</h3>\n"
                                note_text += f"<p><b>引用数:</b> {paper.citation_count}</p>\n"
                                if paper.tldr:
                                    note_text += f"<p><b>要点:</b> {paper.tldr}</p>\n"
                                note_text += f"<p><b>关键词匹配:</b> {keyword}</p>"
                                zotero.add_note(item_key, note_text)
                                
                                logger.info(f"Imported to Zotero: {paper.title[:50]}...")
                                
                            except Exception as e:
                                logger.error(f"Failed to import to Zotero: {e}")
                                errors.append(f"Zotero import failed for '{paper.title}': {e}")
                    
                    # Record search history
                    db.record_search(keyword, len(papers), keyword_new)
                    logger.info(f"Keyword '{keyword}': {len(papers)} found, {keyword_new} new")
                    
                except Exception as e:
                    logger.error(f"Search failed for keyword '{keyword}': {e}")
                    errors.append(f"Search failed for '{keyword}': {e}")
                    db.record_search(keyword, 0, 0, error=str(e))
            
            # Close Zotero client if opened
            if zotero:
                zotero.close()
            
            # Send notification
            if notifier and (total_new > 0 or errors):
                date_str = datetime.now().strftime("%Y-%m-%d")
                if errors:
                    # Send error notification
                    error_text = "\n".join(errors[:3])  # First 3 errors
                    notifier.send_error(error_text)
                else:
                    # Send success notification
                    notifier.send_literature_summary(
                        date=date_str,
                        total_found=total_found,
                        new_imported=total_new,
                        papers=imported_papers,
                        max_detail=max_detail,
                    )
        
        # Summary
        logger.info("=" * 50)
        logger.info(f"Crawl complete: {total_found} found, {total_new} new")
        if errors:
            logger.warning(f"Errors: {len(errors)}")
        logger.info("=" * 50)
        
        return total_new
        
    except Exception as e:
        logger.exception(f"Crawl failed: {e}")
        # Try to send error notification
        if bark_key:
            try:
                with BarkNotifier(bark_key, bark_url) as notifier:
                    notifier.send_error(str(e))
            except:
                pass
        raise


def main():
    parser = argparse.ArgumentParser(description="Daily literature crawler for Zotero")
    parser.add_argument(
        "--config",
        default="/root/.openclaw/workspace/projects/zotero-crawler/config/keywords.yaml",
        help="Path to config file",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without importing to Zotero (testing mode)",
    )
    parser.add_argument(
        "--since",
        help="Only fetch papers published after this date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--export-csv",
        help="Export new papers to CSV instead of importing to Zotero",
    )
    
    args = parser.parse_args()
    
    # Load config
    config = load_config(args.config)
    
    # Run crawl
    try:
        count = run_crawl(config, dry_run=args.dry_run, since=args.since)
        
        # Export to CSV if requested
        if args.export_csv and count > 0:
            # This would need refactoring to track which papers to export
            logger.info(f"CSV export requested: {args.export_csv}")
        
        sys.exit(0 if not args.dry_run or count > 0 else 1)
        
    except Exception as e:
        logger.error(f"Failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
