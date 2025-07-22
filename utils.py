import re
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

def get_file_id(text):
    """
    Extract file ID from GigaChat response if it's an image
    
    Args:
        text: Response text from GigaChat
        
    Returns:
        tuple: (file_id or text, is_image flag)
    """
    # Check if the response contains a file ID
    file_pattern = r'file_id:\s*([a-zA-Z0-9-]+)'
    match = re.search(file_pattern, text)
    
    if match:
        file_id = match.group(1)
        logger.info(f"Found file ID: {file_id}")
        return file_id, True
    
    return text, False 

def setup_logging(level: str = "INFO") -> None:
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('bot.log'),
            logging.StreamHandler()
        ]
    )

def safe_json_parse(text: str) -> Optional[Dict[str, Any]]:
    """Safely parse JSON from text, handling various formats."""
    try:
        # Try direct parsing first
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON from text
        try:
            start = text.find('{')
            end = text.rfind('}') + 1
            if start >= 0 and end > start:
                json_str = text[start:end]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass
    return None

def validate_chat_id(chat_id: str) -> Optional[int]:
    """Validate and convert chat ID string to integer."""
    try:
        return int(chat_id)
    except (ValueError, TypeError):
        return None

def format_timestamp(timestamp: datetime) -> str:
    """Format timestamp for display."""
    return timestamp.strftime('%Y-%m-%d %H:%M:%S')

def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to specified length."""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe file operations."""
    import re
    # Remove or replace unsafe characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Limit length
    if len(filename) > 100:
        filename = filename[:100]
    return filename 