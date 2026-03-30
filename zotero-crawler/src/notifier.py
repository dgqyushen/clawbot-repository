"""Bark notification helper for sending daily summaries."""

import httpx
from typing import List, Any
from loguru import logger


class BarkNotifier:
    """Sends notifications via Bark app."""
    
    def __init__(self, device_key: str, server_url: str = "https://api.day.app"):
        """
        Initialize Bark notifier.
        
        Args:
            device_key: Bark device key
            server_url: Bark server URL (default: official server)
        """
        self.device_key = device_key
        self.server_url = server_url.rstrip("/")
        
        self.client = httpx.Client(timeout=10.0)
        logger.debug(f"Bark notifier initialized (server: {server_url})")
    
    def send(self, title: str, body: str, group: str = "Literature", sound: str = "newsflash"):
        """
        Send a notification.
        
        Args:
            title: Notification title
            body: Notification body (max ~4000 chars)
            group: Group name for organization
            sound: Sound to play (newsflash, minuet, etc.)
        """
        url = f"{self.server_url}/{self.device_key}/{title}/{body}"
        
        params = {
            "group": group,
            "sound": sound,
        }
        
        try:
            response = self.client.get(url, params=params)
            response.raise_for_status()
            logger.info(f"Notification sent: {title}")
            return True
            
        except httpx.HTTPError as e:
            logger.error(f"Failed to send notification: {e}")
            return False
    
    def send_literature_summary(
        self,
        date: str,
        total_found: int,
        new_imported: int,
        papers: List[Any],
        max_detail: int = 5,
    ):
        """
        Send daily literature summary.
        
        Args:
            date: Date string (e.g., "2026-03-30")
            total_found: Total papers found
            new_imported: Number of new papers imported
            papers: List of Paper objects with highlights
            max_detail: Max papers to include detailed info
        """
        # Build summary
        title = f"📚 文献更新 - {date}"
        
        lines = [
            f"今日共找到 {total_found} 篇论文",
            f"新增导入 Zotero: {new_imported} 篇",
            "",
        ]
        
        # Add highlights for top papers
        if papers:
            lines.append("📌 重点推荐:")
            lines.append("")
            
            for i, paper in enumerate(papers[:max_detail], 1):
                # Get highlight
                highlight = getattr(paper, 'tldr', None) or ""
                if not highlight and hasattr(paper, 'abstract'):
                    # Use first 100 chars of abstract
                    highlight = paper.abstract[:100] + "..." if paper.abstract else ""
                
                lines.append(f"{i}. {paper.title}")
                lines.append(f"   期刊: {paper.journal or 'N/A'} | {paper.year or 'N/A'}")
                lines.append(f"   引用: {paper.citation_count} 次")
                
                if highlight:
                    # Truncate if too long
                    if len(highlight) > 80:
                        highlight = highlight[:77] + "..."
                    lines.append(f"   💡 {highlight}")
                
                lines.append("")
        
        # Add footer
        if new_imported > 0:
            lines.append(f"✅ 已导入 Zotero 收藏夹: 'Daily Auto-Import'")
        else:
            lines.append("ℹ️ 今日无新增文献")
        
        body = "\n".join(lines)
        
        # Truncate if too long (Bark has ~4000 char limit)
        if len(body) > 3900:
            body = body[:3850] + "\n\n...(内容已截断)"
        
        return self.send(title, body, group="Literature")
    
    def send_error(self, error_message: str):
        """Send error notification."""
        title = "⚠️ 文献爬取失败"
        body = f"运行出错:\n{error_message}\n\n请检查日志。"
        return self.send(title, body, group="Literature", sound="alarm")
    
    def close(self):
        """Close HTTP client."""
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
