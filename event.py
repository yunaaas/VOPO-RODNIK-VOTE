import aiosqlite

class EventDatabase:
    def __init__(self, db_name="events.db"):
        self.db_name = db_name

    async def connect(self):
        self.con = await aiosqlite.connect(self.db_name)
        await self.create_tables()

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

    async def add_event(self, event_name, event_description, event_type):
        async with self.con.cursor() as cursor:
            await cursor.execute("""
                INSERT INTO events (event_name, event_description, event_type)
                VALUES (?, ?, ?)
            """, (event_name, event_description, event_type))
            await self.con.commit()

    async def add_option(self, event_id, option_text):
        async with self.con.cursor() as cursor:
            await cursor.execute("""
                INSERT INTO event_options (event_id, option_text)
                VALUES (?, ?)
            """, (event_id, option_text))
            await self.con.commit()

    async def get_event_id_by_name(self, event_name):
        async with self.con.cursor() as cursor:
            await cursor.execute("SELECT event_id FROM events WHERE event_name = ?", (event_name,))
            result = await cursor.fetchone()
            return result[0] if result else None

    async def add_workshop(self, event_id, workshop_name, workshop_description, instructor, max_participants):
        async with self.con.cursor() as cursor:
            await cursor.execute("""
                INSERT INTO workshops (event_id, workshop_name, workshop_description, instructor, max_participants)
                VALUES (?, ?, ?, ?, ?)
            """, (event_id, workshop_name, workshop_description, instructor, max_participants))
            await self.con.commit()

    async def add_response(self, event_id, user_id, user_name, option_id):
        async with self.con.cursor() as cursor:
            await cursor.execute("""
                INSERT INTO responses (event_id, user_id, user_name, option_id)
                VALUES (?, ?, ?, ?)
            """, (event_id, user_id, user_name, option_id))
            await self.con.commit()

    async def get_all_events(self):
        async with self.con.cursor() as cursor:
            await cursor.execute("SELECT event_id, event_name FROM events")
            events = await cursor.fetchall()
            # Проверяем, преобразуются ли кортежи в словари
            return [{"event_id": event[0], "event_name": event[1]} for event in events]



    async def get_event_by_id(self, event_id):
        async with self.con.cursor() as cursor:
            await cursor.execute("SELECT event_id, event_name, event_description, event_type FROM events WHERE event_id = ?", (event_id,))
        event = await cursor.fetchone()
        if event:
            return {
                "event_id": event[0],
                    "event_name": event[1],
                    "event_description": event[2],
                    "event_type": event[3],
                }
            return None


    # Получаем варианты ответа для голосования
    async def get_event_options(self, event_id):
        async with self.con.cursor() as cursor:
            await cursor.execute("SELECT option_id, option_text FROM event_options WHERE event_id = ?", (event_id,))
            options = await cursor.fetchall()
            return [{"option_id": option[0], "option_text": option[1]} for option in options]

    # Сохраняем ответ на голосование
    async def save_vote(self, user_id, user_name, option_id):
        async with self.con.cursor() as cursor:
            await cursor.execute("""
                INSERT INTO responses (user_id, user_name, option_id)
                VALUES (?, ?, ?)
            """, (user_id, user_name, option_id))
            await self.con.commit()

    # Проверяем, голосовал ли пользователь
    async def has_user_voted(self, user_id, event_id):
        async with self.con.cursor() as cursor:
            await cursor.execute("""
                SELECT COUNT(*) FROM responses WHERE user_id = ? AND event_id = ?
            """, (user_id, event_id))
            result = await cursor.fetchone()
            return result[0] > 0
        


    async def get_workshops_by_event(self, event_id):
        async with self.con.cursor() as cursor:
            await cursor.execute("SELECT workshop_id, workshop_name FROM workshops WHERE event_id = ?", (event_id,))
            workshops = await cursor.fetchall()
            return [{"workshop_id": workshop[0], "workshop_name": workshop[1]} for workshop in workshops]

    # Получаем информацию о мастер-классе по его ID
    async def get_workshop_by_id(self, workshop_id):
        async with self.con.cursor() as cursor:
            await cursor.execute("SELECT workshop_name, workshop_description, instructor, max_participants FROM workshops WHERE workshop_id = ?", (workshop_id,))
            workshop = await cursor.fetchone()
            return {
                "workshop_name": workshop[0],
                "workshop_description": workshop[1],
                "instructor": workshop[2],
                "max_participants": workshop[3]
            } if workshop else None

    # Регистрируем пользователя на мастер-класс
    async def register_for_workshop(self, workshop_id, user_id):
        async with self.con.cursor() as cursor:
            await cursor.execute("""
                INSERT INTO workshop_registrations (workshop_id, user_id)
                VALUES (?, ?)
            """, (workshop_id, user_id))
            await self.con.commit()

    # Проверяем, записан ли пользователь на мастер-класс
    async def has_user_registered_for_workshop(self, user_id, workshop_id):
        async with self.con.cursor() as cursor:
            await cursor.execute("""
                SELECT COUNT(*) FROM workshop_registrations WHERE user_id = ? AND workshop_id = ?
            """, (user_id, workshop_id))
            result = await cursor.fetchone()
            return result[0] > 0
        

    async def get_all_events(self):
        async with self.con.cursor() as cursor:
            await cursor.execute("SELECT * FROM events")
            return await cursor.fetchall()

