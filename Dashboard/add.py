import information

information.create_table()  # safe to call even if table exists
information.add_machine(number=24, mold=0, cyc_limit=0)



print(information.get_machines())  # verify it was inserted