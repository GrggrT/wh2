import os
import logging
import traceback
from aiogram import types
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.utils.markdown import text, bold, code

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
            # Получаем полный стек ошибки
            error_msg = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            logger.error(f"Ошибка при обработке события: {error_msg}")
            
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
                            code(error_msg[:3000]),  # Ограничиваем длину сообщения
                            sep="\n"
                        )
                        
                        try:
                            await bot.send_message(
                                admin_id,
                                admin_error_text,
                                parse_mode=types.ParseMode.MARKDOWN
                            )
                        except Exception as send_err:
                            logger.error(f"Не удалось отправить сообщение админу: {send_err}")
            
            # Возвращаем True, чтобы предотвратить дальнейшую обработку ошибки
            return True 