from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Text, ForeignKey, Table
from sqlalchemy.orm import relationship
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String)
    display_name = Column(String)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class AppSettings(Base):
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True)
    value = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)


# Join table: kein eigenes Modell nötig, SQLAlchemy verwaltet die Rows
# über die secondary-Relationship auf Eintrag.tiere automatisch.
eintrag_tiere = Table(
    "eintrag_tiere",
    Base.metadata,
    Column("eintrag_id", Integer, ForeignKey("eintraege.id"), primary_key=True),
    Column("tier_id", Integer, ForeignKey("tiere.id"), primary_key=True),
)


class Tier(Base):
    __tablename__ = "tiere"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    typ = Column(String)
    emoji = Column(String, default="🐴")
    aktiv = Column(Boolean, default=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserModuleAccess(Base):
    __tablename__ = "user_module_access"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    module_key = Column(String, primary_key=True)


class Eintrag(Base):
    __tablename__ = "eintraege"

    id = Column(Integer, primary_key=True, index=True)
    datum = Column(Date, index=True)
    aktivitaet = Column(Text)
    besonderheiten = Column(Text, nullable=True)
    anpassungen = Column(Text, nullable=True)
    anzahl_kinder = Column(Integer, default=0)
    anzahl_jugendliche = Column(Integer, default=0)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # SQLAlchemy verwaltet eintrag_tiere-Rows automatisch beim Setzen dieser Liste
    tiere = relationship("Tier", secondary=eintrag_tiere)
    user = relationship("User", foreign_keys=[user_id])
