"""
SQLAlchemy models and database helpers.
Tables: menu, orders, order_items, conversation
"""

import os
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, String, create_engine, text,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///restaurant.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


# ── Models ─────────────────────────────────────────────────────────────────────

class MenuItem(Base):
    __tablename__ = "menu"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(120), nullable=False)
    category    = Column(String(60))
    description = Column(String(255))
    price       = Column(Float, nullable=False)   # PKR
    stock       = Column(Integer, default=100)
    available   = Column(Boolean, default=True)


class Order(Base):
    __tablename__ = "orders"

    id            = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String(120))
    status        = Column(String(30), default="pending")   # pending | confirmed | cancelled
    total         = Column(Float, default=0.0)
    created_at    = Column(DateTime, default=datetime.utcnow)


class OrderItem(Base):
    __tablename__ = "order_items"

    id        = Column(Integer, primary_key=True, index=True)
    order_id  = Column(Integer, ForeignKey("orders.id"), nullable=False)
    item_name = Column(String(120), nullable=False)
    quantity  = Column(Integer, nullable=False)
    price     = Column(Float, nullable=False)   # unit price PKR


class Conversation(Base):
    __tablename__ = "conversation"

    id        = Column(Integer, primary_key=True, index=True)
    speaker   = Column(String(30))   # "agent" | "customer"
    message   = Column(String(2000))
    timestamp = Column(DateTime, default=datetime.utcnow)


# ── DB lifecycle ───────────────────────────────────────────────────────────────

def init_db() -> None:
    """Create all tables and seed menu if empty."""
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        if db.query(MenuItem).count() == 0:
            _seed_menu(db)


def get_db() -> Session:
    """Dependency / context-manager for a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Seed data (PKR prices) ─────────────────────────────────────────────────────

_SEED: list[dict] = [
    # Burgers
    dict(name="Zinger Burger",        category="Burgers",  price=690,  stock=80,  description="Crispy fried chicken fillet with coleslaw"),
    dict(name="Zinger Burger Large",  category="Burgers",  price=850,  stock=60,  description="Large crispy chicken fillet — meal size"),
    dict(name="Classic Beef Burger",  category="Burgers",  price=750,  stock=70,  description="Juicy beef patty with lettuce, tomato, cheese"),
    dict(name="Double Beef Burger",   category="Burgers",  price=990,  stock=50,  description="Double beef patty with special sauce"),
    dict(name="Veggie Burger",        category="Burgers",  price=550,  stock=40,  description="Grilled vegetable patty with avocado"),

    # Meals (with fries + drink)
    dict(name="Zinger Meal",          category="Meals",    price=1190, stock=60,  description="Zinger Burger + Fries + Drink"),
    dict(name="Beef Burger Meal",     category="Meals",    price=1290, stock=50,  description="Classic Beef Burger + Fries + Drink"),
    dict(name="Family Box",           category="Meals",    price=3500, stock=20,  description="4 Zingers + 2 large Fries + 4 Drinks"),

    # Sides
    dict(name="French Fries Regular", category="Sides",    price=290,  stock=150, description="Crispy golden fries — regular"),
    dict(name="French Fries Large",   category="Sides",    price=390,  stock=120, description="Crispy golden fries — large"),
    dict(name="Onion Rings",          category="Sides",    price=350,  stock=80,  description="Beer-battered onion rings"),
    dict(name="Coleslaw",             category="Sides",    price=190,  stock=100, description="Creamy house coleslaw"),

    # Drinks
    dict(name="Pepsi Regular",        category="Drinks",   price=130,  stock=200, description="Pepsi — 330 ml"),
    dict(name="Pepsi Large",          category="Drinks",   price=190,  stock=150, description="Pepsi — 500 ml"),
    dict(name="7UP Regular",          category="Drinks",   price=130,  stock=200, description="7UP — 330 ml"),
    dict(name="Mineral Water",        category="Drinks",   price=80,   stock=300, description="500 ml mineral water"),
    dict(name="Chocolate Shake",      category="Drinks",   price=390,  stock=60,  description="Rich chocolate milkshake"),
    dict(name="Vanilla Shake",        category="Drinks",   price=350,  stock=60,  description="Creamy vanilla milkshake"),

    # Desserts
    dict(name="Chocolate Cake Slice", category="Desserts", price=390,  stock=30,  description="Rich double-chocolate layer cake"),
    dict(name="Brownie",              category="Desserts", price=290,  stock=40,  description="Warm chocolate brownie"),
    dict(name="Soft Serve",           category="Desserts", price=180,  stock=80,  description="Vanilla soft-serve cone"),
]


def _seed_menu(db: Session) -> None:
    items = [MenuItem(**row) for row in _SEED]
    db.add_all(items)
    db.commit()
    print(f"[DB] Seeded {len(items)} menu items.")
