import json
import uuid
import os
import logging
import requests
import time
from datetime import datetime, timedelta
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from models import Message, UserPreferences
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

    try:
        response = requests.post(url, headers=headers, data=payload, verify=False, timeout=30)
        if response.status_code == 401 and retry_on_auth_error:
            # Token expired, get new one and retry
            logger.info("Токен истек, обновляем...")
            new_token = get_access_token(force_refresh=True)
            return send_prompt(msg, new_token, retry_on_auth_error=False)
        
        if not response.ok:
            logger.error(f"send_prompt API ошибка: {response.status_code} {response.text}")
            raise RuntimeError("Ошибка в вызове send_prompt API")
        
        resp_json = response.json()
        choices = resp_json.get("choices")
        if not choices or not isinstance(choices, list):
            logger.error(f"send_prompt пустые choices: {resp_json}")
            raise ValueError("Нет choices от GigaChat")
        return choices[0]["message"]["content"]
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка сети в send_prompt: {e}")
        raise RuntimeError(f"Ошибка сети в send_prompt: {e}")

async def evaluate_message_importance(message: Message, user_preferences: UserPreferences) -> float:
    """
    Evaluate the importance of a message using GigaChat API
    
    Returns:
        float: Importance score between 0.0 and 1.0
    """
    # Prepare the prompt for GigaChat
    system_prompt = """
    Ты - помощник, который оценивает важность сообщений в Telegram чатах и каналах. 
    Твоя задача - проанализировать сообщение и определить, достаточно ли оно важное, чтобы уведомить пользователя.
    
    Учитывай следующие факторы при оценке важности:
    1. СРОЧНОСТЬ: Требует ли сообщение немедленного внимания или действий?
    2. РЕЛЕВАНТНОСТЬ: Относится ли сообщение к профессиональным или личным интересам пользователя?
    3. НЕОБХОДИМОСТЬ ДЕЙСТВИЙ: Требует ли сообщение от пользователя выполнения каких-либо действий?
    4. ВРЕМЕННАЯ ЧУВСТВИТЕЛЬНОСТЬ: Касается ли сообщение срочных дел, дедлайнов или важных событий?
    5. ИНФОРМАЦИОННАЯ ЦЕННОСТЬ: Содержит ли сообщение ценную информацию, которую нельзя пропустить?
    6. КОНТЕКСТ: Важно ли сообщение в контексте работы, учебы или личной жизни?
    7. КЛЮЧЕВЫЕ СЛОВА: Содержит ли сообщение важные для пользователя ключевые слова?
    
    ВАЖНО: Ты должен вывести ТОЛЬКО JSON объект со следующими полями:
    {
        "score": число от 0.0 (не важно) до 1.0 (очень важно),
        "reason": "краткое объяснение на русском языке, почему ты присвоил этот балл"
    }
    
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
            return 0.5
        
        # Ensure the score is between 0 and 1
        score = float(result.get('score', 0.5))
        score = max(0.0, min(1.0, score))
        
        # Log the reason for debugging
        reason = result.get('reason', 'Причина не указана')
        logger.info(f"Оценка важности сообщения: {score:.2f} - {reason}")
        
        return score
        
    except Exception as e:
        logger.error(f"Ошибка оценки важности сообщения: {e}")
        # Return a default score in case of error
        return 0.5 