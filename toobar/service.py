from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .database import connect, migrate, seed_menu
from .security import hash_password, new_token, verify_password


class AppError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


class ToobarService:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        with self.connection() as conn:
            migrate(conn)
            seed_menu(conn)

    @contextmanager
    def connection(self):
        conn = connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()

    def register(self, name: str, email: str, password: str) -> dict[str, Any]:
        name = (name or "").strip()
        email = (email or "").strip().lower()
        if not name:
            raise AppError("Informe seu nome.")
        if "@" not in email:
            raise AppError("Informe um email valido.")

        try:
            password_hash = hash_password(password)
            with self.connection() as conn:
                cur = conn.execute(
                    "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                    (name, email, password_hash),
                )
                conn.commit()
                user = {"id": cur.lastrowid, "name": name, "email": email, "role": "customer"}
        except sqlite3.IntegrityError as exc:
            raise AppError("Esse email ja esta cadastrado.", 409) from exc

        token = self.create_session(user["id"])
        return {"user": user, "token": token}

    def login(self, email: str, password: str) -> dict[str, Any]:
        email = (email or "").strip().lower()
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not row or not verify_password(password or "", row["password_hash"]):
            raise AppError("Email ou senha invalidos.", 401)

        user = self.public_user(row)
        token = self.create_session(user["id"])
        return {"user": user, "token": token}

    def logout(self, token: str | None) -> None:
        if not token:
            return
        with self.connection() as conn:
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.commit()

    def create_session(self, user_id: int) -> str:
        token = new_token()
        expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
                (token, user_id, expires_at),
            )
            conn.commit()
        return token

    def current_user(self, token: str | None) -> dict[str, Any] | None:
        if not token:
            return None
        now = datetime.now(timezone.utc).isoformat()
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT users.* FROM sessions
                JOIN users ON users.id = sessions.user_id
                WHERE sessions.token = ? AND sessions.expires_at > ?
                """,
                (token, now),
            ).fetchone()
        return self.public_user(row) if row else None

    def require_user(self, token: str | None) -> dict[str, Any]:
        user = self.current_user(token)
        if not user:
            raise AppError("Autenticacao obrigatoria.", 401)
        return user

    def menu(self, category: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM menu_items WHERE available = 1"
        params: list[Any] = []
        if category and category != "todos":
            sql += " AND category = ?"
            params.append(category)
        sql += " ORDER BY category, name"

        with self.connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def create_order(self, token: str | None, payload: dict[str, Any]) -> dict[str, Any]:
        user = self.require_user(token)
        table_label = (payload.get("table_label") or payload.get("table") or "").strip()
        notes = (payload.get("notes") or "").strip()
        raw_items = payload.get("items") or []

        if not table_label:
            raise AppError("Informe mesa ou endereco.")
        if not isinstance(raw_items, list) or not raw_items:
            raise AppError("Inclua pelo menos um item no pedido.")

        quantities: dict[int, int] = {}
        for entry in raw_items:
            try:
                item_id = int(entry["menu_item_id"])
                qty = int(entry["quantity"])
            except (KeyError, TypeError, ValueError) as exc:
                raise AppError("Item de pedido invalido.") from exc
            if qty <= 0:
                raise AppError("A quantidade precisa ser maior que zero.")
            quantities[item_id] = quantities.get(item_id, 0) + qty

        with self.connection() as conn:
            placeholders = ",".join("?" for _ in quantities)
            rows = conn.execute(
                f"SELECT * FROM menu_items WHERE available = 1 AND id IN ({placeholders})",
                tuple(quantities),
            ).fetchall()
            if len(rows) != len(quantities):
                raise AppError("Um ou mais itens nao estao disponiveis.")

            total = round(sum(row["price"] * quantities[row["id"]] for row in rows), 2)
            cur = conn.execute(
                """
                INSERT INTO orders (user_id, table_label, notes, total)
                VALUES (?, ?, ?, ?)
                """,
                (user["id"], table_label, notes, total),
            )
            order_id = cur.lastrowid
            conn.executemany(
                """
                INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price)
                VALUES (?, ?, ?, ?)
                """,
                [(order_id, row["id"], quantities[row["id"]], row["price"]) for row in rows],
            )
            conn.commit()

        return self.order_by_id(token, order_id)

    def orders_for_user(self, token: str | None) -> list[dict[str, Any]]:
        user = self.require_user(token)
        with self.connection() as conn:
            if user["role"] == "admin":
                rows = conn.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC",
                    (user["id"],),
                ).fetchall()
        return [self.order_by_id(token, row["id"]) for row in rows]

    def order_by_id(self, token: str | None, order_id: int) -> dict[str, Any]:
        user = self.require_user(token)
        with self.connection() as conn:
            order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
            if not order:
                raise AppError("Pedido nao encontrado.", 404)
            if user["role"] != "admin" and order["user_id"] != user["id"]:
                raise AppError("Pedido nao encontrado.", 404)
            items = conn.execute(
                """
                SELECT order_items.quantity, order_items.unit_price, menu_items.name
                FROM order_items
                JOIN menu_items ON menu_items.id = order_items.menu_item_id
                WHERE order_items.order_id = ?
                """,
                (order_id,),
            ).fetchall()

        data = dict(order)
        data["items"] = [dict(item) for item in items]
        return data

    @staticmethod
    def public_user(row: sqlite3.Row | None) -> dict[str, Any]:
        if row is None:
            raise AppError("Usuario nao encontrado.", 404)
        return {"id": row["id"], "name": row["name"], "email": row["email"], "role": row["role"]}
