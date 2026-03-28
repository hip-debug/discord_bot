import discord
from discord import app_commands
from discord.ext import commands
import database as db


class Properties(commands.Cog):
    """Ког системы недвижимости"""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="недвижимость", description="Показать доступную недвижимость")
    async def properties_list(self, interaction: discord.Interaction):
        """Показ списка всей доступной недвижимости"""
        await interaction.response.defer()
        
        properties = await self.bot.pool.fetch("SELECT * FROM properties ORDER BY price")
        
        embed = discord.Embed(
            title="🏠 Доступная недвижимость",
            description="Используйте `/купить_дом` для покупки",
            color=discord.Color.orange()
        )
        
        for prop in properties:
            income_str = f"+${prop['income_per_day']:,}/день" if prop['income_per_day'] > 0 else "Нет дохода"
            embed.add_field(
                name=f"{prop['property_name']} (ID: {prop['property_id']})",
                value=f"💰 Цена: ${prop['price']:,}\n📈 Доход: {income_str}\n📝 {prop['description']}",
                inline=False
            )
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="мои_дома", description="Показать вашу недвижимость")
    async def my_properties(self, interaction: discord.Interaction):
        """Показ недвижимости пользователя"""
        await interaction.response.defer()
        
        user_props = await db.get_user_properties(self.bot.pool, interaction.user.id)
        
        if not user_props:
            await interaction.followup.send("❌ У вас нет недвижимости! Используйте `/недвижимость` для просмотра.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🏠 Ваша недвижимость",
            color=discord.Color.gold()
        )
        
        total_income = sum(prop['income_per_day'] for prop in user_props)
        
        for prop in user_props:
            income_str = f"+${prop['income_per_day']:,}/день" if prop['income_per_day'] > 0 else "Нет дохода"
            embed.add_field(
                name=prop['property_name'],
                value=f"💰 Стоимость: ${prop['price']:,}\n📈 Доход: {income_str}\n📝 {prop['description']}",
                inline=False
            )
        
        embed.add_field(
            name="📊 Общий доход в день",
            value=f"${total_income:,}",
            inline=False
        )
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="купить_дом", description="Купить недвижимость")
    @app_commands.describe(property_id="ID недвижимости для покупки")
    async def buy_property_cmd(self, interaction: discord.Interaction, property_id: int):
        """Покупка недвижимости"""
        await interaction.response.defer()
        
        # Проверка существования недвижимости
        prop = await self.bot.pool.fetchrow(
            "SELECT * FROM properties WHERE property_id = $1", property_id
        )
        
        if not prop:
            await interaction.followup.send("❌ Недвижимость с таким ID не найдена!", ephemeral=True)
            return
        
        # Проверка, есть ли уже эта недвижимость
        user_props = await db.get_user_properties(self.bot.pool, interaction.user.id)
        if any(p['property_id'] == property_id for p in user_props):
            await interaction.followup.send("❌ У вас уже есть эта недвижимость!", ephemeral=True)
            return
        
        # Покупка
        success = await db.buy_property(self.bot.pool, interaction.user.id, property_id)
        
        if success:
            await interaction.followup.send(f"✅ Вы купили **{prop['property_name']}** за ${prop['price']:,}!\n📈 Ежедневный доход: ${prop['income_per_day']:,}")
        else:
            await interaction.followup.send("❌ Недостаточно средств для покупки!", ephemeral=True)

    @app_commands.command(name="доход", description="Получить ежедневный доход от недвижимости")
    async def collect_income(self, interaction: discord.Interaction):
        """Сбор ежедневного дохода от недвижимости"""
        await interaction.response.defer()
        
        user_props = await db.get_user_properties(self.bot.pool, interaction.user.id)
        
        if not user_props:
            await interaction.followup.send("❌ У вас нет недвижимости для получения дохода!", ephemeral=True)
            return
        
        total_income = sum(prop['income_per_day'] for prop in user_props)
        
        if total_income <= 0:
            await interaction.followup.send("❌ Ваша недвижимость не приносит дохода!", ephemeral=True)
            return
        
        await db.update_balance(self.bot.pool, interaction.user.id, total_income)
        
        await interaction.followup.send(f"✅ Вы получили **${total_income:,}** дохода от вашей недвижимости!")


async def setup(bot):
    await bot.add_cog(Properties(bot))
