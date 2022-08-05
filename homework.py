import requests
import telegram
from dotenv import load_dotenv

import os
import time
import logging
from logging.handlers import RotatingFileHandler
from http import HTTPStatus

from urls import ENDPOINT

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

TELEGRAM_RETRY_TIME: int = 600

HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    format='%(asctime)s, %(levelname)s, %(message)s'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(
    'my_logger.log',
    maxBytes=50000000,
    backupCount=5
)
logger.addHandler(handler)

formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)


class APIUnexpectedHTTPStatus(Exception):
    """Исключение при ответе сервера отличным от 200"""
    pass


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.info(f'В Telegram отправлено сообщение {message}')
    except Exception:
        logging.error('Ошибка отправки сообщения в Telegram')


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса.
    Функция должна вернуть ответ API,преобразовав его
    из формата JSON к типам данных Python.
    """
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}

    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except Exception as error:
        logging.error(f'Ошибка при запросе к единственному API: {error}')
        raise APIUnexpectedHTTPStatus(
            f'Ошибка при запросе к основному API: {error}'
        )
    if response.status_code != HTTPStatus.OK:
        status_code = response.status_code
        logging.error(f'Ошибка {status_code}')
        raise APIUnexpectedHTTPStatus(f'Ошибка {status_code}')
    try:
        return response.json()
    except ValueError:
        logger.error('Ошибка парсинга ответа из формата json')
        raise ValueError('Ошибка парсинга ответа из формата json')


def check_response(response):
    """Проверяет ответ API на корректность."""
    try:
        response
        logging.info('Ожидает ответа сервера')
    except APIUnexpectedHTTPStatus:
        logger.error('Ответ сервера не получен')
    if (isinstance(response, list)):
        raise TypeError('Ответ API отличен от словаря')
    try:
        list_homework = response['homeworks']
    except KeyError:
        logger.error('Нет ключа homeworks')
        raise KeyError('Нет ключа homeworks')
    try:
        homework = list_homework[0]
    except IndexError:
        logger.error('Список домашних работ пуст')
        raise IndexError('Список домашних работ пуст')
    return homework


def parse_status(homework):
    """Извлекает статус о конкретной домашней работе."""
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')
    if 'status' not in homework:
        raise Exception('Отсутствует ключ "status" в ответе API')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        raise Exception(f'Неизвестный статус работы: {homework_status}')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    if TELEGRAM_TOKEN and PRACTICUM_TOKEN and TELEGRAM_CHAT_ID:
        return True


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    STATUS = ''

    if not check_tokens():
        logger.critical('Отсутствуют одна или несколько переменных окружения')
        raise Exception('Отсутствуют одна или несколько переменных окружения')
    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = response.get('current_date')
            message = parse_status(check_response(response))
            if message != STATUS:
                send_message(bot, message)
                STATUS = message
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
        finally:
            time.sleep(TELEGRAM_RETRY_TIME)


if __name__ == '__main__':
    main()
