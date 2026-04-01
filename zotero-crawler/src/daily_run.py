# CLI entry point for daily runs
import sys
import os
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from literature_pipeline import run_pipeline_from_config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Entry point for daily literature crawl."""
    # Default config path
    config_path = Path(__file__).parent.parent / "config" / "zotero-crawler.yaml"
    
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        logger.error("Please copy config/zotero-crawler.yaml.example to config/zotero-crawler.yaml and fill in your API keys")
        sys.exit(1)
    
    logger.info("Starting Zotero literature crawl...")
    
    try:
        results = run_pipeline_from_config(str(config_path))
        
        # Print summary
        if 'summary' in results:
            print("\n" + "="*50)
            print(results['summary'])
            print("="*50)
        
        # Exit code based on success
        imported_count = results.get('imported_count', 0)
        if imported_count > 0:
            logger.info(f"Successfully imported {imported_count} papers")
            sys.exit(0)
        else:
            logger.info("No new papers found today")
            sys.exit(0)  # Not an error, just no new content
            
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
