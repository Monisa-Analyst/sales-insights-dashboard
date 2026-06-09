-- Business Analysis Queries for Sales Analytics
-- Using Joins, CTEs, and Window Functions

-- 1. Top 10 Customers by Total Sales and Profit
-- Demonstrates: JOINS, Aggregation, and ORDER BY
SELECT 
    c.customer_id,
    c.customer_name,
    c.segment,
    COUNT(DISTINCT o.order_id) AS total_orders,
    ROUND(SUM(oi.sales), 2) AS total_sales,
    ROUND(SUM(oi.profit), 2) AS total_profit,
    ROUND((SUM(oi.profit) / SUM(oi.sales)) * 100, 2) AS profit_margin_pct
FROM customers c
INNER JOIN orders o ON c.customer_id = o.customer_id
INNER JOIN order_items oi ON o.order_id = oi.order_id
GROUP BY c.customer_id, c.customer_name, c.segment
ORDER BY total_sales DESC
LIMIT 10;


-- 2. Monthly Sales Performance & Running Totals
-- Demonstrates: Substring formatting, Window Functions (SUM OVER)
WITH MonthlySales AS (
    SELECT 
        SUBSTR(o.order_date, 1, 7) AS sales_month,
        ROUND(SUM(oi.sales), 2) AS monthly_sales,
        ROUND(SUM(oi.profit), 2) AS monthly_profit,
        SUM(oi.quantity) AS items_sold
    FROM orders o
    INNER JOIN order_items oi ON o.order_id = oi.order_id
    GROUP BY SUBSTR(o.order_date, 1, 7)
)
SELECT 
    sales_month,
    monthly_sales,
    monthly_profit,
    items_sold,
    -- Running total of sales using Window Function
    ROUND(SUM(monthly_sales) OVER (ORDER BY sales_month), 2) AS running_total_sales
FROM MonthlySales
ORDER BY sales_month;


-- 3. Top 10 Best-Selling Products
-- Demonstrates: JOINS, multi-level aggregations
SELECT 
    p.product_id,
    p.product_name,
    p.category,
    p.sub_category,
    SUM(oi.quantity) AS total_quantity_sold,
    ROUND(SUM(oi.sales), 2) AS total_sales,
    ROUND(SUM(oi.profit), 2) AS total_profit
FROM products p
INNER JOIN order_items oi ON p.product_id = oi.product_id
GROUP BY p.product_id, p.product_name, p.category, p.sub_category
ORDER BY total_quantity_sold DESC
LIMIT 10;


-- 4. Revenue Growth Month-over-Month (MoM %)
-- Demonstrates: CTEs, Window Functions (LAG)
WITH MonthlyRevenue AS (
    SELECT 
        SUBSTR(o.order_date, 1, 7) AS revenue_month,
        SUM(oi.sales) AS monthly_sales
    FROM orders o
    INNER JOIN order_items oi ON o.order_id = oi.order_id
    GROUP BY SUBSTR(o.order_date, 1, 7)
),
RevenueWithLag AS (
    SELECT 
        revenue_month,
        ROUND(monthly_sales, 2) AS current_month_sales,
        -- Get the previous month's revenue using LAG() window function
        ROUND(LAG(monthly_sales, 1) OVER (ORDER BY revenue_month), 2) AS previous_month_sales
    FROM MonthlyRevenue
)
SELECT 
    revenue_month,
    current_month_sales,
    previous_month_sales,
    ROUND(current_month_sales - previous_month_sales, 2) AS absolute_growth,
    -- Calculate percentage growth
    ROUND(
        ((current_month_sales - previous_month_sales) / previous_month_sales) * 100, 
        2
    ) AS growth_percentage
FROM RevenueWithLag
ORDER BY revenue_month;


-- 5. Product Category Sales Contribution (Ranked)
-- Demonstrates: Window Functions (DENSE_RANK)
SELECT 
    p.category,
    p.sub_category,
    ROUND(SUM(oi.sales), 2) AS total_sales,
    ROUND(SUM(oi.profit), 2) AS total_profit,
    DENSE_RANK() OVER (PARTITION BY p.category ORDER BY SUM(oi.sales) DESC) AS rank_within_category
FROM products p
INNER JOIN order_items oi ON p.product_id = oi.product_id
GROUP BY p.category, p.sub_category
ORDER BY p.category, total_sales DESC;