# Получаем событие по ID
    async def get_event_by_id(self, event_id):
        async with self.con.cursor() as cursor:
            await cursor.execute("SELECT * FROM events WHERE event_id = ?", (event_id,))
            return await cursor.fetchone()

    # Получаем варианты для голосования
    async def get_event_options(self, event_id):
        async with self.con.cursor() as cursor:
            await cursor.execute("SELECT * FROM event_options WHERE event_id = ?", (event_id,))
            return await cursor.fetchall()

    # Получаем мастер-классы по событию
    async def get_workshops_by_event(self, event_id):
        async with self.con.cursor() as cursor:
            await cursor.execute("SELECT * FROM workshops WHERE event_id = ?", (event_id,))
            return await cursor.fetchall()

    # Получаем мастер-класс по ID
    async def get_workshop_by_id(self, workshop_id):
        async with self.con.cursor() as cursor:
            await cursor.execute("SELECT * FROM workshops WHERE workshop_id = ?", (workshop_id,))
            return await cursor.fetchone()

    # Проверка регистрации пользователя на мастер-классе
    async def is_user_registered_for_workshop(self, user_id, workshop_id):
        async with self.con.cursor() as cursor:
            await cursor.execute("SELECT * FROM workshop_registrations WHERE user_id = ? AND workshop_id = ?", (user_id, workshop_id))
            return await cursor.fetchone() is not None

    # Регистрация пользователя на мастер-класс
    # async def register_user_for_workshop(user_id: int, workshop_id: int):
    #     query = "INSERT INTO work_registrations (user_id, workshop_id) VALUES (?, ?)"

    #     try:
    #         # Выполнение запроса в базу данных
    #         result = await db.execute(query, (user_id, workshop_id))
    #         print(f"Registration query executed for user {user_id} and workshop {workshop_id}")
    #         return True
    #     except Exception as e:
    #         print(f"Error during registration for user {user_id} on workshop {workshop_id}: {e}")
    #         return False


    async def register_user_for_workshop(self, user_id: int, workshop_id: int, participant_name: str, group_number: str):
        try:
            # Получаем текущие данные мастер-класса
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
            async with self.con.cursor() as cursor:
                await cursor.execute("""
                    SELECT COUNT(*) FROM workshop_registrations WHERE user_id = ?
                """, (user_id,))
                result = await cursor.fetchone()
                return result[0] > 0  # Если результат больше 0, значит, пользователь зарегистрирован хотя бы на одном мастер-классе
        except Exception as e:
            print(f"Error checking user registration: {e}")
            return False
        

    async def add_response(self, event_id: int, user_id: int, user_name: str, option_id: int):
        try:
            async with self.con.cursor() as cursor:
                await cursor.execute("""
                    INSERT INTO responses (event_id, user_id, user_name, option_id)
                    VALUES (?, ?, ?, ?)
                """, (event_id, user_id, user_name, option_id))
                await self.con.commit()
        except Exception as e:
            print(f"Ошибка при записи ответа: {e}")



        


    async def delete_event(self, event_id):
        async with self.con.cursor() as cursor:
            # Удаляем связанные данные
            await cursor.execute("DELETE FROM responses WHERE event_id = ?", (event_id,))
            await cursor.execute("DELETE FROM event_options WHERE event_id = ?", (event_id,))
            await cursor.execute("DELETE FROM workshops WHERE event_id = ?", (event_id,))
            await cursor.execute("DELETE FROM events WHERE event_id = ?", (event_id,))
            await self.con.commit()


    async def is_user_registered_for_event(self, user_id: int, event_id: int) -> bool:
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


    async def get_workshops_by_event(self, event_id: int):
        async with self.con.cursor() as cursor:
            await cursor.execute(
                "SELECT workshop_id, workshop_name, instructor, max_participants FROM workshops WHERE event_id = ?",
                (event_id,)
            )
            return await cursor.fetchall()



    async def has_user_voted(self, user_id: int, event_id: int) -> bool:
        async with self.con.cursor() as cursor:
            await cursor.execute(
                """
                SELECT 1 FROM responses
                WHERE user_id = ? AND event_id = ?
                """,
                (user_id, event_id)
            )
            return await cursor.fetchone() is not None




    async def get_all_workshops_with_participants(self):
        async with self.con.cursor() as cursor:
            await cursor.execute("""
                SELECT w.workshop_id, w.workshop_name, wr.user_name, wr.group_number
                FROM workshops w
                LEFT JOIN workshop_registrations wr ON w.workshop_id = wr.workshop_id
            """)
            rows = await cursor.fetchall()

            workshops = {}
            for row in rows:
                workshop_id = row[0]
                if workshop_id not in workshops:
                    workshops[workshop_id] = {
                        'workshop_name': row[1],
                        'participants': []
                    }
                if row[2]:
                    workshops[workshop_id]['participants'].append({
                        'name': row[2],
                        'group': row[3]
                    })
            return workshops.values()

        

    async def get_all_workshops_with_participants(self):
        async with self.con.cursor() as cursor:
            await cursor.execute("""
                SELECT w.workshop_id, w.workshop_name
                FROM workshops w
            """)
            rows = await cursor.fetchall()
            return [{"workshop_id": row[0], "workshop_name": row[1]} for row in rows]






    async def get_vote_events(self):
        async with self.con.cursor() as cursor:
            await cursor.execute("SELECT event_id, event_name FROM events WHERE event_type='vote'")
            rows = await cursor.fetchall()
            return [{'event_id': row[0], 'event_name': row[1]} for row in rows]



    async def has_user_voted(self, user_id: int, event_id: int) -> bool:
        async with self.con.cursor() as cursor:
            await cursor.execute(
                """
                SELECT 1 FROM responses
                WHERE user_id = ? AND event_id = ?
                """,
                (user_id, event_id)
            )
            return await cursor.fetchone() is not None



    async def get_vote_results(self, event_id: int):
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


    async def get_workshop_participants(self, workshop_id: int):
        async with self.con.cursor() as cursor:
            await cursor.execute("""
                SELECT wr.user_name, wr.group_number
                FROM workshop_registrations wr
                WHERE wr.workshop_id = ?
            """, (workshop_id,))
            rows = await cursor.fetchall()
            return [{"name": row[0], "group": row[1]} for row in rows]




    async def get_workshops_with_participants(self, event_id):
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

                print(f"DEBUG: Результаты запроса по мастер-классам: {rows}")

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
                print(f"DEBUG: Преобразованные данные мастер-классов: {workshops}")
                return workshops
        except Exception as e:
            print(f"Error in get_workshops_with_participants: {e}")
            return {}



    async def get_participants_by_groups(self, event_id):
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
    
                print(f"DEBUG: Результаты запроса по отрядам: {rows}")
    
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
                print(f"DEBUG: Преобразованные данные по отрядам: {groups}")
                return groups
        except Exception as e:
            print(f"Error in get_participants_by_groups: {e}")
            return {}


