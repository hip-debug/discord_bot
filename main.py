import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv

import database as db

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

if not DISCORD_TOKEN:
    print("❌ Ошибка: DISCORD_TOKEN не найден в .env файле!")
    exit(1)

if not DATABASE_URL:
    print("❌ Ошибка: DATABASE_URL не найден в .env файле!")
    exit(1)


class EconomyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        super().__init__(
            command_prefix="!",
            intents=intents,
            description="Бот экономики для Discord"
        )
        self.pool = None

    async def setup_hook(self):
        """Инициализация при запуске бота"""
        # Подключение к базе данных
        self.pool = await db.get_pool()
        await db.init_db(self.pool)
        print("✅ База данных подключена и инициализирована")
        
        # Загрузка когов
        cogs = ["cogs.economy", "cogs.work", "cogs.properties"]
        for cog in cogs:
            try:
                await self.load_extension(cog)
                print(f"✅ Ког {cog} загружен")
            except Exception as e:
                print(f"❌ Ошибка загрузки кога {cog}: {e}")
        
        # Синхронизация команд
        self.tree.copy_global_to(guild=None)
        await self.tree.sync()
        print("✅ Команды синхронизированы")

    async def on_ready(self):
        print(f"\n{'='*50}")
        print(f"✅ Бот готов к работе!")
        print(f"👤 Пользователь: {self.user.name}")
        print(f"🆔 ID: {self.user.id}")
        print(f"📊 Серверов: {len(self.guilds)}")
        print(f"{'='*50}\n")
        print("Доступные команды:")
        print("  /баланс - Проверить баланс")
        print("  /ежедневно - Получить ежедневную награду")
        print("  /депозит <сумма> - Внести деньги в банк")
        print("  /снять <сумма> - Снять деньги из банка")
        print("  /передать <пользователь> <сумма> - Перевести деньги")
        print("  /работы - Список доступных работ")
        print("  /устроиться <ID> - Устроиться на работу")
        print("  /работать - Поработать и получить зарплату")
        print("  /моя_работа - Показать текущую работу")
        print("  /недвижимость - Список недвижимости")
        print("  /мои_дома - Ваша недвижимость")
        print("  /купить_дом <ID> - Купить недвижимость")
        print("  /доход - Получить доход от недвижимости")
        print(f"{'='*50}\n")

    async def on_command_error(self, context, error):
        """Обработка ошибок команд"""
        if isinstance(error, commands.CommandNotFound):
            await context.send("❌ Команда не найдена!")
        elif isinstance(error, commands.MissingPermissions):
            await context.send("❌ Недостаточно прав!")
        else:
            print(f"Ошибка: {error}")
            await context.send(f"❌ Произошла ошибка: {error}")

    async def close(self):
        """Закрытие соединения с БД при остановке"""
        if self.pool:
            await self.pool.close()
        await super().close()


async def main():
    bot = EconomyBot()
    await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
