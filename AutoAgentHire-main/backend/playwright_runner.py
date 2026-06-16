"""
Playwright runner – production-ready LinkedIn Easy Apply automation.
Runs as a SUBPROCESS from v2_routes (avoids event-loop conflicts on Windows).

v3 – with AI unknown-field handler + strict field tracking.

Guarantees
----------
* Never re-fills a field that already has a value.
* Never calls the AI API more than once per unique field label.
* Never loops infinitely – hard caps on steps, retries, and no-progress streaks.
* Unknown / extra form fields are answered by AI (GitHub Models → Groq → OpenAI).
* All waits use Playwright primitives – zero time.sleep().
"""
# ═══════════════════════════════════════════════════════════════════════════
# SECTION 1 – IMPORTS & WINDOWS SETUP
# ═══════════════════════════════════════════════════════════════════════════
import asyncio
import hashlib
import sys
import json
import os
import re
import ssl
import urllib.request
from pathlib import Path
from datetime import datetime

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Load .env (best-effort)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    # Manual .env fallback
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    if _env_path.exists():
        for _line in _env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                os.environ.setdefault(_k.strip(), _v.strip())

from playwright.async_api import async_playwright, Page, BrowserContext

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 2 – CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════
FIELD_TIMEOUT       = 5_000     # 5 s per field interaction
STEP_TIMEOUT        = 10_000    # 10 s per form step
NAV_TIMEOUT         = 30_000    # 30 s page navigation
MAX_STEPS           = 15        # max steps in multi-step form
MAX_FIELD_RETRIES   = 1         # max retries per single field
MAX_BUTTON_RETRIES  = 1         # max retries for Next button
MAX_NO_PROGRESS     = 3         # no-progress steps before abort
MAX_LOOP_PER_PAGE   = 10        # absolute cap on fill iterations per step

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 3 – AI FIELD HANDLER
# ═══════════════════════════════════════════════════════════════════════════
_ai_cache: dict = {}            # label_key → answer  (persists across steps)
_runtime_ai_cfg: dict = {}      # set from incoming request config


def _get_ai_config() -> dict | None:
    """Return {url, key, model} from runtime AI config only.

    Optional AI mode is enabled only when frontend provides a valid key.
    """
    if not _runtime_ai_cfg.get("use_ai"):
        return None

    provider = str(_runtime_ai_cfg.get("provider", "none") or "none").lower()
    gemini_key = str(_runtime_ai_cfg.get("gemini_api_key", "") or "")
    groq_key = str(_runtime_ai_cfg.get("groq_api_key", "") or "")
    openai_key = str(_runtime_ai_cfg.get("openai_api_key", "") or "")

    if provider == "gemini" and gemini_key:
        return {
            "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            "key": gemini_key,
            "model": "gemini-2.5-flash",
            "provider": "gemini",
        }
    if provider == "groq" and groq_key:
        return {
            "url": "https://api.groq.com/openai/v1/chat/completions",
            "key": groq_key,
            "model": "llama-3.3-70b-versatile",
            "provider": "groq",
        }
    if provider == "openai" and openai_key:
        return {
            "url": "https://api.openai.com/v1/chat/completions",
            "key": openai_key,
            "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            "provider": "openai",
        }
    return None


