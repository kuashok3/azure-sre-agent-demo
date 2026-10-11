-- Orders schema. Money is stored as integer cents to avoid floating-point rounding.
CREATE TABLE IF NOT EXISTS orders (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id       VARCHAR(64)  NOT NULL,
    status            VARCHAR(20)  NOT NULL DEFAULT 'PENDING'
                      CHECK (status IN ('PENDING', 'PAID', 'PAYMENT_FAILED')),
    currency          CHAR(3)      NOT NULL,
    total_cents       BIGINT       NOT NULL CHECK (total_cents >= 0),
    payment_reference VARCHAR(64),
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS order_items (
    id               BIGSERIAL PRIMARY KEY,
    order_id         UUID        NOT NULL REFERENCES orders (id) ON DELETE CASCADE,
    sku              VARCHAR(64) NOT NULL,
    quantity         INT         NOT NULL CHECK (quantity BETWEEN 1 AND 100),
    unit_price_cents BIGINT      NOT NULL CHECK (unit_price_cents > 0)
);

CREATE INDEX IF NOT EXISTS ix_order_items_order_id ON order_items (order_id);
CREATE INDEX IF NOT EXISTS ix_orders_created_at ON orders (created_at DESC);
