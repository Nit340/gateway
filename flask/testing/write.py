import asyncio
import aiohttp
import time

SERVER_URL = "http://localhost:8080/api/general-configuration"

async def write_collision(client_id, session):
    # Payload to change a setting
    payload = {"network": {"mode": "wifi", "wifi": {"ssid": f"Test_{client_id}"}}}
    
    start = time.perf_counter()
    try:
        async with session.put(SERVER_URL, json=payload) as resp:
            status = resp.status
            data = await resp.json()
            latency = (time.perf_counter() - start) * 1000
            print(f"Device_{client_id} | Status: {status} | Latency: {latency:.2f}ms | Success: {data.get('success')}")
    except Exception as e:
        print(f"Device_{client_id} CRASHED: {e}")

async def main():
    async with aiohttp.ClientSession() as session:
        # Launching 10 simultaneous writes
        tasks = [write_collision(i, session) for i in range(10)]
        print("--- TESTING CONCURRENT WRITES ---")
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())