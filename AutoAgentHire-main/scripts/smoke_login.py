import asyncio
import sys
from pathlib import Path

# Ensure repo root is on sys.path so `import backend...` works when running as a script.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.automation.linkedin_auto_apply import LinkedInAutoApply


async def main():
    # Use a known-good text resume file in the repo for smoke testing.
    # (Keeps this test independent of PDF parsing quirks.)
    resume_path = REPO_ROOT / "data" / "resumes" / "sample_resume.txt"
    bot = LinkedInAutoApply(headless=True, use_llm=False, resume_path=str(resume_path))
    await bot.initialize_browser()
    ok = await bot.login_linkedin()
    print(f"LOGIN={ok}")

    # Clean shutdown
    if bot.browser:
        await bot.browser.close()
    if bot.playwright:
        await bot.playwright.stop()


if __name__ == "__main__":
    asyncio.run(main())
