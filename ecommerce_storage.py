import sqlite3
import json
from datetime import datetime, timezone
import logging
from storage import DB_PATH

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Store Management
# ──────────────────────────────────────────────────────────────

def create_store(store_id: str, name: str, phone: str, admin_phone: str, address: str, group_url: str = "") -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            INSERT INTO stores (id, name, phone_number, admin_phone, address, group_url, is_open)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                phone_number=excluded.phone_number,
                admin_phone=excluded.admin_phone,
                address=excluded.address,
                group_url=excluded.group_url
        """, (store_id, name, phone, admin_phone, address, group_url))
        conn.commit()
    finally:
        conn.close()

def get_store(store_id: str) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM stores WHERE id = ? OR name = ?", (store_id, store_id)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def get_store_by_admin(admin_id: str) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    clean_id = admin_id.split('@')[0] if admin_id else ""
    try:
        row = conn.execute("SELECT * FROM stores WHERE admin_phone = ? OR phone_number = ?", (clean_id, clean_id)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def get_all_stores() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM stores").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def set_store_open(store_id: str, is_open: bool) -> bool:
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.execute("UPDATE stores SET is_open = ? WHERE id = ? OR name = ?", (int(is_open), store_id, store_id))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()

def follow_store(store_id: str, user_id: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("INSERT OR IGNORE INTO store_followers (store_id, user_id) VALUES (?, ?)", (store_id, user_id))
        conn.commit()
    finally:
        conn.close()

def unfollow_store(store_id: str, user_id: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM store_followers WHERE store_id = ? AND user_id = ?", (store_id, user_id))
        conn.commit()
    finally:
        conn.close()

def get_store_followers(store_id: str) -> list[str]:
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute("SELECT user_id FROM store_followers WHERE store_id = ?", (store_id,)).fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()

# ──────────────────────────────────────────────────────────────
# Product Management
# ──────────────────────────────────────────────────────────────

def get_products(store_id: str = None) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        if store_id:
            rows = conn.execute("SELECT * FROM products WHERE store_id = ?", (store_id,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM products").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def search_products(keyword: str) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        query = f"%{keyword}%"
        rows = conn.execute("SELECT * FROM products WHERE name LIKE ? OR description LIKE ?", (query, query)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_product(product_id: str) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM products WHERE id = ? OR name = ?", (product_id, product_id)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def replace_store_products(store_id: str, products: list[dict]) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        # Delete old products for the store
        conn.execute("DELETE FROM products WHERE store_id = ?", (store_id,))
        for p in products:
            conn.execute("""
                INSERT INTO products (id, store_id, name, description, image_url, price, stock)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (p['id'], store_id, p['name'], p.get('description', ''), p.get('image_url', ''), p.get('price', 0), p.get('stock', 0)))
        conn.commit()
    finally:
        conn.close()

# ──────────────────────────────────────────────────────────────
# Cart Management
# ──────────────────────────────────────────────────────────────

def add_to_cart(user_id: str, store_id: str, product_id: str, qty: int) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            INSERT INTO carts (user_id, store_id, product_id, qty)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, product_id) DO UPDATE SET qty = qty + excluded.qty
        """, (user_id, store_id, product_id, qty))
        conn.commit()
    finally:
        conn.close()

def remove_from_cart(user_id: str, product_id: str, qty: int = None) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        if qty is None:
            conn.execute("DELETE FROM carts WHERE user_id = ? AND product_id = ?", (user_id, product_id))
        else:
            conn.execute("""
                UPDATE carts SET qty = qty - ? 
                WHERE user_id = ? AND product_id = ?
            """, (qty, user_id, product_id))
            # Clean up zero or negative
            conn.execute("DELETE FROM carts WHERE user_id = ? AND qty <= 0", (user_id,))
        conn.commit()
    finally:
        conn.close()

def clear_cart(user_id: str, store_id: str = None) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        if store_id:
            conn.execute("DELETE FROM carts WHERE user_id = ? AND store_id = ?", (user_id, store_id))
        else:
            conn.execute("DELETE FROM carts WHERE user_id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()

def get_cart(user_id: str, store_id: str = None) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        if store_id:
            rows = conn.execute("""
                SELECT c.*, p.name, p.price, p.stock 
                FROM carts c 
                JOIN products p ON c.product_id = p.id 
                WHERE c.user_id = ? AND c.store_id = ?
            """, (user_id, store_id)).fetchall()
        else:
            rows = conn.execute("""
                SELECT c.*, p.name, p.price, p.stock 
                FROM carts c 
                JOIN products p ON c.product_id = p.id 
                WHERE c.user_id = ?
            """, (user_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

# ──────────────────────────────────────────────────────────────
# Order Types & Payment Methods
# ──────────────────────────────────────────────────────────────

def get_order_types(active_only: bool = True) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        if active_only:
            rows = conn.execute("SELECT * FROM order_types WHERE is_active = 1").fetchall()
        else:
            rows = conn.execute("SELECT * FROM order_types").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def set_order_type_status(name: str, is_active: bool) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            INSERT INTO order_types (id, name, is_active) 
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET is_active = excluded.is_active
        """, (name.lower(), name, int(is_active)))
        conn.commit()
    finally:
        conn.close()

