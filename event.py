'''
Класс для работы с бд
'''

import aiosqlite

class EventDatabase:
    def __init__(self, db_name="events.db"):
        self.db_name = db_name
        self.con = None

    # Метод для подключения к базе данных
    async def connect(self):
        if self.con is None:
            self.con = await aiosqlite.connect(self.db_name)
            await self.create_tables()

    # Создание таблиц, если они не существуют
    async def create_tables(self):
        async with self.con.cursor() as cursor:
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_name TEXT NOT NULL,
                    event_description TEXT NOT NULL,
                    event_type TEXT NOT NULL
                );
            """)
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS event_options (
                    option_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER,
                    option_text TEXT NOT NULL,
                    FOREIGN KEY(event_id) REFERENCES events(event_id)
                );
            """)
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS workshops (
                    workshop_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER,
                    workshop_name TEXT NOT NULL,
                    workshop_description TEXT NOT NULL,
                    instructor TEXT NOT NULL,
                    max_participants INTEGER NOT NULL,
                    current_participants INTEGER DEFAULT 0,
                    FOREIGN KEY(event_id) REFERENCES events(event_id)
                );
            """)
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS responses (
                    response_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER,
                    user_id INTEGER,
                    user_name TEXT,
                    option_id INTEGER,
                    response_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(event_id) REFERENCES events(event_id),
                    FOREIGN KEY(option_id) REFERENCES event_options(option_id)
                );
            """)
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS workshop_registrations (
                    registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workshop_id INTEGER,
                    user_id INTEGER,
                    user_name TEXT,
                    group_number TEXT,
                    registration_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(workshop_id) REFERENCES workshops(workshop_id)
                );
            """)
            await self.con.commit()

    # Метод для добавления события
    async def add_event(self, event_name, event_description, event_type):
        await self.connect()  # Подключаемся, если еще не подключены
        async with self.con.cursor() as cursor:
            await cursor.execute("""
                INSERT INTO events (event_name, event_description, event_type)
                VALUES (?, ?, ?)
            """, (event_name, event_description, event_type))
            await self.con.commit()

    # Метод для добавления варианта ответа для события
    async def add_option(self, event_id, option_text):
        await self.connect()  # Подключаемся, если еще не подключены
        async with self.con.cursor() as cursor:
            await cursor.execute("""
                INSERT INTO event_options (event_id, option_text)
                VALUES (?, ?)
            """, (event_id, option_text))
            await self.con.commit()

    # Получаем все события
    async def get_all_events(self):
        await self.connect()
        async with self.con.cursor() as cursor:
            await cursor.execute("""
                SELECT event_id, event_name, event_description, event_type
                FROM events
            """)
            rows = await cursor.fetchall()
            return [
                {
                    "event_id": row[0],
                    "event_name": row[1],
                    "event_description": row[2],
                    "event_type": row[3],
                }
                for row in rows
            ]

    # Получаем событие по ID
    async def get_event_by_id(self, event_id):
        await self.connect()  # Подключаемся, если еще не подключены
        async with self.con.cursor() as cursor:
            await cursor.execute("SELECT event_id, event_name, event_description, event_type FROM events WHERE event_id = ?", (event_id,))
            event = await cursor.fetchone()
            if event:
                return {"event_id": event[0], "event_name": event[1], "event_description": event[2], "event_type": event[3]}
            return None

    # Получаем варианты для голосования
    async def get_event_options(self, event_id):
        await self.connect()  # Подключаемся, если еще не подключены
        async with self.con.cursor() as cursor:
            await cursor.execute("SELECT option_id, option_text FROM event_options WHERE event_id = ?", (event_id,))
            options = await cursor.fetchall()
            return [{"option_id": option[0], "option_text": option[1]} for option in options]

    async def get_event_id_by_name(self, event_name):
        await self.connect()
        async with self.con.cursor() as cursor:
            await cursor.execute("SELECT event_id FROM events WHERE event_name = ?", (event_name,))
            result = await cursor.fetchone()
            return result[0] if result else None


    async def add_workshop(self, event_id, workshop_name, workshop_description, instructor, max_participants):
        await self.connect()
        async with self.con.cursor() as cursor:
            await cursor.execute("""
                INSERT INTO workshops (event_id, workshop_name, workshop_description, instructor, max_participants)
                VALUES (?, ?, ?, ?, ?)
            """, (event_id, workshop_name, workshop_description, instructor, max_participants))
            await self.con.commit()

    async def add_response(self, event_id, user_id, user_name, option_id):
        await self.connect()
        async with self.con.cursor() as cursor:
            await cursor.execute("""
                INSERT INTO responses (event_id, user_id, user_name, option_id)
                VALUES (?, ?, ?, ?)
            """, (event_id, user_id, user_name, option_id))
            await self.con.commit()

    # async def get_all_events(self):
    #     await self.connect()
    #     async with self.con.cursor() as cursor:
    #         await cursor.execute("SELECT event_id, event_name FROM events")
    #         events = await cursor.fetchall()
    #         # Проверяем, преобразуются ли кортежи в словари
    #         return [{"event_id": event[0], "event_name": event[1]} for event in events]

    # Добавляем ответ на голосование
    async def add_response(self, event_id, user_id, user_name, option_id):
        await self.connect()  # Подключаемся, если еще не подключены
        async with self.con.cursor() as cursor:
            await cursor.execute("""
                INSERT INTO responses (event_id, user_id, user_name, option_id)
                VALUES (?, ?, ?, ?)
            """, (event_id, user_id, user_name, option_id))
            await self.con.commit()

    # Получаем мастер-классы по событию
    async def get_workshops_by_event(self, event_id):
        await self.connect()  # Подключаемся, если еще не подключены
        async with self.con.cursor() as cursor:
            await cursor.execute("SELECT workshop_id, workshop_name FROM workshops WHERE event_id = ?", (event_id,))
            workshops = await cursor.fetchall()
            return [{"workshop_id": workshop[0], "workshop_name": workshop[1]} for workshop in workshops]

    # Регистрируем пользователя на мастер-класс
    async def register_for_workshop(self, workshop_id, user_id, user_name, group_number):
        await self.connect()  # Подключаемся, если еще не подключены
        async with self.con.cursor() as cursor:
            # Получаем текущие данные мастер-класса
            await cursor.execute("SELECT max_participants, current_participants FROM workshops WHERE workshop_id = ?", (workshop_id,))
            workshop = await cursor.fetchone()

            if workshop:
                max_participants, current_participants = workshop
                # Проверяем, что не превышен лимит участников
                if current_participants >= max_participants:
                    return False  # Мастер-класс переполнен

                # Добавляем пользователя в таблицу workshop_registrations
                await cursor.execute("""
                    INSERT INTO workshop_registrations (workshop_id, user_id, user_name, group_number)
                    VALUES (?, ?, ?, ?)
                """, (workshop_id, user_id, user_name, group_number))
                await self.con.commit()

                # Обновляем количество участников мастер-класса
                new_participant_count = current_participants + 1
                await cursor.execute("""
                    UPDATE workshops
                    SET current_participants = ?
                    WHERE workshop_id = ?
                """, (new_participant_count, workshop_id))
                await self.con.commit()

                return True  # Успешная регистрация
            else:
                return False  # Мастер-класс не найден

    # Проверка регистрации пользователя на мастер-классе
    async def is_user_registered_for_workshop(self, user_id, workshop_id):
        await self.connect()  # Подключаемся, если еще не подключены
        async with self.con.cursor() as cursor:
            await cursor.execute("SELECT 1 FROM workshop_registrations WHERE user_id = ? AND workshop_id = ?", (user_id, workshop_id))
            return await cursor.fetchone() is not None

    async def is_user_registered_for_event(self, user_id: int, event_id: int) -> bool:
        await self.connect()
        async with self.con.cursor() as cursor:
            await cursor.execute(
                """
                SELECT 1
                FROM workshop_registrations wr
                JOIN workshops w ON wr.workshop_id = w.workshop_id
                WHERE wr.user_id = ? AND w.event_id = ?
                """,
                (user_id, event_id)
            )
            return await cursor.fetchone() is not None

    async def get_workshop_by_id(self, workshop_id: int):
        await self.connect()
        async with self.con.cursor() as cursor:
            await cursor.execute("""
                SELECT workshop_id, workshop_name, workshop_description, instructor, max_participants, current_participants
                FROM workshops
                WHERE workshop_id = ?
            """, (workshop_id,))
            row = await cursor.fetchone()
            if row:
                return {
                    "workshop_id": row[0],
                    "workshop_name": row[1],
                    "workshop_description": row[2],
                    "instructor": row[3],
                    "max_participants": row[4],
                    "current_participants": row[5],
                }
            return None

    async def delete_event(self, event_id):
        await self.connect()
        async with self.con.cursor() as cursor:
            # Удаляем связанные данные
            await cursor.execute("DELETE FROM responses WHERE event_id = ?", (event_id,))
            await cursor.execute("DELETE FROM event_options WHERE event_id = ?", (event_id,))
            await cursor.execute("DELETE FROM workshops WHERE event_id = ?", (event_id,))
            await cursor.execute("DELETE FROM events WHERE event_id = ?", (event_id,))
            await self.con.commit()

    async def register_user_for_workshop(self, user_id: int, workshop_id: int, participant_name: str, group_number: str):
        try:
            # Получаем текущие данные мастер-класса
            await self.connect()
            async with self.con.cursor() as cursor:
                await cursor.execute("SELECT max_participants, current_participants FROM workshops WHERE workshop_id = ?", (workshop_id,))
                workshop = await cursor.fetchone()

            if workshop:
                max_participants, current_participants = workshop
                # Проверяем, что не превышен лимит участников
                if current_participants >= max_participants:
                    return False  # Мастер-класс переполнен

                # Добавляем пользователя в таблицу workshop_registrations
                async with self.con.cursor() as cursor:
                    await cursor.execute("""
                        INSERT INTO workshop_registrations (workshop_id, user_id, user_name, group_number)
                        VALUES (?, ?, ?, ?)
                    """, (workshop_id, user_id, participant_name, group_number))
                    await self.con.commit()

                # Обновляем количество участников мастер-класса
                new_participant_count = current_participants + 1
                async with self.con.cursor() as cursor:
                    await cursor.execute("""
                        UPDATE workshops
                        SET current_participants = ?
                        WHERE workshop_id = ?
                    """, (new_participant_count, workshop_id))
                    await self.con.commit()

                return True  # Успешная регистрация
            else:
                return False  # Мастер-класс не найден

        except Exception as e:
            print(f"Error during registration: {e}")
            return False

    async def is_user_registered_for_any_workshop(self, user_id: int):
        try:
            # Выполним запрос на проверку, зарегистрирован ли пользователь на любом мастер-классе
            await self.connect()
            async with self.con.cursor() as cursor:
                await cursor.execute("""
                    SELECT COUNT(*) FROM workshop_registrations WHERE user_id = ?
                """, (user_id,))
                result = await cursor.fetchone()
                return result[0] > 0  # Если результат больше 0, значит, пользователь зарегистрирован хотя бы на одном мастер-классе
        except Exception as e:
            print(f"Error checking user registration: {e}")
            return False

    # Удаляем событие и связанные данные
    async def delete_event(self, event_id):
        await self.connect()  # Подключаемся, если еще не подключены
        async with self.con.cursor() as cursor:
            await cursor.execute("DELETE FROM responses WHERE event_id = ?", (event_id,))
            await cursor.execute("DELETE FROM event_options WHERE event_id = ?", (event_id,))
            await cursor.execute("DELETE FROM workshops WHERE event_id = ?", (event_id,))
            await cursor.execute("DELETE FROM events WHERE event_id = ?", (event_id,))
            await self.con.commit()

    # Получаем список участников для мастер-класса
    async def get_workshop_participants(self, workshop_id):
        await self.connect()  # Подключаемся, если еще не подключены
        async with self.con.cursor() as cursor:
            await cursor.execute("""
                SELECT wr.user_name, wr.group_number
                FROM workshop_registrations wr
                WHERE wr.workshop_id = ?
            """, (workshop_id,))
            rows = await cursor.fetchall()
            return [{"name": row[0], "group": row[1]} for row in rows]

    # Проверка, голосовал ли пользователь на событие
    async def has_user_voted(self, user_id, event_id):
        await self.connect()  # Подключаемся, если еще не подключены
        async with self.con.cursor() as cursor:
            await cursor.execute("""
                SELECT 1 FROM responses WHERE user_id = ? AND event_id = ?
            """, (user_id, event_id))
            return await cursor.fetchone() is not None

    # Получаем результаты голосования для события
    async def get_vote_results(self, event_id):
        await self.connect()  # Подключаемся, если еще не подключены
        async with self.con.cursor() as cursor:
            await cursor.execute("""
                SELECT eo.option_text, COUNT(r.response_id) AS vote_count
                FROM event_options eo
                LEFT JOIN responses r ON eo.option_id = r.option_id
                WHERE eo.event_id = ?
                GROUP BY eo.option_id
            """, (event_id,))
            rows = await cursor.fetchall()
            return [{"option_text": row[0], "vote_count": row[1]} for row in rows]

    # Получаем события, которые являются голосованиями
    async def get_vote_events(self):
        await self.connect()  # Подключаемся, если еще не подключены
        async with self.con.cursor() as cursor:
            await cursor.execute("SELECT event_id, event_name FROM events WHERE event_type='vote'")
            rows = await cursor.fetchall()
            return [{'event_id': row[0], 'event_name': row[1]} for row in rows]

    # Проверка, голосовал ли пользователь на событие
    async def has_user_voted(self, user_id: int, event_id: int) -> bool:
        await self.connect()  # Подключаемся, если еще не подключены
        try:
            async with self.con.cursor() as cursor:
                await cursor.execute("""
                    SELECT 1 FROM responses
                    WHERE user_id = ? AND event_id = ?
                """, (user_id, event_id))
                return await cursor.fetchone() is not None
        except Exception as e:
            print(f"Error in has_user_voted: {e}")
            return False

    # Получаем результаты голосования для события
    async def get_vote_results(self, event_id: int):
        await self.connect()  # Подключаемся, если еще не подключены
        try:
            async with self.con.cursor() as cursor:
                await cursor.execute("""
                    SELECT eo.option_text, COUNT(r.response_id) AS vote_count
                    FROM event_options eo
                    LEFT JOIN responses r ON eo.option_id = r.option_id
                    WHERE eo.event_id = ?
                    GROUP BY eo.option_id
                """, (event_id,))
                rows = await cursor.fetchall()
                return [{"option_text": row[0], "vote_count": row[1]} for row in rows]
        except Exception as e:
            print(f"Error in get_vote_results: {e}")
            return []

    # Получаем участников мастер-класса
    async def get_workshop_participants(self, workshop_id: int):
        await self.connect()  # Подключаемся, если еще не подключены
        try:
            async with self.con.cursor() as cursor:
                await cursor.execute("""
                    SELECT wr.user_name, wr.group_number
                    FROM workshop_registrations wr
                    WHERE wr.workshop_id = ?
                """, (workshop_id,))
                rows = await cursor.fetchall()
                return [{"name": row[0], "group": row[1]} for row in rows]
        except Exception as e:
            print(f"Error in get_workshop_participants: {e}")
            return []

    # Получаем мастер-классы с участниками по событию
    async def get_workshops_with_participants(self, event_id):
        await self.connect()  # Подключаемся, если еще не подключены
        try:
            async with self.con.cursor() as cursor:
                print(f"DEBUG: Выполняется запрос для event_id {event_id}")
                await cursor.execute("""
                    SELECT 
                        w.workshop_name,
                        wr.user_name,
                        wr.group_number
                    FROM workshops w
                    LEFT JOIN workshop_registrations wr ON w.workshop_id = wr.workshop_id
                    WHERE w.event_id = ?
                    ORDER BY w.workshop_name, wr.group_number;
                """, (event_id,))
                rows = await cursor.fetchall()

                # Преобразуем данные в ожидаемый формат
                workshops = {}
                for row in rows:
                    workshop_name = row[0]
                    if workshop_name not in workshops:
                        workshops[workshop_name] = []
                    if row[1]:  # Если есть участники
                        workshops[workshop_name].append({
                            "name": row[1],
                            "group_number": row[2]
                        })
                return workshops
        except Exception as e:
            print(f"Error in get_workshops_with_participants: {e}")
            return {}

    # Получаем участников по группам в рамках события
    async def get_participants_by_groups(self, event_id):
        await self.connect()  # Подключаемся, если еще не подключены
        try:
            async with self.con.cursor() as cursor:
                print(f"DEBUG: Выполняется запрос для event_id {event_id} по отрядам")
                await cursor.execute("""
                    SELECT 
                        wr.group_number,
                        wr.user_name,
                        w.workshop_name
                    FROM workshop_registrations wr
                    JOIN workshops w ON wr.workshop_id = w.workshop_id
                    WHERE w.event_id = ?
                    ORDER BY wr.group_number, wr.user_name;
                """, (event_id,))
                rows = await cursor.fetchall()

                # Преобразуем данные в формат "отряды -> участники"
                groups = {}
                for row in rows:
                    group_number = row[0]
                    if group_number not in groups:
                        groups[group_number] = []
                    groups[group_number].append({
                        "name": row[1],
                        "workshop_name": row[2]
                    })
                return groups
        except Exception as e:
            print(f"Error in get_participants_by_groups: {e}")
            return {}

# Получаем список событий, в которых пользователь уже участвовал (голосовал или зарегистрировался на мастер-классе)
    async def get_user_participated_event_ids(self, user_id: int):
        # Получаем события, в которых пользователь проголосовал
        voted_events = await self.get_voted_event_ids(user_id)
        # Получаем события, на которые пользователь зарегистрировался (мастер-классы)
        registered_events = await self.get_registered_event_ids(user_id)

        # Объединяем события и удаляем дубликаты
        return list(set(voted_events + registered_events))


    # Получаем список event_id для событий, в которых пользователь проголосовал
# Получаем список event_id для событий, в которых пользователь проголосовал
    async def get_voted_event_ids(self, user_id: int):
        query = """
            SELECT event_id
            FROM responses
            WHERE user_id = ?
        """
        async with self.con.cursor() as cursor:
            await cursor.execute(query, (user_id,))
            rows = await cursor.fetchall()
        return [row[0] for row in rows]


    # Получаем список event_id для событий, на которые пользователь зарегистрировался
# Получаем список event_id для событий, на которые пользователь зарегистрировался (мастер-классы)
    async def get_registered_event_ids(self, user_id: int):
        query = """
            SELECT w.event_id
            FROM workshop_registrations wr
            JOIN workshops w ON wr.workshop_id = w.workshop_id
            WHERE wr.user_id = ?
        """
        async with self.con.cursor() as cursor:
            await cursor.execute(query, (user_id,))
            rows = await cursor.fetchall()
        return [row[0] for row in rows]


    # Получаем список будущих событий, в которых пользователь еще не участвовал
# Получаем список будущих событий, в которых пользователь еще не участвовал
    async def get_upcoming_events(self, user_id: int):
        # Получаем все события
        events = await self.get_all_events()
        # Получаем события, в которых пользователь уже участвовал
        participated_event_ids = await self.get_user_participated_event_ids(user_id)
        # Фильтруем только те события, в которых пользователь еще не участвовал
        upcoming_events = [event for event in events if event['event_id'] not in participated_event_ids]
        return upcoming_events

async def get_available_slots_for_workshop(self, workshop_id):
    """
    Возвращает количество доступных мест на мастер-классе.
    """
    await self.connect()
    async with self.con.cursor() as cursor:
        await cursor.execute("""
            SELECT max_participants - current_participants
            FROM workshops
            WHERE workshop_id = ?
        """, (workshop_id,))
        row = await cursor.fetchone()
        if row:
            return max(row[0], 0)  # Убедимся, что количество доступных мест не отрицательное
        return 0  # Если мастер-класс не найден
