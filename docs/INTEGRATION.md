# Руководство по интеграции

## Обзор API

### Основные эндпоинты
```
POST /api/v1/records      # Создание записи
GET  /api/v1/records     # Получение записей
POST /api/v1/workplaces  # Создание рабочего места
GET  /api/v1/reports     # Получение отчетов
```

## Аутентификация

### Получение токена
```http
POST /api/v1/auth/token
Content-Type: application/json

{
    "telegram_id": 123456789,
    "auth_code": "123456"
}

Response:
{
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "token_type": "bearer",
    "expires_in": 3600
}
```

### Использование токена
```http
GET /api/v1/records
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
```

## Работа с записями

### Создание записи
```http
POST /api/v1/records
Content-Type: application/json
Authorization: Bearer <token>

{
    "workplace_id": 1,
    "start_time": "2024-03-20T09:00:00Z",
    "end_time": "2024-03-20T17:00:00Z",
    "description": "Разработка нового функционала"
}

Response:
{
    "id": 1,
    "workplace_id": 1,
    "start_time": "2024-03-20T09:00:00Z",
    "end_time": "2024-03-20T17:00:00Z",
    "description": "Разработка нового функционала",
    "created_at": "2024-03-20T17:01:00Z"
}
```

### Получение записей
```http
GET /api/v1/records?start_date=2024-03-01&end_date=2024-03-31
Authorization: Bearer <token>

Response:
{
    "total": 1,
    "items": [
        {
            "id": 1,
            "workplace_id": 1,
            "workplace_name": "Офис",
            "start_time": "2024-03-20T09:00:00Z",
            "end_time": "2024-03-20T17:00:00Z",
            "description": "Разработка нового функционала",
            "duration_hours": 8,
            "earnings": 8000.00
        }
    ]
}
```

### Обновление записи
```http
PUT /api/v1/records/{record_id}
Content-Type: application/json
Authorization: Bearer <token>

{
    "end_time": "2024-03-20T18:00:00Z",
    "description": "Разработка и тестирование"
}

Response:
{
    "id": 1,
    "workplace_id": 1,
    "start_time": "2024-03-20T09:00:00Z",
    "end_time": "2024-03-20T18:00:00Z",
    "description": "Разработка и тестирование",
    "updated_at": "2024-03-20T18:01:00Z"
}
```

### Удаление записи
```http
DELETE /api/v1/records/{record_id}
Authorization: Bearer <token>

Response: 204 No Content
```

## Управление рабочими местами

### Создание рабочего места
```http
POST /api/v1/workplaces
Content-Type: application/json
Authorization: Bearer <token>

{
    "name": "Офис",
    "rate": 1000.50
}

Response:
{
    "id": 1,
    "name": "Офис",
    "rate": 1000.50,
    "created_at": "2024-03-20T12:00:00Z"
}
```

### Получение списка рабочих мест
```http
GET /api/v1/workplaces
Authorization: Bearer <token>

Response:
{
    "total": 1,
    "items": [
        {
            "id": 1,
            "name": "Офис",
            "rate": 1000.50,
            "records_count": 10,
            "total_hours": 80,
            "total_earnings": 80040.00
        }
    ]
}
```

## Отчеты

### Получение отчета
```http
GET /api/v1/reports?type=weekly&date=2024-03-20
Authorization: Bearer <token>

Response:
{
    "period": {
        "start": "2024-03-14T00:00:00Z",
        "end": "2024-03-20T23:59:59Z"
    },
    "summary": {
        "total_hours": 40,
        "total_earnings": 40020.00,
        "records_count": 5
    },
    "by_workplace": [
        {
            "workplace_id": 1,
            "workplace_name": "Офис",
            "hours": 40,
            "earnings": 40020.00,
            "records_count": 5
        }
    ]
}
```

### Экспорт отчета
```http
GET /api/v1/reports/export?type=monthly&date=2024-03&format=xlsx
Authorization: Bearer <token>

Response:
Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
Content-Disposition: attachment; filename="report_202403.xlsx"
```

## Настройки

