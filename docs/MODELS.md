# Модели данных

## User (Пользователь)

### Описание
Модель для хранения информации о пользователях бота.

### Поля
| Поле | Тип | Описание |
|------|-----|----------|
| id | IntField | Первичный ключ |
| telegram_id | BigIntField | ID пользователя в Telegram |
| username | CharField | Имя пользователя (опционально) |
| timezone | CharField | Часовой пояс пользователя |
| created_at | DatetimeField | Дата и время создания |

### Пример
```python
user = await User.create(
    telegram_id=123456789,
    username="example_user",
    timezone="Europe/Moscow"
)
```

## Workplace (Рабочее место)

### Описание
Модель для хранения информации о рабочих местах пользователя.

### Поля
| Поле | Тип | Описание |
|------|-----|----------|
| id | IntField | Первичный ключ |
| user | ForeignKeyField | Связь с пользователем |
| name | CharField | Название рабочего места |
| rate | DecimalField | Почасовая ставка |
| created_at | DatetimeField | Дата и время создания |

### Связи
- `user`: Связь с моделью `User` (один ко многим)

### Пример
```python
workplace = await Workplace.create(
    user=user,
    name="Офис",
    rate=1000.50
)
```

## Record (Запись)

### Описание
Модель для хранения записей о рабочем времени.

### Поля
| Поле | Тип | Описание |
|------|-----|----------|
| id | IntField | Первичный ключ |
| user | ForeignKeyField | Связь с пользователем |
| workplace | ForeignKeyField | Связь с рабочим местом |
| start_time | DatetimeField | Время начала |
| end_time | DatetimeField | Время окончания (опционально) |
| description | TextField | Описание работы (опционально) |
| created_at | DatetimeField | Дата и время создания |
| updated_at | DatetimeField | Дата и время обновления |

### Связи
- `user`: Связь с моделью `User` (один ко многим)
- `workplace`: Связь с моделью `Workplace` (один ко многим)

### Пример
```python
record = await Record.create(
    user=user,
    workplace=workplace,
    start_time=datetime.now(),
    end_time=datetime.now() + timedelta(hours=8),
    description="Разработка нового функционала"
)
```

## Диаграмма связей

```
┌──────────┐       ┌───────────┐       ┌─────────┐
│   User   │──1:N──│ Workplace │──1:N──│ Record  │
└──────────┘       └───────────┘       └─────────┘
```

## Валидация

### WorkplaceInput
```python
class WorkplaceInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    rate: float = Field(..., ge=0)
```

### TimeInput
```python
class TimeInput(BaseModel):
    hour: int = Field(..., ge=0, le=23)
    minute: int = Field(..., ge=0, le=59)
```

### RecordInput
```python
class RecordInput(BaseModel):
    workplace_id: int
    start_time: datetime
    end_time: datetime
    description: Optional[str] = None
```

## Индексы

### User
- `telegram_id`: Уникальный индекс

### Workplace
- `user_id`: Индекс для быстрого поиска рабочих мест пользователя

### Record
- `user_id`: Индекс для быстрого поиска записей пользователя
- `workplace_id`: Индекс для быстрого поиска записей рабочего места
- `start_time`: Индекс для быстрого поиска по дате

## Ограничения

### User
- `telegram_id`: Уникальное значение
- `timezone`: Валидный часовой пояс

### Workplace
- `name`: От 1 до 100 символов
- `rate`: Неотрицательное число

### Record
- `end_time`: Должно быть позже `start_time`
- `description`: Максимум 500 символов

## Каскадное удаление

### При удалении User
- Удаляются все связанные Workplace
- Удаляются все связанные Record

### При удалении Workplace
- Удаляются все связанные Record

## Миграции

### Создание миграции
```bash
aerich migrate --name add_new_field
```

### Применение миграций
```bash
aerich upgrade
```

### Откат миграций
```bash
aerich downgrade
```

## Примеры запросов

### Получение всех рабочих мест пользователя
```python
workplaces = await Workplace.filter(user=user).all()
```

### Получение записей за период
```python
records = await Record.filter(
    user=user,
    start_time__gte=start_date,
    start_time__lte=end_date
).prefetch_related('workplace')
```

### Подсчет статистики
```python
from tortoise.functions import Sum

stats = await Record.filter(
    user=user,
    workplace=workplace
).annotate(
    total_hours=Sum('end_time' - 'start_time')
).first()
```

## Оптимизация

### Prefetch Related
```python
records = await Record.filter(
    user=user
).prefetch_related('workplace')
```

### Select Related
```python
record = await Record.filter(
    id=record_id
).select_related('user', 'workplace').first()
```

### Bulk Create
```python
records = [
    Record(
        user=user,
        workplace=workplace,
        start_time=start,
        end_time=end
    )
    for start, end in time_pairs
]
await Record.bulk_create(records)
```

## Тестирование

### Создание тестовых данных
```python
@pytest.fixture
async def user():
    user = await User.create(
        telegram_id=123456789,
        username="test_user",
        timezone="Europe/Moscow"
    )
    yield user
    await user.delete()
```

### Тестирование валидации
```python
def test_workplace_validation():
    with pytest.raises(ValueError):
        WorkplaceInput(name="", rate=-100)
```

### Тестирование связей
```python
async def test_cascade_deletion(user, workplace):
    await user.delete()
    assert not await Workplace.exists(id=workplace.id)
``` 