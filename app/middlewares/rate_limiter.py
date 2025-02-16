import time
from collections import defaultdict
from aiogram import types
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.utils.markdown import text, bold

class RateLimiterMiddleware(BaseMiddleware):
    """
    Middleware для ограничения количества запросов от пользователей
    """
    
    def __init__(self):
        super().__init__()
        # Словарь для хранения времени последних запросов пользователей
        self.last_requests = defaultdict(lambda: defaultdict(float))
        
        # Настройки ограничений для разных команд (команда: (лимит, период в секундах))
        self.limits = {
            'add_record': (5, 60),  # 5 запросов в минуту
            'workplaces': (10, 60),  # 10 запросов в минуту
            'reports': (3, 60),  # 3 запроса в минуту
            'settings': (5, 60),  # 5 запросов в минуту
            'default': (20, 60)  # 20 запросов в минуту для остальных команд
        }
    
    def _get_command(self, message: types.Message) -> str:
        """
        Получение команды из сообщения
        
        :param message: Сообщение пользователя
        :return: Название команды или 'default'
        """
        if message.get_command():
            return message.get_command()[1:]  # Убираем символ '/'
        return 'default'
    
    def _check_limit(self, user_id: int, command: str, current_time: float) -> bool:
        """
        Проверка лимита запросов
        
        :param user_id: ID пользователя
        :param command: Команда
        :param current_time: Текущее время
        :return: True если лимит не превышен, False иначе
        """
        limit, period = self.limits.get(command, self.limits['default'])
        user_requests = self.last_requests[user_id][command]
        
        # Очищаем старые запросы
        self.last_requests[user_id][command] = [
            t for t in user_requests if current_time - t < period
        ]
        
        # Проверяем количество запросов
        if len(self.last_requests[user_id][command]) >= limit:
            return False
        
        # Добавляем новый запрос
        self.last_requests[user_id][command].append(current_time)
        return True
    
    async def __call__(self, handler, event, data):
        """
        Обработка запроса
        
        :param handler: Обработчик события
        :param event: Событие (сообщение)
        :param data: Дополнительные данные
        :return: Результат обработки
        """
        if not isinstance(event, types.Message):
            return await handler(event, data)
        
        user_id = event.from_user.id
        command = self._get_command(event)
        current_time = time.time()
        
        if not self._check_limit(user_id, command, current_time):
            limit, period = self.limits.get(command, self.limits['default'])
            await event.reply(
                text(
                    bold("⚠️ Превышен лимит запросов"),
                    "",
                    f"Доступно {limit} запросов за {period} секунд.",
                    "Пожалуйста, подождите немного перед следующим запросом.",
                    sep="\n"
                ),
                parse_mode=types.ParseMode.MARKDOWN
            )
            return True
        
        return await handler(event, data) 