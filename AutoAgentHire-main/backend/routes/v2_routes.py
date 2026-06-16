"""
V2 API Routes - Frontend Compatible Endpoints
"""

import asyncio
import subprocess
import sys
import uuid
import json
import re as _re
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, HTTPException, UploadFile, File, Form

# Heavy bot import is deferred to first request to avoid slowing server startup
AutoAgentHireBot = None

def _get_bot_class():
    """Lazy-load AutoAgentHireBot on first use."""
    global AutoAgentHireBot
    if AutoAgentHireBot is None:
        from backend.agents.autoagenthire_bot import AutoAgentHireBot as _Bot
        AutoAgentHireBot = _Bot
    return AutoAgentHireBot

# Database imports
engine = None
sql_text = None
try:
    from backend.database.connection import get_db_session, engine
    from sqlalchemy import text as sql_text
    DB_AVAILABLE = True
except Exception:
    DB_AVAILABLE = False

# Resume parser import
ResumeParser = None
try:
    from backend.parsers.resume_parser import ResumeParser
    PARSER_AVAILABLE = True
except Exception:
    PARSER_AVAILABLE = False

router = APIRouter(prefix="/api/v2", tags=["V2 Automation"])

active_tasks = {}
automation_results = {}


def _save_application_to_db(app_data: dict, session_id: str):
    """Persist a single application record to PostgreSQL using a lightweight v2_applications table."""
    if not DB_AVAILABLE:
        return
    assert engine is not None and sql_text is not None
    try:
        _ensure_v2_tables()
        with engine.connect() as conn:
            conn.execute(sql_text("""
                INSERT INTO v2_applications (session_id, job_title, company_name, job_url, status, match_score, applied_at, form_data)
                VALUES (:sid, :title, :company, :url, :status, :score, CURRENT_TIMESTAMP, :form_data)
            """), {
                'sid': session_id,
                'title': (app_data.get('title') or 'Unknown')[:200],
                'company': (app_data.get('company') or 'Unknown')[:200],
                'url': (app_data.get('url') or '')[:500],
                'status': app_data.get('status', 'unknown'),
                'score': float(app_data.get('matchScore') or 0),
                'form_data': json.dumps(app_data),
            })
            conn.commit()
    except Exception as e:
        print(f"[DB] Failed to save application: {e}")


def _create_agent_run(session_id: str, config: dict):
    """Create an agent run record in the DB."""
    if not DB_AVAILABLE:
        return
    assert engine is not None and sql_text is not None
    try:
        _ensure_v2_tables()
        with engine.connect() as conn:
            conn.execute(sql_text("""
                INSERT INTO v2_agent_runs (session_id, status, keyword, location, max_applications, dry_run, started_at)
                VALUES (:sid, 'running', :kw, :loc, :max, :dry, CURRENT_TIMESTAMP)
            """), {
                'sid': session_id,
                'kw': config.get('keyword', ''),
                'loc': config.get('location', ''),
                'max': config.get('max_applications', 5),
                'dry': config.get('dry_run', True),
            })
            conn.commit()
    except Exception as e:
        print(f"[DB] Failed to create agent run: {e}")


def _complete_agent_run(session_id: str, task: dict):
    """Finalise the agent run record."""
    if not DB_AVAILABLE:
        return
    assert engine is not None and sql_text is not None
    try:
        with engine.connect() as conn:
            conn.execute(sql_text("""
                UPDATE v2_agent_runs
                SET status = :status, completed_at = CURRENT_TIMESTAMP,
                    jobs_found = :found, applications_submitted = :submitted, applications_failed = :failed
                WHERE session_id = :sid
            """), {
                'sid': session_id,
                'status': task.get('status', 'completed'),
                'found': task.get('jobs_found', 0),
                'submitted': task.get('applications_submitted', 0),
                'failed': task.get('applications_failed', 0),
            })
            conn.commit()
    except Exception as e:
        print(f"[DB] Failed to complete agent run: {e}")


_v2_tables_created = False

