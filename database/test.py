from opc_client import OPCClient
from tags import OPC_SERVER_URL, MACHINES

try:
    client = OPCClient(OPC_SERVER_URL)
    client.connect()
    
    # Read raw data from machine
    result = client.read_machine(60, MACHINES)
    
    
    for tag, value in result.items():
        print(f"{tag}: {value}")

except Exception as e:
    print("Error:", e)
finally:
    client.disconnect()

