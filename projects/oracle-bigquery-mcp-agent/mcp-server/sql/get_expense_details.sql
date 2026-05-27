SELECT expense_id, amount, description, status
FROM expenses
WHERE expense_id = :1
