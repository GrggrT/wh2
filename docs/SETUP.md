# Установка и настройка

## Требования

### Системные требования
- Python 3.8 или выше
- PostgreSQL 12 или выше
- Redis 6 или выше
- 1 ГБ RAM минимум
- 2 ГБ свободного места на диске

### Зависимости Python
```
aiogram==2.25.1
python-dotenv==1.0.0
tortoise-orm==0.19.3
aerich==0.7.1
aioredis==2.0.1
aiohttp==3.8.5
pydantic==2.0.3
pytz==2023.3
```

## Установка

### 1. Клонирование репозитория
```bash
git clone https://github.com/username/project.git
cd project
```

### 2. Создание виртуального окружения
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows
```

### 3. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 4. Настройка базы данных
```bash
# Создание базы данных
createdb worktime_bot

# Применение миграций
aerich upgrade
```

### 5. Настройка Redis
```bash
# Установка Redis (Ubuntu/Debian)
sudo apt-get install redis-server

# Установка Redis (macOS)
brew install redis

# Установка Redis (Windows)
# Скачайте и установите Redis с официального сайта
```

## Конфигурация

### 1. Создание файла .env
```bash
cp .env.example .env
```

### 2. Настройка переменных окружения
```env
# Telegram
BOT_TOKEN=your_bot_token
ADMIN_ID=your_admin_id

# База данных
DATABASE_URL=postgres://user:password@localhost:5432/worktime_bot

# Redis
REDIS_URL=redis://localhost:6379/0

# Timezone API
TIMEZONE_DB_API_KEY=your_api_key

# Логирование
LOG_LEVEL=INFO

# Webhook (опционально)
WEBHOOK_URL=https://your-domain.com/webhook
WEBHOOK_PATH=/webhook
```

### 3. Настройка логирования
```bash
# Создание директории для логов
mkdir logs
```

## Запуск

### Режим разработки
```bash
# Запуск бота в режиме long polling
python -m app.bot
```

### Режим production
```bash
# Запуск с помощью systemd
sudo systemctl start worktime_bot

# Запуск с помощью supervisor
supervisorctl start worktime_bot
```

## Настройка systemd

### 1. Создание сервиса
```bash
sudo nano /etc/systemd/system/worktime_bot.service
```

### 2. Конфигурация сервиса
```ini
[Unit]
Description=Worktime Bot
After=network.target

[Service]
Type=simple
User=your_user
Group=your_group
WorkingDirectory=/path/to/project
Environment=PYTHONPATH=/path/to/project
ExecStart=/path/to/project/venv/bin/python -m app.bot
Restart=always

[Install]
WantedBy=multi-user.target
```

### 3. Активация сервиса
```bash
sudo systemctl daemon-reload
sudo systemctl enable worktime_bot
sudo systemctl start worktime_bot
```

## Настройка supervisor

### 1. Установка supervisor
```bash
sudo apt-get install supervisor  # Ubuntu/Debian
brew install supervisor         # macOS
```

### 2. Создание конфигурации
```bash
sudo nano /etc/supervisor/conf.d/worktime_bot.conf
```

### 3. Конфигурация процесса
```ini
[program:worktime_bot]
command=/path/to/project/venv/bin/python -m app.bot
directory=/path/to/project
user=your_user
autostart=true
autorestart=true
stderr_logfile=/var/log/worktime_bot/error.log
stdout_logfile=/var/log/worktime_bot/access.log
environment=PYTHONPATH="/path/to/project"
```

### 4. Обновление и запуск
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start worktime_bot
```

## Мониторинг

### Логи systemd
```bash
# Просмотр логов
journalctl -u worktime_bot

# Просмотр логов в реальном времени
journalctl -u worktime_bot -f
```

### Логи supervisor
```bash
# Просмотр логов
tail -f /var/log/worktime_bot/error.log
tail -f /var/log/worktime_bot/access.log
```

### Статус сервиса
```bash
# Проверка статуса systemd
systemctl status worktime_bot

# Проверка статуса supervisor
supervisorctl status worktime_bot
```

## Резервное копирование

### База данных
```bash
# Создание бэкапа
pg_dump worktime_bot > backup.sql

# Восстановление из бэкапа
psql worktime_bot < backup.sql
```

### Логи
```bash
# Архивация логов
tar -czf logs_backup.tar.gz logs/

# Восстановление логов
tar -xzf logs_backup.tar.gz
```

## Обновление

### 1. Обновление кода
```bash
git pull origin master
```

### 2. Обновление зависимостей
```bash
pip install -r requirements.txt --upgrade
```

### 3. Применение миграций
```bash
aerich upgrade
```

### 4. Перезапуск сервиса
```bash
# Для systemd
sudo systemctl restart worktime_bot

# Для supervisor
supervisorctl restart worktime_bot
```

## Устранение неполадок

### Проблемы с базой данных
1. Проверьте подключение:
```bash
psql -U your_user -d worktime_bot
```

2. Проверьте миграции:
```bash
aerich history
```

### Проблемы с Redis
1. Проверьте статус:
```bash
redis-cli ping
```

2. Очистка кэша:
```bash
redis-cli flushall
```

### Проблемы с ботом
1. Проверьте токен:
```bash
curl https://api.telegram.org/bot<BOT_TOKEN>/getMe
```

2. Проверьте логи:
```bash
tail -f logs/error.log
```

## Безопасность

### Права доступа
```bash
# Настройка прав на директорию проекта
chmod -R 750 /path/to/project
chown -R your_user:your_group /path/to/project

# Настройка прав на файл .env
chmod 600 .env
```

### Firewall
```bash
# Разрешение портов (Ubuntu/Debian)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

### SSL (для webhook)
```bash
# Установка certbot
sudo apt-get install certbot

# Получение сертификата
sudo certbot certonly --standalone -d your-domain.com
``` 