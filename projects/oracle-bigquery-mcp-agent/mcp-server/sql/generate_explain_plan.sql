SELECT plan_table_output FROM table(dbms_xplan.display_cursor(:sql_id, NULL, 'TYPICAL'))
