import time
from typing import Dict, Any, Callable
from urllib.parse import urlparse

from app.config import settings
from app.core.exceptions import PolicyViolationError
from app.tools.registry import tool_registry

class PolicyEnforcer:
    """Enforces boundaries and security constraints before and during execution."""
    
    @staticmethod
    def validate_tool_exists(tool_name: str) -> None:
        try:
            tool_registry.get_tool(tool_name)
        except Exception:
            raise PolicyViolationError(f"Tool {tool_name} is not whitelisted/registered or does not exist.")

    @staticmethod
    def enforce_timeout(func: Callable, args: Any, timeout: int) -> Any:
        # In a real async/multiprocessing setup, this would forcibly kill the execution.
        # For simplicity in this sync mockup, we rely on the tools themselves 
        # (like subprocess.run timeout) to respect the timeout.
        start = time.time()
        result = func(args)
        elapsed = time.time() - start
        
        if elapsed > timeout:
            raise PolicyViolationError(f"Execution exceeded allowed timeout of {timeout}s")
            
        return result
        
    @staticmethod
    def validate_execution_step(tool_name: str, args: Dict[str, Any]) -> None:
        """Central validation hub run before ANY tool execution"""
        PolicyEnforcer.validate_tool_exists(tool_name)

        if tool_name in ("fetch_rss_news", "create_latest_news_xlsx", "create_latest_news_file"):
            requested_limit = int(args.get("limit", 10))
            if requested_limit < 1 or requested_limit > settings.NEWS_MAX_ITEMS_PER_REQUEST:
                raise PolicyViolationError(
                    f"limit must be between 1 and {settings.NEWS_MAX_ITEMS_PER_REQUEST}"
                )

            feed_urls = args.get("feed_urls") or settings.NEWS_RSS_FEEDS
            if not feed_urls:
                raise PolicyViolationError("No feed URLs configured for fetch_rss_news")

            allowed = [d.lower() for d in settings.ALLOWED_FETCH_DOMAINS]
            for feed_url in feed_urls:
                parsed = urlparse(feed_url)
                host = (parsed.hostname or "").lower()
                if parsed.scheme not in ("http", "https"):
                    raise PolicyViolationError(f"Unsupported URL scheme in feed URL: {feed_url}")
                if not host:
                    raise PolicyViolationError(f"Invalid feed URL host: {feed_url}")
                if not any(host == domain or host.endswith(f".{domain}") for domain in allowed):
                    raise PolicyViolationError(
                        f"Feed domain not allowed by policy: {host}"
                    )

        if tool_name in ("create_xlsx_from_rows", "create_latest_news_xlsx"):
            out_path = str(args.get("path", "")).strip().lower()
            if not out_path.endswith(".xlsx"):
                raise PolicyViolationError(f"{tool_name} path must end with .xlsx")

        if tool_name == "create_latest_news_file":
            out_path = str(args.get("path", "")).strip().lower()
            allowed_ext = (".xlsx", ".txt", ".docx", ".md", ".json", ".csv")
            if not out_path.endswith(allowed_ext):
                raise PolicyViolationError(
                    "create_latest_news_file path must end with one of: .xlsx, .txt, .docx, .md, .json, .csv"
                )

        if tool_name == "web_fetch_tool":
            out_path = str(args.get("output_path", "")).strip().lower()
            if out_path:
                allowed_ext = (".xlsx", ".txt", ".docx", ".md", ".json", ".csv")
                if not out_path.endswith(allowed_ext):
                    raise PolicyViolationError(
                        "web_fetch_tool output_path must end with one of: .xlsx, .txt, .docx, .md, .json, .csv"
                    )
        
        # Tools will independently enforce path, size, and shell limits internally 
        # via the `app.sandbox.limits` module.
