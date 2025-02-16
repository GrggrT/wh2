from datetime import datetime, timedelta
from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.markdown import text, bold, code
from app.db.models import User, Record, Workplace

class ReportForm(StatesGroup):
    """Состояния формы генерации отчёта"""
    waiting_for_period = State()
    waiting_for_start_date = State()
    waiting_for_end_date = State()

async def reports_handler(message: types.Message):
    """Обработчик команды /reports"""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add("За сегодня")
    keyboard.add("За неделю")
    keyboard.add("За месяц")
    keyboard.add("За произвольный период")
    
    await ReportForm.waiting_for_period.set()
    await message.reply(
        "Выберите период для отчёта:",
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
    
    else:
        await message.reply(
            "❌ Пожалуйста, выберите период из предложенных вариантов",
            parse_mode=types.ParseMode.MARKDOWN
        )

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

def register_handlers(dp: Dispatcher):
    """Регистрация обработчиков"""
    dp.register_message_handler(reports_handler, commands=['reports'])
    dp.register_message_handler(process_period_choice, state=ReportForm.waiting_for_period)
    dp.register_message_handler(process_start_date, state=ReportForm.waiting_for_start_date)
    dp.register_message_handler(process_end_date, state=ReportForm.waiting_for_end_date) 