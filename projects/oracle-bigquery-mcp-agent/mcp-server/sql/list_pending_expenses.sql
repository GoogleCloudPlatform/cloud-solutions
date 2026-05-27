SELECT expense_id, amount, description, status
FROM expenses
WHERE UPPER(status) = 'PENDING' AND amount >= :1
ORDER BY expense_id DESC
OFFSET :2 ROWS FETCH NEXT :3 ROWS ONLY
