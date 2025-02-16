from datetime import datetime, timedelta
from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.markdown import text, bold, code
from app.db.models import User, Record, Workplace
from app.utils.analytics import analytics
from app.utils.export import export_manager

class ReportForm(StatesGroup):
    """Состояния формы генерации отчёта"""
    waiting_for_period = State()
    waiting_for_start_date = State()
    waiting_for_end_date = State()
    waiting_for_export_format = State()

async def reports_handler(message: types.Message):
    """Обработчик команды /reports"""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add("За сегодня")
    keyboard.add("За неделю")
    keyboard.add("За месяц")
    keyboard.add("За произвольный период")
    keyboard.add("Статистика эффективности")
    keyboard.add("График активности")
    keyboard.add("Тепловая карта")
    keyboard.add("Экспорт данных")
    
    await ReportForm.waiting_for_period.set()
    await message.reply(
        text(
            bold("📊 Отчеты и аналитика"),
            "",
            "Выберите тип отчета:",
            sep="\n"
        ),
        reply_markup=keyboard,
        parse_mode=types.ParseMode.MARKDOWN
    )

async def process_period_choice(message: types.Message, state: FSMContext):
    """Обработка выбора периода"""
    today = datetime.now().date()
    
    if message.text == "За сегодня":
        start_date = today
        end_date = today
        await generate_report(message, start_date, end_date)
        await state.finish()
    
    elif message.text == "За неделю":
        start_date = today - timedelta(days=7)
        end_date = today
        await generate_report(message, start_date, end_date)
        await state.finish()
    
    elif message.text == "За месяц":
        start_date = today - timedelta(days=30)
        end_date = today
        await generate_report(message, start_date, end_date)
        await state.finish()
    
    elif message.text == "За произвольный период":
        await ReportForm.waiting_for_start_date.set()
        await message.reply(
            text(
                "Введите начальную дату в формате ДД.ММ.ГГГГ",
                "Например: 01.02.2024",
                sep="\n"
            ),
            reply_markup=types.ReplyKeyboardRemove(),
            parse_mode=types.ParseMode.MARKDOWN
        )
    
    elif message.text == "Статистика эффективности":
        await generate_efficiency_report(message)
        await state.finish()
    
    elif message.text == "График активности":
        await generate_activity_chart(message)
        await state.finish()
    
    elif message.text == "Тепловая карта":
        await generate_heatmap(message)
        await state.finish()
    
    elif message.text == "Экспорт данных":
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add("CSV")
        keyboard.add("JSON")
        keyboard.add("Excel")
        keyboard.add("Отмена")
        
        await ReportForm.waiting_for_export_format.set()
        await message.reply(
            text(
                bold("📥 Экспорт данных"),
                "",
                "Выберите формат экспорта:",
                sep="\n"
            ),
            reply_markup=keyboard,
            parse_mode=types.ParseMode.MARKDOWN
        )
    
    else:
        await message.reply(
            "❌ Пожалуйста, выберите тип отчета из предложенных вариантов",
            parse_mode=types.ParseMode.MARKDOWN
        )

