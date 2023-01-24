import logging
import os
import time
from http import HTTPStatus
import sys

import requests
import telegram
from dotenv import load_dotenv

import exceptions

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

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)


def check_tokens():
    """Проверка существования переменных окружения."""
    if not all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)):
        logger.critical('Отсутсвует один или несколько токенов')
        raise exceptions.MissingEnvironmentVariable(
            'Отсутсвует один или несколько токенов'
        )
    else:
        logger.info('Токены успешно проверены')


def send_message(bot, message):
    """Функция отправки сообщения."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Удачная отправка сообщения в Telegram.')
    except telegram.TelegramError as error:
        logger.error(f'Ошибка отправки сообщения в Telegram: {error}')


def get_api_answer(timestamp):
    """Функция получения ответа от API."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except requests.RequestException:
        logger.error('Ошибка запроса к API')
    if response.status_code != HTTPStatus.OK:
        logger.error(f'Статус-код не 200. Статус-код: {response.status_code}')
        raise requests.exceptions.HTTPError('Код ответа API не 200.')
    return response.json()


def check_response(response):
    """Функция проверка ответа на валидность.
    Проверка статус-код ответа, тип данных, наличие ключей.
    """
    if type(response) != dict:
        logger.error(f'Неожиданный тип ответа: {type(response)}')
        raise TypeError
    elif not all(k in response.keys() for k in ('homeworks', 'current_date')):
        logger.error('В ответе API отсутствуют ожидаемые ключи')
        raise KeyError('В ответе API отсутствуют ожидаемые ключи')
    elif type(response['homeworks']) != list:
        logger.error(f'Неожиданный тип ответа [homeworks]: {type(response)}')
        raise TypeError
    else:
        logger.info('Ответ API корректен')


def parse_status(homework: dict):
    """Функция извлекает из ответа статус конретной работы."""
    if 'homework_name' not in homework.keys():
        logger.error('Ошибка: в словаре homework нет необходимых ключей')
        raise exceptions.KeysNotExist()
    try:
        homework_name = homework.get('homework_name')
        homework_status = homework.get('status')
        verdict = HOMEWORK_VERDICTS[homework_status]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    except KeyError:
        logger.error('Ошибка: в словаре homework нет необходимых ключей')
        raise KeyError('Ошибка: в словаре homework нет необходимых ключей')


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    msg_list = []
    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            try:
                homework_last = response['homeworks'][0]
                timestamp = response['current_date']
                message = parse_status(homework_last)
            except IndexError:
                logger.debug('Новые работы отсутсвуют')
                message = 'Бот начал работу. Новые работы отсутсвуют.'
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.critical(f'Сбой в работе программы: {error}')
        finally:
            if message in msg_list:
                logger.info('Измнений статусов нет')
            else:
                send_message(bot, message)
                msg_list.append(message)
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
