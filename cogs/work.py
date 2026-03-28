import discord
from discord import app_commands
from discord.ext import commands
import database as db
from datetime import datetime, timedelta


class Work(commands.Cog):
    """Ког системы работы и профессий"""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="работы", description="Показать список доступных работ")
    async def jobs_list(self, interaction: discord.Interaction):
        """Показ списка всех доступных работ"""
        await interaction.response.defer()
        
        jobs = await self.bot.pool.fetch("SELECT * FROM jobs ORDER BY salary")
        
        embed = discord.Embed(
            title="💼 Доступные работы",
            description="Выберите работу командой `/устроиться`",
            color=discord.Color.blue()
        )
        
        for job in jobs:
            cooldown = job['cooldown_hours']
            cooldown_str = f"{cooldown}ч" if cooldown > 0 else "Нет"
            embed.add_field(
                name=f"{job['job_name']} (ID: {job['job_id']})",
                value=f"💰 Зарплата: ${job['salary']:,}\n⏱️ Перерыв: {cooldown_str}",
                inline=True
            )
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="устроиться", description="Устроиться на работу")
    @app_commands.describe(job_id="ID желаемой работы")
    async def set_job(self, interaction: discord.Interaction, job_id: int):
        """Устройство на работу"""
        await interaction.response.defer()
        
        # Проверка существования работы
        job = await self.bot.pool.fetchrow(
            "SELECT * FROM jobs WHERE job_id = $1", job_id
        )
        
        if not job:
            await interaction.followup.send("❌ Работа с таким ID не найдена!", ephemeral=True)
            return
        
        await db.set_job(self.bot.pool, interaction.user.id, job_id)
        await db.get_or_create_user(self.bot.pool, interaction.user.id, interaction.user.name)
        
        await interaction.followup.send(f"✅ Вы устроились на работу: **{job['job_name']}**!\n💰 Зарплата: ${job['salary']:,}\n⏱️ Перерыв между работами: {job['cooldown_hours']}ч")

    @app_commands.command(name="работать", description="Поработать и получить зарплату")
    async def work(self, interaction: discord.Interaction):
        """Выполнение работы и получение зарплаты"""
        await interaction.response.defer()
        
        user = await db.get_or_create_user(
            self.bot.pool, 
            interaction.user.id, 
            interaction.user.name
        )
        
        if not user['job_id']:
            await interaction.followup.send("❌ У вас нет работы! Используйте `/работы` для просмотра и `/устроиться` для устройства.", ephemeral=True)
            return
        
        job = await self.bot.pool.fetchrow(
            "SELECT * FROM jobs WHERE job_id = $1", user['job_id']
        )
        
        if job['salary'] <= 0:
            await interaction.followup.send("❌ Вы безработный. Найдьте работу!", ephemeral=True)
            return
        
        async with self.bot.pool.acquire() as conn:
            last_work = await conn.fetchval(
                "SELECT last_work_timestamp FROM users WHERE user_id = $1",
                interaction.user.id
            )
            
            cooldown_hours = job['cooldown_hours']
            now = datetime.now()
            
            if last_work:
                elapsed = now - last_work
                required_cooldown = timedelta(hours=cooldown_hours)
                
                if elapsed < required_cooldown:
                    remaining = required_cooldown - elapsed
                    hours = remaining.seconds // 3600
                    minutes = (remaining.seconds % 3600) // 60
                    await interaction.followup.send(
                        f"⏰ Вы ещё не можете работать. Подождите {hours}ч {minutes}м.",
                        ephemeral=True
                    )
                    return
            
            # Начисление зарплаты
            await db.update_balance(self.bot.pool, interaction.user.id, job['salary'])
            await conn.execute(
                "UPDATE users SET last_work_timestamp = $1 WHERE user_id = $2",
                now, interaction.user.id
            )
            
            await interaction.followup.send(f"✅ Вы поработали и получили **${job['salary']:,}**!\nВаша профессия: {job['job_name']}")

    @app_commands.command(name="моя_работа", description="Показать текущую работу")
    async def my_job(self, interaction: discord.Interaction):
        """Показ текущей работы пользователя"""
        await interaction.response.defer()
        
        user = await db.get_or_create_user(
            self.bot.pool, 
            interaction.user.id, 
            interaction.user.name
        )
        
        if not user['job_id']:
            await interaction.followup.send("❌ У вас нет работы!", ephemeral=True)
            return
        
        job = await self.bot.pool.fetchrow(
            "SELECT * FROM jobs WHERE job_id = $1", user['job_id']
        )
        
        embed = discord.Embed(
            title=f"💼 Ваша работа: {job['job_name']}",
            color=discord.Color.green()
        )
        embed.add_field(name="💰 Зарплата", value=f"${job['salary']:,}", inline=True)
        embed.add_field(name="⏱️ Перерыв", value=f"{job['cooldown_hours']}ч", inline=True)
        
        # Время до следующей работы
        if user['last_work_timestamp']:
            now = datetime.now()
            elapsed = now - user['last_work_timestamp']
            required_cooldown = timedelta(hours=job['cooldown_hours'])
            
            if elapsed < required_cooldown:
                remaining = required_cooldown - elapsed
                hours = remaining.seconds // 3600
                minutes = (remaining.seconds % 3600) // 60
                embed.add_field(
                    name="⏳ До следующей работы",
                    value=f"{hours}ч {minutes}м",
                    inline=False
                )
            else:
                embed.add_field(
                    name="✅ Статус",
                    value="Готов к работе!",
                    inline=False
                )
        
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Work(bot))
