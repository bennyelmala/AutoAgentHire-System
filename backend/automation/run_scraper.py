import sys
import os
import asyncio
import json

# Ensure project root is in sys.path so both `automation.*` and `backend.*` imports resolve.
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from backend.automation.linkedin_recommended_jobs import fetch_recommended_jobs

async def main():
    email = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] != "None" else None
    password = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] != "None" else None
    
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
    try:
        # Disable logging to stdout from Playwright if possible, or isolate output
        jobs = await fetch_recommended_jobs(email, password)
        print("\n---JSON_OUTPUT_START---")
        print(json.dumps(jobs))
        print("---JSON_OUTPUT_END---\n")
    except Exception as e:
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    if sys.platform == 'win32':
        with asyncio.Runner(loop_factory=asyncio.ProactorEventLoop) as runner:
            runner.run(main())
    else:
        asyncio.run(main())
