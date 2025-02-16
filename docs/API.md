# API Документация

## Модели данных

### User
```python
class User(models.Model):
    """Модель пользователя"""
    id: int  # Primary Key
    telegram_id: int  # Telegram ID пользователя
    username: str  # Имя пользователя в Telegram
    timezone: str  # Часовой пояс (например, "Europe/Moscow")
    created_at: datetime  # Дата и время создания
```

### Workplace
```python
class Workplace(models.Model):
    """Модель рабочего места"""
    id: int  # Primary Key
    user: ForeignKey[User]  # Связь с пользователем
    name: str  # Название рабочего места
    rate: Decimal  # Почасовая ставка
    created_at: datetime  # Дата и время создания
```

### Record
```python
class Record(models.Model):
    """Модель записи рабочего времени"""
    id: int  # Primary Key
    user: ForeignKey[User]  # Связь с пользователем
    workplace: ForeignKey[Workplace]  # Связь с рабочим местом
    start_time: datetime  # Время начала
    end_time: datetime  # Время окончания
    description: str  # Описание работы
    created_at: datetime  # Дата создания
    updated_at: datetime  # Дата обновления
```

## Обработчики команд

### Start Handler
```python
async def start_handler(message: types.Message) -> None:
    """
    Обработчик команды /start
    Создает нового пользователя или получает существующего
    """
```

### Workplaces Handler
```python
async def workplaces_handler(message: types.Message) -> None:
    """
    Обработчик команды /workplaces
    Показывает список рабочих мест пользователя
    """

async def add_workplace_handler(message: types.Message, state: FSMContext) -> None:
    """
    Обработчик команды /add_workplace
    Запускает процесс создания нового рабочего места
    """
```

### Records Handler
```python
async def add_record_handler(message: types.Message, state: FSMContext) -> None:
    """
    Обработчик команды /add_record
    Запускает процесс создания новой записи
    """
```

### Reports Handler
```python
async def reports_handler(message: types.Message, state: FSMContext) -> None:
    """
    Обработчик команды /reports
    Показывает меню генерации отчетов
    """
```

### Settings Handler
```python
async def settings_handler(message: types.Message) -> None:
    """
    Обработчик команды /settings
    Показывает меню настроек
    """
```

## Middleware

### Error Handler
```python
class ErrorHandlerMiddleware(BaseMiddleware):
    """
    Middleware для обработки ошибок
    - Логирует ошибки
    - Отправляет уведомления администратору
    - Отправляет сообщение пользователю
    """
```

### Rate Limiter
```python
class RateLimiterMiddleware(BaseMiddleware):
    """
    Middleware для ограничения частоты запросов
    Настройки по умолчанию:
    - add_record: 5 запросов в минуту
    - workplaces: 10 запросов в минуту
    - reports: 3 запроса в минуту
    - settings: 5 запросов в минуту
    - default: 20 запросов в минуту
    """
```

## Планировщик задач

### TaskScheduler
```python
class TaskScheduler:
    """
    Планировщик фоновых задач
    
    Методы:
    - check_unfinished_records(): Проверка незавершенных записей
    - send_weekly_reports(): Отправка еженедельных отчетов
    - cleanup_old_data(): Очистка старых данных
    - backup_database(): Резервное копирование БД
    
    Расписание:
    - Проверка записей: ежедневно в 20:00
    - Отчеты: воскресенье в 23:00
    - Очистка: 1 число месяца в 02:00
    - Бэкап: ежедневно в 03:00
    """
```

## Валидаторы

### WorkplaceInput
```python
class WorkplaceInput(BaseModel):
    """
    Валидатор входных данных рабочего места
    
    Поля:
    - name: str (1-100 символов)
    - rate: float (>= 0)
    """
```

### TimeInput
```python
class TimeInput(BaseModel):
    """
    Валидатор времени
    
    Поля:
    - hour: int (0-23)
    - minute: int (0-59)
    """
```

### RecordInput
```python
class RecordInput(BaseModel):
    """
    Валидатор записи рабочего времени
    
    Поля:
    - workplace_id: int
    - start_time: datetime
    - end_time: datetime
    - description: str (опционально, макс. 500 символов)
    
    Валидация:
    - end_time должно быть позже start_time
    """
```

## Утилиты

### Health Check
```python
class HealthCheck:
    """
    Проверка работоспособности системы
    
    Проверяет:
    - Подключение к базе данных
    - Доступность Telegram API
    - Работу планировщика задач
    
    Интервал проверки: 60 секунд
    """
```

### TimeZone Utility
```python
class TimeZoneDB:
    """
    Утилита для работы с TimeZoneDB API
    
    Методы:
    - get_time_zone(lat: float, lng: float) -> Dict
    - get_time_zone_by_zone(zone: str) -> Dict
    - convert_time(time: datetime, from_zone: str, to_zone: str) -> datetime
    """
```

## Примеры использования

### Создание рабочего места
```python
workplace = await Workplace.create(
    user=user,
    name="Офис",
    rate=1000.50
)
```

### Добавление записи
```python
record = await Record.create(
    user=user,
    workplace=workplace,
    start_time=datetime.now(),
    end_time=datetime.now() + timedelta(hours=8),
    description="Разработка нового функционала"
)
```

### Получение отчета
```python
records = await Record.filter(
    user=user,
    start_time__gte=week_ago
).prefetch_related('workplace')

total_duration = sum((r.end_time - r.start_time).total_seconds() / 3600 
                    for r in records if r.end_time)
total_earnings = sum(duration * float(r.workplace.rate) 
                    for r, duration in zip(records, durations))
```

## Обработка ошибок

### Типы ошибок
```python
class WorkplaceNotFoundError(Exception):
    """Рабочее место не найдено"""
    pass

class InvalidTimeError(Exception):
    """Некорректное время"""
    pass

class RateLimitExceededError(Exception):
    """Превышен лимит запросов"""
    pass
```

### Пример обработки
```python
try:
    workplace = await Workplace.get(id=workplace_id, user=user)
except DoesNotExist:
    raise WorkplaceNotFoundError("Рабочее место не найдено")
```

## События

### Типы событий
```python
EVENTS = {
    'record_created': 'Создана новая запись',
    'record_updated': 'Запись обновлена',
    'record_deleted': 'Запись удалена',
    'workplace_created': 'Создано новое рабочее место',
    'workplace_updated': 'Рабочее место обновлено',
    'workplace_deleted': 'Рабочее место удалено',
    'report_generated': 'Сгенерирован отчет',
    'backup_created': 'Создана резервная копия',
    'error_occurred': 'Произошла ошибка'
}
```

## Конфигурация

### Переменные окружения
```python
# Обязательные
BOT_TOKEN: str  # Токен Telegram бота
ADMIN_ID: int  # ID администратора
DATABASE_URL: str  # URL базы данных
TIMEZONE_DB_API_KEY: str  # Ключ API TimeZoneDB

# Опциональные
LOG_LEVEL: str = "INFO"  # Уровень логирования
BACKUP_RETENTION_DAYS: int = 7  # Срок хранения бэкапов
RATE_LIMIT_DEFAULT: int = 20  # Лимит запросов по умолчанию
``` 