SELECT expense_id, amount, description, status
FROM expenses
WHERE UPPER(status) = 'HOLD'
ORDER BY expense_id DESC
OFFSET :1 ROWS FETCH NEXT :2 ROWS ONLY
