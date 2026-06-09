# Power BI Data Modeling & Setup Guide

This document describes how to load the cleaned sales data into Power BI, set up relationships, and define core DAX measures to recreate the executive dashboard.

---

## 1. Importing the Data

To import the cleaned dataset into Power BI:
1. Open **Power BI Desktop**.
2. Click **Get Data** > **Text/CSV**.
3. Import the following CSV files from the `data/` directory:
   * `cleaned_customers.csv`
   * `cleaned_products.csv`
   * `cleaned_locations.csv`
   * `cleaned_orders.csv`
   * `cleaned_order_items.csv`

---

## 2. Defining Relationships (Star Schema)

Navigate to the **Model View** tab in Power BI and establish the following active relationships. All connections should be **1-to-Many (1:*)**:

| Table 1 (Dimension) | Column | Table 2 (Fact/Bridge) | Column | Cross Filter Direction |
|:---|:---|:---|:---|:---|
| `cleaned_customers` | `customer_id` | `cleaned_orders` | `customer_id` | Single |
| `cleaned_locations` | `location_id` | `cleaned_orders` | `location_id` | Single |
| `cleaned_products`  | `product_id`  | `cleaned_order_items` | `product_id` | Single |
| `cleaned_orders`    | `order_id`    | `cleaned_order_items` | `order_id` | Both |

> [!NOTE]
> Setting the relationship between `cleaned_orders` and `cleaned_order_items` to "Both" or using a star schema design allows slicers on Order attributes (like Date, Shipping Mode, Priority) to automatically filter Order Item metrics (like Sales and Profit).

---

## 3. Core DAX Measures

Create a new table named `_Measures` and add the following DAX calculations:

### Total Sales
```dax
Total Sales = SUM(cleaned_order_items[sales])
```

### Total Profit
```dax
Total Profit = SUM(cleaned_order_items[profit])
```

### Profit Margin %
```dax
Profit Margin % = DIVIDE([Total Profit], [Total Sales], 0)
```

### Order Count
```dax
Order Count = DISTINCTCOUNT(cleaned_orders[order_id])
```

### Average Order Value (AOV)
```dax
Average Order Value = DIVIDE([Total Sales], [Order Count], 0)
```

### Previous Month Sales (MoM Analysis)
```dax
Prev Month Sales = 
CALCULATE(
    [Total Sales],
    DATEADD(cleaned_orders[order_date].[Date], -1, MONTH)
)
```

### Sales Growth Month-over-Month %
```dax
Sales Growth MoM % = 
DIVIDE(
    [Total Sales] - [Prev Month Sales],
    [Prev Month Sales],
    0
)
```

---

## 4. Visual Layout Recommendations

To replicate the layout in the dashboard mockup:
1. **Background**: Use a dark gray/blue aesthetic (e.g., hex `#0E1117` or `#1A1C24`).
2. **KPIs**: Position a row of Card visuals at the top for **Sales**, **Profit**, **Margin %**, and **Orders**.
3. **Monthly Trend**: Use an Area Chart with `cleaned_orders[order_date]` on the X-axis (grouped by Year & Month) and `[Total Sales]` on the Y-axis. Apply a gradient fill.
4. **Top Customers**: Use a Horizontal Bar Chart with `cleaned_customers[customer_name]` on the Y-axis and `[Total Sales]` on the X-axis, sorted descending.
5. **Product Category Distribution**: Use a Donut Chart with `cleaned_products[category]` as the legend and `[Total Sales]` as values.
6. **Filters**: Place Slicers on the left sidebar for:
   * `cleaned_locations[market]`
   * `cleaned_orders[order_date]` (Year slider)
   * `cleaned_customers[segment]`
