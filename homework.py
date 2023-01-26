import logging
import os
import time
from http import HTTPStatus
import sys

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler1 = logging.StreamHandler(sys.stdout)
handler2 = logging.FileHandler('bot.log', mode='w')
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(lineno)d - %(funcName)s - %(message)s'
)
handler1.setFormatter(formatter)
handler2.setFormatter(formatter)
logger.addHandler(handler1)
logger.addHandler(handler2)


def check_tokens() -> bool:
    """Проверка существования переменных окружения."""
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def send_message(bot, message):
    """Функция отправки сообщения."""
    logger.debug(
        f'Запущена функция отправки сообщений в Telegram: '
        f'{send_message.__name__}'
    )
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.TelegramError as error:
        logger.error(f'Ошибка отправки сообщения в Telegram: {error}')
    else:
        logger.debug('Удачная отправка сообщения в Telegram.')


def get_api_answer(timestamp):
    """Функция получения ответа от API."""
    logger.debug(
        f'Запущена функция получения ответа API: '
        f'{get_api_answer.__name__}'
    )
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except requests.RequestException:
        logger.error('Ошибка запроса к API')
#        raise requests.RequestException('Ошибка запроса к API')
    if response.status_code != HTTPStatus.OK:
        raise requests.exceptions.HTTPError(
            f'Статус-код не 200. Статус-код: {response.status_code}'
        )
    return response.json()


def check_response(response) -> bool:
    """Функция проверка ответа на валидность.
    Проверка статус-код ответа, тип данных, наличие ключей.
    """
    logger.debug(
        f'Запущена функция проверки ответа API: '
        f'{check_response.__name__}'
    )
    if not isinstance(response, dict):
        raise TypeError(f'Неожиданный тип ответа: {type(response)}')
    if 'homeworks' not in response.keys():
        raise KeyError('В ответе API отсутствуют ожидаемый ключ homeworks')
    if 'current_date' not in response.keys():
        raise KeyError('В ответе API отсутствуют ожидаемый ключ current_date')
    if not isinstance(response['homeworks'], list):
        raise TypeError(
            f'Неожиданный тип ответа [homeworks]: '
            f'{type(response["homeworks"])}'
        )
    logger.info('Ответ API корректен')
    return True


def parse_status(homework: dict):
    """Функция извлекает из ответа статус конретной работы."""
    logger.debug(
        f'Запущена извлечения статуса работы:  '
        f'{parse_status.__name__}'
    )
    if 'homework_name' not in homework.keys():
        raise KeyError(
            'Ошибка: в словаре homework нет необходимого ключа "homework_name"'
        )
    if 'status' not in homework.keys():
        raise KeyError(
            'Ошибка: в словаре homework нет необходимого ключа "status"'
        )
    if homework['status'] not in HOMEWORK_VERDICTS.keys():
        raise KeyError(
            'Недокументированный статус домашней работы'
        )
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутсвует один или несколько токенов')
    else:
        logger.info('Токены успешно проверены')
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        timestamp = int(time.time())
        last_msg: str = ''
        while True:
            try:
                response = get_api_answer(timestamp)
                if (check_response(response)
                        and len(response['homeworks']) != 0):
                    homework_last = response['homeworks'][0]
                    timestamp = response.get('current_date', timestamp)
                    message = parse_status(homework_last)
                else:
                    message = 'Бот начал работу. Новые работы отсутсвуют.'
                    logger.debug(message)
            except Exception as error:
                message = f'Сбой в работе программы: {error}'
                logger.error(message, exc_info=True)
            finally:
                if message == last_msg:
                    logger.info('Измнений статусов работ и ошибок нет')
                else:
                    send_message(bot, message)
                    last_msg = message
                time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
