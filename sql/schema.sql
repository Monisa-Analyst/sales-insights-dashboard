-- SQL Schema Definition for MySQL / PostgreSQL
-- Normalized Star Schema for E-Commerce Sales Analytics

-- 1. Customers Dimension Table
CREATE TABLE IF NOT EXISTS customers (
    customer_id VARCHAR(50) PRIMARY KEY,
    customer_name VARCHAR(255) NOT NULL,
    segment VARCHAR(50) NOT NULL
);

-- 2. Products Dimension Table
CREATE TABLE IF NOT EXISTS products (
    product_id VARCHAR(50) PRIMARY KEY,
    product_name VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    sub_category VARCHAR(100) NOT NULL
);

-- 3. Locations Dimension Table
CREATE TABLE IF NOT EXISTS locations (
    location_id SERIAL PRIMARY KEY, -- or AUTO_INCREMENT in MySQL
    city VARCHAR(100) NOT NULL,
    state VARCHAR(100),
    country VARCHAR(100) NOT NULL,
    postal_code VARCHAR(20),
    market VARCHAR(50) NOT NULL,
    region VARCHAR(50) NOT NULL
);

-- 4. Orders Dimension Table
CREATE TABLE IF NOT EXISTS orders (
    order_id VARCHAR(50) PRIMARY KEY,
    order_date DATE NOT NULL,
    ship_date DATE NOT NULL,
    ship_mode VARCHAR(50) NOT NULL,
    customer_id VARCHAR(50) REFERENCES customers(customer_id) ON DELETE CASCADE,
    location_id INT REFERENCES locations(location_id) ON DELETE RESTRICT,
    shipping_cost DECIMAL(10, 2) DEFAULT 0.00,
    order_priority VARCHAR(20) NOT NULL
);

-- 5. Order Items Fact Table
CREATE TABLE IF NOT EXISTS order_items (
    order_item_id SERIAL PRIMARY KEY, -- or AUTO_INCREMENT in MySQL
    order_id VARCHAR(50) REFERENCES orders(order_id) ON DELETE CASCADE,
    product_id VARCHAR(50) REFERENCES products(product_id) ON DELETE RESTRICT,
    sales DECIMAL(12, 2) NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    discount DECIMAL(4, 2) DEFAULT 0.00,
    profit DECIMAL(12, 2) NOT NULL
);

-- Create Indexes for Query Performance Optimization
CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders (customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_location ON orders (location_id);
CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items (order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product ON order_items (product_id);
CREATE INDEX IF NOT EXISTS idx_orders_date ON orders (order_date);
