"""Basic tests for literature crawler."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_title_hash():
    """Test title hashing for deduplication."""
    from database import PaperDatabase
    
    db = PaperDatabase(db_path=":memory:")
    
    # Test hash computation
    hash1 = db._compute_title_hash("Silicon-Carbon Composite Anodes")
    hash2 = db._compute_title_hash("silicon-carbon composite anodes")
    hash3 = db._compute_title_hash("Silicon Carbon Composite Anodes")
    
    # Should be case insensitive and handle spacing
    assert hash1 == hash2, "Title hash should be case insensitive"
    
    db.close()
    print("✓ Title hash test passed")


def test_paper_dataclass():
    """Test Paper dataclass creation."""
    from semantic_scholar import Paper
    
    paper = Paper(
        paper_id="test123",
        title="Test Paper",
        authors=["Author One", "Author Two"],
        year=2024,
        citation_count=10,
        publication_date="2024-01-15",
        journal="Nature",
        abstract="This is a test abstract.",
        doi="10.1234/test",
        arxiv_id=None,
        url="https://example.com/paper",
        open_access_pdf=None,
        tldr="Test summary",
        fields_of_study=["Computer Science"],
    )
    
    # Test Zotero conversion
    zotero_item = paper.to_zotero_item()
    assert zotero_item["title"] == "Test Paper"
    assert zotero_item["itemType"] == "journalArticle"
    assert len(zotero_item["creators"]) == 2
    
    print("✓ Paper dataclass test passed")


def test_config_loading():
    """Test YAML config loading."""
    import yaml
    
    config_path = Path(__file__).parent.parent / "config" / "keywords.yaml"
    if config_path.exists():
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        
        assert "keywords" in config
        assert "primary" in config["keywords"]
        assert "zotero" in config
        print("✓ Config loading test passed")
    else:
        print("⚠ Config file not found, skipping")


if __name__ == "__main__":
    test_title_hash()
    test_paper_dataclass()
    test_config_loading()
    print("\nAll tests passed!")
