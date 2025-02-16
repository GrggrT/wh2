import os
import csv
import json
import logging
import aiofiles
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List
import pandas as pd
import xlsxwriter
from app.db.models import User, Workplace, Record
from app.utils.profiler import profiler

logger = logging.getLogger(__name__)

class ExportManager:
    """Менеджер экспорта данных"""
    
    def __init__(self):
        """Инициализация менеджера экспорта"""
        self.export_dir = Path("exports")
        self.export_dir.mkdir(exist_ok=True)
        
        # Поддерживаемые форматы
        self.formats = {
            "csv": self._export_to_csv,
            "json": self._export_to_json,
            "xlsx": self._export_to_excel
        }
    
    @profiler.profile(name="export_records")
    async def export_records(
        self,
        user_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        export_format: str = "csv"
    ) -> Optional[Path]:
        """
        Экспорт записей пользователя
        
        :param user_id: ID пользователя
        :param start_date: Начальная дата
        :param end_date: Конечная дата
        :param export_format: Формат экспорта (csv, json, xlsx)
        :return: Путь к файлу экспорта или None
        """
        try:
            # Проверяем формат
            if export_format not in self.formats:
                raise ValueError(f"Неподдерживаемый формат: {export_format}")
            
            # Получаем пользователя
            user = await User.get(telegram_id=user_id)
            
            # Формируем фильтр по датам
            filter_params = {"user": user}
            if start_date:
                filter_params["start_time__gte"] = start_date
            if end_date:
                filter_params["start_time__lte"] = end_date
            
            # Получаем записи
            records = await Record.filter(
                **filter_params
            ).prefetch_related('workplace')
            
            if not records:
                return None
            
            # Подготавливаем данные
            export_data = []
            for record in records:
                duration = (
                    record.end_time - record.start_time
                    if record.end_time
                    else timedelta()
                )
                earnings = (
                    duration.total_seconds() / 3600 * float(record.workplace.rate)
                    if record.end_time
                    else 0
                )
                
                export_data.append({
                    "workplace": record.workplace.name,
                    "start_time": record.start_time.isoformat(),
                    "end_time": record.end_time.isoformat() if record.end_time else None,
                    "duration_hours": duration.total_seconds() / 3600,
                    "earnings": earnings,
                    "description": record.description
                })
            
            # Экспортируем данные в выбранном формате
            return await self.formats[export_format](export_data, user_id)
        
        except Exception as e:
            logger.error(f"Ошибка при экспорте данных: {e}")
            return None
    
    async def _export_to_csv(self, data: List[Dict[str, Any]], user_id: int) -> Optional[Path]:
        """
        Экспорт в CSV
        
        :param data: Данные для экспорта
        :param user_id: ID пользователя
        :return: Путь к файлу или None
        """
        try:
            file_path = self.export_dir / f"export_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            async with aiofiles.open(file_path, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=data[0].keys())
                await f.write(writer.writeheader())
                for row in data:
                    await f.write(writer.writerow(row))
            
            return file_path
        
        except Exception as e:
            logger.error(f"Ошибка при экспорте в CSV: {e}")
            return None
    
    async def _export_to_json(self, data: List[Dict[str, Any]], user_id: int) -> Optional[Path]:
        """
        Экспорт в JSON
        
        :param data: Данные для экспорта
        :param user_id: ID пользователя
        :return: Путь к файлу или None
        """
        try:
            file_path = self.export_dir / f"export_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(
                    data,
                    ensure_ascii=False,
                    indent=2
                ))
            
            return file_path
        
        except Exception as e:
            logger.error(f"Ошибка при экспорте в JSON: {e}")
            return None
    
    async def _export_to_excel(self, data: List[Dict[str, Any]], user_id: int) -> Optional[Path]:
        """
        Экспорт в Excel
        
        :param data: Данные для экспорта
        :param user_id: ID пользователя
        :return: Путь к файлу или None
        """
        try:
            file_path = self.export_dir / f"export_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            
            # Создаем DataFrame
            df = pd.DataFrame(data)
            
            # Создаем Excel файл
            with pd.ExcelWriter(
                file_path,
                engine='xlsxwriter',
                datetime_format='dd.mm.yyyy hh:mm'
            ) as writer:
                df.to_excel(writer, sheet_name='Records', index=False)
                
                # Получаем объекты для форматирования
                workbook = writer.book
                worksheet = writer.sheets['Records']
                
                # Форматы
                header_format = workbook.add_format({
                    'bold': True,
                    'text_wrap': True,
                    'valign': 'top',
                    'bg_color': '#D7E4BC',
                    'border': 1
                })
                
                money_format = workbook.add_format({
                    'num_format': '#,##0.00 ₽'
                })
                
                time_format = workbook.add_format({
                    'num_format': '[h]:mm'
                })
                
                # Применяем форматы
                for col_num, value in enumerate(df.columns.values):
                    worksheet.write(0, col_num, value, header_format)
                
                # Устанавливаем ширину колонок
                worksheet.set_column('A:A', 20)  # workplace
                worksheet.set_column('B:C', 18)  # start_time, end_time
                worksheet.set_column('D:D', 12)  # duration_hours
                worksheet.set_column('E:E', 15)  # earnings
                worksheet.set_column('F:F', 40)  # description
                
                # Применяем форматы к колонкам
                worksheet.set_column('D:D', None, time_format)
                worksheet.set_column('E:E', None, money_format)
            
            return file_path
        
        except Exception as e:
            logger.error(f"Ошибка при экспорте в Excel: {e}")
            return None
    
    async def cleanup_old_exports(self, days: int = 7):
        """
        Очистка старых файлов экспорта
        
        :param days: Количество дней хранения
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            for file in self.export_dir.glob("export_*"):
                if file.stat().st_mtime < cutoff_date.timestamp():
                    file.unlink()
                    logger.info(f"Удален старый файл экспорта: {file}")
        
        except Exception as e:
            logger.error(f"Ошибка при очистке старых экспортов: {e}")

# Создаем глобальный экземпляр менеджера экспорта
export_manager = ExportManager() 