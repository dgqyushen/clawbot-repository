"""SQLite database for paper deduplication and tracking."""

import sqlite3
import hashlib
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import asdict
from loguru import logger
from pathlib import Path


class PaperDatabase:
    """Manages SQLite database for paper tracking."""
    
    def __init__(self, db_path: str | None = None):
        """Initialize database connection."""
        if db_path is None:
            db_path = str(Path(__file__).resolve().parent.parent / "data" / "papers.db")

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        
        self._init_tables()
        logger.info(f"Database initialized: {self.db_path}")
    
    def _init_tables(self):
        """Create tables if they don't exist."""
        cursor = self.conn.cursor()
        
        # Main papers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS papers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id TEXT UNIQUE NOT NULL,  -- Semantic Scholar ID
                doi TEXT UNIQUE,
                title TEXT NOT NULL,
                title_hash TEXT NOT NULL,  -- For similarity checking
                authors TEXT,  -- JSON list
                year INTEGER,
                citation_count INTEGER DEFAULT 0,
                journal TEXT,
                abstract TEXT,
                url TEXT,
                open_access_pdf TEXT,
                tldr TEXT,  -- AI summary
                fields_of_study TEXT,  -- JSON list
                keywords_matched TEXT,  -- JSON list of matching keywords
                first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                imported_to_zotero BOOLEAN DEFAULT 0,
                zotero_item_key TEXT,
                zotero_imported_at TIMESTAMP,
                skipped BOOLEAN DEFAULT 0,
                skip_reason TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Index for fast lookups
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers(doi)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_papers_title_hash ON papers(title_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_papers_imported ON papers(imported_to_zotero)")
        
        self.conn.commit()
    
    def _compute_title_hash(self, title: str) -> str:
        """Compute normalized hash for title similarity checking."""
        # Normalize: lowercase, remove extra spaces, punctuation
        normalized = " ".join(title.lower().split())
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def is_duplicate(self, paper) -> tuple[bool, Optional[int]]:
        """
        Check if paper is already in database.
        
        Returns:
            (is_duplicate, existing_id)
        """
        cursor = self.conn.cursor()
        
        # Check by DOI (most reliable)
        if paper.doi:
            cursor.execute("SELECT id FROM papers WHERE doi = ?", (paper.doi,))
            row = cursor.fetchone()
            if row:
                return True, row["id"]
        
        # Check by Semantic Scholar ID
        cursor.execute("SELECT id FROM papers WHERE paper_id = ?", (paper.paper_id,))
        row = cursor.fetchone()
        if row:
            return True, row["id"]
        
        # Check by title hash (fallback)
        title_hash = self._compute_title_hash(paper.title)
        cursor.execute("SELECT id FROM papers WHERE title_hash = ?", (title_hash,))
        row = cursor.fetchone()
        if row:
            return True, row["id"]
        
        return False, None
    
    def add_paper(self, paper, keywords_matched: List[str]) -> int:
        """
        Add new paper to database.
        
        Returns:
            ID of inserted paper
        """
        cursor = self.conn.cursor()
        
        import json
        
        cursor.execute("""
            INSERT INTO papers (
                paper_id, doi, title, title_hash, authors, year, citation_count,
                journal, abstract, url, open_access_pdf, tldr, fields_of_study,
                keywords_matched
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            paper.paper_id,
            paper.doi,
            paper.title,
            self._compute_title_hash(paper.title),
            json.dumps(paper.authors),
            paper.year,
            paper.citation_count,
            paper.journal,
            paper.abstract,
            paper.url,
            paper.open_access_pdf,
            paper.tldr,
            json.dumps(paper.fields_of_study),
            json.dumps(keywords_matched),
        ))
        
        self.conn.commit()
        return cursor.lastrowid
    
    def mark_imported(self, paper_id: str, zotero_item_key: str):
        """Mark paper as imported to Zotero."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE papers 
            SET imported_to_zotero = 1, zotero_item_key = ?, zotero_imported_at = ?
            WHERE paper_id = ?
        """, (zotero_item_key, datetime.now().isoformat(), paper_id))
        self.conn.commit()
        logger.debug(f"Marked imported: {paper_id} -> {zotero_item_key}")
    
    def mark_skipped(self, paper_id: str, reason: str):
        """Mark paper as skipped (not interested)."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE papers SET skipped = 1, skip_reason = ? WHERE paper_id = ?
        """, (reason, paper_id))
        self.conn.commit()
    
    def get_new_papers(self, since: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get papers that haven't been imported yet."""
        cursor = self.conn.cursor()
        
        query = "SELECT * FROM papers WHERE imported_to_zotero = 0 AND skipped = 0"
        params = []
        
        if since:
            query += " AND first_seen_at >= ?"
            params.append(since)
        
        query += " ORDER BY citation_count DESC"
        
        if limit:
            query += f" LIMIT {limit}"
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_stats(self) -> Dict[str, int]:
        """Get database statistics."""
        cursor = self.conn.cursor()
        
        stats = {}
        
        cursor.execute("SELECT COUNT(*) FROM papers")
        stats["total_papers"] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM papers WHERE imported_to_zotero = 1")
        stats["imported_count"] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM papers WHERE imported_to_zotero = 0 AND skipped = 0")
        stats["pending_count"] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM papers WHERE skipped = 1")
        stats["skipped_count"] = cursor.fetchone()[0]
        
        return stats
    
    def close(self):
        """Close database connection."""
        self.conn.close()
        logger.info("Database connection closed")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
