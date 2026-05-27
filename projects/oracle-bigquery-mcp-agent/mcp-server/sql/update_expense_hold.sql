UPDATE expenses
SET status = 'HOLD',
    description = SUBSTRB(description, 1, 255 - LENGTHB(' [AI FLAG: High Risk]')) || ' [AI FLAG: High Risk]'
WHERE expense_id = :1
