UPDATE expenses
SET status = 'REJECTED',
    description = SUBSTRB(description, 1, 255 - LENGTHB(' [AI FLAG: Rejected for Policy Violation]')) || ' [AI FLAG: Rejected for Policy Violation]'
WHERE expense_id = :1
