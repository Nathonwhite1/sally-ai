from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, DateTime, ForeignKey, JSON, Text
from sqlalchemy.sql import func

class Base(DeclarativeBase):
    pass

class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)

class Lead(Base):
    __tablename__ = "leads"
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))

    status: Mapped[str] = mapped_column(String(40), default="new")
    project_type: Mapped[str | None] = mapped_column(String(40), nullable=True)

    address: Mapped[str | None] = mapped_column(String(200), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    timeline: Mapped[str | None] = mapped_column(String(200), nullable=True)

    occupied: Mapped[bool | None] = mapped_column(nullable=True)
    access_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    intake_stage: Mapped[str] = mapped_column(String(40), default="stage1")
    intake_data: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"))
    direction: Mapped[str] = mapped_column(String(10))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Proposal(Base):
    __tablename__ = "proposals"
    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"))
    total_price: Mapped[int] = mapped_column(default=0)
    scope_text: Mapped[str] = mapped_column(Text)
    extras_text: Mapped[str] = mapped_column(Text)
    payment_text: Mapped[str] = mapped_column(Text)
    warranty_text: Mapped[str] = mapped_column(Text)
    pdf_path: Mapped[str | None] = mapped_column(String(400), nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
