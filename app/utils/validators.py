from datetime import datetime, time
from typing import Optional
from pydantic import BaseModel, validator, Field

class WorkplaceInput(BaseModel):
    """Модель для валидации входных данных рабочего места"""
    name: str = Field(..., min_length=1, max_length=100)
    rate: float = Field(..., ge=0)
    
    @validator('name')
    def validate_name(cls, v):
        """Валидация названия рабочего места"""
        v = v.strip()
        if not v:
            raise ValueError("Название не может быть пустым")
        return v
    
    @validator('rate')
    def validate_rate(cls, v):
        """Валидация почасовой ставки"""
        if v < 0:
            raise ValueError("Ставка не может быть отрицательной")
        return round(v, 2)

class TimeInput(BaseModel):
    """Модель для валидации времени"""
    hour: int = Field(..., ge=0, le=23)
    minute: int = Field(..., ge=0, le=59)
    
    @validator('hour')
    def validate_hour(cls, v):
        """Валидация часа"""
        if not (0 <= v <= 23):
            raise ValueError("Час должен быть от 0 до 23")
        return v
    
    @validator('minute')
    def validate_minute(cls, v):
        """Валидация минут"""
        if not (0 <= v <= 59):
            raise ValueError("Минуты должны быть от 0 до 59")
        return v
    
    def to_time(self) -> time:
        """Преобразование в объект time"""
        return time(hour=self.hour, minute=self.minute)

class RecordInput(BaseModel):
    """Модель для валидации записи рабочего времени"""
    workplace_id: int
    start_time: datetime
    end_time: datetime
    description: Optional[str] = None
    
    @validator('end_time')
    def validate_end_time(cls, v, values):
        """Валидация времени окончания"""
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError("Время окончания должно быть позже времени начала")
        return v
    
    @validator('description')
    def validate_description(cls, v):
        """Валидация описания"""
        if v:
            v = v.strip()
            if len(v) > 500:
                raise ValueError("Описание не должно превышать 500 символов")
        return v

def parse_time(time_str: str) -> TimeInput:
    """
    Парсинг строки времени в формате ЧЧ:ММ
    
    :param time_str: Строка времени
    :return: Объект TimeInput
    :raises ValueError: Если формат времени неверный
    """
    try:
        hour, minute = map(int, time_str.split(':'))
        return TimeInput(hour=hour, minute=minute)
    except (ValueError, TypeError):
        raise ValueError("Неверный формат времени. Используйте формат ЧЧ:ММ")

def parse_date(date_str: str) -> datetime:
    """
    Парсинг строки даты в формате ДД.ММ.ГГГГ
    
    :param date_str: Строка даты
    :return: Объект datetime
    :raises ValueError: Если формат даты неверный
    """
    try:
        return datetime.strptime(date_str, "%d.%m.%Y")
    except ValueError:
        raise ValueError("Неверный формат даты. Используйте формат ДД.ММ.ГГГГ") 