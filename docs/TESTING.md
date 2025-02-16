# Руководство по тестированию

## Обзор

### Типы тестов
1. Модульные тесты (unit tests)
2. Интеграционные тесты (integration tests)
3. Функциональные тесты (functional tests)
4. Тесты производительности (performance tests)

### Инструменты
- pytest
- pytest-asyncio
- pytest-cov
- pytest-mock
- coverage

## Настройка окружения

### Установка зависимостей
```bash
pip install -r requirements.txt
```

### Конфигурация pytest
```ini
# pytest.ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --cov=app --cov-report=term-missing
markers =
    asyncio: mark a test as an async test
    slow: mark test as slow
    integration: mark test as integration test
```

## Структура тестов

### Организация файлов
```
tests/
├── conftest.py              # Общие фикстуры
├── test_models.py           # Тесты моделей
├── test_handlers.py         # Тесты обработчиков
├── test_middleware.py       # Тесты middleware
├── test_validators.py       # Тесты валидаторов
├── test_scheduler.py        # Тесты планировщика
└── test_utils/             # Тесты утилит
    ├── test_timezone.py
    └── test_health_check.py
```

### Фикстуры
```python
# conftest.py
import pytest
from aiogram import Bot, Dispatcher
from app.db.models import User, Workplace

@pytest.fixture
async def bot():
    """Фикстура для создания тестового бота"""
    bot = Bot(token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
    try:
        yield bot
    finally:
        await bot.close()

@pytest.fixture
async def dp(bot):
    """Фикстура для создания тестового диспетчера"""
    dp = Dispatcher(bot)
    return dp

@pytest.fixture
async def user():
    """Фикстура для создания тестового пользователя"""
    user = await User.create(
        telegram_id=123456789,
        username="test_user",
        timezone="Europe/Moscow"
    )
    yield user
    await user.delete()
```

## Написание тестов

### Модульные тесты
```python
# test_models.py
import pytest
from app.db.models import User, Workplace, Record

@pytest.mark.asyncio
async def test_user_creation():
    """Тест создания пользователя"""
    user = await User.create(
        telegram_id=123456789,
        username="test_user",
        timezone="Europe/Moscow"
    )
    assert user.telegram_id == 123456789
    assert user.username == "test_user"
    await user.delete()

@pytest.mark.asyncio
async def test_workplace_creation(user):
    """Тест создания рабочего места"""
    workplace = await Workplace.create(
        user=user,
        name="Test Workplace",
        rate=1000.50
    )
    assert workplace.name == "Test Workplace"
    assert float(workplace.rate) == 1000.50
    await workplace.delete()
```

### Интеграционные тесты
```python
# test_handlers.py
import pytest
from app.handlers.start import start_handler
from app.handlers.workplaces import add_workplace_handler

@pytest.mark.asyncio
async def test_start_command(message, bot):
    """Тест команды /start"""
    response = await start_handler(message)
    assert "Добро пожаловать" in response.text

@pytest.mark.asyncio
async def test_add_workplace(message, state, user):
    """Тест добавления рабочего места"""
    message.text = "Test Workplace"
    await add_workplace_handler(message, state)
    workplace = await Workplace.get(user=user, name="Test Workplace")
    assert workplace is not None
```

### Тесты middleware
```python
# test_middleware.py
import pytest
from app.middlewares.rate_limiter import RateLimiterMiddleware

@pytest.mark.asyncio
async def test_rate_limiter(message):
    """Тест ограничителя запросов"""
    middleware = RateLimiterMiddleware()
    
    # Первый запрос должен пройти
    result = await middleware(handler, message, {})
    assert result is not True
    
    # Создаем много запросов для превышения лимита
    for _ in range(30):
        await middleware(handler, message, {})
    
    # Следующий запрос должен быть заблокирован
    result = await middleware(handler, message, {})
    assert result is True
```

### Тесты валидаторов
```python
# test_validators.py
import pytest
from app.utils.validators import WorkplaceInput, TimeInput

def test_workplace_input_validation():
    """Тест валидации входных данных рабочего места"""
    # Тест валидных данных
    data = WorkplaceInput(name="Test", rate=1000.50)
    assert data.name == "Test"
    assert data.rate == 1000.50
    
    # Тест невалидных данных
    with pytest.raises(ValueError):
        WorkplaceInput(name="", rate=-100)
```

## Запуск тестов

### Все тесты
```bash
pytest
```

### Конкретный тест
```bash
pytest tests/test_models.py -v
```

### С покрытием кода
```bash
pytest --cov=app --cov-report=html
```

### Только помеченные тесты
```bash
pytest -m slow
pytest -m integration
```

## Анализ покрытия

### Генерация отчета
```bash
coverage run -m pytest
coverage report
coverage html
```

### Игнорирование кода
```python
# pragma: no cover
def debug_only_function():
    pass
```

## Мок-объекты

### Создание мока
```python
from unittest.mock import Mock, patch

@pytest.mark.asyncio
async def test_with_mock():
    mock_bot = Mock()
    mock_bot.send_message = Mock()
    
    await some_function(mock_bot)
    mock_bot.send_message.assert_called_once()
```

### Патчинг
```python
@patch('app.utils.timezone.timezone_db.get_time_zone')
async def test_timezone(mock_get_time_zone):
    mock_get_time_zone.return_value = {
        "timezone": "Europe/London",
        "offset": 0
    }
    
    result = await get_user_timezone(123456789)
    assert result == "Europe/London"
```

## Непрерывная интеграция

### GitHub Actions
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:latest
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test_db
        ports:
          - 5432:5432
        options: --health-cmd pg_isready
    
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
    
    - name: Run tests
      run: |
        pytest --cov=app
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

## Советы и рекомендации

### Лучшие практики
1. Пишите тесты до написания кода (TDD)
2. Каждый тест должен проверять одну функциональность
3. Используйте говорящие имена тестов
4. Следуйте паттерну AAA (Arrange-Act-Assert)
5. Изолируйте тесты друг от друга

### Отладка тестов
```bash
# Подробный вывод
pytest -vv

# Показать print statements
pytest -s

# Остановка при первой ошибке
pytest -x

# Отладка с помощью pdb
pytest --pdb
```

### Производительность тестов
1. Используйте `pytest-xdist` для параллельного запуска
2. Применяйте `pytest-timeout` для ограничения времени
3. Метьте медленные тесты маркером `@pytest.mark.slow`

### Документация тестов
1. Добавляйте docstrings к тестам
2. Описывайте входные данные и ожидаемый результат
3. Указывайте зависимости и предусловия 