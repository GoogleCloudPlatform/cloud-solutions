SELECT
  e.EXPENSE_ID,
  e.AMOUNT,
  e.EXPENSE_DATE,
  e.MERCHANT_NAME,
  e.STATUS,
  emp.FIRST_NAME || ' ' || emp.LAST_NAME AS employee_name,
  d.DEPT_NAME,
  c.CATEGORY_NAME,
  c.BUDGET_LIMIT AS ALLOCATED_BUDGET,
  co.COUNTRY_NAME,
  r.REGION_NAME,
  r.DESCRIPTION AS continent
FROM `${project_id}.${dataset_id}.${oracle_schema}_EXPENSES` e
JOIN `${project_id}.${dataset_id}.${oracle_schema}_EMPLOYEES` emp ON e.EMP_ID = emp.EMP_ID
JOIN `${project_id}.${dataset_id}.${oracle_schema}_DEPARTMENTS` d ON emp.DEPT_ID = d.DEPT_ID
JOIN `${project_id}.${dataset_id}.${oracle_schema}_EXPENSE_CATEGORIES` c ON e.CATEGORY_ID = c.CATEGORY_ID
JOIN `${project_id}.${dataset_id}.${oracle_schema}_COUNTRIES` co ON emp.COUNTRY_ID = co.COUNTRY_ID
JOIN `${project_id}.${dataset_id}.${oracle_schema}_REGIONS` r ON co.REGION_ID = r.REGION_ID