def _ensure_v2_tables():
    """Create lightweight v2 tables if they don't exist (no FK constraints)."""
    global _v2_tables_created
    if _v2_tables_created or not DB_AVAILABLE:
        return
    assert engine is not None and sql_text is not None
    try:
        is_pg = getattr(engine, 'name', '') == 'postgresql'
        pk_type = "SERIAL PRIMARY KEY" if is_pg else "INTEGER PRIMARY KEY"
        
        with engine.connect() as conn:
            conn.execute(sql_text(f"""
                CREATE TABLE IF NOT EXISTS v2_agent_runs (
                    id {pk_type},
                    session_id TEXT UNIQUE NOT NULL,
                    status TEXT DEFAULT 'pending',
                    keyword TEXT,
                    location TEXT,
                    max_applications INTEGER DEFAULT 5,
                    dry_run INTEGER DEFAULT 1,
                    jobs_found INTEGER DEFAULT 0,
                    applications_submitted INTEGER DEFAULT 0,
                    applications_failed INTEGER DEFAULT 0,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                )
            """))
            conn.execute(sql_text(f"""
                CREATE TABLE IF NOT EXISTS v2_applications (
                    id {pk_type},
                    session_id TEXT NOT NULL,
                    job_title TEXT,
                    company_name TEXT,
                    job_url TEXT,
                    status TEXT DEFAULT 'unknown',
                    match_score REAL DEFAULT 0,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    form_data TEXT
                )
            """))
            conn.execute(sql_text(f"""
                CREATE TABLE IF NOT EXISTS v2_user_profiles (
                    id {pk_type},
                    session_id TEXT NOT NULL,
                    first_name TEXT,
                    last_name TEXT,
                    email TEXT,
                    phone TEXT,
                    city TEXT,
                    state TEXT,
                    zip_code TEXT,
                    country TEXT,
                    address TEXT,
                    linkedin_url TEXT,
                    current_title TEXT,
                    current_company TEXT,
                    years_experience TEXT,
                    skill_set TEXT,
                    profile_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()
        _v2_tables_created = True
    except Exception as e:
        print(f"[DB] Failed to create v2 tables: {e}")


def _save_user_profile_to_db(session_id: str, user_profile: dict):
    """Persist user profile to PostgreSQL before automation starts."""
    if not DB_AVAILABLE:
        return
    assert engine is not None and sql_text is not None
    try:
        _ensure_v2_tables()
        with engine.connect() as conn:
            conn.execute(sql_text("""
                INSERT INTO v2_user_profiles
                    (session_id, first_name, last_name, email, phone, city, state,
                     zip_code, country, address, linkedin_url, current_title,
                     current_company, years_experience, skill_set, profile_json)
                VALUES
                    (:sid, :fn, :ln, :em, :ph, :ci, :st,
                     :zc, :co, :ad, :li, :ct,
                     :cc, :ye, :sk, :pj)
            """), {
                'sid': session_id,
                'fn': (user_profile.get('first_name') or '')[:100],
                'ln': (user_profile.get('last_name') or '')[:100],
                'em': (user_profile.get('email') or '')[:200],
                'ph': (user_profile.get('phone_number') or '')[:50],
                'ci': (user_profile.get('city') or '')[:100],
                'st': (user_profile.get('state') or '')[:100],
                'zc': (user_profile.get('zip_code') or '')[:20],
                'co': (user_profile.get('country') or '')[:100],
                'ad': (user_profile.get('address') or '')[:300],
                'li': (user_profile.get('linkedin_url') or '')[:500],
                'ct': (user_profile.get('current_title') or '')[:200],
                'cc': (user_profile.get('current_company') or '')[:200],
                'ye': str(user_profile.get('years_experience', ''))[:10],
                'sk': (user_profile.get('skill_set') or '')[:2000],
                'pj': json.dumps(user_profile),
            })
            conn.commit()
        print(f"[DB] User profile saved for session {session_id}")
    except Exception as e:
        print(f"[DB] Failed to save user profile: {e}")


def _parse_resume_for_skills(resume_path: str) -> dict:
    """Parse an uploaded resume and return a skill_experience map + raw_text."""
    if not PARSER_AVAILABLE or not resume_path:
        return {}
    assert ResumeParser is not None
    try:
        parser = ResumeParser()
        parsed = parser.parse(resume_path)
        # Build skill → years map from parsed data
        skill_exp = {}
        for skill in (parsed.get('skills') or []):
            skill_exp[skill.lower()] = 1  # default 1 year per listed skill
        for exp in (parsed.get('experience') or []):
            # If a duration is present, try to extract years
            duration = str(exp.get('duration', '') or '')
            nums = _re.findall(r'(\d+)', duration)
            years = int(nums[0]) if nums else 1
            title = (exp.get('title') or '').lower()
            for word in title.split():
                if len(word) > 2:
                    skill_exp[word] = max(skill_exp.get(word, 0), years)
        return {
            'skill_experience': skill_exp,
            'raw_text': parsed.get('raw_text', ''),
            'parsed_contact': parsed.get('contact', {}),
        }
    except Exception as e:
        print(f"[RESUME] Parse error: {e}")
        return {}


@router.post("/start-automation")
async def start_automation_v2(
    linkedin_email: str = Form(...),
    linkedin_password: str = Form(...),
    job_keywords: str = Form("Software Engineer"),
    job_location: str = Form("Remote"),
    max_applications: int = Form(5),
    first_name: str = Form(""),
    last_name: str = Form(""),
    phone: str = Form(""),
    phone_number: str = Form(""),  # Accept both phone and phone_number from frontend
    email: str = Form(""),
    city: str = Form(""),
    state: str = Form(""),
    zip_code: str = Form(""),
    country: str = Form("United States"),
    address: str = Form(""),
    linkedin_url: str = Form(""),
    github_url: str = Form(""),
    portfolio_url: str = Form(""),
    current_company: str = Form(""),
    current_title: str = Form(""),
    years_experience: str = Form("0"),
    skill_set: str = Form(""),
    work_authorization_us: str = Form("Yes"),
    require_sponsorship: str = Form("No"),
    willing_to_relocate: str = Form("Yes"),
    ai_provider: str = Form("none"),
    use_ai: str = Form("false"),
    gemini_api_key: str = Form(""),
    groq_api_key: str = Form(""),
    openai_api_key: str = Form(""),
    dry_run: str = Form("false"),  # CHANGED: Default to false (actually submit)
    headless: str = Form("true"),
    resume: UploadFile = File(None)
):
    """V2: Start automation with multipart form data"""
    session_id = str(uuid.uuid4())[:8]
    
    is_dry_run = dry_run.lower() == "true"
    
    def _clean(val: str) -> str:
        """Strip JS 'undefined'/'null'/whitespace-only strings coming from the frontend."""
        if not val:
            return ''
        stripped = val.strip()
        if stripped.lower() in ('undefined', 'null', 'none', 'nan'):
            return ''
        return stripped
    
    # Sanitize every field arriving from the browser
    first_name = _clean(first_name)
    last_name = _clean(last_name)
    phone = _clean(phone)
    phone_number = _clean(phone_number)
    email = _clean(email)
    city = _clean(city)
    state = _clean(state)
    zip_code = _clean(zip_code)
    country = _clean(country) or 'United States'
    address = _clean(address)
    linkedin_url = _clean(linkedin_url)
    github_url = _clean(github_url)
    portfolio_url = _clean(portfolio_url)
    current_company = _clean(current_company)
    current_title = _clean(current_title)
    years_experience = _clean(years_experience) or '0'
    skill_set = _clean(skill_set)
    ai_provider = _clean(ai_provider).lower() or 'none'
    gemini_api_key = _clean(gemini_api_key)
    groq_api_key = _clean(groq_api_key)
    openai_api_key = _clean(openai_api_key)
    use_ai_flag = use_ai.lower() == "true"
    has_any_ai_key = bool(gemini_api_key or groq_api_key or openai_api_key)
    if ai_provider not in ("gemini", "groq", "openai"):
        ai_provider = "none"
    effective_use_ai = use_ai_flag and has_any_ai_key and ai_provider != "none"
    
    # Use phone_number if phone is empty (frontend sends phone_number)
    actual_phone = phone or phone_number
    
    print(f"\n[AUTOMATION V2] Starting with dry_run={is_dry_run}")
    print(f"[AUTOMATION V2] User: first_name='{first_name}' last_name='{last_name}'")
    print(f"[AUTOMATION V2] Email: '{email}', Phone: '{actual_phone}' (phone='{phone}', phone_number='{phone_number}')")
    print(f"[AUTOMATION V2] City: '{city}', State: '{state}', Zip: '{zip_code}', Country: '{country}'")
    print(f"[AUTOMATION V2] Address: '{address}', LinkedIn: '{linkedin_url}'")
    print(f"[AUTOMATION V2] Current Title: '{current_title}', Company: '{current_company}'")
    print(f"[AUTOMATION V2] Location: '{job_location}', Years Exp: '{years_experience}', Skills: '{skill_set}'")
    print(f"[AUTOMATION V2] AI mode: use_ai={effective_use_ai}, provider={ai_provider}")
    
    resume_path = None
    if resume:
        uploads_dir = Path("uploads")
        uploads_dir.mkdir(parents=True, exist_ok=True)
        resume_path = uploads_dir / f"{session_id}_{resume.filename}"
        with open(resume_path, "wb") as f:
            content = await resume.read()
            f.write(content)
        resume_path = str(resume_path)
    
    # Parse resume to extract skills and experience
    resume_data = _parse_resume_for_skills(resume_path) if resume_path else {}
    parsed_contact = resume_data.get('parsed_contact', {})
    
    user_profile = {
        "first_name": first_name if first_name else (parsed_contact.get('name', '').split()[0] if parsed_contact.get('name') else ''),
        "last_name": last_name if last_name else (parsed_contact.get('name', '').split()[-1] if parsed_contact.get('name') and len(parsed_contact.get('name', '').split()) > 1 else ''),
        "full_name": f"{first_name} {last_name}".strip() or parsed_contact.get('name', ''),
        "email": email or parsed_contact.get('email', ''),
        "phone_number": actual_phone or parsed_contact.get('phone', ''),
        "phone": actual_phone or parsed_contact.get('phone', ''),
        "city": city,
        "state": state,
        "zip_code": zip_code,
        "postal_code": zip_code,
        "country": country,
        "address": address,
        "street": address,
        "street_address": address,
        "linkedin_url": linkedin_url,
        "github_url": github_url,
        "portfolio_url": portfolio_url,
        "current_company": current_company,
        "current_title": current_title,
        "years_experience": years_experience,
        "skill_set": skill_set,
        "work_authorization": work_authorization_us,
        "work_authorization_us": work_authorization_us,
        "sponsorship": require_sponsorship,
        "require_sponsorship": require_sponsorship,
        "relocate": "yes" if willing_to_relocate == "Yes" else "no",
        "willing_to_relocate": willing_to_relocate == "Yes",
        "visa_status": "Authorized to work" if work_authorization_us == "Yes" else "Requires sponsorship",
        "location": job_location,
        "preferred_location": job_location,
        # Skill experience from resume parsing
        "skill_experience": resume_data.get('skill_experience', {}),
    }
    
    active_tasks[session_id] = {
        "status": "initializing",
        "phase": "setup",
        "jobs_found": 0,
        "current_job": 0,
        "total_jobs": 0,
        "current_job_title": "",
        "applications_submitted": 0,
        "applications_failed": 0,
        "error": None,
    }
    
    automation_results[session_id] = {"results": [], "summary": {}}
    
    config = {
        "keyword": job_keywords,
        "location": job_location,
        "max_applications": min(max_applications, 20),
        "easy_apply_only": True,
        "auto_apply": not is_dry_run,
        "dry_run": is_dry_run,
        "headless": headless.lower() == "true",
        "linkedin_email": linkedin_email,
        "linkedin_password": linkedin_password,
        "resume_path": resume_path,
        "user_profile": user_profile,
        "resume_text": resume_data.get('raw_text', ''),
        "ai_config": {
            "use_ai": effective_use_ai,
            "provider": ai_provider,
            "gemini_api_key": gemini_api_key,
            "groq_api_key": groq_api_key,
            "openai_api_key": openai_api_key,
        },
    }
    
    active_tasks[session_id]["config"] = config
    _create_agent_run(session_id, config)
    _save_user_profile_to_db(session_id, user_profile)
    asyncio.create_task(run_automation_v2(session_id, config))
    
    return {
        "status": "started",
        "session_id": session_id,
        "message": f"Automation started",
        "dry_run": is_dry_run
    }


async def run_playwright_subprocess(session_id: str, config: dict):
    """Run Playwright in a subprocess to avoid event loop conflicts on Windows"""
    import threading
    
    task = active_tasks[session_id]
    
    def run_in_thread():
        """Run subprocess in a separate thread to avoid asyncio conflicts"""
        try:
            # Build config for the subprocess
            subprocess_config = {
                "linkedin_email": config.get("linkedin_email"),
                "linkedin_password": config.get("linkedin_password"),
                "keyword": config.get("keyword", "Software Engineer"),
                "location": config.get("location", "Remote"),
                "max_applications": config.get("max_applications", 5),
                "dry_run": config.get("dry_run", True),
                "headless": config.get("headless", True),
                "user_profile": config.get("user_profile", {}),
                "resume_path": config.get("resume_path", ""),
                "resume_text": config.get("resume_text", ""),
                "ai_config": config.get("ai_config", {}),
            }
            
            config_json = json.dumps(subprocess_config)
            
            # Run the playwright_runner.py script
            runner_path = Path(__file__).parent.parent / "playwright_runner.py"
            python_exe = sys.executable
            
            print(f"🚀 Starting Playwright subprocess: {runner_path}")
            print(f"🐍 Python: {python_exe}")
            print(f"📂 CWD: {Path(__file__).parent.parent.parent}")
            
            task["status"] = "running"
            task["phase"] = "subprocess_started"
            
            # Ensure subprocess uses UTF-8 encoding (critical on Windows)
            import os as _os
            subprocess_env = _os.environ.copy()
            subprocess_env["PYTHONIOENCODING"] = "utf-8"
            ai_cfg = config.get("ai_config", {})
            if ai_cfg.get("use_ai"):
                subprocess_env["AI_PROVIDER"] = str(ai_cfg.get("provider", "none"))
                if ai_cfg.get("gemini_api_key"):
                    subprocess_env["GEMINI_API_KEY"] = str(ai_cfg.get("gemini_api_key"))
                    subprocess_env["GOOGLE_API_KEY"] = str(ai_cfg.get("gemini_api_key"))
                if ai_cfg.get("groq_api_key"):
                    subprocess_env["GROQ_API_KEY"] = str(ai_cfg.get("groq_api_key"))
                    subprocess_env["groq_api_key"] = str(ai_cfg.get("groq_api_key"))
                if ai_cfg.get("openai_api_key"):
                    subprocess_env["OPENAI_API_KEY"] = str(ai_cfg.get("openai_api_key"))
            
            # Use subprocess.Popen with threading instead of asyncio
            process = subprocess.Popen(
                [python_exe, str(runner_path), config_json],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(Path(__file__).parent.parent.parent),
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=subprocess_env,
            )
            
            # Stream output
            output_lines = []
            for line in iter(process.stdout.readline, '') if process.stdout else []:
                if not line:
                    break
                line_str = line.strip()
                output_lines.append(line_str)
                print(f"[SUBPROCESS] {line_str}")
                
                # Update task status based on output (matches new playwright_runner.py log format)
                if "Browser initialized" in line_str or "[OK] Browser" in line_str:
                    task["phase"] = "browser_initialized"
                elif "Login successful" in line_str or "Already logged in" in line_str or "[OK] Login" in line_str:
                    task["phase"] = "logged_in"
                elif "[SEARCH]" in line_str or "Starting job search" in line_str:
                    task["phase"] = "searching_jobs"
                elif "[OK] Collected" in line_str or ("Collected" in line_str and "jobs" in line_str) or "[COLLECT]" in line_str:
                    task["phase"] = "jobs_collected"
                    try:
                        import re
                        match = re.search(r'Collected (\d+)', line_str)
                        if match:
                            task["jobs_found"] = int(match.group(1))
                            task["total_jobs"] = min(int(match.group(1)), config.get("max_applications", 5))
                    except:
                        pass
                elif "Found" in line_str and "Easy Apply" in line_str:
                    task["phase"] = "jobs_collected"
                    try:
                        import re
                        match = re.search(r'Found (\d+)', line_str) or re.search(r'Collected (\d+)', line_str)
                        if match:
                            task["jobs_found"] = int(match.group(1))
                            task["total_jobs"] = min(int(match.group(1)), config.get("max_applications", 5))
                    except:
                        pass
                elif "[APPLY] Applying to:" in line_str or "Applying to:" in line_str:
                    task["phase"] = "applying"
                    task["current_job"] = task.get("current_job", 0) + 1
                    task["current_job_title"] = line_str.split("Applying to:")[-1].strip()[:50]
                elif "[SUCCESS]" in line_str or "Application submitted" in line_str:
                    task["applications_submitted"] = task.get("applications_submitted", 0) + 1
                elif "[DRY RUN]" in line_str or "DRY RUN" in line_str:
                    task["applications_submitted"] = task.get("applications_submitted", 0) + 1
                elif "[FATAL]" in line_str or "FATAL" in line_str:
                    task["error"] = line_str.split("[FATAL]")[-1].strip()[:200] if "[FATAL]" in line_str else line_str[:200]
            
            process.wait()
            return_code = process.returncode
            
            # Parse result JSON from output - find the JSON block after ===RESULT_JSON===
            result_json = None
            json_started = False
            json_lines = []
            for line in output_lines:
                if "===RESULT_JSON===" in line:
                    json_started = True
                    continue
                if json_started:
                    # Stop at first non-JSON line (exception traces, etc)
                    if line.startswith("Exception") or line.startswith("Traceback"):
                        break
                    json_lines.append(line)
            
            if json_lines:
                result_json = "\n".join(json_lines)
            
            if result_json:
                try:
                    result = json.loads(result_json)
                    task["jobs_found"] = int(result.get("jobs_found", task.get("jobs_found", 0)) or 0)
                    task["total_jobs"] = min(task["jobs_found"], int(config.get("max_applications", 5) or 5))
                    if result.get("errors"):
                        try:
                            first_error = result.get("errors", [""])[0]
                            if first_error:
                                task["error"] = str(first_error)[:200]
                        except Exception:
                            pass
                    app_results = []
                    for app in result.get("applications", []):
                        raw_status = app.get("status", "FAILED")
                        app_record = {
                            "title": app.get("title", "Unknown"),
                            "company": app.get("company", "Unknown"),
                            "url": app.get("url", ""),
                            "status": raw_status,  # Keep original: APPLIED, DRY_RUN, FAILED, INCOMPLETE
                            "reason": app.get("error", ""),
                            "appliedAt": datetime.now().isoformat(),
                            "matchScore": app.get("match_score", 0),
                        }
                        app_results.append(app_record)
                        # Persist to PostgreSQL
                        _save_application_to_db(app_record, session_id)
                    
                    automation_results[session_id]["results"] = app_results
                    task["applications_submitted"] = len([a for a in result.get("applications", []) if a.get("status") in ["APPLIED", "DRY_RUN"]])
                    task["applications_failed"] = len([a for a in result.get("applications", []) if a.get("status") not in ["APPLIED", "DRY_RUN"]])
                except json.JSONDecodeError as e:
                    print(f"Failed to parse result JSON: {e}")
                    pass

            if return_code != 0:
                task["status"] = "failed"
                task["phase"] = "failed"
                if not task.get("error"):
                    task["error"] = f"Playwright subprocess exited with code {return_code}"
            elif task.get("error"):
                task["status"] = "failed"
                task["phase"] = "failed"
            elif task.get("jobs_found", 0) == 0:
                task["status"] = "completed"
                task["phase"] = "no_jobs_found"
            else:
                task["status"] = "completed"
                task["phase"] = "finished"
            _complete_agent_run(session_id, task)
            
            print(f"\n{'='*60}")
            print(f"✅ SUBPROCESS AUTOMATION COMPLETE")
            print(f"{'='*60}")
            
        except Exception as e:
            import traceback
            print(f"\n❌ SUBPROCESS ERROR: {str(e)}")
            traceback.print_exc()
            task["status"] = "failed"
            task["error"] = str(e)
    
    # Start thread and return immediately
    thread = threading.Thread(target=run_in_thread, daemon=True)
    thread.start()


async def run_automation_v2(session_id: str, config: dict):
    """Run the automation workflow - uses subprocess on Windows to avoid event loop issues"""
    
    # On Windows, use subprocess approach to avoid Playwright event loop conflicts
    import platform
    if platform.system() == "Windows":
        print("🪟 Windows detected - using subprocess for Playwright")
        await run_playwright_subprocess(session_id, config)
        return
    
    # On other platforms, use direct async approach
    bot = None
    try:
        task = active_tasks[session_id]
        task["status"] = "running"
        task["phase"] = "logging_in"
        
        print(f"\n{'='*60}")
        print(f"🚀 AUTOMATION SESSION: {session_id}")
        print(f"{'='*60}")
        print(f"Config: keyword={config.get('keyword')}, location={config.get('location')}")
        print(f"Max applications: {config.get('max_applications')}")
        print(f"Dry run: {config.get('dry_run')}")
        
        bot = _get_bot_class()(config)
        
        if config.get("resume_path"):
            try:
                print(f"📄 Loading resume from: {config.get('resume_path')}")
                bot.parse_resume(config["resume_path"])
            except Exception as e:
                print(f"⚠️  Resume load warning: {e}")
        
        if config.get("user_profile"):
            bot.user_profile = config["user_profile"]
            print(f"👤 User profile loaded: {config['user_profile'].get('first_name')} {config['user_profile'].get('last_name')}")
        
        # Initialize browser
        print("\n📍 Initializing browser...")
        await bot.initialize_browser()
        print("✅ Browser initialized")
        
        print("\n📍 Logging into LinkedIn...")
        login_success = await bot.login_linkedin()
        
        if not login_success:
            task["status"] = "failed"
            task["error"] = "Failed to login to LinkedIn - check your credentials"
            print("❌ Login failed!")
            return
        
        print("✅ LinkedIn login successful")
        task["phase"] = "searching_jobs"
        
        print(f"\n📍 Searching for jobs: '{config['keyword']}' in '{config['location']}'...")
        await bot.search_jobs(
            keyword=config["keyword"],
            location=config["location"]
        )
        
        # Collect job listings after search
        print(f"📍 Collecting job listings (max {config['max_applications'] * 2})...")
        jobs = await bot.collect_job_listings(max_jobs=config["max_applications"] * 2)
        
        task["jobs_found"] = len(jobs)
        task["total_jobs"] = min(len(jobs), config["max_applications"])
        
        print(f"✅ Found {len(jobs)} jobs")
        
        if not jobs:
            task["status"] = "completed"
            task["phase"] = "no_jobs_found"
            task["error"] = "No jobs found matching your criteria"
            print("⚠️  No jobs found!")
            return
        
        task["phase"] = "applying"
        results = []
        
        print(f"\n📍 Starting applications (up to {config['max_applications']})...")
        for i, job in enumerate(jobs[:config["max_applications"]]):
            task["current_job"] = i + 1
            task["current_job_title"] = job.get("title", "Unknown")
            
            try:
                result = await bot.auto_apply_job(job)
                
                # Check application status from result dict
                # auto_apply_job returns a job dict with 'application_status' field
                app_status = result.get("application_status", "FAILED")
                is_success = app_status in ["APPLIED", "DRY_RUN"]
                
                app_result = {
                    "title": result.get("title", job.get("title", "Unknown")),
                    "company": result.get("company", job.get("company", "Unknown")),
                    "location": result.get("location", job.get("location", "")),
                    "url": result.get("url", job.get("url", "")),
                    "status": "applied" if is_success else "failed",
                    "reason": result.get("application_reason", result.get("message", "")),
                    "appliedAt": datetime.now().isoformat(),
                    "matchScore": result.get("match_score", job.get("match_score", 80))
                }
                
                results.append(app_result)
                
                if is_success:
                    task["applications_submitted"] += 1
                else:
                    task["applications_failed"] += 1
                    
            except Exception as e:
                print(f"❌ Application error for {job.get('title', 'Unknown')}: {str(e)}")
                task["applications_failed"] += 1
                results.append({
                    "title": job.get("title", "Unknown"),
                    "company": job.get("company", "Unknown"),
                    "location": job.get("location", ""),
                    "url": job.get("url", ""),
                    "status": "error",
                    "reason": str(e),
                    "appliedAt": datetime.now().isoformat(),
                })
            
            await asyncio.sleep(2)
        
        automation_results[session_id]["results"] = results
        task["status"] = "completed"
        task["phase"] = "finished"
        
        print(f"\n{'='*60}")
        print(f"✅ AUTOMATION COMPLETE")
        print(f"{'='*60}")
        print(f"Jobs found: {task['jobs_found']}")
        print(f"Applications submitted: {task['applications_submitted']}")
        print(f"Applications failed: {task['applications_failed']}")
        
    except Exception as e:
        import traceback
        print(f"\n❌ AUTOMATION ERROR: {str(e)}")
        traceback.print_exc()
        active_tasks[session_id]["status"] = "failed"
        active_tasks[session_id]["error"] = str(e)
    finally:
        if bot:
            try:
                await bot.close()
                print("🔒 Browser closed")
            except:
                pass



@router.get("/automation-status/{session_id}")
async def get_automation_status_v2(session_id: str):
    """V2: Get real-time automation status"""
    if session_id not in active_tasks:
        raise HTTPException(status_code=404, detail="Session not found")
    
    task = active_tasks[session_id]
    return {
        "session_id": session_id,
        "status": task.get("status", "unknown"),
        "phase": task.get("phase", ""),
        "jobs_found": task.get("jobs_found", 0),
        "current_job": task.get("current_job", 0),
        "total_jobs": task.get("total_jobs", 0),
        "current_job_title": task.get("current_job_title", ""),
        "applications_submitted": task.get("applications_submitted", 0),
        "applications_failed": task.get("applications_failed", 0),
        "error": task.get("error"),
    }


@router.get("/automation-results/{session_id}")
async def get_automation_results_v2(session_id: str):
    """V2: Get automation results"""
    if session_id not in automation_results:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return automation_results[session_id]


@router.get("/applications")
async def get_all_applications():
    """V2: Get all application records from PostgreSQL."""
    if not DB_AVAILABLE:
        return {"applications": [], "message": "Database not available"}
    assert engine is not None and sql_text is not None
    try:
        _ensure_v2_tables()
        with engine.connect() as conn:
            rows = conn.execute(sql_text(
                "SELECT id, session_id, job_title, company_name, job_url, status, match_score, applied_at "
                "FROM v2_applications ORDER BY applied_at DESC LIMIT 200"
            )).fetchall()
        return {
            "applications": [
                {
                    "id": r[0],
                    "session_id": r[1],
                    "title": r[2],
                    "company": r[3],
                    "url": r[4],
                    "status": r[5],
                    "matchScore": r[6],
                    "appliedAt": r[7].isoformat() if r[7] else None,
                }
                for r in rows
            ]
        }
    except Exception as e:
        return {"applications": [], "error": str(e)}


@router.get("/agent-runs")
async def get_all_agent_runs():
    """V2: Get all agent run records from PostgreSQL."""
    if not DB_AVAILABLE:
        return {"runs": [], "message": "Database not available"}
    assert engine is not None and sql_text is not None
    try:
        _ensure_v2_tables()
        with engine.connect() as conn:
            rows = conn.execute(sql_text(
                "SELECT id, session_id, status, keyword, location, max_applications, dry_run, "
                "jobs_found, applications_submitted, applications_failed, started_at, completed_at "
                "FROM v2_agent_runs ORDER BY started_at DESC LIMIT 50"
            )).fetchall()
        return {
            "runs": [
                {
                    "id": r[0],
                    "session_id": r[1],
                    "status": r[2],
                    "keyword": r[3],
                    "location": r[4],
                    "max_applications": r[5],
                    "dry_run": r[6],
                    "jobs_found": r[7],
                    "applications_submitted": r[8],
                    "applications_failed": r[9],
                    "started_at": r[10].isoformat() if r[10] else None,
                    "completed_at": r[11].isoformat() if r[11] else None,
                }
                for r in rows
            ]
        }
    except Exception as e:
        return {"runs": [], "error": str(e)}