async def process_export_format(message: types.Message, state: FSMContext):
    """Обработка выбора формата экспорта"""
    if message.text == "Отмена":
        await state.finish()
        await message.reply(
            "Экспорт отменен",
            reply_markup=types.ReplyKeyboardRemove(),
            parse_mode=types.ParseMode.MARKDOWN
        )
        return
    
    format_mapping = {
        "CSV": "csv",
        "JSON": "json",
        "Excel": "xlsx"
    }
    
    if message.text not in format_mapping:
        await message.reply(
            "❌ Пожалуйста, выберите формат из предложенных вариантов",
            parse_mode=types.ParseMode.MARKDOWN
        )
        return
    
    # Экспортируем данные
    export_format = format_mapping[message.text]
    file_path = await export_manager.export_records(
        user_id=message.from_user.id,
        export_format=export_format
    )
    
    if not file_path:
        await message.reply(
            text(
                bold("❌ Ошибка"),
                "",
                "Не удалось экспортировать данные",
                "Возможно, у вас нет записей для экспорта",
                sep="\n"
            ),
            reply_markup=types.ReplyKeyboardRemove(),
            parse_mode=types.ParseMode.MARKDOWN
        )
    else:
        # Отправляем файл
        await message.reply_document(
            types.InputFile(
                file_path,
                filename=f"worktime_export_{datetime.now().strftime('%Y%m%d')}{file_path.suffix}"
            ),
            caption=text(
                bold("✅ Данные успешно экспортированы"),
                "",
                "В файле содержится информация о всех ваших записях",
                sep="\n"
            ),
            reply_markup=types.ReplyKeyboardRemove(),
            parse_mode=types.ParseMode.MARKDOWN
        )
    
    await state.finish()

async def process_start_date(message: types.Message, state: FSMContext):
    """Обработка начальной даты"""
    try:
        start_date = datetime.strptime(message.text, "%d.%m.%Y").date()
        
        async with state.proxy() as data:
            data['start_date'] = start_date
        
        await ReportForm.waiting_for_end_date.set()
        await message.reply(
            text(
                "Введите конечную дату в формате ДД.ММ.ГГГГ",
                "Например: 28.02.2024",
                sep="\n"
            ),
            parse_mode=types.ParseMode.MARKDOWN
        )
    except ValueError:
        await message.reply(
            "❌ Неверный формат даты. Пожалуйста, используйте формат ДД.ММ.ГГГГ",
            parse_mode=types.ParseMode.MARKDOWN
        )

async def process_end_date(message: types.Message, state: FSMContext):
    """Обработка конечной даты"""
    try:
        end_date = datetime.strptime(message.text, "%d.%m.%Y").date()
        
        async with state.proxy() as data:
            start_date = data['start_date']
            
            if end_date < start_date:
                await message.reply(
                    "❌ Конечная дата не может быть раньше начальной",
                    parse_mode=types.ParseMode.MARKDOWN
                )
                return
            
            await generate_report(message, start_date, end_date)
        
        await state.finish()
    except ValueError:
        await message.reply(
            "❌ Неверный формат даты. Пожалуйста, используйте формат ДД.ММ.ГГГГ",
            parse_mode=types.ParseMode.MARKDOWN
        )

async def generate_report(message: types.Message, start_date: datetime.date, end_date: datetime.date):
    """Генерация отчёта за период"""
    user = await User.get(telegram_id=message.from_user.id)
    
    # Получаем записи за период
    records = await Record.filter(
        user=user,
        start_time__gte=datetime.combine(start_date, datetime.min.time()),
        start_time__lte=datetime.combine(end_date, datetime.max.time())
    ).prefetch_related('workplace')
    
    if not records:
        await message.reply(
            text(
                bold("📊 Отчёт"),
                f"За период: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}",
                "",
                "Записей не найдено",
                sep="\n"
            ),
            parse_mode=types.ParseMode.MARKDOWN
        )
        return
    
    # Группируем записи по рабочим местам
    workplace_stats = {}
    total_duration = timedelta()
    total_cost = 0.0
    
    for record in records:
        duration = record.end_time - record.start_time
        cost = duration.total_seconds() / 3600 * float(record.workplace.rate)
        
        if record.workplace.name not in workplace_stats:
            workplace_stats[record.workplace.name] = {
                'duration': duration,
                'cost': cost,
                'count': 1
            }
        else:
            workplace_stats[record.workplace.name]['duration'] += duration
            workplace_stats[record.workplace.name]['cost'] += cost
            workplace_stats[record.workplace.name]['count'] += 1
        
        total_duration += duration
        total_cost += cost
    
    # Формируем отчёт
    report_lines = [
        bold("📊 Отчёт"),
        f"За период: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}",
        "",
        bold("По рабочим местам:"),
    ]
    
    for workplace, stats in workplace_stats.items():
        duration_hours = stats['duration'].total_seconds() / 3600
        report_lines.extend([
            f"📍 {workplace}:",
            f"   ⏱ Часов: {duration_hours:.2f}",
            f"   💰 Сумма: {stats['cost']:.2f} руб",
            f"   📝 Записей: {stats['count']}",
            ""
        ])
    
    total_hours = total_duration.total_seconds() / 3600
    report_lines.extend([
        bold("Итого:"),
        f"⏱ Всего часов: {total_hours:.2f}",
        f"💰 Общая сумма: {total_cost:.2f} руб",
        f"📝 Всего записей: {len(records)}"
    ])
    
    await message.reply(
        text(*report_lines, sep="\n"),
        parse_mode=types.ParseMode.MARKDOWN
    )

