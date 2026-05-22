def migrate(cr, installed_version):
    cr.execute("""
        UPDATE prescription_line 
        SET is_morning = TRUE,
            morning_before = (time LIKE 'morning%' AND time LIKE '%before%'),
            morning_after = (time LIKE 'morning%' AND time LIKE '%after%'),
            is_afternoon = (time LIKE 'afternoon%'),
            afternoon_before = (time LIKE 'afternoon%' AND time LIKE '%before%'),
            afternoon_after = (time LIKE 'afternoon%' AND time LIKE '%after%'),
            is_evening = (time LIKE 'evening%'),
            evening_before = (time LIKE 'evening%' AND time LIKE '%before%'),
            evening_after = (time LIKE 'evening%' AND time LIKE '%after%')
        WHERE time IS NOT NULL
    """)