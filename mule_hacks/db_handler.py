import sqlite3 as sql
import uuid

PATH = "server.db"

def init_db():
    with sql.connect(PATH) as c:
        c.execute("PRAGMA foreign_keys = ON")

        c.executescript("""
        -- Users
        CREATE TABLE IF NOT EXISTS userbase (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            password TEXT,
            name TEXT,
            linkedin TEXT,
            comfort_level INTEGER
        );

        CREATE TABLE IF NOT EXISTS interestbase (
            interest_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            text TEXT,
            FOREIGN KEY (user_id) REFERENCES userbase(user_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS moralbase (
            moral_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            question1 INTEGER,
            question2 INTEGER,
            question3 INTEGER,
            question4 INTEGER,
            question5 INTEGER,
            question6 INTEGER,
            question7 INTEGER,
            FOREIGN KEY (user_id) REFERENCES userbase(user_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS connectionbase (
            user_id INT PRIMARY KEY,
            score FLOAT,
            FOREIGN KEY (other_id) REFERENCES userbase(user_id)
        );

        -- Polls
        CREATE TABLE IF NOT EXISTS pollbase (
            poll_id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt TEXT,
            option1 TEXT,
            option2 TEXT,
            option3 TEXT,
            option4 TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            anonymous_percent INTEGER
        );

        CREATE TABLE IF NOT EXISTS pollresponsebase (
            response_id INTEGER PRIMARY KEY AUTOINCREMENT,
            poll_id INTEGER NOT NULL,
            sender_id INTEGER,
            choice INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (poll_id) REFERENCES pollbase(poll_id) ON DELETE CASCADE,
            FOREIGN KEY (sender_id) REFERENCES userbase(user_id)
        );

        -- DMs
        CREATE TABLE IF NOT EXISTS directthreadbase (
            thread_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER,
            receiver_id INTEGER,
            FOREIGN KEY (sender_id) REFERENCES userbase(user_id),
            FOREIGN KEY (receiver_id) REFERENCES userbase(user_id)
        );

        CREATE TABLE IF NOT EXISTS directmessagebase (
            msg_id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            sender_id INTEGER,
            content TEXT,
            FOREIGN KEY (thread_id) REFERENCES directthreadbase(thread_id) ON DELETE CASCADE,
            FOREIGN KEY (sender_id) REFERENCES userbase(user_id)
        );

        -- Daily Qs
        CREATE TABLE IF NOT EXISTS dailyquestionbase (
            thread_id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS dailyresponsebase (
            response_id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            content TEXT,
            sender_id INTEGER,
            FOREIGN KEY (thread_id) REFERENCES dailyquestionbase(thread_id) ON DELETE CASCADE,
            FOREIGN KEY (sender_id) REFERENCES userbase(user_id)
        );

        -- Forum threads
        CREATE TABLE IF NOT EXISTS threadbase (
            thread_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            body TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS threadmessagebase (
            response_id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id INTEGER NOT NULL,
            content TEXT,
            sender_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (thread_id) REFERENCES threadbase(thread_id) ON DELETE CASCADE,
            FOREIGN KEY (sender_id) REFERENCES userbase(user_id)
        );
        """)

def create_user(pswd, name, linkedin, clevel):
    with sql.connect(PATH) as c:
        _uuid = uuid.uuid4() 
        c.execute("INSERT INTO users (user_id, password, name, linkedin, confort_level) VALUE (?, ?, ?, ?, ?)",
                  (_uuid, pswd, name, linkedin, clevel))

def get_username(_uuid):
    with sql.connect(PATH) as c:
        c.execute("")

def get_connections(_uuid, threshold):
    with sql.connect(PATH) as c:
        cursor = c.execute(
            "SELECT other_id FROM connectionbase WHERE user_id = ? ORDER BY score ASC",
            (_uuid, ))
        return cursor.fetchall()