async def generate_efficiency_report(message: types.Message):
    """Генерация отчета об эффективности"""
    metrics = await analytics.get_efficiency_metrics(message.from_user.id)
    
    if not metrics:
        await message.reply(
            text(
                bold("❌ Ошибка"),
                "",
                "Не удалось получить метрики эффективности",
                sep="\n"
            ),
            parse_mode=types.ParseMode.MARKDOWN
        )
        return
    
    report_lines = [
        bold("📊 Анализ эффективности"),
        "",
        f"⏱ Общее количество часов: {metrics['total_hours']:.2f}",
        f"💰 Общий заработок: {metrics['total_earnings']:.2f} руб",
        f"📈 Среднее количество часов в день: {metrics['avg_daily_hours']:.2f}",
        f"✨ Оценка эффективности: {metrics['efficiency_score']:.1f}%",
        "",
        bold("💡 Рекомендация:"),
        metrics['recommendation']
    ]
    
    await message.reply(
        text(*report_lines, sep="\n"),
        parse_mode=types.ParseMode.MARKDOWN
    )

async def generate_activity_chart(message: types.Message):
    """Генерация графика активности"""
    chart_data = await analytics.generate_activity_chart()
    
    if not chart_data:
        await message.reply(
            text(
                bold("❌ Ошибка"),
                "",
                "Не удалось сгенерировать график активности",
                sep="\n"
            ),
            parse_mode=types.ParseMode.MARKDOWN
        )
        return
    
    await message.reply_photo(
        types.InputFile(chart_data),
        caption=text(
            bold("📈 График активности"),
            "",
            "Показывает распределение рабочего времени и количество записей по дням",
            sep="\n"
        ),
        parse_mode=types.ParseMode.MARKDOWN
    )

async def generate_heatmap(message: types.Message):
    """Генерация тепловой карты"""
    heatmap_data = await analytics.generate_heatmap()
    
    if not heatmap_data:
        await message.reply(
            text(
                bold("❌ Ошибка"),
                "",
                "Не удалось сгенерировать тепловую карту",
                sep="\n"
            ),
            parse_mode=types.ParseMode.MARKDOWN
        )
        return
    
    await message.reply_photo(
        types.InputFile(heatmap_data),
        caption=text(
            bold("🌡 Тепловая карта активности"),
            "",
            "Показывает распределение рабочего времени по дням недели и часам",
            sep="\n"
        ),
        parse_mode=types.ParseMode.MARKDOWN
    )

def register_handlers(dp: Dispatcher):
    """Регистрация обработчиков"""
    dp.register_message_handler(reports_handler, commands=['reports'])
    dp.register_message_handler(process_period_choice, state=ReportForm.waiting_for_period)
    dp.register_message_handler(process_start_date, state=ReportForm.waiting_for_start_date)
    dp.register_message_handler(process_end_date, state=ReportForm.waiting_for_end_date)
    dp.register_message_handler(process_export_format, state=ReportForm.waiting_for_export_format) 