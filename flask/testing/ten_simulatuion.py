import asyncio
import aiohttp
import time
import statistics
from datetime import datetime
from fpdf import FPDF

# --- CONFIG ---
SERVER_URL = "http://localhost:8080"
NUM_CLIENTS = 10  # Increase to 50 or 100 for true stress
REPORT_FILE = "Simultaneous_Burst_Report.pdf"

class BurstStats:
    def __init__(self):
        self.results = [] # List of (latency, status)
        self.errors = 0

stats = BurstStats()
starting_gate = asyncio.Event() # The "Sync" mechanism

async def simultaneous_request(client_id, session):
    # 1. Wait at the gate until everyone is ready
    await starting_gate.wait() 
    
    # 2. Fire the request immediately
    start = time.perf_counter()
    try:
        async with session.get(f"{SERVER_URL}/api/general-configuration") as resp:
            content = await resp.read()
            latency = (time.perf_counter() - start) * 1000
            stats.results.append((latency, resp.status))
    except Exception as e:
        stats.errors += 1
        print(f"Client {client_id} failed: {e}")

async def run_burst_test():
    async with aiohttp.ClientSession() as session:
        # Create all tasks
        tasks = [simultaneous_request(i, session) for i in range(NUM_CLIENTS)]
        
        print(f"Preparing {NUM_CLIENTS} clients...")
        # Start the tasks - they will all block at 'starting_gate.wait()'
        pending_tasks = asyncio.gather(*tasks)
        
        # Give them a moment to initialize
        await asyncio.sleep(1) 
        
        print("--- FIRING BURST NOW ---")
        starting_gate.set() # Releasing the gate!
        
        await pending_tasks

# --- PDF GENERATION ---
def generate_pdf():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Industrial Synchronized Burst Report", ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"Testing {NUM_CLIENTS} simultaneous connections", ln=True)
    pdf.set_font("Arial", '', 11)
    
    latencies = [r[0] for r in stats.results]
    
    if latencies:
        pdf.cell(0, 10, f"Average Latency: {statistics.mean(latencies):.2f}ms", ln=True)
        pdf.cell(0, 10, f"Slowest Connection: {max(latencies):.2f}ms", ln=True)
        pdf.cell(0, 10, f"Fastest Connection: {min(latencies):.2f}ms", ln=True)
        pdf.cell(0, 10, f"Success Rate: {len(latencies)/(len(latencies)+stats.errors)*100:.1f}%", ln=True)
        
        pdf.ln(5)
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(40, 8, "Client ID", 1)
        pdf.cell(40, 8, "Latency (ms)", 1)
        pdf.cell(40, 8, "HTTP Status", 1, ln=True)
        
        pdf.set_font("Arial", '', 10)
        for i, (lat, status) in enumerate(stats.results):
            pdf.cell(40, 8, f"Device_{i}", 1)
            pdf.cell(40, 8, f"{lat:.2f}", 1)
            pdf.cell(40, 8, f"{status}", 1, ln=True)
    
    pdf.output(REPORT_FILE)
    print(f"PDF Report Saved: {REPORT_FILE}")

if __name__ == "__main__":
    asyncio.run(run_burst_test())
    generate_pdf()