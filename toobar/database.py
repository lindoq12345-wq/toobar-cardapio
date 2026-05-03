import sqlite3
from pathlib import Path


MENU_SEED = [
    ("Bolinho de costela", "Costela desfiada, queijo meia cura e molho da casa.", 34.90, "petiscos", "/api/assets/menu/petiscos.svg"),
    ("Batata brava", "Fritas crocantes, paprika, aioli e cheiro verde.", 29.90, "petiscos", "/api/assets/menu/petiscos.svg"),
    ("Isca de peixe", "Tirinhas empanadas com limao siciliano e tartaro.", 42.90, "petiscos", "/api/assets/menu/petiscos.svg"),
    ("Burger Toobar", "Blend 160g, queijo, bacon, picles e maionese defumada.", 39.90, "pratos", "/api/assets/menu/pratos.svg"),
    ("Parmegiana da casa", "File alto, molho rustico, mussarela e arroz branco.", 54.90, "pratos", "/api/assets/menu/pratos.svg"),
    ("Caipirinha tropical", "Limao, maracuja, cachaca premium e acucar na medida.", 24.90, "drinks", "/api/assets/menu/drinks.svg"),
    ("Gin botanico", "Gin, tonica, alecrim, zimbro e rodela de laranja.", 32.90, "drinks", "/api/assets/menu/drinks.svg"),
    ("Chopp pilsen", "Caneca 400ml, colarinho cremoso e temperatura ideal.", 13.90, "bebidas", "/api/assets/menu/bebidas.svg"),
]


def connect(db_path: str | Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'customer',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS menu_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            price REAL NOT NULL CHECK (price >= 0),
            category TEXT NOT NULL,
            image_url TEXT NOT NULL,
            available INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            table_label TEXT NOT NULL,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'received',
            total REAL NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            menu_item_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL CHECK (quantity > 0),
            unit_price REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
            FOREIGN KEY (menu_item_id) REFERENCES menu_items(id)
        );
        """
    )
    conn.commit()


def seed_menu(conn: sqlite3.Connection) -> None:
    total = conn.execute("SELECT COUNT(*) FROM menu_items").fetchone()[0]
    if total:
        conn.executemany(
            "UPDATE menu_items SET image_url = ? WHERE category = ?",
            [
                ("/api/assets/menu/petiscos.svg", "petiscos"),
                ("/api/assets/menu/pratos.svg", "pratos"),
                ("/api/assets/menu/drinks.svg", "drinks"),
                ("/api/assets/menu/bebidas.svg", "bebidas"),
            ],
        )
        conn.commit()
        return

    conn.executemany(
        """
        INSERT INTO menu_items (name, description, price, category, image_url)
        VALUES (?, ?, ?, ?, ?)
        """,
        MENU_SEED,
    )
    conn.commit()