def get_payment_methods(active_only: bool = True) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        if active_only:
            rows = conn.execute("SELECT * FROM payment_methods WHERE is_active = 1").fetchall()
        else:
            rows = conn.execute("SELECT * FROM payment_methods").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_payment_method(name: str) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM payment_methods WHERE id = ? OR name = ?", (name.lower(), name)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def set_payment_method_status(name: str, is_active: bool) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            INSERT INTO payment_methods (id, name, is_active) 
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET is_active = excluded.is_active
        """, (name.lower(), name, int(is_active)))
        conn.commit()
    finally:
        conn.close()

def set_payment_method_image(name: str, image_url: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            INSERT INTO payment_methods (id, name, is_active, image_url) 
            VALUES (?, ?, 1, ?)
            ON CONFLICT(id) DO UPDATE SET image_url = excluded.image_url
        """, (name.lower(), name, image_url))
        conn.commit()
    finally:
        conn.close()

# ──────────────────────────────────────────────────────────────
# Orders
# ──────────────────────────────────────────────────────────────

def create_order(order_id: str, user_id: str, store_id: str, order_type_id: str, payment_method_id: str, items: list[dict]) -> dict:
    conn = sqlite3.connect(DB_PATH)
    now = datetime.now(timezone.utc).isoformat()
    # Expire in 10 minutes for dev
    expires_at = datetime.fromtimestamp(datetime.now(timezone.utc).timestamp() + 600, timezone.utc).isoformat()
    total_amount = sum(item['price'] * item['qty'] for item in items)
    
    try:
        conn.execute("""
            INSERT INTO orders (id, user_id, store_id, order_type_id, payment_method_id, status, total_amount, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?)
        """, (order_id, user_id, store_id, order_type_id, payment_method_id, total_amount, now, expires_at))
        
        for item in items:
            conn.execute("""
                INSERT INTO order_items (order_id, product_id, qty, price)
                VALUES (?, ?, ?, ?)
            """, (order_id, item['product_id'], item['qty'], item['price']))
            
            # Decrease stock
            conn.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (item['qty'], item['product_id']))
            
        conn.commit()
        return {"order_id": order_id, "total_amount": total_amount, "expires_at": expires_at}
    finally:
        conn.close()

def get_order(order_id: str) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if not row:
            return None
        
        order = dict(row)
        items = conn.execute("""
            SELECT oi.*, p.name 
            FROM order_items oi 
            JOIN products p ON oi.product_id = p.id 
            WHERE oi.order_id = ?
        """, (order_id,)).fetchall()
        order['items'] = [dict(i) for i in items]
        return order
    finally:
        conn.close()

def get_orders(user_id: str) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def update_order_status(order_id: str, status: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    try:
        if status == 'cancel':
            # Restore stock
            items = conn.execute("SELECT product_id, qty FROM order_items WHERE order_id = ?", (order_id,)).fetchall()
            for item in items:
                conn.execute("UPDATE products SET stock = stock + ? WHERE id = ?", (item[1], item[0]))
                
        cursor = conn.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()
