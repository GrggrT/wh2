# Руководство по развертыванию

## Требования к системе

### Минимальные требования
- Python 3.11 или выше
- PostgreSQL 13 или выше
- 1 ГБ RAM
- 10 ГБ свободного места на диске

### Рекомендуемые требования
- Python 3.11
- PostgreSQL 14
- 2 ГБ RAM
- 20 ГБ SSD

## Подготовка окружения

### Установка Python
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev

# CentOS/RHEL
sudo dnf install python3.11 python3.11-devel
```

### Установка PostgreSQL
```bash
# Ubuntu/Debian
sudo apt install postgresql postgresql-contrib

# CentOS/RHEL
sudo dnf install postgresql postgresql-server
sudo postgresql-setup --initdb
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

## Развертывание через Docker

### Сборка образа
```bash
# Сборка образа
docker build -t timetracker-bot .

# Проверка образа
docker images | grep timetracker-bot
```

### Запуск контейнера
```bash
docker run -d \
  --name timetracker-bot \
  --restart unless-stopped \
  --env-file .env \
  timetracker-bot
```

### Просмотр логов
```bash
# Просмотр логов в реальном времени
docker logs -f timetracker-bot

# Просмотр последних 100 строк
docker logs --tail 100 timetracker-bot
```

## Ручное развертывание

### Клонирование репозитория
```bash
git clone https://github.com/GrggrT/wh2.git
cd wh2
```

### Создание виртуального окружения
```bash
python3.11 -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows
```

### Установка зависимостей
```bash
pip install -r requirements.txt
```

### Настройка базы данных
```bash
# Создание пользователя и базы данных
sudo -u postgres psql

CREATE USER timetracker WITH PASSWORD 'your_password';
CREATE DATABASE timetracker_db OWNER timetracker;
\q

# Применение миграций
aerich upgrade
```

### Настройка переменных окружения
```bash
# Создание файла .env
cp .env.example .env

# Редактирование файла
nano .env
```

Необходимые переменные:
```
BOT_TOKEN=your_bot_token
ADMIN_ID=your_admin_id
DATABASE_URL=postgresql://user:pass@host:port/dbname
TIMEZONE_DB_API_KEY=your_timezone_db_api_key
```

### Запуск бота
```bash
# Запуск в режиме разработки
python -m app.bot

# Запуск через systemd
sudo nano /etc/systemd/system/timetracker-bot.service
```

Содержимое файла службы:
```ini
[Unit]
Description=Telegram Time Tracker Bot
After=network.target

[Service]
Type=simple
User=timetracker
WorkingDirectory=/path/to/wh2
Environment=PYTHONPATH=/path/to/wh2
ExecStart=/path/to/wh2/venv/bin/python -m app.bot
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Активация службы:
```bash
sudo systemctl daemon-reload
sudo systemctl start timetracker-bot
sudo systemctl enable timetracker-bot
```

## Развертывание на Railway

### Подготовка
1. Создайте аккаунт на Railway.app
2. Установите Railway CLI:
```bash
npm i -g @railway/cli
railway login
```

### Создание проекта
```bash
# Инициализация проекта
railway init

# Привязка репозитория
railway link
```

### Настройка переменных
```bash
# Добавление переменных окружения
railway variables set BOT_TOKEN=your_bot_token
railway variables set ADMIN_ID=your_admin_id
railway variables set TIMEZONE_DB_API_KEY=your_key
```

### Развертывание
```bash
# Деплой приложения
railway up
```

## Мониторинг и обслуживание

### Проверка состояния
```bash
# Статус службы
sudo systemctl status timetracker-bot

# Просмотр логов
sudo journalctl -u timetracker-bot -f
```

### Резервное копирование
```bash
# Бэкап базы данных
pg_dump -U timetracker timetracker_db > backup_$(date +%Y%m%d).sql

# Восстановление из бэкапа
psql -U timetracker timetracker_db < backup.sql
```

### Обновление
```bash
# Остановка бота
sudo systemctl stop timetracker-bot

# Обновление кода
git pull origin master

# Обновление зависимостей
source venv/bin/activate
pip install -r requirements.txt

# Применение миграций
aerich upgrade

# Запуск бота
sudo systemctl start timetracker-bot
```

## Безопасность

### Настройка брандмауэра
```bash
# Ubuntu/Debian
sudo ufw allow ssh
sudo ufw allow 5432/tcp  # PostgreSQL
sudo ufw enable

# CentOS/RHEL
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --permanent --add-port=5432/tcp
sudo firewall-cmd --reload
```

### SSL/TLS для базы данных
```bash
# Генерация сертификатов
openssl req -new -x509 -days 365 -nodes -text -out server.crt \
  -keyout server.key -subj "/CN=dbhost"

# Настройка PostgreSQL
ssl = on
ssl_cert_file = 'server.crt'
ssl_key_file = 'server.key'
```

### Настройка прав доступа
```bash
# Установка правильных разрешений
chmod 600 .env
chmod 700 backups/
chmod 600 backups/*
```

## Устранение неполадок

### Проблемы с подключением к БД
```bash
# Проверка подключения
psql -U timetracker -h localhost -d timetracker_db

# Проверка логов PostgreSQL
sudo tail -f /var/log/postgresql/postgresql-14-main.log
```

### Проблемы с ботом
```bash
# Проверка статуса
curl -s https://api.telegram.org/bot$BOT_TOKEN/getWebhookInfo

# Очистка webhook
curl -s https://api.telegram.org/bot$BOT_TOKEN/deleteWebhook
```

### Проблемы с Docker
```bash
# Проверка состояния контейнера
docker ps -a | grep timetracker-bot

# Просмотр использования ресурсов
docker stats timetracker-bot
``` 