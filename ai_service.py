import json
import uuid
import os
import logging
import requests
import time
from datetime import datetime, timedelta
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from models import Message, UserPreferences, Storage
from config import DEFAULT_IMPORTANCE_THRESHOLD
from utils import safe_json_parse

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
CLIENT_ID = os.getenv("CLIENT_ID")
SECRET = os.getenv("SECRET")
if not CLIENT_ID or not SECRET:
    logger.error("CLIENT_ID или SECRET не установлены в переменных окружения. Пожалуйста, добавьте CLIENT_ID и SECRET в ваш .env файл.")
    raise RuntimeError("Отсутствуют учетные данные GigaChat: CLIENT_ID и SECRET должны быть установлены.")

# Token cache with expiration
token_cache = {
    "token": None,
    "expires_at": None
}

def get_access_token(force_refresh=False) -> str:
    """Get access token with caching and auto-refresh."""
    current_time = datetime.now()
    
    # Check if we have a valid cached token
    if not force_refresh and token_cache["token"] and token_cache["expires_at"]:
        if current_time < token_cache["expires_at"]:
            return token_cache["token"]
    
    # Get new token
    url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json',
        'RqUID': str(uuid.uuid4()),
    }
    payload = {"scope": "GIGACHAT_API_PERS"}
    
    max_retries = 3
    retry_delay = 1  # seconds
    
    for attempt in range(max_retries):
        try:
            res = requests.post(
                url=url,
                headers=headers,
                auth=requests.auth.HTTPBasicAuth(CLIENT_ID, SECRET),
                data=payload,
                verify=False,
                timeout=10
            )
            token = res.json().get("access_token")
            if not token:
                logger.error(f"get_access_token не удался: {res.status_code} {res.text}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                raise RuntimeError("Не удалось получить access token")
            
            # Cache token with expiration (30 minutes before actual expiration)
            token_cache["token"] = token
            token_cache["expires_at"] = current_time + timedelta(minutes=30)
            return token
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка сети в get_access_token (попытка {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            raise RuntimeError(f"Ошибка сети после {max_retries} попыток: {e}")

def send_prompt(msg: str, access_token: str, retry_on_auth_error=True):
    """Send prompt to GigaChat with automatic token refresh on auth error."""
    url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"

    payload = json.dumps({
        "model": "GigaChat-2",
        "messages": [
            {
                "role": "user",
                "content": msg,
            }
        ],
    })
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': f'Bearer {access_token}'
    }

    max_retries = 3
    retry_delay = 2  # seconds

    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, data=payload, verify=False, timeout=30)
            
            if response.status_code == 401 and retry_on_auth_error:
                logger.warning("Получен 401 ошибка, обновляем токен...")
                access_token = get_access_token(force_refresh=True)
                headers['Authorization'] = f'Bearer {access_token}'
                # Retry with new token (only once)
                response = requests.post(url, headers=headers, data=payload, verify=False, timeout=30)
            
            response.raise_for_status()
            
            response_data = response.json()
            content = response_data['choices'][0]['message']['content']
            logger.info(f"GigaChat ответил успешно (попытка {attempt + 1})")
            return content

        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP ошибка в send_prompt (попытка {attempt + 1}): {response.status_code} - {response.text}")
            if response.status_code == 429:  # Rate limit
                wait_time = min(retry_delay * (2 ** attempt), 60)  # Exponential backoff, max 60 seconds
                logger.info(f"Ждем {wait_time} секунд из-за лимита скорости...")
                time.sleep(wait_time)
                continue
            elif response.status_code >= 500 and attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            else:
                raise RuntimeError(f"HTTP ошибка: {response.status_code} - {response.text}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка сети в send_prompt (попытка {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            else:
                raise RuntimeError(f"Ошибка сети после {max_retries} попыток: {e}")

def apply_importance_criteria(base_score: float, message: Message, user_preferences: UserPreferences) -> float:
    """Apply additional importance criteria to modify the base AI score"""
    config = Storage.bot_config
    criteria = config.importance_criteria
    modified_score = base_score
    
    # Length criteria
    msg_length = len(message.text)
    if msg_length < criteria.min_message_length:
        modified_score *= 0.5  # Reduce importance for very short messages
    elif msg_length > criteria.max_message_length:
        modified_score *= 0.8  # Slightly reduce importance for very long messages
    
    # Keywords boost/reduce
    message_lower = message.text.lower()
    
    # Check boost keywords
    for keyword in criteria.keywords_boost:
        if keyword.lower() in message_lower:
            modified_score = min(1.0, modified_score + 0.2)
            break
    
    # Check reduce keywords
    for keyword in criteria.keywords_reduce:
        if keyword.lower() in message_lower:
            modified_score = max(0.0, modified_score - 0.3)
            break
    
    # User personal keywords
    for keyword in user_preferences.keywords:
        if keyword.lower() in message_lower:
            modified_score = min(1.0, modified_score + 0.25)
            break
    
    # User exclude keywords
    for keyword in user_preferences.exclude_keywords:
        if keyword.lower() in message_lower:
            modified_score = max(0.0, modified_score - 0.4)
            break
    
    # Source-based adjustments
    if message.chat_id in criteria.sources_boost:
        modified_score = min(1.0, modified_score + 0.15)
    elif message.chat_id in criteria.sources_reduce:
        modified_score = max(0.0, modified_score - 0.25)
    
    # Time sensitivity (newer messages get slight boost)
    if criteria.time_sensitivity:
        hours_old = (datetime.now() - message.date).total_seconds() / 3600
        if hours_old < 1:  # Less than 1 hour old
            modified_score = min(1.0, modified_score + 0.1)
        elif hours_old > 24:  # More than 24 hours old
            modified_score = max(0.0, modified_score - 0.1)
    
    return max(0.0, min(1.0, modified_score))

def evaluate_message_importance(message: Message, user_preferences: UserPreferences) -> float:
    """
    Evaluate the importance of a message using AI and additional criteria.
    
    Args:
        message: The message to evaluate
        user_preferences: User preferences for filtering
    
    Returns:
        float: Importance score from 0.0 to 1.0
    """
    
    # System prompt for importance evaluation
    system_prompt = f"""
    Ты - эксперт по анализу важности сообщений в мессенджерах. Твоя задача - оценить важность сообщения для пользователя по шкале от 0.0 до 1.0.

    Критерии важности:
    - 0.9-1.0: Критически важные сообщения (срочные уведомления, важные новости, дедлайны)
    - 0.7-0.8: Важные сообщения (рабочие вопросы, планы встреч, значимая информация)
    - 0.5-0.6: Умеренно важные (интересная информация, обсуждения)
    - 0.3-0.4: Маловажные (обычные разговоры, общие темы)
    - 0.0-0.2: Неважные (спам, реклама, флуд, случайные сообщения)

    ВАЖНО: Отвечай ТОЛЬКО в формате JSON:
    {{
        "score": число от 0.0 (не важно) до 1.0 (очень важно),
        "reason": "краткое объяснение на русском языке, почему ты присвоил этот балл"
    }}
    
    Не добавляй никакого дополнительного текста, только JSON.
    
    Примеры важных сообщений:
    - Срочные уведомления о встречах, дедлайнах
    - Важные новости, касающиеся работы или учебы
    - Сообщения с ключевыми словами пользователя
    - Требующие действий или ответов
    - Информация о важных событиях
    
    Примеры неважных сообщений:
    - Обычные приветствия, поздравления
    - Общие обсуждения, не касающиеся пользователя
    - Рекламные сообщения
    - Технические детали, не требующие внимания
    """
    
    # Create a user prompt with the message and user preferences
    user_prompt = f"""
    {system_prompt}
    
    Сообщение для оценки:
    {message.to_prompt()}
    
    Предпочтения пользователя:
    - Важные ключевые слова: {', '.join(user_preferences.keywords) if user_preferences.keywords else 'Не указаны'}
    - Ключевые слова для игнорирования: {', '.join(user_preferences.exclude_keywords) if user_preferences.exclude_keywords else 'Не указаны'}
    
    Оцени важность этого сообщения и предоставь оценку в виде JSON объекта.
    """
    
    try:
        # Get token
        access_token = get_access_token()
        
        # Send the prompt to GigaChat
        response_content = send_prompt(user_prompt, access_token)
        
        # Parse the response using safe JSON parser
        result = safe_json_parse(response_content)
        
        if result is None:
            logger.error(f"Не удалось разобрать ответ GigaChat: {response_content}")
            # Return a default score in case of parsing error
            base_score = 0.5
        else:
            # Ensure the score is between 0 and 1
            base_score = float(result.get('score', 0.5))
            base_score = max(0.0, min(1.0, base_score))
            
            # Log the reason for debugging
            reason = result.get('reason', 'Причина не указана')
            logger.info(f"Базовая оценка важности сообщения от ИИ: {base_score:.2f} - {reason}")
        
        # Apply additional criteria
        final_score = apply_importance_criteria(base_score, message, user_preferences)
        
        if abs(final_score - base_score) > 0.05:
            logger.info(f"Оценка скорректирована критериями: {base_score:.2f} → {final_score:.2f}")
        
        return final_score
        
    except Exception as e:
        logger.error(f"Ошибка оценки важности сообщения: {e}")
        # Return a default score in case of error, but still apply criteria
        base_score = 0.5
        return apply_importance_criteria(base_score, message, user_preferences) 