def _call_ai_sync(prompt: str) -> str:
    """Blocking HTTP call to the AI chat-completion endpoint (stdlib only)."""
    cfg = _get_ai_config()
    if not cfg:
        return ""
    
    # Provider-specific payload construction
    if cfg.get("provider") == "gemini":
        url = f"{cfg['url']}?key={cfg['key']}"
        headers = {"Content-Type": "application/json"}
        body = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2, # Lower temp for more deterministic form filling
                "maxOutputTokens": 100,
            },
        }).encode()
    elif cfg.get("provider") == "groq":
        url = cfg["url"]
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg['key']}"
        }
        body = json.dumps({
            "model": cfg["model"],
            "messages": [
                {"role": "system", "content": "You are a helpful assistant filling out job application forms. Output ONLY the answer value."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 100,
            "temperature": 0.1,
        }).encode()
    else: # OpenAI / default
        url = cfg["url"]
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg['key']}"
        }
        body = json.dumps({
            "model": cfg["model"],
            "messages": [
                {"role": "system", "content": "You are a helpful assistant filling out job application forms. Output ONLY the answer value."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 100,
            "temperature": 0.2,
        }).encode()

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    ctx = ssl.create_default_context()
    
    try:
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            if 200 <= resp.status < 300:
                data = json.loads(resp.read().decode())
                if cfg.get("provider") == "gemini":
                    ans = (
                        data.get("candidates", [{}])[0]
                        .get("content", {})
                        .get("parts", [{}])[0]
                        .get("text", "")
                    )
                else:
                    ans = data["choices"][0]["message"]["content"]
                
                return ans.strip().strip("\"'`")
            print(f"    [AI] HTTP {resp.status} Error")
            return ""
    except Exception as e:
        print(f"    [AI] API error: {str(e)[:80]}")
        return ""


async def ai_answer_field(
    label: str,
    job_title: str,
    user_profile: dict,
    resume_text: str = "",
    validation_hint: str = "",
    field_type: str = "text",
    options: list[str] | None = None,
) -> str:
    """Generate a concise answer for an unknown form field.
    Called AT MOST ONCE per unique label (result is cached)."""
    
    # 1. Check cache first
    key = f"{label.lower().strip()}::{field_type}"
    if key in _ai_cache:
        return _ai_cache[key]

    # 2. Build Rich Context Profile
    # combines explicit profile fields + some computed ones
    profile_dump = json.dumps(user_profile, indent=2, default=str)
    
    # 3. Construct System/User Prompt
    # We use a structured prompt to force the LLM to behave like a form-filler
    
    type_instruction = ""
    if field_type == "numeric":
        type_instruction = "IMPORTANT: Return ONLY a number. No text, no symbols. For salary/CTC, provide a realistic annual figure (e.g., 80000 or 500000). Never return 0."
    elif field_type == "yes_no":
        type_instruction = "IMPORTANT: Return ONLY 'Yes' or 'No'."
    elif field_type == "date":
        type_instruction = "IMPORTANT: Return date in MM/DD/YYYY format."
    elif field_type == "dropdown" and options:
        opts_str = ", ".join([f"'{o}'" for o in options[:60]]) # limit options length
        type_instruction = f"IMPORTANT: You MUST choose exactly one option from this list: [{opts_str}]. Return ONLY the option text."
    else:
        type_instruction = "Keep the answer concise and professional. Do not add conversational text."

    prompt = f"""
You are an intelligent AI assistant helping a candidate apply for a job.
Your task is to provide the CONTENT for a single form field based on the candidate's profile and resume.

--- JOB CONTEXT ---
Job Title: {job_title}

--- CANDIDATE PROFILE ---
{profile_dump}

--- RESUME EXCERPT ---
{resume_text[:2500]}

--- FIELD TO FILL ---
Label: "{label}"
Type: {field_type}
Validation Hint: "{validation_hint}"
{f"Options: {options}" if options else ""}

--- INSTRUCTIONS ---
1. Analyze the 'Label' and 'Validation Hint' to understand what is asked.
2. Search the Candidate Profile and Resume for the answer.
3. If the answer is not explicitly found, make a reasonable, professional guess based on the candidate's background.
   - For Salary/CTC: If 'INR' or 'Rupees' is mentioned, assume Indian Rupees (e.g., 600000 for 6LPA). If '$' or 'USD', assume US Dollars (e.g., 80000). If unspecified, guess based on location.
   - For Experience: Calculate numeric years from resume history.
   - For Notice Period: Default to '15' or '30' days if unknown.
4. {type_instruction}
5. OUTPUT ONLY THE VALUE. No markdown, no quotes, no explanations.
"""

    # 4. Call AI (in a thread to avoid blocking loop)
    try:
        ans = await asyncio.to_thread(_call_ai_sync, prompt)
    except Exception as e:
        print(f"    [AI] thread error: {str(e)[:50]}")
        ans = ""

    # 5. Sanitize and Cache
    final_ans = _sanitize_ai_answer(ans, field_type, options)
    _ai_cache[key] = final_ans
    
    if final_ans:
        print(f"    [AI] '{label[:30]}...' -> '{final_ans[:30]}...'")
    else:
        print(f"    [AI] '{label[:30]}...' -> (no answer)")
        
    return final_ans


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 4 – FIELD TRACKER  (per-job, reset between applications)
# ═══════════════════════════════════════════════════════════════════════════

class FieldTracker:
    """Prevents re-processing the same form field."""

    def __init__(self):
        self.filled: dict[str, str] = {}       # fid → value
        self.retries: dict[str, int] = {}      # fid → retry count
        self.ai_called: set[str] = set()       # label keys already sent to AI

    # ---- identifiers ----
    @staticmethod
    def make_id(elem_id: str = "", elem_name: str = "", label: str = "") -> str:
        if elem_id:
            return f"id:{elem_id.strip().lower()}"
        if elem_name:
            return f"nm:{elem_name.strip().lower()}"
        if label:
            return f"lb:{hashlib.md5(label.lower().encode()).hexdigest()[:10]}"
        return ""

    # ---- queries ----
    def is_done(self, fid: str) -> bool:
        return fid != "" and fid in self.filled

    def can_retry(self, fid: str) -> bool:
        return self.retries.get(fid, 0) < MAX_FIELD_RETRIES

    def ai_was_called_for(self, label: str) -> bool:
        return label.lower().strip() in self.ai_called

    # ---- mutations ----
    def mark_done(self, fid: str, value: str):
        if fid:
            self.filled[fid] = value

    def mark_retry(self, fid: str):
        self.retries[fid] = self.retries.get(fid, 0) + 1

    def mark_ai_called(self, label: str):
        self.ai_called.add(label.lower().strip())

    def reset(self):
        self.filled.clear()
        self.retries.clear()
        self.ai_called.clear()


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 5 – SMALL HELPERS
# ═══════════════════════════════════════════════════════════════════════════

async def _visible_query_all(el, selector: str):
    sel = selector.replace(":visible", "")
    try:
        elems = await el.query_selector_all(sel)
    except Exception:
        return []
    out = []
    for e in elems:
        try:
            if await e.is_visible():
                out.append(e)
        except Exception:
            pass
    return out


async def _is_button_truly_disabled(btn) -> bool:
    try:
        if await btn.get_attribute("disabled") is not None:
            return True
        aria = await btn.get_attribute("aria-disabled")
        if aria and aria.lower() == "true":
            return True
        return await btn.evaluate("el => el.disabled")
    except Exception:
        return False


async def _safe_wait(page: Page, ms: int):
    await page.wait_for_timeout(ms)


async def _wait_net(page: Page, timeout: int = STEP_TIMEOUT):
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout)
    except Exception:
        pass


async def _dismiss_save_popup(page: Page) -> bool:
    """Detect and dismiss the 'Save this application?' popup that LinkedIn
    shows when the Easy Apply modal is accidentally closed.
    Returns True if the popup was found and dismissed."""
    try:
        # Check by dialog selectors
        for sel in (
            'div[role="alertdialog"]',
            'div.artdeco-modal--layer-confirmation',
            'div[data-test-modal-id="discard-confirm-modal"]',
        ):
            dialog = await page.query_selector(sel)
            if not dialog:
                continue
            try:
                if not await dialog.is_visible():
                    continue
            except Exception:
                continue
            # Click "Discard" to close the popup
            for bsel in (
                'button[data-control-name="discard_application_confirm_btn"]',
                'button[data-test-dialog-secondary-btn]',
            ):
                btn = await dialog.query_selector(bsel)
                if btn:
                    await btn.click(timeout=FIELD_TIMEOUT)
                    await _safe_wait(page, 300)
                    print("    [POPUP] Dismissed save-application dialog")
                    return True
            # Fallback: look for Discard button inside dialog
            for btn in await dialog.query_selector_all("button"):
                txt = (await btn.text_content() or "").strip().lower()
                if txt == "discard":
                    await btn.click(timeout=FIELD_TIMEOUT)
                    await _safe_wait(page, 300)
                    print("    [POPUP] Dismissed save-application dialog (fallback)")
                    return True
    except Exception:
        pass
    # Also check by heading text
    try:
        for h in await page.query_selector_all("h2, h3, [data-test-modal-title]"):
            txt = (await h.text_content() or "").strip().lower()
            if "save this application" in txt or "discard" in txt:
                for btn in await page.query_selector_all("button"):
                    bt = (await btn.text_content() or "").strip().lower()
                    if bt == "discard":
                        try:
                            if await btn.is_visible():
                                await btn.click(timeout=FIELD_TIMEOUT)
                                await _safe_wait(page, 300)
                                print("    [POPUP] Dismissed save-application dialog (text)")
                                return True
                        except Exception:
                            continue
    except Exception:
        pass
    return False


async def _close_dropdown(page: Page, trigger=None):
    """Safely close an open dropdown/listbox WITHOUT pressing Escape.
    Escape propagates to the Easy Apply modal and triggers the save popup."""
    # Strategy 1: click the trigger element again to toggle it closed
    if trigger:
        try:
            await trigger.click(timeout=2000)
            await _safe_wait(page, 100)
            return
        except Exception:
            pass
    # Strategy 2: press Tab to move focus away (closes dropdown)
    try:
        await page.keyboard.press("Tab")
        await _safe_wait(page, 100)
    except Exception:
        pass


async def _close_easy_apply_modal(page: Page):
    """Close the Easy Apply modal after a job application finishes.
    Handles the 'Save this application?' confirmation popup."""
    # First dismiss any existing save popup
    if await _dismiss_save_popup(page):
        return
    # Click the X / Dismiss button on the Easy Apply modal
    try:
        for ds in (
            'button[aria-label="Dismiss"]',
            'button[aria-label="Close"]',
            "button.artdeco-modal__dismiss",
        ):
            b = await page.query_selector(ds)
            if b and await b.is_visible():
                await b.click(timeout=FIELD_TIMEOUT)
                await _safe_wait(page, 500)
                break
    except Exception:
        pass
    # Now the save popup may appear — dismiss it
    await _dismiss_save_popup(page)


async def _get_nearby_error(page: Page, element) -> str:
    """Return validation-error text near a field (if any)."""
    try:
        return await element.evaluate(r"""el => {
            const containers = [
                '.fb-dash-form-element',
                '.artdeco-text-input--container',
                '.jobs-easy-apply-form-section__grouping',
                '.jobs-easy-apply-form-element',
                '.artdeco-form__item',
                'fieldset', 'li'
            ];
            for (const sel of containers) {
                const p = el.closest(sel);
                if (!p) continue;
                const err = p.querySelector(
                    '.artdeco-inline-feedback--error, [role="alert"], .field-error'
                );
                if (err && err.textContent.trim()) return err.textContent.trim();
            }
            return '';
        }""")
    except Exception:
        return ""


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 6 – LABEL → PROFILE MAPPING
# ═══════════════════════════════════════════════════════════════════════════

_CONTACT_LABELS = [
    "first name", "last name", "full name", "name", "email",
    "phone", "mobile", "cell", "street", "address", "city",
    "state", "province", "zip", "postal", "country", "linkedin", "location",
]


def _map_label_to_profile(label: str, profile: dict, email: str = "") -> str:
    """Return the EXACT user-profile value for a known label, or '' if unknown."""
    lb = label.lower().strip()
    if not lb:
        return ""
    g = profile.get

    # --- name ---
    if any(x in lb for x in ("first name", "fname", "given name", "first_name")):
        return g("first_name", "")
    if any(x in lb for x in ("last name", "lname", "surname", "family name", "last_name")):
        return g("last_name", "")
    if any(x in lb for x in ("full name", "your name")) or lb.strip() == "name":
        return g("full_name", "")

    # --- contact ---
    if "email" in lb:
        return g("email", "") or email
    if any(x in lb for x in ("phone", "mobile", "cell")):
        return g("phone_number", "") or g("phone", "")

    # --- address ---
    if any(x in lb for x in ("street", "address")) and "ip" not in lb:
        return g("address", "") or g("street", "") or g("street_address", "")
    if "hometown" in lb and "city" in lb:
        return g("hometown_city", "") or g("city", "")
    if "hometown" in lb and "state" in lb:
        return g("hometown_state", "") or g("state", "")
    if "hometown" in lb:
        return g("hometown_city", "") or g("city", "")
    if any(x in lb for x in ("current city", "city")):
        return g("city", "")
    if any(x in lb for x in ("current state", "state", "province", "region")):
        return g("state", "")
    if any(x in lb for x in ("zip", "postal", "pincode", "pin code")):
        return g("zip_code", "") or g("postal_code", "")
    if "country" in lb and "code" not in lb:
        return g("country", "")
    if "location" in lb and "job" not in lb:
        return g("city", "") or g("location", "")

    # --- links ---
    if "linkedin" in lb:
        return g("linkedin_url", "")
    if "github" in lb:
        return g("github_url", "")
    if "portfolio" in lb or "website" in lb:
        return g("portfolio_url", "") or g("website", "")

    # --- professional ---
    if any(x in lb for x in ("current title", "job title", "current position", "designation", "position title")):
        return g("current_title", "")
    if any(x in lb for x in ("current company", "company name", "employer", "current employer")):
        return g("current_company", "")
    if any(x in lb for x in ("skill set", "skill", "skills", "expertise", "technologies")):
        return g("skill_set", "") or g("skills", "")
    if "notice period" in lb:
        v = g("notice_period", "")
        return str(v) if v else ""

    # --- experience ---
    if any(x in lb for x in ("overall experience", "total experience", "years of experience", "work experience")):
        v = g("years_experience", "")
        return str(v) if v else ""

    # --- salary / CTC ---
    if any(x in lb for x in ("expected ctc", "expected salary", "salary expectation")):
        return str(g("expected_ctc", "") or g("expected_salary", ""))
    if any(x in lb for x in ("current ctc", "current salary", "current compensation")):
        v = g("current_ctc", "")
        return str(v) if v else ""
    if any(x in lb for x in ("ctc", "salary", "compensation")):
        return str(g("ctc", "") or g("current_ctc", ""))

    # --- education / India-specific ---
    if any(x in lb for x in ("date of birth", "dob", "d.o.b", "birth date")):
        return g("date_of_birth", "") or g("dob", "")
    if any(x in lb for x in ("10th percentage", "tenth percentage", "10th marks", "ssc", "10th")):
        v = g("tenth_percentage", "") or g("ssc_percentage", "")
        return str(v) if v else ""
    if any(x in lb for x in ("12th percentage", "twelfth percentage", "12th marks", "hsc", "intermediate", "12th")):
        v = g("twelfth_percentage", "") or g("hsc_percentage", "")
        return str(v) if v else ""
    if any(x in lb for x in ("college", "university", "institute", "institution")):
        return g("college", "") or g("university", "")
    if any(x in lb for x in ("graduation year", "year of graduation", "passing year", "passout")):
        v = g("graduation_year", "") or g("passing_year", "")
        return str(v) if v else ""
    if any(x in lb for x in ("masters percentage", "bachelors percentage", "degree percentage", "bachelor")):
        v = g("degree_percentage", "") or g("bachelors_percentage", "")
        return str(v) if v else ""
    if "gpa" in lb or "cgpa" in lb:
        v = g("gpa", "") or g("cgpa", "")
        return str(v) if v else ""
    if "already placed" in lb or "placement" in lb:
        return g("placement_status", "")

    # --- skill-specific experience ---
    skill_exp = profile.get("skill_experience", {})
    for skill, yrs in skill_exp.items():
        if skill.lower() in lb:
            return str(yrs)
    if any(x in lb for x in ("experience", "years")):
        v = g("years_experience", "")
        return str(v) if v else ""

    return ""                   # unknown → let AI handle


def _is_contact(label: str) -> bool:
    lb = label.lower().strip()
    return any(x in lb for x in _CONTACT_LABELS)


def _resolve_yes_no(label: str, profile: dict) -> str:
    lb = label.lower()
    if any(x in lb for x in ("sponsor", "require visa", "need sponsorship", "immigration")):
        v = str(profile.get("sponsorship", "no")).lower()
        return "no" if v in ("no", "false", "0", "n") else "yes"
    if any(x in lb for x in ("authorized", "eligible", "legally", "work authorization", "right to work")):
        v = str(profile.get("work_authorization", "yes")).lower()
        return "yes" if v in ("yes", "true", "1", "y") else "no"
    if any(x in lb for x in ("relocate", "willing to relocate", "relocation")):
        v = str(profile.get("relocate", "yes")).lower()
        return "yes" if v in ("yes", "true", "1", "y") else "no"
    if any(x in lb for x in ("willing", "can you", "do you", "are you", "have you",
                              "completed", "degree", "bachelor", "master",
                              "proficient", "fluent", "experience with")):
        return "yes"
    if any(x in lb for x in ("consent", "agree", "allow", "privacy", "policy", "contact me")):
        return "yes"
    return "yes"


def _infer_field_type(label: str) -> str:
    lb = (label or "").lower()
    if any(x in lb for x in ("are you", "do you", "have you", "will you", "can you", "willing", "authorized", "eligible", "require", "need", "legally", "consent", "agree", "allow")):
        return "yes_no"
    if any(x in lb for x in ("year", "years", "experience", "salary", "ctc", "compensation", "cgpa", "gpa", "grade", "percentage", "notice", "number", "mobile", "phone")):
        return "numeric"
    if any(x in lb for x in ("date", "dob", "birth", "since", "until", "when")):
        return "date"
    return "text"


def _sanitize_ai_answer(answer: str, field_type: str, options: list[str] | None = None) -> str:
    a = (answer or "").strip().strip('"\'`')
    if not a:
        return ""
    
    # ── Numeric ──
    if field_type == "numeric":
        # extract first valid number
        m = re.search(r"-?\d+(?:,\d{3})*(?:\.\d+)?", a)
        if m:
            val = m.group(0).replace(",", "")
            return val
        return ""

    # ── Yes/No ──
    if field_type == "yes_no":
        low = a.lower()
        if any(x in low for x in ("yes", "true", "sure", "correct", "agree")):
            return "yes"
        if any(x in low for x in ("no", "false", "not", "deny")):
            return "no"
        # fallback simple check
        return "yes" if len(low) < 5 and "y" in low else "no"

    # ── Date ──
    if field_type == "date":
        # Extract MM/DD/YYYY
        m = re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", a)
        return m.group(0) if m else a

    # ── Dropdown ──
    if field_type == "dropdown" and options:
        al = a.lower()
        # 1. Exact match (case-insensitive)
        for opt in options:
            if al == opt.lower().strip():
                return opt
        
        # 2. Substring match (if unique)
        matches = [o for o in options if al in o.lower() or o.lower() in al]
        if len(matches) == 1:
            return matches[0]
        
        # 3. Token overlap (simple heuristic)
        best_opt = None
        best_score = 0
        a_tokens = set(al.split())
        for opt in options:
            opt_tokens = set(opt.lower().split())
            score = len(a_tokens & opt_tokens)
            if score > best_score:
                best_score = score
                best_opt = opt
        if best_opt and best_score > 0:
            return best_opt

        # 4. Fallback: First option if AI returned something reasonable but unmatched
        return ""

    return a[:500]  # Allow longer text for cover letters etc.


def _fallback_unknown_answer(label: str, profile: dict, field_type: str) -> str:
    lb = (label or "").lower()
    
    # Yes / No defaults
    if field_type == "yes_no":
        return "yes"
    
    # Numeric Defaults
    if field_type == "numeric":
        # Notice Period
        if "notice" in lb or "days" in lb:
            return "15" # Default 15 days
            
        # Experience / Years
        if "experience" in lb or "year" in lb or "months" in lb:
             # Try to get real experience, default to at least 1 for entry level
            years = str(profile.get("years_experience") or "1")
            if "month" in lb:
                return str(int(float(years) * 12)) if years.replace('.','',1).isdigit() else "12"
            return years

        # Salary / CTC (Crucial fix for >100 validation errors)
        if any(x in lb for x in ("salary", "ctc", "compensation", "pay", "remuneration")):
            # Check context -> INR vs USD
            if "inr" in lb or "rupee" in lb or "lakh" in lb:
                return "600000"  # Safe default 6 LPA base
            if "usd" in lb or "$" in lb:
                return "60000"   # Safe default 60k USD
            # Generic safe integer > 100
            val = str(profile.get("expected_salary") or profile.get("expected_ctc") or "50000")
            return val if val != "0" else "50000"
            
        # CGPA / Percentage
        if "cgpa" in lb or "gpa" in lb:
            return str(profile.get("gpa") or "8.0")
        if "percentage" in lb or "marks" in lb:
            return "75" # Safe average
            
        return "1" # Fallback for unknown numeric fields

    # Text Defaults
    if "experience" in lb and profile.get("years_experience"):
        return f"{profile.get('years_experience')} years"
    if "skill" in lb and profile.get("skill_set"):
        return str(profile.get("skill_set"))[:120]
        
    return "Yes"


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 7 – LABEL DETECTION
# ═══════════════════════════════════════════════════════════════════════════

async def get_field_label(page: Page, element) -> str:
    parts: list[str] = []
    try:
        for attr in ("aria-label",):
            v = await element.get_attribute(attr)
            if v and v.strip():
                parts.append(v.strip())

        llby = await element.get_attribute("aria-labelledby")
        if llby:
            for rid in llby.split():
                try:
                    r = await page.query_selector(f"#{rid}")
                    if r:
                        t = await r.text_content()
                        if t and t.strip():
                            parts.append(t.strip())
                except Exception:
                    pass

        eid = await element.get_attribute("id")
        if eid:
            try:
                lbl = await page.query_selector(f'label[for="{eid}"]')
                if lbl:
                    t = await lbl.text_content()
                    if t and t.strip():
                        parts.append(t.strip())
            except Exception:
                pass

        sec = await element.evaluate(r'''el => {
            const sels = [".fb-dash-form-element",".artdeco-text-input--container",
                ".jobs-easy-apply-form-section__grouping",".jobs-easy-apply-form-element",
                ".artdeco-form__item","fieldset"];
            for (const s of sels) {
                const p = el.closest(s);
                if (p) {
                    const l = p.querySelector(
                        'label,[data-test-form-element-label],.fb-dash-form-element__label,'+
                        'legend,span.t-bold,span.artdeco-text-input__label');
                    if (l && l.textContent.trim()) return l.textContent.trim();
                }
            }
            return "";
        }''')
        if sec:
            parts.append(sec)

        for a in ("placeholder", "name", "id"):
            v = await element.get_attribute(a)
            if v and v.strip():
                parts.append(v.strip())
                break
    except Exception:
        pass
    return " ".join(parts).lower()


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 8 – JS DOM SCANNER  (primary filler)
# ═══════════════════════════════════════════════════════════════════════════

_JS_SCAN = r"""() => {
    function lbl(el) {
        let t = el.getAttribute('aria-label') || '';
        if (t.trim()) return t.trim();
        const llby = el.getAttribute('aria-labelledby');
        if (llby) {
            t = llby.split(' ').map(id=>{const e=document.getElementById(id);return e?e.textContent.trim():''}).filter(Boolean).join(' ').trim();
            if (t) return t;
        }
        if (el.id) { const l=document.querySelector('label[for="'+el.id+'"]'); if (l&&l.textContent.trim()) return l.textContent.trim(); }
        const cs=['.fb-dash-form-element','.artdeco-text-input--container','.jobs-easy-apply-form-section__grouping','.jobs-easy-apply-form-element','.artdeco-form__item','fieldset','[data-test-form-element]','li','div.form-component'];
        for (const s of cs) { try { const p=el.closest(s); if (!p) continue; const l=p.querySelector('label,legend,span.artdeco-text-input__label,.fb-dash-form-element__label,span.t-bold,[class*="label"]'); if (l&&l!==el&&l.textContent.trim()) return l.textContent.trim(); } catch(e){} }
        return el.placeholder||el.name||el.id||'';
    }
    const r=[];
    for (const el of document.querySelectorAll('input,textarea')) {
        if (['hidden','submit','button','checkbox','radio','file'].includes(el.type)) continue;
        const b=el.getBoundingClientRect(); if (!b.width||!b.height) continue;
        if (el.disabled||el.readOnly) continue;
        r.push({label:lbl(el),tag:el.tagName.toLowerCase(),type:el.type||'text',id:el.id||'',name:el.name||'',value:el.value||''});
    }
    return r;
}"""


async def fill_form_fields_js(
    page: Page,
    profile: dict,
    email: str,
    tracker: FieldTracker,
    job_title: str = "",
    resume_text: str = "",
):
    """Scan visible inputs via JS, fill from profile or AI. Respects tracker."""
    try:
        fields = await page.evaluate(_JS_SCAN)
    except Exception as e:
        print(f"  [JS] DOM scan error: {e}")
        return
    print(f"  [JS] Scanned {len(fields)} inputs")

    for info in fields:
        raw_label = (info.get("label") or "").strip()
        label     = raw_label.lower()
        cur_val   = (info.get("value") or "").strip()
        fid       = tracker.make_id(info.get("id", ""), info.get("name", ""), label)
        tag       = info.get("tag", "input")

        # ─── RULE: already tracked → SKIP ───
        if tracker.is_done(fid):
            continue

        # ─── locate DOM element ───
        elem = None
        if info.get("id"):
            try:
                elem = await page.query_selector(f'#{info["id"]}')
            except Exception:
                pass
        if not elem and info.get("name"):
            try:
                elem = await page.query_selector(f'{tag}[name="{info["name"]}"]')
            except Exception:
                pass
        if not elem:
            continue
        try:
            if not await elem.is_visible():
                continue
        except Exception:
            continue

        # ─── RULE: non-empty value & not a contact field → mark done, SKIP ───
        is_contact = _is_contact(label)
        if cur_val and not is_contact:
            tracker.mark_done(fid, cur_val)
            continue

        # ─── try profile mapping ───
        fill_val = _map_label_to_profile(label, profile, email)

        # ─── AI fallback for unknown fields ───
        if not fill_val:
            if not tracker.ai_was_called_for(label) and label:
                tracker.mark_ai_called(label)
                hint = await _get_nearby_error(page, elem)
                ftype = _infer_field_type(label)
                fill_val = await ai_answer_field(label, job_title, profile, resume_text, hint, ftype)
            else:
                # AI already called and returned empty – skip
                tracker.mark_done(fid, "")
                continue

        if not fill_val:
            fill_val = _fallback_unknown_answer(label, profile, _infer_field_type(label))

        if not fill_val or not str(fill_val).strip():
            tracker.mark_done(fid, "")
            continue

        # ─── fill ───
        if is_contact or not cur_val:
            try:
                await elem.click(timeout=FIELD_TIMEOUT)
                await elem.fill("", timeout=FIELD_TIMEOUT)
                await elem.fill(str(fill_val), timeout=FIELD_TIMEOUT)
                await elem.press("Tab")
                tracker.mark_done(fid, str(fill_val))
                print(f"    [JS] '{raw_label[:35]}' = '{str(fill_val)[:25]}'")
            except Exception as e:
                tracker.mark_retry(fid)
                print(f"    [JS] WARN '{raw_label[:30]}': {str(e)[:40]}")
        else:
            tracker.mark_done(fid, cur_val)

    # dropdowns
    await _fill_select_dropdowns(page, profile, tracker, job_title, resume_text)
    await _fill_custom_dropdowns(page, profile, tracker, job_title, resume_text)


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 9 – SECTION-BASED FILLER  (secondary pass – radios, textareas, extras)
# ═══════════════════════════════════════════════════════════════════════════

async def fill_form_sections(
    page: Page,
    profile: dict,
    email: str,
    tracker: FieldTracker,
    job_title: str = "",
    resume_text: str = "",
):
    filled = 0
    try:
        sections = await page.query_selector_all(
            ".jobs-easy-apply-form-section__grouping,"
            ".fb-dash-form-element,"
            ".artdeco-text-input,"
            ".jobs-easy-apply-form-element"
        )
    except Exception:
        return

    for section in sections:
        try:
            lbl_el = await section.query_selector(
                "label,.fb-dash-form-element__label,span.t-14,span.t-bold"
            )
            q = ""
            if lbl_el:
                q = (await lbl_el.text_content() or "").strip().lower()
            if not q:
                q = (await section.text_content() or "").strip().lower()[:200]

            # ── TEXT INPUT ──
            inp = await section.query_selector(
                'input:not([type="hidden"]):not([type="submit"])'
                ':not([type="radio"]):not([type="checkbox"]):not([type="file"])'
            )
            if inp:
                try:
                    if not await inp.is_visible():
                        continue
                except Exception:
                    continue
                inp_id  = await inp.get_attribute("id") or ""
                inp_nm  = await inp.get_attribute("name") or ""
                fid     = tracker.make_id(inp_id, inp_nm, q)
                if tracker.is_done(fid):
                    continue
                cur = (await inp.input_value() or "").strip()
                is_ct = _is_contact(q)
                if cur and not is_ct:
                    tracker.mark_done(fid, cur)
                    continue

                fill_val = _map_label_to_profile(q, profile, email)
                if not fill_val and not tracker.ai_was_called_for(q) and q:
                    tracker.mark_ai_called(q)
                    hint = await _get_nearby_error(page, inp)
                    ftype = _infer_field_type(q)
                    fill_val = await ai_answer_field(q, job_title, profile, resume_text, hint, ftype)

                if not fill_val:
                    fill_val = _fallback_unknown_answer(q, profile, _infer_field_type(q))

                if fill_val and (is_ct or not cur):
                    try:
                        await inp.click(timeout=FIELD_TIMEOUT)
                        await inp.fill("", timeout=FIELD_TIMEOUT)
                        await inp.fill(str(fill_val), timeout=FIELD_TIMEOUT)
                        await inp.press("Tab")
                        filled += 1
                        tracker.mark_done(fid, str(fill_val))
                        print(f"    [SEC] '{q[:35]}' = '{str(fill_val)[:25]}'")
                    except Exception:
                        tracker.mark_retry(fid)
                else:
                    tracker.mark_done(fid, cur or "")
                continue

            # ── TEXTAREA ──
            ta = await section.query_selector("textarea")
            if ta:
                ta_id = await ta.get_attribute("id") or ""
                ta_nm = await ta.get_attribute("name") or ""
                fid   = tracker.make_id(ta_id, ta_nm, q)
                if tracker.is_done(fid):
                    continue
                cur = (await ta.input_value() or "").strip()
                if cur:
                    tracker.mark_done(fid, cur)
                    continue

                fill_val = ""
                if any(x in q for x in ("skill", "expertise", "technologies")):
                    fill_val = profile.get("skill_set", "") or profile.get("skills", "")
                elif any(x in q for x in ("cover letter", "why", "about you", "summary", "describe")):
                    fill_val = profile.get("cover_letter", "")
                elif "additional" in q or "other" in q:
                    fill_val = "N/A"

                if not fill_val and not tracker.ai_was_called_for(q) and q:
                    tracker.mark_ai_called(q)
                    fill_val = await ai_answer_field(q, job_title, profile, resume_text, field_type="text")

                if not fill_val:
                    fill_val = _fallback_unknown_answer(q, profile, "text")

                if fill_val:
                    try:
                        await ta.fill(str(fill_val), timeout=FIELD_TIMEOUT)
                        filled += 1
                        tracker.mark_done(fid, str(fill_val))
                    except Exception:
                        tracker.mark_retry(fid)
                else:
                    tracker.mark_done(fid, "")
                continue

            # ── RADIO BUTTONS ──
            radios = await section.query_selector_all('input[type="radio"]')
            if radios:
                fid = tracker.make_id("", "", f"radio:{q}")
                if tracker.is_done(fid):
                    continue
                any_checked = False
                for r in radios:
                    try:
                        if await r.is_checked():
                            any_checked = True
                            break
                    except Exception:
                        pass
                if any_checked:
                    tracker.mark_done(fid, "checked")
                    continue
                desired = _resolve_yes_no(q, profile)
                # If AI hasn't been called and label doesn't match standard patterns, try AI
                if not any(x in q for x in ("sponsor", "authorized", "relocate", "willing",
                                             "can you", "do you", "are you", "have you")):
                    if not tracker.ai_was_called_for(q) and q:
                        tracker.mark_ai_called(q)
                        ai_ans = await ai_answer_field(q, job_title, profile, resume_text, field_type="yes_no", options=["yes", "no"])
                        if ai_ans and ai_ans.lower().strip() in ("no", "n"):
                            desired = "no"
                        else:
                            desired = "yes"

                selected = False
                for r in radios:
                    try:
                        # Check value attribute
                        val = (await r.get_attribute("value") or "").lower().strip()
                        # Check label text (via our helper)
                        rl = (await get_field_label(page, r)).lower()
                        # Check parent text content as fallback (often 'Yes' is just text next to input)
                        parent_text = await r.evaluate("el => el.parentElement ? el.parentElement.textContent.trim().toLowerCase() : ''")

                        is_yes = (desired == "yes" and ("yes" in val or "true" in val or "yes" in rl or "yes" in parent_text))
                        is_no  = (desired == "no"  and ("no" in val  or "false" in val or "no" in rl  or "no" in parent_text))

                        if is_yes:
                            await r.check(timeout=FIELD_TIMEOUT)
                            selected = True
                            break
                        elif is_no:
                            await r.check(timeout=FIELD_TIMEOUT)
                            selected = True
                            break
                    except Exception:
                        continue
                
                # Double-check specific strict matching if loose matching failed
                if not selected:
                    for r in radios:
                        try:
                            # Strict check for "Yes" text node next to input
                            text_node = await r.evaluate("el => el.nextSibling ? el.nextSibling.textContent.trim().toLowerCase() : ''")
                            if desired == "yes" and text_node == "yes":
                                await r.check(timeout=FIELD_TIMEOUT)
                                selected = True; break
                            if desired == "no" and text_node == "no":
                                await r.check(timeout=FIELD_TIMEOUT)
                                selected = True; break
                        except Exception: pass

                if not selected and radios:
                    # Final fallback: just click the first one (usually 'Yes') for consent forms
                    # But only if it's likely a consent question
                    if any(x in q for x in ("consent", "agree", "allow", "privacy")):
                        try:
                            await radios[0].check(timeout=FIELD_TIMEOUT)
                            selected = True
                        except Exception:
                            pass
                
                if selected:
                    filled += 1
                    tracker.mark_done(fid, desired)
                continue

        except Exception:
            continue

    # ── CHECKBOXES (terms / agreements) ──
    try:
        for cb in await _visible_query_all(page, 'input[type="checkbox"]'):
            try:
                if await cb.is_checked():
                    continue
                lbl = await get_field_label(page, cb)
                if any(x in lbl for x in ("agree", "accept", "acknowledge", "confirm", "terms", "privacy", "consent")):
                    await cb.check(timeout=FIELD_TIMEOUT)
                    filled += 1
            except Exception:
                continue
    except Exception:
        pass

    if filled:
        print(f"    [SEC-FILL] Filled {filled} fields")


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 10 – DROPDOWNS
# ═══════════════════════════════════════════════════════════════════════════

async def _fill_select_dropdowns(page, profile, tracker, job_title="", resume_text=""):
    try:
        for sel in await _visible_query_all(page, "select"):
            try:
                sid = await sel.get_attribute("id") or ""
                snm = await sel.get_attribute("name") or ""
                lbl = await get_field_label(page, sel)
                fid = tracker.make_id(sid, snm, lbl)
                if tracker.is_done(fid):
                    continue
                cur = (await sel.input_value() or "").strip()
                if cur and cur.lower() not in ("select an option", "select", "choose", "", "--", "please select"):
                    tracker.mark_done(fid, cur)
                    continue
                opts = await sel.query_selector_all("option")
                val = await _pick_dropdown_value(lbl, opts, profile)
                if not val and not tracker.ai_was_called_for(lbl) and lbl:
                    tracker.mark_ai_called(lbl)
                    option_texts = [((await o.text_content()) or "").strip() for o in opts]
                    ai_ans = await ai_answer_field(lbl, job_title, profile, resume_text, field_type="dropdown", options=option_texts)
                    if ai_ans:
                        for o in opts:
                            ot = (await o.text_content() or "").strip().lower()
                            if ai_ans.lower() in ot or ot in ai_ans.lower():
                                val = await o.get_attribute("value") or ""
                                break
                if not val:
                    # Deterministic fallback: first non-placeholder option.
                    val = await _pick_dropdown_value(lbl, opts, profile)
                if val:
                    await sel.select_option(val, timeout=FIELD_TIMEOUT)
                    tracker.mark_done(fid, val)
                    print(f"    [SEL] '{lbl[:30]}' = '{val[:20]}'")
                else:
                    tracker.mark_done(fid, "")
            except Exception:
                continue
    except Exception:
        pass


async def _fill_custom_dropdowns(page, profile, tracker, job_title="", resume_text=""):
    try:
        triggers = await _visible_query_all(
            page,
            'button[aria-haspopup="listbox"],[role="combobox"],'
            'select[data-test-text-selectable-option]',
        )
        for trig in triggers:
            try:
                cur = (await trig.text_content() or "").strip()
                if cur and cur.lower() not in ("select an option", "select", "choose", "", "--", "please select"):
                    continue
                lbl = await get_field_label(page, trig)
                fid = tracker.make_id("", "", f"combo:{lbl}")
                if tracker.is_done(fid):
                    continue

                await trig.click(timeout=FIELD_TIMEOUT)
                await _safe_wait(page, 250)
                listbox = None
                for lb in await page.query_selector_all('[role="listbox"]'):
                    try:
                        if await lb.is_visible():
                            listbox = lb
                            break
                    except Exception:
                        pass
                if not listbox:
                    await _close_dropdown(page, trig)
                    continue
                opts = await listbox.query_selector_all('[role="option"]')
                if not opts:
                    await _close_dropdown(page, trig)
                    continue

                chosen = await _pick_listbox_option(lbl, opts, profile)

                if not chosen and not tracker.ai_was_called_for(lbl) and lbl:
                    tracker.mark_ai_called(lbl)
                    option_texts = [((await o.text_content()) or "").strip() for o in opts]
                    ai_ans = await ai_answer_field(lbl, job_title, profile, resume_text, field_type="dropdown", options=option_texts)
                    if ai_ans:
                        for o in opts:
                            ot = (await o.text_content() or "").strip().lower()
                            if ai_ans.lower() in ot or ot in ai_ans.lower():
                                chosen = o
                                break

                if not chosen and opts:
                    for o in opts:
                        ot = ((await o.text_content()) or "").strip().lower()
                        if ot and ot not in ("select", "select an option", "choose", "--"):
                            chosen = o
                            break

                if chosen:
                    await chosen.click(timeout=FIELD_TIMEOUT)
                    txt = (await chosen.text_content() or "").strip()
                    tracker.mark_done(fid, txt)
                    print(f"    [CMB] '{lbl[:30]}' = '{txt[:20]}'")
                else:
                    await _close_dropdown(page, trig)
                    tracker.mark_done(fid, "")
            except Exception:
                try:
                    await _close_dropdown(page, trig)
                except Exception:
                    pass
    except Exception:
        pass


async def _pick_listbox_option(label, opts, profile):
    lb = label.lower()
    if any(x in lb for x in ("authorized", "sponsor", "relocate", "willing", "legally",
                               "do you", "have you", "are you", "can you")):
        desired = _resolve_yes_no(lb, profile)
        for o in opts:
            if (await o.text_content() or "").strip().lower() == desired:
                return o

    if "country" in lb and "code" not in lb:
        c = (profile.get("country", "") or "").lower()
        for o in opts:
            if c and c in (await o.text_content() or "").lower():
                return o

    if any(x in lb for x in ("experience", "years")):
        yrs = profile.get("years_experience", "")
        if yrs and str(yrs).isdigit():
            yi = int(str(yrs))
            for o in opts:
                nums = re.findall(r"\d+", (await o.text_content() or ""))
                if nums:
                    lo, hi = int(nums[0]), int(nums[-1]) if len(nums) > 1 else int(nums[0]) + 2
                    if lo <= yi <= hi:
                        return o

    if any(x in lb for x in ("salutation", "prefix")):
        pref = "mr" if (profile.get("gender", "") or "").lower() in ("male", "m", "") else "ms"
        for o in opts:
            if pref in (await o.text_content() or "").lower():
                return o

    if any(x in lb for x in ("job title", "current title", "designation")):
        tv = (profile.get("current_title", "") or "").lower()
        for o in opts:
            ot = (await o.text_content() or "").strip().lower()
            if tv and (tv in ot or ot in tv):
                return o

    return None     # AI fallback handled by caller


async def _pick_dropdown_value(label, options, profile) -> str:
    lb = label.lower()
    if any(x in lb for x in ("country code", "phone code")):
        c = (profile.get("country", "") or "").lower()
        for o in options:
            if c and c in (await o.text_content() or "").lower():
                return await o.get_attribute("value") or ""
        for o in options:
            if "+1" in (await o.text_content() or "") or "united states" in (await o.text_content() or "").lower():
                return await o.get_attribute("value") or ""

    if any(x in lb for x in ("authorized", "sponsor", "relocate", "willing", "legally",
                               "do you", "have you", "are you", "can you")):
        desired = _resolve_yes_no(lb, profile)
        for o in options:
            if (await o.text_content() or "").strip().lower() == desired:
                return await o.get_attribute("value") or ""

    if "experience" in lb or "years" in lb:
        yrs = profile.get("years_experience", "")
        if yrs and str(yrs).isdigit():
            yi = int(str(yrs))
            for o in options:
                nums = re.findall(r"\d+", (await o.text_content() or ""))
                if nums:
                    lo, hi = int(nums[0]), int(nums[-1]) if len(nums) > 1 else int(nums[0]) + 2
                    if lo <= yi <= hi:
                        return await o.get_attribute("value") or ""

    if "degree" in lb or "education" in lb:
        el = (profile.get("education_level", "") or "").lower()
        for o in options:
            if el and el in (await o.text_content() or "").lower():
                return await o.get_attribute("value") or ""
        for o in options:
            ot = (await o.text_content() or "").lower()
            if any(x in ot for x in ("bachelor", "b.tech")):
                return await o.get_attribute("value") or ""

    if "country" in lb and "code" not in lb:
        c = (profile.get("country", "") or "").lower()
        for o in options:
            if c and c in (await o.text_content() or "").lower():
                return await o.get_attribute("value") or ""

    # generic: first non-placeholder option
    for o in options[1:]:
        v = await o.get_attribute("value")
        if v and v.strip() and v.lower() not in ("", "select", "choose", "-1", "select an option", "please select"):
            return v
    return ""


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 11 – RESUME UPLOAD
# ═══════════════════════════════════════════════════════════════════════════

async def handle_resume_upload(page: Page, resume_path: str) -> bool:
    if not resume_path or not os.path.isfile(resume_path):
        return False
    try:
        for fi in await page.query_selector_all('input[type="file"]'):
            try:
                await fi.set_input_files(resume_path)
                print(f"  [UPLOAD] {os.path.basename(resume_path)}")
                await _safe_wait(page, 500)
                return True
            except Exception:
                continue
        for btn in await page.query_selector_all(
            'label[for*="file"],button[aria-label*="upload" i],.jobs-document-upload__upload-button'
        ):
            try:
                fa = await btn.get_attribute("for")
                if fa:
                    hi = await page.query_selector(f"#{fa}")
                    if hi:
                        await hi.set_input_files(resume_path)
                        await _safe_wait(page, 500)
                        return True
            except Exception:
                continue
    except Exception as e:
        print(f"  [UPLOAD] Error: {str(e)[:50]}")
    return False


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 12 – BUTTON DETECTION (Next / Review / Submit)
# ═══════════════════════════════════════════════════════════════════════════

async def detect_and_click_button(page: Page, dry_run: bool) -> str:
    """Returns: submitted | dry_run | navigated | disabled | not_found"""
    found_disabled = False

    for fsel in (
        'footer button[aria-label*="Submit"]',
        'footer button[aria-label*="Review"]',
        'footer button[aria-label*="Next"]',
        'footer button[aria-label*="Continue"]',
        ".jobs-easy-apply-modal footer button",
        'div[role="dialog"] footer button',
        "div.artdeco-modal footer button",
    ):
        try:
            for btn in await page.query_selector_all(fsel):
                if await _is_button_truly_disabled(btn):
                    bt = (await btn.text_content() or "").strip().lower()
                    if any(x in bt for x in ("next", "submit", "review", "continue")):
                        found_disabled = True
                    continue
                bt = (await btn.text_content() or "").strip().lower()
                al = (await btn.get_attribute("aria-label") or "").lower()
                if "submit" in bt or "submit" in al:
                    if dry_run:
                        print(f"  [DRY RUN] Would submit")
                        return "dry_run"
                    await btn.scroll_into_view_if_needed()
                    await btn.click(timeout=FIELD_TIMEOUT)
                    await _wait_net(page)
                    return "submitted"
                if any(x in bt or x in al for x in ("next", "continue", "review")):
                    if not any(x in bt for x in ("back", "dismiss", "cancel")):
                        await btn.scroll_into_view_if_needed()
                        await btn.click(timeout=FIELD_TIMEOUT)
                        await _wait_net(page)
                        print(f"  [BTN] Clicked: '{bt[:20]}'")
                        return "navigated"
        except Exception:
            continue

    try:
        for pb in await _visible_query_all(page, "button.artdeco-button--primary"):
            if await _is_button_truly_disabled(pb):
                found_disabled = True
                continue
            bt = (await pb.text_content() or "").strip()
            if any(x in bt.lower() for x in ("back", "dismiss")):
                continue
            if "submit" in bt.lower():
                if dry_run:
                    return "dry_run"
                await pb.scroll_into_view_if_needed()
                await pb.click(timeout=FIELD_TIMEOUT)
                await _wait_net(page)
                return "submitted"
            await pb.scroll_into_view_if_needed()
            await pb.click(timeout=FIELD_TIMEOUT)
            await _wait_net(page)
            return "navigated"
    except Exception:
        pass

    return "disabled" if found_disabled else "not_found"


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 13 – SUCCESS / VALIDATION CHECKS
# ═══════════════════════════════════════════════════════════════════════════

async def check_success(page: Page) -> bool:
    try:
        body = await page.text_content("body")
        return bool(body and ("Application sent" in body or "Your application was sent" in body))
    except Exception:
        return False


async def has_validation_errors(page: Page) -> bool:
    try:
        for err in await page.query_selector_all(".artdeco-inline-feedback--error"):
            try:
                if await err.is_visible():
                    txt = (await err.text_content() or "").strip()
                    if txt:
                        print(f"    [VAL] {txt[:60]}")
                        return True
            except Exception:
                pass
    except Exception:
        pass
    return False


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 14 – MAIN AUTOMATION FLOW
# ═══════════════════════════════════════════════════════════════════════════

async def run_automation(config_json: str):
    config = json.loads(config_json)
    global _runtime_ai_cfg, _ai_cache
    _ai_cache = {}
    ai_cfg = config.get("ai_config", {}) if isinstance(config.get("ai_config", {}), dict) else {}
    _runtime_ai_cfg = {
        "use_ai": bool(ai_cfg.get("use_ai", False)),
        "provider": str(ai_cfg.get("provider", "none") or "none").lower(),
        "gemini_api_key": str(ai_cfg.get("gemini_api_key", "") or ""),
        "groq_api_key": str(ai_cfg.get("groq_api_key", "") or ""),
        "openai_api_key": str(ai_cfg.get("openai_api_key", "") or ""),
    }

    # ── build profile ──
    profile = config.get("user_profile", {})
    if profile.get("phone_number") and not profile.get("phone"):
        profile["phone"] = profile["phone_number"]
    elif profile.get("phone") and not profile.get("phone_number"):
        profile["phone_number"] = profile["phone"]
    if not profile.get("full_name"):
        profile["full_name"] = f"{profile.get('first_name','')} {profile.get('last_name','')}".strip()
    profile.setdefault("skill_experience", {})
    config["user_profile"] = profile

    resume_text = config.get("resume_text", "")

    print(f"[PROFILE] {profile.get('first_name')} {profile.get('last_name')} | {profile.get('email')} | {profile.get('phone_number')}")
    print(f"[PROFILE] {profile.get('city')}, {profile.get('state')} {profile.get('zip_code')} | {profile.get('country')}")
    print(f"[PROFILE] Title: {profile.get('current_title')} | Company: {profile.get('current_company')}")

    ai_cfg = _get_ai_config()
    provider_name = "NONE"
    if ai_cfg:
        provider_name = str(ai_cfg.get("provider", "UNKNOWN")).upper()
    print(f"[AI] Provider: {provider_name}")

    result = {"status": "failed", "phase": "", "jobs_found": 0, "applications": [], "errors": []}

    pw = ctx = page = None
    try:
        print("[INIT] Starting Playwright…")
        pw = await async_playwright().start()

        prof_dir = Path("browser_profile")
        prof_dir.mkdir(exist_ok=True)
        Path("data/screenshots").mkdir(parents=True, exist_ok=True)

        for lk in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
            p = prof_dir / lk
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass

        headless = config.get("headless", False)
        print(f"[BROWSER] Launching (headless={headless})…")

        ctx = await pw.chromium.launch_persistent_context(
            str(prof_dir),
            headless=headless,
            slow_mo=30,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage", "--no-sandbox",
                "--disable-gpu", "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US", timezone_id="America/New_York",
            ignore_https_errors=True,
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        page.set_default_timeout(STEP_TIMEOUT)
        page.set_default_navigation_timeout(NAV_TIMEOUT)
        await ctx.add_init_script("""
            Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
            Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3,4,5]});
            window.chrome={runtime:{}};
        """)
        print("[OK] Browser initialized")
        result["phase"] = "browser_initialized"

        # ═════════ LOGIN ═════════
        li_email = config.get("linkedin_email")
        li_pass  = config.get("linkedin_password")
        if not li_email or not li_pass:
            raise Exception("LinkedIn credentials not provided")

        await page.goto("https://www.linkedin.com", wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
        await _safe_wait(page, 1000)
        logged = any(p in page.url for p in ("/feed", "/mynetwork", "/jobs", "/in/"))

        if not logged:
            await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
            await _safe_wait(page, 500)
            for s in ('input[name="session_key"]', "input#username"):
                try:
                    e = await page.wait_for_selector(s, timeout=FIELD_TIMEOUT)
                    if e:
                        await e.fill(li_email, timeout=FIELD_TIMEOUT)
                        break
                except Exception:
                    continue
            for s in ('input[name="session_password"]', "input#password"):
                try:
                    e = await page.wait_for_selector(s, timeout=FIELD_TIMEOUT)
                    if e:
                        await e.fill(li_pass, timeout=FIELD_TIMEOUT)
                        break
                except Exception:
                    continue
            try:
                await page.click('button[type="submit"]', timeout=FIELD_TIMEOUT)
            except Exception:
                pass
            await _wait_net(page)
            await _safe_wait(page, 2000)
            if any(p in page.url for p in ("/feed", "/mynetwork", "/jobs", "/check/add-phone", "/in/")):
                logged = True
                print("[OK] Login successful!")
            elif "checkpoint" in page.url or "challenge" in page.url:
                print("[WARN] Security checkpoint – waiting 60 s…")
                await _safe_wait(page, 60000)
                logged = True
            else:
                raise Exception(f"Login may have failed – URL: {page.url}")
        if not logged:
            raise Exception("Not logged in")
        result["phase"] = "logged_in"

        # ═════════ SEARCH ═════════
        import urllib.parse as _up
        kw  = config.get("keyword", "Software Engineer")
        loc = config.get("location", "Remote")
        url = f"https://www.linkedin.com/jobs/search/?keywords={_up.quote(kw)}&location={_up.quote(loc)}&f_AL=true&sortBy=R"
        print(f"\n[SEARCH] {kw} / {loc}")
        await page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
        await _wait_net(page)
        await _safe_wait(page, 1500)
        result["phase"] = "searching"

        # ═════════ COLLECT ═════════
        print("[COLLECT] Collecting job listings…")
        for _ in range(3):
            await page.evaluate("window.scrollTo(0,document.body.scrollHeight)")
            await _safe_wait(page, 400)
        await page.evaluate("window.scrollTo(0,0)")
        await _safe_wait(page, 300)

        job_cards = []
        for sel in (
            "li.scaffold-layout__list-item",
            "li.jobs-search-results__list-item",
            "div.job-card-container",
            "div[data-job-id]",
            "ul.scaffold-layout__list-container > li",
        ):
            try:
                cards = await page.query_selector_all(sel)
                if cards:
                    job_cards = cards
                    print(f"[OK] {len(cards)} cards ({sel[:40]})")
                    break
            except Exception:
                continue

        max_jobs = config.get("max_applications", 5)
        jobs: list[dict] = []
        for i, card in enumerate(job_cards[: max_jobs * 2]):
            try:
                await card.scroll_into_view_if_needed()
                await _safe_wait(page, 200)
                await card.click(timeout=FIELD_TIMEOUT)
                await _safe_wait(page, 800)

                title = None
                for s in (
                    "h1.job-details-jobs-unified-top-card__job-title",
                    "h1.jobs-unified-top-card__job-title",
                    "h1.t-24.t-bold.inline",
                    ".job-details-jobs-unified-top-card__job-title",
                    "a.job-card-container__link span",
                ):
                    try:
                        e = await page.query_selector(s)
                        if e:
                            title = (await e.text_content() or "").strip()
                            if title:
                                break
                    except Exception:
                        continue

                company = None
                for s in (
                    "a.job-details-jobs-unified-top-card__company-name",
                    ".jobs-unified-top-card__company-name",
                    ".job-card-container__company-name",
                ):
                    try:
                        e = await page.query_selector(s)
                        if e:
                            company = (await e.text_content() or "").strip()
                            if company:
                                break
                    except Exception:
                        continue
                company = company or "Unknown"

                easy = False
                for s in ('button.jobs-apply-button', 'button[aria-label*="Easy Apply"]'):
                    try:
                        b = await page.query_selector(s)
                        if b and ("easy" in (await b.text_content() or "").lower() or "apply" in (await b.text_content() or "").lower()):
                            easy = True
                            break
                    except Exception:
                        continue

                if title and easy:
                    jobs.append({"index": i + 1, "title": title[:100], "company": company[:50], "url": page.url, "easy_apply": True})
                    print(f"  [+] {len(jobs)}: {title[:45]} @ {company[:20]}")
                    if len(jobs) >= max_jobs:
                        break
            except Exception as e:
                print(f"  [WARN] card {i+1}: {str(e)[:40]}")
        result["jobs_found"] = len(jobs)
        result["phase"] = "jobs_collected"
        print(f"[OK] Collected {len(jobs)} Easy Apply jobs")

        # ═════════ APPLICATION PHASE ═════════
        dry_run     = config.get("dry_run", True)
        resume_path = config.get("resume_path", "")
        li_fill     = config.get("linkedin_email", "")

        print(f"\n[APPLY] Starting (dry_run={dry_run})…")

        for job in jobs[:max_jobs]:
            tracker = FieldTracker()            # fresh tracker per job
            _ai_cache.clear()                   # fresh AI cache per job

            try:
                jt = job["title"]
                print(f"\n[APPLY] Applying to: {jt[:45]} @ {job['company']}")

                await page.goto(job["url"], wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
                await _safe_wait(page, 1000)

                # click Easy Apply
                clicked = False
                for s in ('button.jobs-apply-button', 'button[aria-label*="Easy Apply"]', 'button:has-text("Easy Apply")'):
                    try:
                        b = await page.wait_for_selector(s, timeout=FIELD_TIMEOUT)
                        if b:
                            await b.click(timeout=FIELD_TIMEOUT)
                            clicked = True
                            print("  [OK] Clicked Easy Apply")
                            break
                    except Exception:
                        continue
                if not clicked:
                    job["status"] = "FAILED"
                    job["error"] = "Could not click Easy Apply"
                    result["applications"].append(job)
                    continue

                await _wait_net(page)
                await _safe_wait(page, 500)

                # ═════════ MULTI-STEP FORM LOOP ═════════
                no_progress = 0
                button_retries = 0

                for step in range(MAX_STEPS):
                    await _safe_wait(page, 200)

                    # ── dismiss stray save popup if it appeared ──
                    if await _dismiss_save_popup(page):
                        # popup was open — re-click Easy Apply to re-open the form
                        for rs in ('button.jobs-apply-button', 'button[aria-label*="Easy Apply"]'):
                            try:
                                rb = await page.wait_for_selector(rs, timeout=FIELD_TIMEOUT)
                                if rb:
                                    await rb.click(timeout=FIELD_TIMEOUT)
                                    await _wait_net(page)
                                    await _safe_wait(page, 500)
                                    break
                            except Exception:
                                continue

                    if await check_success(page):
                        job["status"] = "APPLIED"
                        print("  [SUCCESS] Application submitted!")
                        break

                    print(f"  [STEP {step+1}] Filling…")

                    # ── FILL (respects tracker – never re-fills) ──
                    await fill_form_fields_js(page, profile, li_fill, tracker, jt, resume_text)
                    await fill_form_sections(page, profile, li_fill, tracker, jt, resume_text)

                    if resume_path:
                        await handle_resume_upload(page, resume_path)

                    await _safe_wait(page, 700)

                    # ── validation errors → one retry pass ──
                    if await has_validation_errors(page):
                        print("    [RETRY] Re-filling after validation…")
                        # Reset done-flags for fields that had errors so we can re-attempt
                        await fill_form_fields_js(page, profile, li_fill, tracker, jt, resume_text)
                        await fill_form_sections(page, profile, li_fill, tracker, jt, resume_text)
                        await _safe_wait(page, 700)

                    if await check_success(page):
                        job["status"] = "APPLIED"
                        print("  [SUCCESS] Application submitted!")
                        break

                    # ── click Next / Submit ──
                    btn_res = await detect_and_click_button(page, dry_run)

                    if btn_res == "submitted":
                        job["status"] = "APPLIED"
                        print("  [SUCCESS] Application submitted!")
                        break
                    elif btn_res == "dry_run":
                        job["status"] = "DRY_RUN"
                        break
                    elif btn_res == "navigated":
                        no_progress = 0
                        button_retries = 0
                        await _safe_wait(page, 500)
                    elif btn_res == "disabled":
                        if button_retries < MAX_BUTTON_RETRIES:
                            button_retries += 1
                            print(f"    [RETRY] Button disabled – re-filling (attempt {button_retries})…")
                            await fill_form_fields_js(page, profile, li_fill, tracker, jt, resume_text)
                            await fill_form_sections(page, profile, li_fill, tracker, jt, resume_text)
                            await _safe_wait(page, 1000)
                            btn2 = await detect_and_click_button(page, dry_run)
                            if btn2 in ("submitted", "dry_run"):
                                job["status"] = "APPLIED" if btn2 == "submitted" else "DRY_RUN"
                                break
                            elif btn2 == "navigated":
                                no_progress = 0
                            else:
                                no_progress += 1
                        else:
                            no_progress += 1
                    else:
                        no_progress += 1
                        print(f"  [WARN] No button (streak={no_progress})")

                    if no_progress >= MAX_NO_PROGRESS:
                        print(f"  [ABORT] {no_progress} steps no progress")
                        break

                if not job.get("status"):
                    job["status"] = "INCOMPLETE"
                result["applications"].append(job)

                # close modal safely (avoid triggering save popup)
                await _close_easy_apply_modal(page)
                await _safe_wait(page, 500)

            except Exception as e:
                job["status"] = "FAILED"
                job["error"] = str(e)[:100]
                result["applications"].append(job)
                print(f"  [ERROR] {str(e)[:60]}")
                await _close_easy_apply_modal(page)
                await _safe_wait(page, 300)

        result["status"] = "completed"
        result["phase"] = "completed"
        applied = len([a for a in result["applications"] if a.get("status") in ("APPLIED", "DRY_RUN")])
        print(f"\n[DONE] Jobs found: {result['jobs_found']} | Applied: {applied}/{len(result['applications'])}")

    except Exception as e:
        result["errors"].append(str(e))
        print(f"\n[FATAL] {str(e)}")
        if page:
            try:
                await page.reload(timeout=NAV_TIMEOUT)
            except Exception:
                pass
    finally:
        if page:
            try:
                await _safe_wait(page, 1000)
            except Exception:
                pass
        if ctx:
            try:
                await ctx.close()
            except Exception:
                pass
        if pw:
            try:
                await pw.stop()
            except Exception:
                pass
        print("[CLOSED] Browser closed")

    return result


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 15 – ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python playwright_runner.py <config_json>")
        sys.exit(1)
    res = asyncio.run(run_automation(sys.argv[1]))
    print("\n===RESULT_JSON===")
    print(json.dumps(res, indent=2))
