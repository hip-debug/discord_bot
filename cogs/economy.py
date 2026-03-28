import discord
from discord import app_commands
from discord.ext import commands
import database as db
from datetime import datetime, timedelta


class Economy(commands.Cog):
    """Ког экономики с банковскими операциями"""

    def __init__(self, bot):
        self.bot = bot

    async def get_user_embed(self, user_data):
        """Создание embed с информацией о пользователе"""
        job_name = "Безработный"
        if user_data['job_id']:
            job = await self.bot.pool.fetchrow(
                "SELECT job_name FROM jobs WHERE job_id = $1",
                user_data['job_id']
            )
            if job:
                job_name = job['job_name']

        embed = discord.Embed(
            title=f"💰 Профиль: {user_data['username']}",
            color=discord.Color.gold()
        )
        embed.add_field(name="💵 Наличные", value=f"${user_data['balance']:,}", inline=True)
        embed.add_field(name="🏦 В банке", value=f"${user_data['bank_balance']:,}", inline=True)
        embed.add_field(name="💼 Работа", value=job_name, inline=True)
        embed.add_field(name="📊 Общий капитал", value=f"${user_data['balance'] + user_data['bank_balance']:,}", inline=False)
        return embed

    @app_commands.command(name="баланс", description="Проверить свой баланс")
    async def balance(self, interaction: discord.Interaction):
        """Проверка баланса пользователя"""
        await interaction.response.defer()
        
        user = await db.get_or_create_user(
            self.bot.pool, 
            interaction.user.id, 
            interaction.user.name
        )
        
        embed = await self.get_user_embed(user)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="ежедневно", description="Получить ежедневную награду")
    async def daily(self, interaction: discord.Interaction):
        """Получение ежедневной награды"""
        await interaction.response.defer()
        
        user = await db.get_or_create_user(
            self.bot.pool, 
            interaction.user.id, 
            interaction.user.name
        )
        
        async with self.bot.pool.acquire() as conn:
            last_daily = await conn.fetchval(
                "SELECT last_salary_timestamp FROM users WHERE user_id = $1",
                interaction.user.id
            )
            
            now = datetime.now()
            if last_daily and (now - last_daily) < timedelta(hours=24):
                remaining = timedelta(hours=24) - (now - last_daily)
                hours = remaining.seconds // 3600
                minutes = (remaining.seconds % 3600) // 60
                await interaction.followup.send(
                    f"⏰ Следующая ежедневная награда через {hours}ч {minutes}м",
                    ephemeral=True
                )
                return
            
            daily_amount = 500
            await db.update_balance(self.bot.pool, interaction.user.id, daily_amount)
            await conn.execute(
                "UPDATE users SET last_salary_timestamp = $1 WHERE user_id = $2",
                now, interaction.user.id
            )
            
            await interaction.followup.send(f"✅ Вы получили ${daily_amount} ежедневной награды!")

    @app_commands.command(name="депозит", description="Внести деньги в банк")
    @app_commands.describe(amount="Сумма для внесения")
    async def deposit(self, interaction: discord.Interaction, amount: int):
        """Внесение денег на банковский счёт"""
        await interaction.response.defer()
        
        if amount <= 0:
            await interaction.followup.send("❌ Сумма должна быть положительной!", ephemeral=True)
            return
        
        user = await db.get_or_create_user(
            self.bot.pool, 
            interaction.user.id, 
            interaction.user.name
        )
        
        if user['balance'] < amount:
            await interaction.followup.send("❌ Недостаточно наличных!", ephemeral=True)
            return
        
        await db.update_balance(self.bot.pool, interaction.user.id, -amount)
        await db.update_bank_balance(self.bot.pool, interaction.user.id, amount)
        
        await interaction.followup.send(f"✅ Вы внесли ${amount:,} в банк!")

    @app_commands.command(name="снять", description="Снять деньги из банка")
    @app_commands.describe(amount="Сумма для снятия")
    async def withdraw(self, interaction: discord.Interaction, amount: int):
        """Снятие денег с банковского счёта"""
        await interaction.response.defer()
        
        if amount <= 0:
            await interaction.followup.send("❌ Сумма должна быть положительной!", ephemeral=True)
            return
        
        user = await db.get_or_create_user(
            self.bot.pool, 
            interaction.user.id, 
            interaction.user.name
        )
        
        if user['bank_balance'] < amount:
            await interaction.followup.send("❌ Недостаточно средств в банке!", ephemeral=True)
            return
        
        await db.update_bank_balance(self.bot.pool, interaction.user.id, -amount)
        await db.update_balance(self.bot.pool, interaction.user.id, amount)
        
        await interaction.followup.send(f"✅ Вы сняли ${amount:,} из банка!")

    @app_commands.command(name="передать", description="Передать деньги другому пользователю")
    @app_commands.describe(user="Пользователь для перевода", amount="Сумма перевода")
    async def transfer(self, interaction: discord.Interaction, user: discord.User, amount: int):
        """Перевод денег другому пользователю"""
        await interaction.response.defer()
        
        if amount <= 0:
            await interaction.followup.send("❌ Сумма должна быть положительной!", ephemeral=True)
            return
        
        if user.id == interaction.user.id:
            await interaction.followup.send("❌ Нельзя перевести деньги самому себе!", ephemeral=True)
            return
        
        sender = await db.get_or_create_user(
            self.bot.pool, 
            interaction.user.id, 
            interaction.user.name
        )
        
        if sender['balance'] < amount:
            await interaction.followup.send("❌ Недостаточно наличных!", ephemeral=True)
            return
        
        await db.update_balance(self.bot.pool, interaction.user.id, -amount)
        await db.update_balance(self.bot.pool, user.id, amount)
        
        await interaction.followup.send(f"✅ Вы перевели ${amount:,} пользователю {user.mention}!")


async def setup(bot):
    await bot.add_cog(Economy(bot))
