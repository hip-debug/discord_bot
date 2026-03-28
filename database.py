import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


async def get_pool():
    """Создание пула соединений с базой данных"""
    return await asyncpg.create_pool(DATABASE_URL)


async def init_db(pool):
    """Инициализация таблиц базы данных"""
    async with pool.acquire() as conn:
        # Таблица пользователей
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT NOT NULL,
                balance BIGINT DEFAULT 0,
                bank_balance BIGINT DEFAULT 0,
                job_id INTEGER REFERENCES jobs(job_id),
                last_work_timestamp TIMESTAMP,
                last_salary_timestamp TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица работ
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id SERIAL PRIMARY KEY,
                job_name TEXT NOT NULL UNIQUE,
                salary INTEGER NOT NULL,
                cooldown_hours INTEGER NOT NULL DEFAULT 1
            )
        """)

        # Таблица недвижимости
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS properties (
                property_id SERIAL PRIMARY KEY,
                property_name TEXT NOT NULL UNIQUE,
                price INTEGER NOT NULL,
                income_per_day INTEGER DEFAULT 0,
                description TEXT
            )
        """)

        # Таблица владения недвижимостью
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_properties (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                property_id INTEGER REFERENCES properties(property_id),
                purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, property_id)
            )
        """)

        # Таблица транзакций
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                transaction_id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                amount INTEGER NOT NULL,
                transaction_type TEXT NOT NULL,
                description TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Заполнение начальными данными для работ
        await conn.execute("""
            INSERT INTO jobs (job_name, salary, cooldown_hours) VALUES
            ('Безработный', 0, 0),
            ('Уборщик', 100, 1),
            ('Курьер', 250, 2),
            ('Продавец', 500, 4),
            ('Полицейский', 1000, 6),
            ('Врач', 2000, 8),
            ('Инженер', 3500, 12),
            ('Программист', 5000, 24),
            ('Предприниматель', 10000, 24)
            ON CONFLICT (job_name) DO NOTHING
        """)

        # Заполнение начальными данными для недвижимости
        await conn.execute("""
            INSERT INTO properties (property_name, price, income_per_day, description) VALUES
            ('Палатка', 1000, 10, 'Простое убежище'),
            ('Домик', 5000, 50, 'Небольшой дом'),
            ('Квартира', 15000, 150, 'Уютная квартира'),
            ('Особняк', 50000, 500, 'Роскошный особняк'),
            ('Вилла', 150000, 1500, 'Элитная вилла'),
            ('Небоскрёб', 500000, 5000, 'Собственный небоскрёб')
            ON CONFLICT (property_name) DO NOTHING
        """)

        print("База данных успешно инициализирована!")


async def get_or_create_user(pool, user_id: int, username: str):
    """Получить или создать пользователя"""
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE user_id = $1", user_id
        )
        if not user:
            await conn.execute(
                "INSERT INTO users (user_id, username) VALUES ($1, $2)",
                user_id, username
            )
            user = await conn.fetchrow(
                "SELECT * FROM users WHERE user_id = $1", user_id
            )
        return user


async def update_balance(pool, user_id: int, amount: int):
    """Обновить баланс пользователя"""
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET balance = balance + $1 WHERE user_id = $2",
            amount, user_id
        )
        await conn.execute(
            "INSERT INTO transactions (user_id, amount, transaction_type, description) VALUES ($1, $2, 'balance_change', 'Изменение баланса')",
            user_id, amount
        )


async def update_bank_balance(pool, user_id: int, amount: int):
    """Обновить баланс в банке"""
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET bank_balance = bank_balance + $1 WHERE user_id = $2",
            amount, user_id
        )
        await conn.execute(
            "INSERT INTO transactions (user_id, amount, transaction_type, description) VALUES ($1, $2, 'bank_change', 'Изменение банковского счёта')",
            user_id, amount
        )


async def set_job(pool, user_id: int, job_id: int):
    """Установить работу пользователю"""
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET job_id = $1, last_work_timestamp = NULL WHERE user_id = $2",
            job_id, user_id
        )


async def get_user_properties(pool, user_id: int):
    """Получить всю недвижимость пользователя"""
    async with pool.acquire() as conn:
        return await conn.fetch("""
            SELECT p.* FROM properties p
            JOIN user_properties up ON p.property_id = up.property_id
            WHERE up.user_id = $1
        """, user_id)


async def buy_property(pool, user_id: int, property_id: int):
    """Купить недвижимость"""
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Проверка баланса
            user = await conn.fetchrow(
                "SELECT balance FROM users WHERE user_id = $1", user_id
            )
            prop = await conn.fetchrow(
                "SELECT price FROM properties WHERE property_id = $1", property_id
            )
            
            if user['balance'] >= prop['price']:
                await conn.execute(
                    "UPDATE users SET balance = balance - $1 WHERE user_id = $2",
                    prop['price'], user_id
                )
                await conn.execute(
                    "INSERT INTO user_properties (user_id, property_id) VALUES ($1, $2)",
                    user_id, property_id
                )
                await conn.execute(
                    "INSERT INTO transactions (user_id, amount, transaction_type, description) VALUES ($1, $2, 'property_purchase', 'Покупка недвижимости')",
                    user_id, -prop['price']
                )
                return True
            return False
