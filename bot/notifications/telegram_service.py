import logging
import telegram

logger = logging.getLogger(__name__)


class TelegramService:
    def __init__(self, token: str):
        self.token = token
        self.bot = telegram.Bot(token=self.token)

    async def send_message(self, chat_id: str, text: str):
        try:
            await self.bot.send_message(chat_id=chat_id, text=text, parse_mode=telegram.ParseMode.HTML)
            logger.info(f"Sent Telegram message: {text}")
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
