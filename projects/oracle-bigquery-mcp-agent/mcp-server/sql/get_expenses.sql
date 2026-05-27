SELECT expense_id, amount, description, status
FROM expenses
ORDER BY expense_id DESC
OFFSET :row_offset ROWS FETCH NEXT :row_limit ROWS ONLY
