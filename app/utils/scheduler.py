import os
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot
from app.db.models import User, Record, Workplace
from tortoise.transactions import atomic
from app.utils.timezone_sync import timezone_sync

logger = logging.getLogger(__name__)

class TaskScheduler:
    """Планировщик фоновых задач"""
    
    def __init__(self, bot: Bot):
        """
        Инициализация планировщика
        
        :param bot: Экземпляр бота для отправки уведомлений
        """
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        self._setup_jobs()
    
    def _setup_jobs(self):
        """Настройка фоновых задач"""
        # Ежедневные напоминания о незавершенных записях
        self.scheduler.add_job(
            self.check_unfinished_records,
            CronTrigger(hour=20),  # Каждый день в 20:00
            id='check_unfinished_records',
            replace_existing=True
        )
        
        # Еженедельные отчеты
        self.scheduler.add_job(
            self.send_weekly_reports,
            CronTrigger(day_of_week='sun', hour=23),  # Каждое воскресенье в 23:00
            id='weekly_reports',
            replace_existing=True
        )
        
        # Ежемесячная очистка старых данных
        self.scheduler.add_job(
            self.cleanup_old_data,
            CronTrigger(day=1, hour=2),  # Первое число каждого месяца в 02:00
            id='cleanup_old_data',
            replace_existing=True
        )
        
        # Ежедневное резервное копирование
        self.scheduler.add_job(
            self.backup_database,
            CronTrigger(hour=3),  # Каждый день в 03:00
            id='backup_database',
            replace_existing=True
        )
        
        # Синхронизация часовых поясов
        self.scheduler.add_job(
            timezone_sync.sync_all_users,
            CronTrigger(hour=4),  # Каждый день в 04:00
            id='timezone_sync',
            replace_existing=True
        )
    
    def start(self):
        """Запуск планировщика"""
        self.scheduler.start()
        logger.info("Планировщик задач запущен")
    
    def shutdown(self):
        """Остановка планировщика"""
        self.scheduler.shutdown()
        logger.info("Планировщик задач остановлен")
    
    async def check_unfinished_records(self):
        """Проверка и отправка уведомлений о незавершенных записях"""
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
                    
                    try:
                        await self.bot.send_message(record.user.telegram_id, message)
                        logger.info(f"Отправлено напоминание пользователю {record.user.telegram_id}")
                    except Exception as e:
                        logger.error(f"Ошибка при отправке напоминания: {e}")
        
        except Exception as e:
            logger.error(f"Ошибка при проверке незавершенных записей: {e}")
    
    async def send_weekly_reports(self):
        """Отправка еженедельных отчетов"""
        try:
            # Получаем всех активных пользователей
            users = await User.all()
            week_ago = datetime.now() - timedelta(days=7)
            
            for user in users:
                # Получаем записи за неделю
                records = await Record.filter(
                    user=user,
                    start_time__gte=week_ago
                ).prefetch_related('workplace')
                
                if not records:
                    continue
                
                # Группируем записи по рабочим местам
                workplace_stats = {}
                total_duration = timedelta()
                total_earnings = 0
                
                for record in records:
                    if not record.end_time:
                        continue
                    
                    duration = record.end_time - record.start_time
                    earnings = duration.total_seconds() / 3600 * float(record.workplace.rate)
                    
                    if record.workplace.name not in workplace_stats:
                        workplace_stats[record.workplace.name] = {
                            'duration': duration,
                            'earnings': earnings
                        }
                    else:
                        workplace_stats[record.workplace.name]['duration'] += duration
                        workplace_stats[record.workplace.name]['earnings'] += earnings
                    
                    total_duration += duration
                    total_earnings += earnings
                
                # Формируем отчет
                report = [
                    "📊 Еженедельный отчет",
                    f"За период: {week_ago.strftime('%d.%m.%Y')} - {datetime.now().strftime('%d.%m.%Y')}",
                    ""
                ]
                
                for workplace, stats in workplace_stats.items():
                    hours = stats['duration'].total_seconds() / 3600
                    report.extend([
                        f"📍 {workplace}:",
                        f"⏱ Часов: {hours:.2f}",
                        f"💰 Заработано: {stats['earnings']:.2f} руб",
                        ""
                    ])
                
                total_hours = total_duration.total_seconds() / 3600
                report.extend([
                    "Итого:",
                    f"⏱ Всего часов: {total_hours:.2f}",
                    f"💰 Общий заработок: {total_earnings:.2f} руб"
                ])
                
                try:
                    await self.bot.send_message(user.telegram_id, "\n".join(report))
                    logger.info(f"Отправлен еженедельный отчет пользователю {user.telegram_id}")
                except Exception as e:
                    logger.error(f"Ошибка при отправке отчета: {e}")
        
        except Exception as e:
            logger.error(f"Ошибка при формировании еженедельных отчетов: {e}")
    
    @atomic()
    async def cleanup_old_data(self):
        """Очистка старых данных"""
        try:
            # Удаляем записи старше 1 года
            year_ago = datetime.now() - timedelta(days=365)
            deleted_count = await Record.filter(start_time__lt=year_ago).delete()
            logger.info(f"Удалено {deleted_count} старых записей")
            
            # Удаляем неиспользуемые рабочие места
            workplaces = await Workplace.all()
            for workplace in workplaces:
                records_count = await Record.filter(workplace=workplace).count()
                if records_count == 0:
                    await workplace.delete()
                    logger.info(f"Удалено неиспользуемое рабочее место: {workplace.name}")
        
        except Exception as e:
            logger.error(f"Ошибка при очистке старых данных: {e}")
    
    async def backup_database(self):
        """Резервное копирование базы данных"""
        try:
            # Получаем параметры подключения из переменных окружения
            db_name = os.getenv("DB_NAME")
            db_user = os.getenv("DB_USER")
            db_password = os.getenv("DB_PASSWORD")
            db_host = os.getenv("DB_HOST")
            
            # Формируем имя файла для бэкапа
            backup_dir = "backups"
            os.makedirs(backup_dir, exist_ok=True)
            
            backup_file = os.path.join(
                backup_dir,
                f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
            )
            
            # Формируем команду для pg_dump
            command = (
                f"PGPASSWORD='{db_password}' pg_dump "
                f"-h {db_host} -U {db_user} -d {db_name} "
                f"-F p -f {backup_file}"
            )
            
            # Выполняем команду
            result = os.system(command)
            
            if result == 0:
                logger.info(f"Резервная копия создана: {backup_file}")
                
                # Удаляем старые бэкапы (оставляем только за последние 7 дней)
                for file in os.listdir(backup_dir):
                    file_path = os.path.join(backup_dir, file)
                    if os.path.getctime(file_path) < (datetime.now() - timedelta(days=7)).timestamp():
                        os.remove(file_path)
                        logger.info(f"Удален старый бэкап: {file}")
            else:
                raise Exception(f"Ошибка при создании резервной копии, код: {result}")
        
        except Exception as e:
            logger.error(f"Ошибка при создании резервной копии: {e}")

# Создаем глобальный экземпляр планировщика
scheduler: TaskScheduler = None

def setup_scheduler(bot: Bot):
    """
    Инициализация и запуск планировщика
    
    :param bot: Экземпляр бота
    """
    global scheduler
    scheduler = TaskScheduler(bot)
    scheduler.start()
    return scheduler 