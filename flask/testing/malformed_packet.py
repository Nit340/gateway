import asyncio
import aiohttp

SERVER_URL = "http://localhost:8080/api/general-configuration"

async def test_chaos():
    chaos_payloads = [
        ("Invalid JSON syntax", "{ 'network': missing_quotes }"),
        ("Wrong Data Type", {"network": {"mode": 12345}}), # Int where string expected
        ("Empty Payload", ""),
        ("Huge Payload (1MB)", {"data": "A" * 1024 * 1024}), 
        ("SQL Injection Attempt", {"ssid": "'; DROP TABLE configurations;--"}),
    ]

    async with aiohttp.ClientSession() as session:
        print("--- STARTING MALFORMED PACKET TEST ---")
        for description, payload in chaos_payloads:
            try:
                # Use PUT for data modification
                if isinstance(payload, str):
                    async with session.put(SERVER_URL, data=payload) as resp:
                        status = resp.status
                else:
                    async with session.put(SERVER_URL, json=payload) as resp:
                        status = resp.status
                
                print(f"Test: {description:20} | Result: HTTP {status}")
                
            except Exception as e:
                print(f"Test: {description:20} | SERVER CRASHED: {e}")

if __name__ == "__main__":
    asyncio.run(test_chaos())