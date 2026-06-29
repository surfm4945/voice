"""
Agent tools — all 11 callable functions for the LiveKit agent.
These are pure functions that take a db Session and return strings
the LLM can read and relay to the customer.
"""

import json
from typing import Optional

from sqlalchemy.orm import Session

from database import Conversation, MenuItem, Order, OrderItem, SessionLocal

# ── In-memory cart (per-session) ───────────────────────────────────────────────
# In production, replace with Redis or a session store.

_cart: list[dict] = []
_customer_name: str = ""


def _get_db() -> Session:
    return SessionLocal()


# ── 1. search_menu ─────────────────────────────────────────────────────────────

def search_menu(query: str = "") -> str:
    """Return menu items matching query, grouped by category. Empty query = full menu."""
    db = _get_db()
    try:
        q = db.query(MenuItem).filter(MenuItem.available == True)
        if query.strip():
            q = q.filter(MenuItem.name.ilike(f"%{query}%"))
        items = q.order_by(MenuItem.category, MenuItem.name).all()
        if not items:
            return f"No menu items found for '{query}'."
        grouped: dict[str, list[str]] = {}
        for i in items:
            grouped.setdefault(i.category, []).append(
                f"{i.name} — Rs {i.price:,.0f}"
            )
        lines = []
        for cat, rows in grouped.items():
            lines.append(f"{cat}:")
            lines.extend(f"  • {r}" for r in rows)
        return "\n".join(lines)
    finally:
        db.close()


# ── 2. check_inventory ─────────────────────────────────────────────────────────

def check_inventory(item_name: str) -> str:
    """Check whether an item is in stock and how many units remain."""
    db = _get_db()
    try:
        item = (
            db.query(MenuItem)
            .filter(MenuItem.name.ilike(f"%{item_name}%"), MenuItem.available == True)
            .first()
        )
        if not item:
            return f"'{item_name}' is not on the menu or is unavailable."
        if item.stock <= 0:
            return f"Sorry, {item.name} is currently out of stock."
        return f"{item.name} is available. {item.stock} units in stock."
    finally:
        db.close()


# ── 3. get_price ───────────────────────────────────────────────────────────────

def get_price(item_name: str) -> str:
    """Return the PKR price for a menu item."""
    db = _get_db()
    try:
        item = (
            db.query(MenuItem)
            .filter(MenuItem.name.ilike(f"%{item_name}%"), MenuItem.available == True)
            .first()
        )
        if not item:
            return f"'{item_name}' not found in menu."
        return f"{item.name} costs Rs {item.price:,.0f}."
    finally:
        db.close()


# ── 4. add_to_cart ─────────────────────────────────────────────────────────────

def add_to_cart(item_name: str, quantity: int = 1) -> str:
    """Add an item to the current order cart."""
    global _cart
    if quantity < 1:
        return "Quantity must be at least 1."
    db = _get_db()
    try:
        item = (
            db.query(MenuItem)
            .filter(MenuItem.name.ilike(f"%{item_name}%"), MenuItem.available == True)
            .first()
        )
        if not item:
            return f"'{item_name}' is not available."
        if item.stock < quantity:
            return f"Only {item.stock} units of {item.name} available."
        # Update existing cart entry
        for entry in _cart:
            if entry["id"] == item.id:
                entry["quantity"] += quantity
                subtotal = entry["quantity"] * item.price
                return (
                    f"Updated {item.name} to ×{entry['quantity']}. "
                    f"Subtotal: Rs {subtotal:,.0f}."
                )
        _cart.append({"id": item.id, "name": item.name, "price": item.price, "quantity": quantity})
        return f"Added ×{quantity} {item.name} at Rs {item.price:,.0f} each. Subtotal: Rs {quantity * item.price:,.0f}."
    finally:
        db.close()


# ── 5. remove_from_cart ────────────────────────────────────────────────────────

def remove_from_cart(item_name: str) -> str:
    """Remove an item from the cart entirely."""
    global _cart
    for i, entry in enumerate(_cart):
        if item_name.lower() in entry["name"].lower():
            removed = _cart.pop(i)
            return f"Removed {removed['name']} from your order."
    return f"'{item_name}' was not found in your cart."


