# Примеры использования API

## Работа с пользователями

### Создание нового пользователя
```python
from app.db.models import User

# Создание пользователя
user = await User.create(
    telegram_id=123456789,
    username="example_user",
    timezone="Europe/Moscow"
)

# Получение существующего пользователя
user = await User.get_or_create(
    telegram_id=123456789,
    defaults={
        'username': 'example_user',
        'timezone': 'Europe/Moscow'
    }
)
```

### Обновление часового пояса
```python
from app.utils.timezone import timezone_db

# Получение информации о часовом поясе
timezone_info = await timezone_db.get_time_zone_by_zone("Europe/London")

# Обновление пользователя
user.timezone = timezone_info["timezone"]
await user.save()
```

## Управление рабочими местами

### Создание рабочего места
```python
from app.db.models import Workplace
from app.utils.validators import WorkplaceInput

# Валидация входных данных
workplace_data = WorkplaceInput(
    name="Офис",
    rate=1000.50
)

# Создание рабочего места
workplace = await Workplace.create(
    user=user,
    name=workplace_data.name,
    rate=workplace_data.rate
)
```

### Получение списка рабочих мест
```python
# Получение всех рабочих мест пользователя
workplaces = await Workplace.filter(user=user)

# Получение рабочих мест с определенной ставкой
high_rate_workplaces = await Workplace.filter(
    user=user,
    rate__gte=1000.00
)
```

## Учет рабочего времени

### Добавление записи
```python
from app.db.models import Record
from app.utils.validators import RecordInput
from datetime import datetime, timedelta

# Текущее время
now = datetime.now()

# Валидация входных данных
record_data = RecordInput(
    workplace_id=workplace.id,
    start_time=now,
    end_time=now + timedelta(hours=8),
    description="Разработка нового функционала"
)

# Создание записи
record = await Record.create(
    user=user,
    workplace=workplace,
    start_time=record_data.start_time,
    end_time=record_data.end_time,
    description=record_data.description
)
```

### Получение записей за период
```python
from datetime import datetime, timedelta

# Определение периода
week_ago = datetime.now() - timedelta(days=7)
today = datetime.now()

# Получение записей
records = await Record.filter(
    user=user,
    start_time__gte=week_ago,
    start_time__lte=today
).prefetch_related('workplace')

# Подсчет статистики
total_duration = sum(
    (r.end_time - r.start_time).total_seconds() / 3600 
    for r in records if r.end_time
)
total_earnings = sum(
    duration * float(r.workplace.rate)
    for r, duration in zip(records, durations)
)
```

## Генерация отчетов

### Еженедельный отчет
```python
from datetime import datetime, timedelta

async def generate_weekly_report(user_id: int) -> str:
    # Получаем пользователя
    user = await User.get(telegram_id=user_id)
    
    # Определяем период
    week_ago = datetime.now() - timedelta(days=7)
    
    # Получаем записи
    records = await Record.filter(
        user=user,
        start_time__gte=week_ago
    ).prefetch_related('workplace')
    
    # Группируем по рабочим местам
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
    report_lines = [
        "📊 Еженедельный отчет",
        f"За период: {week_ago.strftime('%d.%m.%Y')} - {datetime.now().strftime('%d.%m.%Y')}",
        ""
    ]
    
    for workplace, stats in workplace_stats.items():
        hours = stats['duration'].total_seconds() / 3600
        report_lines.extend([
            f"📍 {workplace}:",
            f"⏱ Часов: {hours:.2f}",
            f"💰 Заработано: {stats['earnings']:.2f} руб",
            ""
        ])
    
    total_hours = total_duration.total_seconds() / 3600
    report_lines.extend([
        "Итого:",
        f"⏱ Всего часов: {total_hours:.2f}",
        f"💰 Общий заработок: {total_earnings:.2f} руб"
    ])
    
    return "\n".join(report_lines)
```

## Работа с планировщиком

### Настройка задач
```python
from app.utils.scheduler import TaskScheduler
from aiogram import Bot

async def setup_scheduler(bot: Bot):
    scheduler = TaskScheduler(bot)
    
    # Добавление собственной задачи
    scheduler.scheduler.add_job(
        custom_task,
        'cron',
        hour=15,
        minute=30,
        id='custom_task'
    )
    
    scheduler.start()
    return scheduler

async def custom_task():
    """Пример пользовательской задачи"""
    users = await User.all()
    for user in users:
        # Ваша логика
        pass
```

## Обработка ошибок

### Пример middleware
```python
from aiogram import types
from aiogram.dispatcher.middlewares import BaseMiddleware

class CustomMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        try:
            return await handler(event, data)
        except Exception as e:
            if isinstance(event, types.Message):
                await event.reply(
                    f"❌ Произошла ошибка: {str(e)}"
                )
            return True
```

### Валидация данных
```python
from app.utils.validators import TimeInput

try:
    # Парсинг времени
    time_input = TimeInput(hour=25, minute=0)
except ValueError as e:
    print(f"Ошибка валидации: {e}")

try:
    # Проверка рабочего места
    workplace = await Workplace.get(id=1)
except DoesNotExist:
    raise WorkplaceNotFoundError("Рабочее место не найдено")
```

## Мониторинг

### Проверка состояния
```python
from app.utils.health_check import HealthCheck

async def check_system_health(bot: Bot):
    health_check = HealthCheck(bot)
    status = await health_check.check()
    
    if not status["is_healthy"]:
        logger.error(f"Система нездорова: {status}")
        # Отправка уведомления администратору
        await bot.send_message(
            ADMIN_ID,
            f"❌ Проблемы с системой:\n{status}"
        )
```

## Утилиты

### Работа с часовыми поясами
```python
from app.utils.timezone import timezone_db
from datetime import datetime

# Получение часового пояса по координатам
timezone_info = await timezone_db.get_time_zone(
    lat=55.7558,
    lng=37.6173
)

# Конвертация времени между зонами
moscow_time = datetime.now()
london_time = await timezone_db.convert_time(
    moscow_time,
    "Europe/Moscow",
    "Europe/London"
)
``` 