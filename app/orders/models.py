"""Request and response schemas for the orders API (also drive the OpenAPI docs at /docs)."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

OrderStatus = Literal["PENDING", "PAID", "PAYMENT_FAILED"]


class OrderItemIn(BaseModel):
    sku: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    quantity: int = Field(ge=1, le=100)
    unit_price_cents: int = Field(gt=0, le=10_000_000)


class OrderCreate(BaseModel):
    customer_id: str = Field(min_length=1, max_length=64)
    currency: Literal["USD", "EUR", "INR"] = "USD"
    items: list[OrderItemIn] = Field(min_length=1, max_length=50)


class OrderItemOut(BaseModel):
    sku: str
    quantity: int
    unit_price_cents: int


class OrderSummary(BaseModel):
    id: UUID
    customer_id: str
    status: OrderStatus
    currency: str
    total_cents: int
    payment_reference: str | None
    created_at: datetime
    updated_at: datetime


class OrderOut(OrderSummary):
    items: list[OrderItemOut]


class OrderListItem(OrderSummary):
    item_count: int


class OrderList(BaseModel):
    count: int
    orders: list[OrderListItem]


class OrderStats(BaseModel):
    total_orders: int
    orders_by_status: dict[str, int]
    paid_revenue_cents: int
