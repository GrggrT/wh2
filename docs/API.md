# API Документация

## Общая информация

### Описание
Telegram бот для учета рабочего времени с поддержкой множества рабочих мест, аналитикой и отчетами.

### Версия
1.0.0

### Базовый URL
`https://t.me/your_bot_username`

## Аутентификация
Бот использует стандартную аутентификацию Telegram. Дополнительная аутентификация не требуется.

## Команды

### Основные команды

#### /start
Начало работы с ботом.

**Ответ:**
```
👋 Добро пожаловать в бот учёта рабочего времени!

🔹 Этот бот поможет вам вести учёт рабочего времени и создавать отчёты.
🔹 Используйте /help для получения списка доступных команд.

Начните с добавления рабочего места командой /workplaces
```

#### /help
Показать список доступных команд.

**Ответ:**
```
📋 Доступные команды:

🔸 /start - Начало работы с ботом
🔸 /help - Показать это сообщение
🔸 /add_record - Добавить запись о рабочем времени
🔸 /workplaces - Управление рабочими местами
🔸 /reports - Генерация отчётов
🔸 /calendar - Просмотр и редактирование записей
🔸 /settings - Персональные настройки
```

### Управление рабочими местами

#### /workplaces
Просмотр и управление рабочими местами.

**Ответ при отсутствии рабочих мест:**
```
📍 У вас пока нет рабочих мест

Добавьте новое рабочее место командой /add_workplace
```

**Ответ при наличии рабочих мест:**
```
📍 Ваши рабочие места:

🔹 [Название места] - [ставка] руб/час

Команды:
/add_workplace - Добавить новое место
/edit_workplace - Редактировать место
/delete_workplace - Удалить место
```

#### /add_workplace
Добавление нового рабочего места.

**Процесс:**
1. Бот запрашивает название места
2. Бот запрашивает почасовую ставку
3. Создается новое рабочее место

**Пример диалога:**
```
Бот: Введите название рабочего места:
Пользователь: Офис
Бот: Введите почасовую ставку (в рублях):
Пользователь: 1000
Бот: ✅ Рабочее место успешно добавлено!

📍 Название: Офис
💰 Ставка: 1000 руб/час
```

### Учет времени

#### /add_record
Добавление записи о рабочем времени.

**Процесс:**
1. Выбор рабочего места
2. Ввод времени начала (ЧЧ:ММ)
3. Ввод времени окончания (ЧЧ:ММ)
4. Опциональное описание работы

**Пример диалога:**
```
Бот: Выберите рабочее место:
[Список мест]
Пользователь: Офис
Бот: Введите время начала работы в формате ЧЧ:ММ
Пользователь: 09:00
Бот: Введите время окончания работы в формате ЧЧ:ММ
Пользователь: 18:00
Бот: Введите описание работы (необязательно)
Пользователь: Разработка нового функционала
Бот: ✅ Запись успешно добавлена!

📍 Место: Офис
🕒 Начало: 09:00
🕒 Конец: 18:00
⏱ Продолжительность: 9.00 ч
💰 Стоимость: 9000.00 руб
📝 Описание: Разработка нового функционала
```

### Отчеты

#### /reports
Генерация отчетов о работе.

**Варианты отчетов:**
- За сегодня
- За неделю
- За месяц
- За произвольный период

**Пример отчета:**
```
📊 Отчет
За период: 01.03.2024 - 31.03.2024

По рабочим местам:
📍 Офис:
   ⏱ Часов: 160.00
   💰 Сумма: 160000.00 руб
   📝 Записей: 20

Итого:
⏱ Всего часов: 160.00
💰 Общий заработок: 160000.00 руб
```

### Календарь

#### /calendar
Просмотр и редактирование записей в календаре.

**Функции:**
- Навигация по месяцам
- Просмотр записей за день
- Добавление/редактирование записей
- Быстрый переход к текущей дате

### Настройки

#### /settings
Управление персональными настройками.

**Доступные настройки:**
- Часовой пояс
- Формат отображения времени
- Настройки уведомлений
- Экспорт данных

## Уведомления

### Типы уведомлений
1. Системные уведомления
   - Запуск/остановка бота
   - Обновления системы
   - Технические работы

2. Напоминания о задачах
   - Незавершенные записи
   - Регулярные напоминания
   - Календарные события

3. Оповещения о производительности
   - Проблемы с производительностью
   - Превышение лимитов
   - Системные предупреждения

### Формат уведомлений
```
[Emoji] [Тип уведомления]

[Основной текст]

[Дополнительная информация]
[Рекомендуемые действия]
```

## Ограничения

### Лимиты запросов
- /add_record: 5 запросов в минуту
- /workplaces: 10 запросов в минуту
- /reports: 3 запроса в минуту
- /settings: 5 запросов в минуту
- Остальные команды: 20 запросов в минуту

### Технические ограничения
- Максимальная длина описания: 500 символов
- Максимальное количество рабочих мест: не ограничено
- Период хранения записей: 1 год
- Максимальный размер экспорта: 50 МБ

## Обработка ошибок

### Формат ошибки
```
❌ Произошла ошибка

К сожалению, произошла ошибка при обработке вашего запроса.
Пожалуйста, попробуйте позже или обратитесь к администратору.

Описание ошибки: [текст ошибки]
```

### Типы ошибок
1. Ошибки валидации
   - Неверный формат времени
   - Неверный формат даты
   - Некорректные значения

2. Ошибки доступа
   - Превышение лимитов запросов
   - Недостаточно прав
   - Заблокированные функции

3. Системные ошибки
   - Ошибки базы данных
   - Ошибки сети
   - Внутренние ошибки

## Форматы данных

### Время
- Формат: ЧЧ:ММ
- Пример: 09:00, 18:30

### Дата
- Формат: ДД.ММ.ГГГГ
- Пример: 01.03.2024

### Денежные значения
- Разделитель: точка
- Два знака после запятой
- Пример: 1000.50

## Безопасность

### Защита данных
- Все данные хранятся в зашифрованном виде
- Доступ только через Telegram API
- Регулярное резервное копирование

### Приватность
- Данные доступны только владельцу
- Нет передачи данных третьим лицам
- Возможность экспорта и удаления данных

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