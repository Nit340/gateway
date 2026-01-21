import asyncio
import aiohttp
import time
import statistics

SERVER_URL = "http://localhost:8080/api/general-configuration"
TOTAL_REQUESTS = 200

async def soak_test():
    latencies = []
    print(f"--- STARTING SOAK TEST ({TOTAL_REQUESTS} Requests) ---")
    
    async with aiohttp.ClientSession() as session:
        for i in range(TOTAL_REQUESTS):
            start = time.perf_counter()
            async with session.get(SERVER_URL) as resp:
                await resp.read()
                latencies.append((time.perf_counter() - start) * 1000)
            
            if i % 50 == 0 and i > 0:
                print(f"Progress: {i}/{TOTAL_REQUESTS}...")

    # Compare first 20 vs last 20
    first_20 = statistics.mean(latencies[:20])
    last_20 = statistics.mean(latencies[-20:])
    degradation = last_20 - first_20

    print(f"\n--- SOAK RESULTS ---")
    print(f"Initial Latency (Avg): {first_20:.2f}ms")
    print(f"Final Latency (Avg):   {last_20:.2f}ms")
    
    if degradation > 50:
        print(f"WARNING: Latency increased by {degradation:.2f}ms. Possible Memory/Socket Leak!")
    else:
        print("STABILITY: PASS - Server performance is consistent.")

if __name__ == "__main__":
    asyncio.run(soak_test())