### Получение настроек
```http
GET /api/v1/settings
Authorization: Bearer <token>

Response:
{
    "timezone": "Europe/Moscow",
    "notifications_enabled": true,
    "weekly_report_day": "sunday",
    "weekly_report_time": "23:00"
}
```

### Обновление настроек
```http
PATCH /api/v1/settings
Content-Type: application/json
Authorization: Bearer <token>

{
    "timezone": "Europe/London",
    "notifications_enabled": false
}

Response:
{
    "timezone": "Europe/London",
    "notifications_enabled": false,
    "weekly_report_day": "sunday",
    "weekly_report_time": "23:00",
    "updated_at": "2024-03-20T15:00:00Z"
}
```

## Уведомления

### Подписка на webhook
```http
POST /api/v1/webhooks
Content-Type: application/json
Authorization: Bearer <token>

{
    "url": "https://example.com/webhook",
    "events": ["record.created", "record.updated", "report.generated"]
}

Response:
{
    "id": "wh_123456",
    "url": "https://example.com/webhook",
    "events": ["record.created", "record.updated", "report.generated"],
    "created_at": "2024-03-20T16:00:00Z"
}
```

### Формат webhook-уведомлений
```json
{
    "event": "record.created",
    "timestamp": "2024-03-20T16:30:00Z",
    "data": {
        "record_id": 1,
        "workplace_id": 1,
        "start_time": "2024-03-20T09:00:00Z",
        "end_time": "2024-03-20T17:00:00Z"
    }
}
```

## Обработка ошибок

### Формат ошибок
```json
{
    "error": {
        "code": "validation_error",
        "message": "Неверный формат данных",
        "details": {
            "start_time": ["Обязательное поле"],
            "workplace_id": ["Рабочее место не найдено"]
        }
    }
}
```

### Коды ошибок
```
400 Bad Request
- validation_error: Ошибка валидации данных
- invalid_parameters: Неверные параметры запроса

401 Unauthorized
- invalid_token: Неверный токен
- token_expired: Токен истек

403 Forbidden
- permission_denied: Нет доступа
- rate_limit_exceeded: Превышен лимит запросов

404 Not Found
- resource_not_found: Ресурс не найден

500 Internal Server Error
- internal_error: Внутренняя ошибка сервера
```

## Ограничения

### Лимиты запросов
```
POST /api/v1/records: 60 запросов в минуту
GET  /api/v1/records: 120 запросов в минуту
POST /api/v1/workplaces: 30 запросов в минуту
GET  /api/v1/reports: 30 запросов в минуту
```

### Размеры данных
```
description: максимум 500 символов
name: максимум 100 символов
batch_size: максимум 100 записей
file_size: максимум 10 МБ
```

## Примеры интеграции

### Python
```python
import requests

class TimeTrackerAPI:
    def __init__(self, token):
        self.token = token
        self.base_url = "https://api.timetracker.com/v1"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def create_record(self, workplace_id, start_time, end_time, description=None):
        data = {
            "workplace_id": workplace_id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "description": description
        }
        response = requests.post(
            f"{self.base_url}/records",
            json=data,
            headers=self.headers
        )
        return response.json()
    
    def get_weekly_report(self, date):
        response = requests.get(
            f"{self.base_url}/reports",
            params={"type": "weekly", "date": date.isoformat()},
            headers=self.headers
        )
        return response.json()
```

### JavaScript
```javascript
class TimeTrackerAPI {
    constructor(token) {
        this.token = token;
        this.baseUrl = 'https://api.timetracker.com/v1';
    }

    async createRecord(workplaceId, startTime, endTime, description) {
        const response = await fetch(`${this.baseUrl}/records`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${this.token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                workplace_id: workplaceId,
                start_time: startTime.toISOString(),
                end_time: endTime.toISOString(),
                description
            })
        });
        return response.json();
    }

    async getWeeklyReport(date) {
        const response = await fetch(
            `${this.baseUrl}/reports?type=weekly&date=${date.toISOString()}`,
            {
                headers: {
                    'Authorization': `Bearer ${this.token}`
                }
            }
        );
        return response.json();
    }
}
``` 