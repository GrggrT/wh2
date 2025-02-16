import os
import logging
import traceback
from aiogram import types
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.utils.markdown import text, bold, code
from app.utils.logger import log_manager

logger = logging.getLogger(__name__)

class ErrorHandlerMiddleware(BaseMiddleware):
    """Middleware для обработки ошибок"""
    
    async def __call__(self, handler, event, data):
        """
        Обработка ошибок во время выполнения хендлеров
        
        :param handler: Обработчик события
        :param event: Событие (сообщение, callback и т.д.)
        :param data: Дополнительные данные
        :return: Результат обработки
        """
        try:
            return await handler(event, data)
        except Exception as e:
            # Логируем ошибку
            context = {
                "handler": handler.__name__ if hasattr(handler, "__name__") else str(handler),
                "event_type": type(event).__name__,
                "data": str(data)
            }
            
            if isinstance(event, types.Message):
                context.update({
                    "chat_id": event.chat.id,
                    "message_text": event.text,
                    "command": event.get_command()
                })
            
            await log_manager.log_error(
                e,
                user_id=event.from_user.id if hasattr(event, "from_user") else None,
                context=context
            )
            
            # Отправляем сообщение пользователю
            if isinstance(event, types.Message):
                error_text = text(
                    bold("❌ Произошла ошибка"),
                    "",
                    "К сожалению, произошла ошибка при обработке вашего запроса.",
                    "Пожалуйста, попробуйте позже или обратитесь к администратору.",
                    "",
                    f"Описание ошибки: {str(e)}",
                    sep="\n"
                )
                
                await event.reply(
                    error_text,
                    parse_mode=types.ParseMode.MARKDOWN
                )
                
                # Отправляем уведомление администратору
                admin_id = os.getenv("ADMIN_ID")
                if admin_id:
                    bot = data.get("bot")
                    if bot:
                        admin_error_text = text(
                            bold("🔴 Ошибка в боте"),
                            "",
                            f"Пользователь: {event.from_user.id} (@{event.from_user.username})",
                            f"Команда: {event.text}",
                            "",
                            "Стек ошибки:",
                            code(traceback.format_exc()[:3000]),  # Ограничиваем длину сообщения
                            sep="\n"
                        )
                        
                        try:
                            await bot.send_message(
                                admin_id,
                                admin_error_text,
                                parse_mode=types.ParseMode.MARKDOWN
                            )
                        except Exception as send_err:
                            await log_manager.log_error(
                                send_err,
                                context={"error": "Не удалось отправить сообщение админу"}
                            )
            
            # Возвращаем True, чтобы предотвратить дальнейшую обработку ошибки
            return True 