# ── 6. update_quantity ─────────────────────────────────────────────────────────

def update_quantity(item_name: str, quantity: int) -> str:
    """Set the quantity of an item already in the cart."""
    global _cart
    if quantity < 1:
        return remove_from_cart(item_name)
    for entry in _cart:
        if item_name.lower() in entry["name"].lower():
            old = entry["quantity"]
            entry["quantity"] = quantity
            subtotal = quantity * entry["price"]
            return (
                f"Updated {entry['name']}: ×{old} → ×{quantity}. "
                f"Subtotal: Rs {subtotal:,.0f}."
            )
    return f"'{item_name}' is not in your cart. Add it first."


# ── 7. get_current_order ───────────────────────────────────────────────────────

def get_current_order() -> str:
    """Return a summary of the current cart."""
    if not _cart:
        return "Your cart is empty."
    lines = [f"  ×{e['quantity']} {e['name']}  —  Rs {e['price'] * e['quantity']:,.0f}" for e in _cart]
    total = sum(e["price"] * e["quantity"] for e in _cart)
    return "Current order:\n" + "\n".join(lines) + f"\n\nTotal: Rs {total:,.0f}"


# ── 8. calculate_total ─────────────────────────────────────────────────────────

def calculate_total() -> str:
    """Calculate and return the cart total in PKR."""
    if not _cart:
        return "Your cart is empty."
    total = sum(e["price"] * e["quantity"] for e in _cart)
    return f"Your total is Rs {total:,.0f}."


# ── 9. confirm_order ───────────────────────────────────────────────────────────

def confirm_order(customer_name: str) -> str:
    """Mark the order as confirmed — call save_order() after this."""
    global _customer_name
    if not _cart:
        return "Cart is empty. Please add items before confirming."
    _customer_name = customer_name.strip()
    total = sum(e["price"] * e["quantity"] for e in _cart)
    order_summary = get_current_order()
    return (
        f"Order confirmed for {_customer_name}!\n"
        f"{order_summary}\n"
        f"Total: Rs {total:,.0f}\n"
        "Saving to database..."
    )


# ── 10. save_order ─────────────────────────────────────────────────────────────

def save_order() -> str:
    """Persist the confirmed order to the database and clear the cart."""
    global _cart, _customer_name
    if not _cart:
        return "Nothing to save — cart is empty."
    total = sum(e["price"] * e["quantity"] for e in _cart)
    db = _get_db()
    try:
        order = Order(customer_name=_customer_name or "Guest", status="confirmed", total=total)
        db.add(order)
        db.flush()
        for entry in _cart:
            db.add(OrderItem(
                order_id=entry["id"] if False else order.id,   # use order.id
                item_name=entry["name"],
                quantity=entry["quantity"],
                price=entry["price"],
            ))
            # Deduct stock
            item = db.query(MenuItem).filter(MenuItem.id == entry["id"]).first()
            if item:
                item.stock = max(0, item.stock - entry["quantity"])
        db.commit()
        order_id = order.id
    except Exception as exc:
        db.rollback()
        return f"Failed to save order: {exc}"
    finally:
        db.close()
    snapshot = list(_cart)
    _cart.clear()
    _customer_name = ""
    lines = [f"  ×{e['quantity']} {e['name']}" for e in snapshot]
    return (
        f"Order #{order_id} saved successfully!\n"
        + "\n".join(lines)
        + f"\nTotal: Rs {total:,.0f}\nStatus: CONFIRMED"
    )


# ── 11. cancel_order ───────────────────────────────────────────────────────────

def cancel_order() -> str:
    """Discard the current cart and reset session."""
    global _cart, _customer_name
    if not _cart and not _customer_name:
        return "No active order to cancel."
    _cart.clear()
    _customer_name = ""
    return "Order cancelled. How can I help you?"


# ── Conversation logging ────────────────────────────────────────────────────────

def log_message(speaker: str, message: str) -> None:
    """Persist a conversation turn to the DB (fire-and-forget)."""
    db = _get_db()
    try:
        db.add(Conversation(speaker=speaker, message=message))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
