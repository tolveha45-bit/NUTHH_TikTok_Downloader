import sqlite3
from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc).isoformat()


class Database:

    def __init__(self, path):

        self.path = path

        import os
        os.makedirs(
            os.path.dirname(path) or ".",
            exist_ok=True
        )

        self.init()

    def connect(self):

        return sqlite3.connect(self.path)

    def init(self):

        with self.connect() as c:

            c.executescript("""

            CREATE TABLE IF NOT EXISTS users(
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                downloads INTEGER DEFAULT 0,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS keys(
                key TEXT PRIMARY KEY,
                expires_at TEXT,
                max_downloads INTEGER DEFAULT 0,
                used_downloads INTEGER DEFAULT 0,
                max_users INTEGER DEFAULT 1,
                active INTEGER DEFAULT 1,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS activations(
                user_id INTEGER PRIMARY KEY,
                key TEXT,
                activated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS downloads(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                url TEXT,
                media_type TEXT,
                status TEXT,
                created_at TEXT
            );

            """)

    def add_user(self, uid, username):

        with self.connect() as c:

            c.execute(
                """
                INSERT INTO users(
                    user_id,
                    username,
                    created_at
                )
                VALUES(?,?,?)

                ON CONFLICT(user_id)
                DO UPDATE SET username=?
                """,
                (
                    uid,
                    username or "",
                    now(),
                    username or ""
                )
            )

    def get_activation(self, uid):

        with self.connect() as c:

            return c.execute(
                """
                SELECT key
                FROM activations
                WHERE user_id=?
                """,
                (uid,)
            ).fetchone()

    def create_key(
        self,
        key,
        expires_at,
        max_downloads,
        max_users
    ):

        with self.connect() as c:

            c.execute(
                """
                INSERT INTO keys(
                    key,
                    expires_at,
                    max_downloads,
                    max_users,
                    created_at
                )
                VALUES(?,?,?,?,?)
                """,
                (
                    key,
                    expires_at,
                    max_downloads,
                    max_users,
                    now()
                )
            )

    def activate_key(self, uid, key):

        with self.connect() as c:

            row = c.execute(
                """
                SELECT
                    key,
                    expires_at,
                    max_downloads,
                    used_downloads,
                    max_users,
                    active

                FROM keys

                WHERE key=?
                """,
                (key,)
            ).fetchone()

            if not row:

                return False, "❌ Invalid key."

            (
                k,
                exp,
                max_dl,
                used,
                max_users,
                active
            ) = row

            if not active:

                return False, "❌ This key is disabled."

            if exp:

                if datetime.fromisoformat(exp) <= datetime.now(
                    timezone.utc
                ):

                    return False, "❌ This key has expired."

            count = c.execute(
                """
                SELECT COUNT(*)
                FROM activations
                WHERE key=?
                """,
                (key,)
            ).fetchone()[0]

            existing = c.execute(
                """
                SELECT key
                FROM activations
                WHERE user_id=?
                """,
                (uid,)
            ).fetchone()

            if not existing and count >= max_users:

                return False, (
                    "❌ This key reached "
                    "its user limit."
                )

            c.execute(
                """
                INSERT INTO activations(
                    user_id,
                    key,
                    activated_at
                )
                VALUES(?,?,?)

                ON CONFLICT(user_id)

                DO UPDATE SET
                    key=?,
                    activated_at=?
                """,
                (
                    uid,
                    key,
                    now(),
                    key,
                    now()
                )
            )

            return True, "✅ Key activated successfully!"

    def key_status(self, uid):

        row = self.get_activation(uid)

        if not row:
            return None

        with self.connect() as c:

            return c.execute(
                """
                SELECT
                    k.key,
                    k.expires_at,
                    k.max_downloads,
                    k.used_downloads,
                    k.active

                FROM keys k

                WHERE k.key=?
                """,
                (row[0],)
            ).fetchone()

    def consume_download(self, uid):

        status = self.key_status(uid)

        if not status:

            return (
                False,
                "🔐 Please activate an access key first."
            )

        (
            key,
            exp,
            max_dl,
            used,
            active
        ) = status

        if not active:

            return (
                False,
                "❌ Your key is disabled."
            )

        if exp:

            if datetime.fromisoformat(exp) <= datetime.now(
                timezone.utc
            ):

                return (
                    False,
                    "❌ Your key has expired."
                )

        if max_dl > 0 and used >= max_dl:

            return (
                False,
                "❌ Your download limit has been reached."
            )

        with self.connect() as c:

            c.execute(
                """
                UPDATE keys

                SET used_downloads =
                    used_downloads + 1

                WHERE key=?
                """,
                (key,)
            )

            c.execute(
                """
                UPDATE users

                SET downloads =
                    downloads + 1

                WHERE user_id=?
                """,
                (uid,)
            )

        return True, "OK"

    def log_download(
        self,
        uid,
        url,
        media_type,
        status
    ):

        with self.connect() as c:

            c.execute(
                """
                INSERT INTO downloads(
                    user_id,
                    url,
                    media_type,
                    status,
                    created_at
                )
                VALUES(?,?,?,?,?)
                """,
                (
                    uid,
                    url,
                    media_type,
                    status,
                    now()
                )
            )

    def stats(self):

        with self.connect() as c:

            users = c.execute(
                """
                SELECT COUNT(*)
                FROM users
                """
            ).fetchone()[0]

            downloads = c.execute(
                """
                SELECT COUNT(*)
                FROM downloads
                WHERE status='success'
                """
            ).fetchone()[0]

            keys = c.execute(
                """
                SELECT COUNT(*)
                FROM keys
                """
            ).fetchone()[0]

            return users, downloads, keys
