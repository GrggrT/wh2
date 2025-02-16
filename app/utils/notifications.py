import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from aiogram import Bot
from app.db.models import User, Record
from app.utils.profiler import profiler

logger = logging.getLogger(__name__)

class NotificationManager:
    """Менеджер уведомлений"""
    
    def __init__(self, bot: Bot):
        """
        Инициализация менеджера уведомлений
        
        :param bot: Экземпляр бота
        """
        self.bot = bot
        self.notification_queue: List[Dict[str, Any]] = []
        self.is_running = False
        
        # Настройки по умолчанию
        self.default_settings = {
            "system_notifications": True,
            "task_reminders": True,
            "calendar_notifications": True,
            "performance_alerts": True,
            "quiet_hours_start": 23,  # Время начала тихого режима
            "quiet_hours_end": 8,     # Время окончания тихого режима
            "notification_interval": 60  # Интервал проверки уведомлений в секундах
        }
    
    @profiler.profile(name="add_notification")
    async def add_notification(
        self,
        user_id: int,
        notification_type: str,
        message: str,
        priority: str = "normal",
        scheduled_time: Optional[datetime] = None
    ) -> bool:
        """
        Добавление нового уведомления
        
        :param user_id: ID пользователя
        :param notification_type: Тип уведомления
        :param message: Текст уведомления
        :param priority: Приоритет (high, normal, low)
        :param scheduled_time: Запланированное время отправки
        :return: True если уведомление добавлено успешно
        """
        try:
            notification = {
                "user_id": user_id,
                "type": notification_type,
                "message": message,
                "priority": priority,
                "scheduled_time": scheduled_time or datetime.now(),
                "created_at": datetime.now()
            }
            
            self.notification_queue.append(notification)
            logger.info(f"Добавлено уведомление для пользователя {user_id}: {notification_type}")
            return True
        
        except Exception as e:
            logger.error(f"Ошибка при добавлении уведомления: {e}")
            return False
    
    async def is_quiet_hours(self, user: User) -> bool:
        """
        Проверка тихого режима для пользователя
        
        :param user: Объект пользователя
        :return: True если сейчас тихий режим
        """
        try:
            current_hour = datetime.now().hour
            return (
                current_hour >= self.default_settings["quiet_hours_start"] or
                current_hour < self.default_settings["quiet_hours_end"]
            )
        except Exception as e:
            logger.error(f"Ошибка при проверке тихого режима: {e}")
            return False
    
    @profiler.profile(name="process_notifications")
    async def process_notifications(self):
        """Обработка очереди уведомлений"""
        while self.notification_queue:
            notification = self.notification_queue[0]
            
            try:
                # Проверяем время отправки
                if notification["scheduled_time"] <= datetime.now():
                    # Получаем пользователя
                    user = await User.get(telegram_id=notification["user_id"])
                    
                    # Проверяем тихий режим
                    if notification["priority"] != "high" and await self.is_quiet_hours(user):
                        # Переносим на следующий день
                        notification["scheduled_time"] = (
                            datetime.now().replace(
                                hour=self.default_settings["quiet_hours_end"],
                                minute=0,
                                second=0
                            ) + timedelta(days=1)
                        )
                        continue
                    
                    # Отправляем уведомление
                    await self.bot.send_message(
                        notification["user_id"],
                        notification["message"]
                    )
                    
                    # Удаляем отправленное уведомление
                    self.notification_queue.pop(0)
                    logger.info(f"Отправлено уведомление пользователю {notification['user_id']}")
                
                else:
                    # Если время еще не пришло, переходим к следующей итерации
                    break
            
            except Exception as e:
                logger.error(f"Ошибка при обработке уведомления: {e}")
                # Удаляем проблемное уведомление
                self.notification_queue.pop(0)
    
    async def check_unfinished_records(self):
        """Проверка незавершенных записей"""
        try:
            # Получаем записи без времени окончания
            unfinished_records = await Record.filter(
                end_time__isnull=True
            ).prefetch_related('user', 'workplace')
            
            for record in unfinished_records:
                # Проверяем, что запись началась сегодня
                if record.start_time.date() == datetime.now().date():
                    message = (
                        f"⚠️ У вас есть незавершенная запись:\n"
                        f"📍 Место: {record.workplace.name}\n"
                        f"🕒 Начало: {record.start_time.strftime('%H:%M')}\n"
                        f"Не забудьте указать время окончания!"
                    )
                    
                    await self.add_notification(
                        user_id=record.user.telegram_id,
                        notification_type="task_reminder",
                        message=message,
                        priority="normal"
                    )
        
        except Exception as e:
            logger.error(f"Ошибка при проверке незавершенных записей: {e}")
    
    async def check_performance_alerts(self):
        """Проверка оповещений о производительности"""
        try:
            # Получаем статистику профилировщика
            stats = profiler.get_stats()
            slow_queries = profiler.analyze_slow_queries()
            
            if slow_queries:
                # Получаем всех пользователей с правами администратора
                admin_id = int(self.bot.get_me().id)  # В данном случае только создатель бота
                
                message = (
                    "🔴 Обнаружены проблемы с производительностью:\n\n"
                    f"Медленные операции:\n"
                )
                
                for operation, data in slow_queries.items():
                    message += (
                        f"- {operation}:\n"
                        f"  Количество: {data['count']}\n"
                        f"  Среднее время: {data['avg_time']:.2f} сек\n"
                        f"  Максимальное время: {data['max_time']:.2f} сек\n"
                    )
                
                await self.add_notification(
                    user_id=admin_id,
                    notification_type="performance_alert",
                    message=message,
                    priority="high"
                )
        
        except Exception as e:
            logger.error(f"Ошибка при проверке производительности: {e}")
    
    async def start(self):
        """Запуск обработчика уведомлений"""
        if self.is_running:
            return
        
        self.is_running = True
        logger.info("Запущен обработчик уведомлений")
        
        while self.is_running:
            try:
                await self.process_notifications()
                await asyncio.sleep(self.default_settings["notification_interval"])
            except Exception as e:
                logger.error(f"Ошибка в цикле обработки уведомлений: {e}")
    
    async def stop(self):
        """Остановка обработчика уведомлений"""
        self.is_running = False
        logger.info("Остановлен обработчик уведомлений")

# Создаем глобальный экземпляр менеджера уведомлений
notification_manager: Optional[NotificationManager] = None

def setup_notifications(bot: Bot) -> NotificationManager:
    """
    Инициализация системы уведомлений
    
    :param bot: Экземпляр бота
    :return: Экземпляр менеджера уведомлений
    """
    global notification_manager
    notification_manager = NotificationManager(bot)
    return notification_manager 