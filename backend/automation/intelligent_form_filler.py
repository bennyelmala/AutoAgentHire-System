"""
Intelligent Form Filler — Production-ready LinkedIn Easy Apply automation.

Handles:
  - Native <select> (React-controlled) dropdowns
  - LinkedIn custom ARIA listbox dropdowns
  - Numeric / number input fields (CTC, CGPA, salary, years)
  - Radio buttons, checkboxes, text inputs, textareas
  - Pre-Next validation sweep  (fix invalid / empty *required* fields)
  - Post-Next error recovery    (detect error banners, re-fill, retry once)
"""

import asyncio
import random
import re
from typing import Any, Dict, List, Optional, Tuple
from playwright.async_api import Page, ElementHandle

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PLACEHOLDER_TEXTS = frozenset({
    'select an option', 'select', 'choose', 'please select',
    '--', '- select -', 'pick one', '-- select --',
    'choose an option', 'select option', '',
})

NUMERIC_LABEL_KEYWORDS = [
    'salary', 'ctc', 'compensation', 'pay', 'package',
    'years', 'experience', 'months',
    'percentage', 'cgpa', 'gpa', 'grade point',
    'notice period', 'how soon',
]

YES_NO_QUESTION_CUES = [
    'are you', 'do you', 'have you', 'will you', 'can you', 'could you',
    'willing', 'available', 'agree', 'authorized', 'fine with',
    'immediate joiner', 'open to', 'eligible',
]

# JS: React-safe setter for native <select>
JS_SET_SELECT = """
(el, val) => {
    let opt = Array.from(el.options).find(
        o => o.value === val || o.text.trim().toLowerCase() === val.toLowerCase()
    );
    if (!opt) return false;
    let nativeSetter = Object.getOwnPropertyDescriptor(
        HTMLSelectElement.prototype, 'value'
    ).set;
    nativeSetter.call(el, opt.value);
    el.dispatchEvent(new Event('input',  {bubbles: true}));
    el.dispatchEvent(new Event('change', {bubbles: true}));
    return true;
}
"""

# JS: Walk DOM upward to find the question / label text for any element
JS_FIND_LABEL = """
el => {
    // 1. <label for=id>
    if (el.id) {
        let lbl = document.querySelector('label[for="' + el.id + '"]');
        if (lbl && lbl.innerText.trim()) return lbl.innerText.trim();
    }
    // 2. aria-labelledby
    let lblBy = el.getAttribute('aria-labelledby');
    if (lblBy) {
        for (let id of lblBy.split(/\\s+/)) {
            let node = document.getElementById(id);
            if (node && node.innerText.trim()) return node.innerText.trim();
        }
    }
    // 3. aria-label
    let al = el.getAttribute('aria-label');
    if (al && al.trim()) return al.trim();
    // 4. Walk up DOM — LinkedIn wraps questions in fb-dash-form-element divs
    let n = el.parentElement;
    for (let i = 0; i < 8 && n; i++) {
        let lbl = n.querySelector('label, legend, [data-test-form-element-label], .fb-dash-form-element__label');
        if (lbl) { let t = lbl.innerText.trim(); if (t) return t; }
        let sib = n.previousElementSibling;
        if (sib) { let t = sib.innerText.trim(); if (t && t.length < 300) return t; }
        n = n.parentElement;
    }
    // 5. name attribute
    return el.getAttribute('name') || '';
}
"""


class IntelligentFormFiller:
    """Fills LinkedIn Easy Apply forms with intelligent defaults."""

    def __init__(self, page: Page, user_profile: Dict, resume_text: str = "",
                 groq_api_key: str = "", gemini_api_key: str = ""):
        self.page = page
        self.user_profile = user_profile
        self.resume_text = resume_text
        self.groq_api_key = groq_api_key
        self.gemini_api_key = gemini_api_key
        # AI fallback
        self._ai_service = None
        self.ai_cache: Dict[str, str] = {}
        # Performance: field dedup cache — reset each fill_application_form() call
        self.processed_fields: set = set()
        self._extract_resume_data()
        self._build_smart_defaults()
        self._init_ai_service()

    # ------------------------------------------------------------------
    # Resume extraction
    # ------------------------------------------------------------------
    def _extract_resume_data(self):
        if not self.resume_text:
            return
        phone_m = re.search(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', self.resume_text)
        if phone_m and 'phone_number' not in self.user_profile:
            self.user_profile['phone_number'] = phone_m.group(0)
        li = re.search(r'linkedin\.com/in/[\w-]+', self.resume_text, re.I)
        if li and 'linkedin_url' not in self.user_profile:
            self.user_profile['linkedin_url'] = f"https://{li.group(0)}"
        gh = re.search(r'github\.com/[\w-]+', self.resume_text, re.I)
        if gh and 'github_url' not in self.user_profile:
            self.user_profile['github_url'] = f"https://{gh.group(0)}"
        for pat in [r'(\d+)\+?\s*years?\s+(?:of\s+)?experience',
                    r'experience:?\s*(\d+)\+?\s*years?']:
            m = re.search(pat, self.resume_text, re.I)
            if m and 'years_experience' not in self.user_profile:
                self.user_profile['years_experience'] = m.group(1)
                break

    # ------------------------------------------------------------------
    # Smart defaults table
    # ------------------------------------------------------------------
    def _build_smart_defaults(self):
        p = self.user_profile
        self.smart_defaults: Dict[str, Dict] = {
            'work_authorization': {
                'patterns': ['authorized to work', 'work authorization', 'legal authorization', 'visa status'],
                'answer': 'Yes',
            },
            'sponsorship': {
                'patterns': ['require sponsorship', 'need sponsorship', 'visa sponsorship',
                             'now or in the future require sponsorship'],
                'answer': p.get('requires_sponsorship', 'No'),
            },
            'age_18': {
                'patterns': ['at least 18', '18 years old', 'over 18', 'above 18'],
                'answer': 'Yes',
            },
            'years_experience': {
                'patterns': ['years of experience', 'years experience', 'how many years',
                             'years of work experience'],
                'answer': p.get('years_experience', '3'),
            },
            'start_date': {
                'patterns': ['start date', 'available to start', 'earliest start', 'when can you start'],
                'answer': p.get('start_date', 'Immediately'),
            },
            'start_soon_numeric': {
                'patterns': ['how soon can you start', 'how soon can you join',
                             'notice period in days', 'days notice'],
                'answer': str(p.get('notice_period_days', '0')),
            },
            'immediate_joiner': {
                'patterns': ['immediate joiner', 'immediately join', 'join immediately',
                             'are you immediate'],
                'answer': 'Yes',
            },
            'built_experience': {
                'patterns': ['have you built', 'have you developed', 'have you worked with',
                             'have you used', 'do you have experience', 'do you have hands-on',
                             'are you experienced', 'can you demonstrate', 'production-level',
                             'api integration'],
                'answer': 'Yes',
            },
            'deployed_backend': {
                'patterns': ['deployed backend', 'backend services', 'deployed.*gcp',
                             'deployed.*aws', 'gcp or aws', 'aws or gcp',
                             'cloud.*deploy', 'deploy.*cloud'],
                'answer': 'Yes',
            },
            'llm_integration': {
                'patterns': ['integrated llm', 'llm api', 'openai.*anthropic',
                             'anthropic.*openai', 'llm.*production',
                             'integrated.*api.*production', 'production system'],
                'answer': 'Yes',
            },
            'llm_provider_experience': {
                'patterns': ['llm provider', 'openai, claude', 'claude, or gemini',
                             'openai.*claude.*gemini', 'openai or gemini',
                             'experience with.*llm', 'experience with at least one llm',
                             'large language model'],
                'answer': 'Yes',
            },
            'workflow_integration': {
                'patterns': ['workflow/integration', 'workflow integration',
                             'integration engineering', 'llm-based solution',
                             'llm based solution', 'delivery of llm',
                             'hands-on delivery'],
                'answer': 'Yes',
            },
            'ai_experience': {
                'patterns': ['ai experience', 'artificial intelligence',
                             'machine learning experience', 'ml experience',
                             'deep learning', 'ai/ml', 'ml/ai',
                             'generative ai', 'genai'],
                'answer': 'Yes',
            },
            'structured_experiments': {
                'patterns': ['structured experiment', 'run.*experiment',
                             'improve.*ai.*quality', 'ai output quality',
                             'output quality.*reliability', 'quality.*reliability'],
                'answer': 'Yes',
            },
            'salary': {
                'patterns': ['salary expectation', 'expected salary', 'compensation expectation',
                             'expectation ctc', 'expected ctc'],
                'answer': p.get('expected_salary', ''),
            },
            'current_ctc': {
                'patterns': ['current ctc', 'what is your ctc', 'present ctc', 'current salary',
                             'current compensation', 'current package', 'annual ctc'],
                'answer': str(p.get('current_ctc', p.get('expected_salary', '0'))),
            },
            'notice_period': {
                'patterns': ['notice period', 'current notice', 'how much notice'],
                'answer': p.get('notice_period', '0'),
            },
            'relocation': {
                'patterns': ['willing to relocate', 'open to relocation', 'relocate'],
                'answer': 'Yes' if str(p.get('willing_to_relocate', 'Yes')).lower() in ('yes', 'true', '1', 'y') else 'No',
            },
            'remote_work': {
                'patterns': ['remote', 'work from home', 'hybrid', 'on-site', 'onsite'],
                'answer': 'Yes',
            },
            'referral': {
                'patterns': ['referred by', 'referral', 'how did you hear'],
                'answer': 'LinkedIn',
            },
            'fulltime_intern': {
                'patterns': ['full-time intern', 'full time intern', 'willing to work as.*intern',
                             'work as a full-time intern'],
                'answer': 'Yes',
            },
            'fulltime_commit': {
                'patterns': ['commit full-time', 'commit full time', 'available to commit',
                             'commit for the next', 'commit.*internship'],
                'answer': 'Yes',
            },
            'fulltime_conversion': {
                'patterns': ['converted into a full-time', 'full-time employee after internship',
                             'fine with getting converted', 'ppo', 'pre-placement offer'],
                'answer': 'Yes',
            },
            'graduate_year': {
                'patterns': ['2025 or 2026 graduate', '2026 graduate', 'graduating in',
                             'graduation year', 'are you a 202'],
                'answer': 'Yes',
            },
            'internship_months': {
                'patterns': ['months of internship', 'internship experience', 'months.*intern'],
                'answer': str(p.get('internship_months', '6')),
            },
            'cgpa': {
                'patterns': ['cgpa', 'gpa', 'grade point'],
                'answer': str(p.get('cgpa', '8.0')),
            },
            'drivers_license': {
                'patterns': ["driver's license", 'drivers license', 'driving license', 'valid license'],
                'answer': p.get('drivers_license', 'Yes'),
            },
            'disability': {
                'patterns': ['disability', 'disabled'],
                'answer': 'No',
            },
            'veteran': {
                'patterns': ['veteran', 'military service'],
                'answer': 'No',
            },
            'gender': {
                'patterns': ['gender', 'sex'],
                'answer': p.get('gender', 'Male'),
            },
        }

    # ------------------------------------------------------------------
    # AI service initialisation
    # ------------------------------------------------------------------
    def _init_ai_service(self):
        """Initialise AI service using provided API keys or environment variables."""
        try:
            from backend.llm.multi_ai_service import MultiAIService
            if self.groq_api_key:
                self._ai_service = MultiAIService(provider="groq", api_key=self.groq_api_key)
                print("   [AI] Initialized Groq for form fallback")
            elif self.gemini_api_key:
                self._ai_service = MultiAIService(provider="gemini", api_key=self.gemini_api_key)
                print("   [AI] Initialized Gemini for form fallback")
            else:
                # Auto-detect from environment
                svc = MultiAIService()
                self._ai_service = svc if svc.provider else None
                if self._ai_service:
                    print(f"   [AI] Auto-detected {svc.provider} for form fallback")
        except Exception as e:
            print(f"   [AI] AI service init failed (non-critical): {e}")
            self._ai_service = None

    # ------------------------------------------------------------------
    # AI fallback — answer any unknown field label
    # ------------------------------------------------------------------
    async def _ai_answer_field(self, label: str, field_type: str = "text",
                                options: Optional[List[str]] = None) -> Optional[str]:
        """Use AI to answer an unknown form field. Results are cached per label+type."""
        if not self._ai_service or not label.strip():
            return None

        cache_key = f"{label.strip().lower()}:{field_type}"
        if cache_key in self.ai_cache:
            return self.ai_cache[cache_key]

        try:
            resume_summary = (
                self.resume_text[:1500] if self.resume_text
                else str(self.user_profile)[:500]
            )

            if field_type == "numeric":
                type_instruction = (
                    "Return ONLY a single number (integer or decimal). "
                    "Never return text like N/A, none, or any words."
                )
            elif field_type in ("radio", "dropdown") and options:
                opts_str = ", ".join(options)
                type_instruction = f"Return ONLY one of these exact options: {opts_str}"
            else:
                type_instruction = "Return a short professional answer in 1-10 words."

            prompt = (
                f"You are filling out a job application form.\n"
                f"Question: {label}\n"
                f"Applicant resume summary: {resume_summary}\n"
                f"{type_instruction}\n"
                f"Answer:"
            )

            loop = asyncio.get_event_loop()
            _svc = self._ai_service  # local ref — already None-checked above
            response = await loop.run_in_executor(
                None, lambda: _svc.generate_text(prompt)  # type: ignore[union-attr]
            )

            if response:
                answer = str(response).strip().strip('"').strip("'")
                if field_type == "numeric":
                    # Extract first numeric token; fall back to safe default
                    first_token = answer.split()[0] if answer.split() else "1"
                    cleaned = re.sub(r'[^\d.]', '', first_token)
                    answer = cleaned if cleaned else "1"
                self.ai_cache[cache_key] = answer
                print(f'   [AI] Answered "{label[:40]}" ({field_type}) -> "{answer[:30]}"')
                return answer
        except Exception as e:
            print(f'   [AI] Failed for "{label[:40]}": {e}')
        return None

    # ==================================================================
    # PUBLIC — fill entire visible page
    # ==================================================================
    async def fill_application_form(self) -> Dict:
        filled = 0
        errors: List[str] = []
        self.processed_fields = set()  # reset per-page field cache
        try:
            filled += await self._fill_text_inputs()
            filled += await self._fill_textareas()
            filled += await self._fill_native_selects()
            filled += await self._fill_custom_dropdowns()
            filled += await self._fill_radio_buttons()
            filled += await self._fill_checkboxes()
            print(f"   [FORM] Done -- {filled} fields filled")
        except Exception as e:
            errors.append(str(e))
            print(f"   [FORM] Error: {e}")
        return {'status': 'SUCCESS' if not errors else 'PARTIAL',
                'filled_fields': filled, 'errors': errors}

    # ==================================================================
    # PUBLIC — pre-Next validation sweep
    # ==================================================================
    async def validate_and_fix(self) -> int:
        """Scan all required fields; re-fill any that are empty / invalid.
        Returns number of fields fixed."""
        fixed = 0
        try:
            fixed += await self._fix_empty_required_inputs()
            fixed += await self._fix_unselected_dropdowns()
            fixed += await self._fix_unselected_radios()
        except Exception as e:
            print(f"   [VALIDATE] Error during sweep: {e}")
        if fixed:
            print(f"   [VALIDATE] Fixed {fixed} invalid/empty required fields")
        return fixed

    # ==================================================================
    # PUBLIC — detect "Please enter a valid answer" and re-process
    # ==================================================================
    async def scan_and_fix_validation_errors(self) -> int:
        """Detect visible validation error spans (\"Please enter a valid answer\",
        \"This field is required\", etc.) and re-process the associated dropdown
        / input fields.  Returns number of fixes.

        Step 6 from user spec: scan for
            span:has-text(\"Please enter a valid answer\")
        and re-fill the neighbouring form element.
        """
        fixed = 0
        try:
            # Find all visible error messages
            error_els = await self.page.query_selector_all(
                '.artdeco-inline-feedback--error, '
                '[data-test-form-element-error], '
                '.fb-dash-form-element__error-field'
            )
            for err_el in error_els:
                try:
                    if not await err_el.is_visible():
                        continue
                    # Walk up to the form-element container
                    container = await err_el.evaluate_handle("""
                        el => {
                            let n = el.parentElement;
                            for (let i = 0; i < 8 && n; i++) {
                                if (n.classList.contains('fb-dash-form-element') ||
                                    n.hasAttribute('data-test-form-builder-select-container')) {
                                    return n;
                                }
                                n = n.parentElement;
                            }
                            return null;
                        }
                    """)
                    if not container or await container.evaluate('el => el === null'):
                        continue
                    container_el = container.as_element()
                    if not container_el:
                        continue

                    # Try to fix a dropdown inside this container
                    trigger = None
                    for sel in ['[role="combobox"]', '[aria-haspopup="listbox"]',
                                'select', 'button[aria-haspopup]']:
                        trigger = await container_el.query_selector(sel)
                        if trigger and await trigger.is_visible():
                            break
                        trigger = None

                    if trigger:
                        cur_text = await self._get_trigger_display_text(trigger)
                        if cur_text.lower() in PLACEHOLDER_TEXTS:
                            label = await self._get_container_label(container_el)
                            tag = (await trigger.evaluate('el => el.tagName')).lower()
                            if tag == 'select':
                                opts = await self._collect_select_options(trigger)
                                if opts:
                                    ot = [t for t, _ in opts]
                                    ov = [v for _, v in opts]
                                    chosen = self._pick_dropdown_answer(label, ot, ov)
                                    if chosen and await self._set_native_select(trigger, chosen, ot, ov):
                                        fixed += 1
                            else:
                                if await self._open_and_select_react_dropdown(trigger, label):
                                    fixed += 1
                            continue

                    # Try to fix an input inside this container
                    inp = await container_el.query_selector(
                        'input[type="text"], input[type="number"], input:not([type]), textarea'
                    )
                    if inp and await inp.is_visible():
                        cur = (await inp.input_value()).strip()
                        if not cur:
                            label = await self._label(inp)
                            inp_type = (await inp.get_attribute('type') or 'text').lower()
                            is_num = inp_type == 'number' or self._label_looks_numeric(label)
                            if is_num:
                                val = self.validate_field_value(label, self._resolve_numeric(label, ''), True) or '1'
                            else:
                                raw = self._resolve_text(label, '')
                                val = self.validate_field_value(label, raw, False)
                                if not val:
                                    ai_ans = await self._ai_answer_field(label, 'text')
                                    val = ai_ans
                            if val:
                                await inp.fill(val)
                                await inp.evaluate(
                                    'el => { el.dispatchEvent(new Event("input",{bubbles:true})); '
                                    'el.dispatchEvent(new Event("change",{bubbles:true})); }'
                                )
                                fixed += 1
                except Exception:
                    continue
        except Exception as e:
            print(f"   [VALIDATE-ERR] Error scanning validation messages: {e}")
        if fixed:
            print(f"   [VALIDATE-ERR] Fixed {fixed} fields with validation errors")
        return fixed

    # ==================================================================
    # PUBLIC — detect visible error messages on page
    # ==================================================================
    async def has_visible_errors(self) -> bool:
        """Return True if the page currently shows validation error text."""
        try:
            err_count = await self.page.evaluate("""
                () => {
                    let sels = [
                        '.artdeco-inline-feedback--error',
                        '[data-test-form-element-error]',
                        '.fb-dash-form-element__error-field',
                        '.artdeco-text-input--error',
                        'div[role="alert"]',
                    ];
                    let count = 0;
                    for (let s of sels) {
                        let nodes = document.querySelectorAll(s);
                        for (let n of nodes) {
                            if (n.offsetParent !== null && n.innerText.trim()) count++;
                        }
                    }
                    let spans = document.querySelectorAll('span, p, div');
                    let phrases = ['please enter a valid', 'enter a decimal number',
                                   'this field is required', 'please make a selection',
                                   'enter a valid answer', 'enter a number'];
                    for (let sp of spans) {
                        if (sp.offsetParent === null) continue;
                        let t = sp.innerText.toLowerCase();
                        for (let p of phrases) {
                            if (t.includes(p)) { count++; break; }
                        }
                    }
                    return count;
                }
            """)
            return err_count > 0
        except Exception:
            return False

    # ==================================================================
    # PART 5 — strict value validator
    # ==================================================================
    @staticmethod
    def validate_field_value(label: str, value: Any, is_numeric: bool = False) -> Optional[str]:
        """Return a clean string value, or None if unusable."""
        if value is None:
            return None
        s = str(value).strip()
        if not s or s.lower() in ('n/a', 'na', 'none', 'null', 'undefined', '--'):
            return None
        if is_numeric:
            cleaned = re.sub(r'[^\d.]', '', s)
            if not cleaned:
                return None
            try:
                float(cleaned)
                return cleaned
            except ValueError:
                return None
        return s

    # ------------------------------------------------------------------
    #  LABEL DETECTION
    # ------------------------------------------------------------------
    async def _label(self, el: ElementHandle) -> str:
        try:
            return (await el.evaluate(JS_FIND_LABEL)) or ""
        except Exception:
            return ""

    # ------------------------------------------------------------------
    #  TEXT INPUTS (including type=number)
    # ------------------------------------------------------------------
    async def _fill_text_inputs(self) -> int:
        filled = 0
        try:
            # Scope queries to the active <form> container for speed;
            # fall back to full page when no <form> is found.
            root = self.page
            try:
                form_handle = await self.page.query_selector(
                    "form, .jobs-easy-apply-modal__content, [data-test-modal]"
                )
                if form_handle and await form_handle.is_visible():
                    root = form_handle  # type: ignore[assignment]
            except Exception:
                pass

            inputs = await root.query_selector_all(
                'input[type="text"], input[type="number"], input[type="tel"], '
                'input:not([type])'
            )
            for inp in inputs:
                try:
                    if not await inp.is_visible():
                        continue
                    inp_type = (await inp.get_attribute('type') or 'text').lower()
                    inputmode = (await inp.get_attribute('inputmode') or '').lower()
                    label = await self._label(inp)
                    placeholder = await inp.get_attribute('placeholder') or ''
                    is_num = (inp_type == 'number'
                              or inputmode == 'numeric'
                              or self._label_looks_numeric(label + ' ' + placeholder))

                    # Skip already-processed fields (dedup cache)
                    field_key = f"input:{label.strip().lower()}:{inp_type}"
                    if field_key in self.processed_fields:
                        continue

                    cur = (await inp.input_value()).strip()
                    if cur:
                        # Valid existing value — mark and skip
                        if is_num and self.validate_field_value('', cur, True) is None:
                            pass  # invalid numeric (e.g. "N/A") — fall through to re-fill
                        else:
                            self.processed_fields.add(field_key)
                            continue

                    val: Optional[str] = None
                    if is_num:
                        raw = self._resolve_numeric(label, placeholder)
                        val = self.validate_field_value(label, raw, True)
                        if val is None:
                            # AI fallback for unknown numeric fields
                            ai_ans = await self._ai_answer_field(label, "numeric")
                            val = self.validate_field_value(label, ai_ans, True) if ai_ans else None
                        if val is None:
                            val = '1'  # safe numeric fallback — never "N/A"
                    else:
                        raw = self._resolve_text(label, placeholder)
                        val = self.validate_field_value(label, raw, False)
                        if val is None:
                            # AI fallback for unknown text fields
                            ai_ans = await self._ai_answer_field(label, "text")
                            val = self.validate_field_value(label, ai_ans, False) if ai_ans else None

                    if val:
                        await inp.fill('')
                        await inp.fill(val)
                        await inp.evaluate(
                            'el => { el.dispatchEvent(new Event("input",{bubbles:true})); '
                            'el.dispatchEvent(new Event("change",{bubbles:true})); }'
                        )
                        await asyncio.sleep(0.1)
                        filled += 1
                        self.processed_fields.add(field_key)
                        print(f'   [FORM] Input: "{label[:40]}" = "{val[:20]}"')
                except Exception as e:
                    print(f'   [FORM] Input err: {str(e)[:60]}')
        except Exception as e:
            print(f'   [FORM] Inputs scan err: {e}')
        return filled

    # ------------------------------------------------------------------
    #  TEXTAREAS
    # ------------------------------------------------------------------
    async def _fill_textareas(self) -> int:
        filled = 0
        try:
            for ta in await self.page.query_selector_all('textarea'):
                try:
                    if not await ta.is_visible():
                        continue
                    label = await self._label(ta)
                    field_key = f"textarea:{label.strip().lower()}"
                    if field_key in self.processed_fields:
                        continue
                    cur = (await ta.input_value()).strip()
                    if len(cur) > 20:
                        self.processed_fields.add(field_key)
                        continue
                    val = self._resolve_text(label, '')
                    if val is None:
                        ai_ans = await self._ai_answer_field(label, "text")
                        val = ai_ans if ai_ans else None
                    if val:
                        await ta.fill(val)
                        await asyncio.sleep(0.15)
                        filled += 1
                        self.processed_fields.add(field_key)
                        print(f'   [FORM] Textarea: "{label[:40]}"')
                except Exception:
                    continue
        except Exception:
            pass
        return filled

    # ------------------------------------------------------------------
    #  NATIVE <select> (React-safe, 3-strategy)
    # ------------------------------------------------------------------
    async def _fill_native_selects(self) -> int:
        filled = 0
        try:
            for sel in await self.page.query_selector_all('select'):
                try:
                    if not await sel.is_visible():
                        continue
                    label = await self._label(sel)
                    field_key = f"select:{label.strip().lower()}"
                    if field_key in self.processed_fields:
                        continue
                    cur_text = await sel.evaluate(
                        'el => el.options[el.selectedIndex]'
                        ' ? el.options[el.selectedIndex].text.trim() : ""'
                    )
                    if cur_text.lower() not in PLACEHOLDER_TEXTS:
                        self.processed_fields.add(field_key)
                        continue  # already answered

                    opts = await self._collect_select_options(sel)
                    if not opts:
                        continue
                    opt_texts  = [t for t, _ in opts]
                    opt_values = [v for _, v in opts]

                    chosen = self._pick_dropdown_answer(label, opt_texts, opt_values)
                    if not chosen:
                        # AI fallback for native select
                        ai_ans = await self._ai_answer_field(label, "dropdown", opt_texts)
                        if ai_ans:
                            for i, t in enumerate(opt_texts):
                                if ai_ans.lower() in t.lower() or t.lower() in ai_ans.lower():
                                    chosen = opt_values[i]
                                    break
                            if not chosen and opt_values:
                                chosen = opt_values[0]
                    if not chosen:
                        continue

                    if await self._set_native_select(sel, chosen, opt_texts, opt_values):
                        filled += 1
                        self.processed_fields.add(field_key)
                        print(f'   [FORM] Select: "{label[:40]}" -> "{chosen[:20]}"')
                except Exception as e:
                    print(f'   [FORM] Select err: {str(e)[:60]}')
        except Exception:
            pass
        return filled

    async def _collect_select_options(self, sel: ElementHandle) -> List[Tuple[str, str]]:
        """Return [(text, value), ...] excluding placeholders."""
        result: List[Tuple[str, str]] = []
        for opt in await sel.query_selector_all('option'):
            text  = (await opt.inner_text()).strip()
            value = (await opt.get_attribute('value') or '').strip()
            if text.lower() not in PLACEHOLDER_TEXTS:
                result.append((text, value or text))
        return result

    async def _set_native_select(self, sel: ElementHandle, chosen: str,
                                 opt_texts: List[str], opt_values: List[str]) -> bool:
        """Try 3 strategies to set a native <select> value. Returns True on success."""

        # Strategy 1 — React-safe JS setter (by value, then by text)
        ok = await sel.evaluate(JS_SET_SELECT, chosen)
        if not ok:
            for t in opt_texts:
                if t.lower() == chosen.lower():
                    ok = await sel.evaluate(JS_SET_SELECT, t)
                    if ok:
                        break
        if ok:
            return True

        # Strategy 2 — Playwright select_option + manual events
        try:
            await sel.select_option(value=chosen)
        except Exception:
            try:
                await sel.select_option(label=chosen)
            except Exception:
                pass
        await sel.evaluate(
            'el => { el.dispatchEvent(new Event("input",{bubbles:true})); '
            'el.dispatchEvent(new Event("change",{bubbles:true})); }'
        )
        verify = await sel.evaluate(
            'el => el.options[el.selectedIndex] ? el.options[el.selectedIndex].text.trim() : ""'
        )
        if verify.lower() not in PLACEHOLDER_TEXTS:
            return True

        # Strategy 3 — click + keyboard navigation
        await sel.click()
        await asyncio.sleep(0.25)
        target_idx = 0
        lower_chosen = chosen.lower()
        for i, t in enumerate(opt_texts):
            if t.lower() == lower_chosen:
                target_idx = i
                break
        for _ in range(target_idx + 1):
            await self.page.keyboard.press('ArrowDown')
            await asyncio.sleep(0.05)
        await self.page.keyboard.press('Enter')
        await asyncio.sleep(0.25)
        return True

    # ------------------------------------------------------------------
    #  LINKEDIN CUSTOM DROPDOWNS  (ARIA listbox / combobox)
    #  Robust 5-strategy handler for React-based LinkedIn dropdowns
    # ------------------------------------------------------------------

    # JS: Collect all visible LinkedIn dropdown containers on the page.
    # Returns an array of {index, label, currentValue, triggerSelector} objects.
    JS_FIND_DROPDOWN_CONTAINERS = """
    () => {
        const PLACEHOLDERS = new Set([
            'select an option', 'select', 'choose', 'please select',
            '--', '- select -', 'pick one', '-- select --',
            'choose an option', 'select option', ''
        ]);
        const results = [];

        // Strategy A: fb-dash-form-element containers with a <select> or button trigger
        document.querySelectorAll(
            '.fb-dash-form-element, [data-test-form-builder-select-container]'
        ).forEach((container, idx) => {
            if (container.offsetParent === null) return;
            let labelEl = container.querySelector(
                'label, legend, [data-test-form-element-label], .fb-dash-form-element__label, span.t-14'
            );
            let labelTxt = labelEl ? labelEl.innerText.trim() : '';

            // Dropdown trigger: the clickable element
            let trigger = container.querySelector(
                'select, [role="combobox"], [aria-haspopup="listbox"], ' +
                'button[aria-haspopup], .artdeco-dropdown__trigger'
            );
            if (!trigger || trigger.offsetParent === null) return;
            let curVal = (trigger.innerText || trigger.value || '').trim().toLowerCase();
            if (!PLACEHOLDERS.has(curVal)) return;  // already answered

            results.push({ index: idx, label: labelTxt, tagName: trigger.tagName.toLowerCase() });
        });

        // Strategy B: Standalone ARIA triggers not inside fb-dash containers
        document.querySelectorAll(
            '[aria-haspopup="listbox"], [role="combobox"], ' +
            'button[aria-haspopup="listbox"], .artdeco-dropdown__trigger'
        ).forEach((trigger, idx) => {
            if (trigger.offsetParent === null) return;
            let curVal = (trigger.innerText || trigger.value || '').trim().toLowerCase();
            if (!PLACEHOLDERS.has(curVal)) return;

            // Skip if we already captured this via Strategy A
            let alreadyCovered = trigger.closest(
                '.fb-dash-form-element, [data-test-form-builder-select-container]'
            );
            if (alreadyCovered) return;

            // Walk up to find label
            let labelTxt = '';
            let n = trigger.parentElement;
            for (let i = 0; i < 8 && n; i++) {
                let lbl = n.querySelector('label, legend, [data-test-form-element-label]');
                if (lbl) { labelTxt = lbl.innerText.trim(); break; }
                let sib = n.previousElementSibling;
                if (sib && sib.innerText && sib.innerText.trim().length < 300) {
                    labelTxt = sib.innerText.trim(); break;
                }
                n = n.parentElement;
            }
            results.push({ index: 1000 + idx, label: labelTxt, standalone: true });
        });

        return results;
    }
    """

    async def _fill_custom_dropdowns(self) -> int:
        """Robust LinkedIn React dropdown handler.

        Detection (3 passes, in order):
          0. Locator-based — page.locator('[role="combobox"]') and
             page.locator('button[aria-haspopup="listbox"]')
          1. Container-based — .fb-dash-form-element wrappers
          2. Standalone ARIA triggers

        Each pass scrolls into view, clicks, waits, selects, and verifies.
        """
        filled = 0
        try:
            filled += await self._fill_dropdowns_via_locator()
            filled += await self._fill_dropdowns_via_containers()
            filled += await self._fill_dropdowns_via_aria_triggers()
        except Exception as e:
            print(f'   [FORM] Custom dropdown err: {e}')
        return filled

    # ------------------------------------------------------------------
    #  Strategy 0: Locator-based React dropdown handler (most reliable)
    # ------------------------------------------------------------------
    async def _fill_dropdowns_via_locator(self) -> int:
        """Use Playwright locators to find and fill React dropdowns.

        Targets:
          div[role="combobox"]
          button[aria-haspopup="listbox"]

        Follows the exact 5-step sequence:
          scroll_into_view → click → wait_for_selector → get_by_role → verify.
        """
        filled = 0
        page = self.page

        selectors = [
            '[role="combobox"]',
            'button[aria-haspopup="listbox"]',
        ]

        for selector in selectors:
            try:
                elements = await page.query_selector_all(selector)
                for el in elements:
                    try:
                        if not await el.is_visible():
                            continue

                        cur_text = await self._get_trigger_display_text(el)
                        if cur_text.lower() not in PLACEHOLDER_TEXTS:
                            continue  # already answered

                        label = await self._label(el)
                        field_key = f"dropdown:{label.strip().lower()}"
                        if field_key in self.processed_fields:
                            continue

                        # STEP 1 — Scroll into view
                        await el.scroll_into_view_if_needed()
                        await asyncio.sleep(0.05)

                        # STEP 2 — Click to open
                        await el.click()

                        # STEP 3 — Wait for options
                        try:
                            await page.wait_for_selector(
                                '[role="option"]', state="visible", timeout=2500
                            )
                        except Exception:
                            # retry with Focus + ArrowDown
                            await el.focus()
                            await page.keyboard.press('ArrowDown')
                            try:
                                await page.wait_for_selector(
                                    '[role="option"]', state="visible", timeout=2000
                                )
                            except Exception:
                                await self._close_dropdown()
                                continue

                        # Collect visible options
                        option_els = await self._collect_visible_options()
                        if not option_els:
                            await self._close_dropdown()
                            continue

                        opt_map: List[Tuple[str, ElementHandle]] = []
                        for oel in option_els:
                            try:
                                t = (await oel.inner_text()).strip()
                                if t and t.lower() not in PLACEHOLDER_TEXTS:
                                    opt_map.append((t, oel))
                            except Exception:
                                continue

                        if not opt_map:
                            await self._close_dropdown()
                            continue

                        opt_texts = [t for t, _ in opt_map]

                        # STEP 4 — Pick best option
                        desired = self._pick_dropdown_answer(label, opt_texts, opt_texts)
                        if not desired:
                            ai_ans = await self._ai_answer_field(label, "dropdown", opt_texts)
                            if ai_ans:
                                desired = ai_ans

                        chosen_el = None
                        chosen_text = ""
                        if desired:
                            dl = desired.lower()
                            for t, oel in opt_map:
                                if t.lower() == dl:
                                    chosen_el = oel; chosen_text = t; break
                            if not chosen_el:
                                for t, oel in opt_map:
                                    if dl in t.lower() or t.lower() in dl:
                                        chosen_el = oel; chosen_text = t; break

                        # Fallback: prefer "Yes"
                        if not chosen_el:
                            for t, oel in opt_map:
                                if t.lower() in ('yes', 'y'):
                                    chosen_el = oel; chosen_text = t; break
                        if not chosen_el:
                            idx = 1 if len(opt_map) > 1 else 0
                            chosen_el = opt_map[idx][1]
                            chosen_text = opt_map[idx][0]

                        # Click option
                        try:
                            await chosen_el.scroll_into_view_if_needed()
                            await chosen_el.click()
                        except Exception:
                            try:
                                await chosen_el.evaluate('el => el.click()')
                            except Exception:
                                await self._close_dropdown()
                                continue

                        await asyncio.sleep(0.2)

                        # STEP 5 — Verify selection stuck
                        verify = await self._get_trigger_display_text(el)
                        if verify.lower() in PLACEHOLDER_TEXTS:
                            # Retry once
                            await el.scroll_into_view_if_needed()
                            await el.click()
                            try:
                                await page.wait_for_selector(
                                    '[role="option"]', state="visible", timeout=2000
                                )
                            except Exception:
                                pass
                            option_els2 = await self._collect_visible_options()
                            for oel2 in option_els2:
                                try:
                                    t2 = (await oel2.inner_text()).strip()
                                    if t2.lower() == chosen_text.lower():
                                        await oel2.click()
                                        await asyncio.sleep(0.2)
                                        break
                                except Exception:
                                    continue
                            verify2 = await self._get_trigger_display_text(el)
                            if verify2.lower() in PLACEHOLDER_TEXTS:
                                print(f'   [FORM] Locator dropdown "{label[:40]}" — STILL placeholder after retry')
                                continue

                        filled += 1
                        self.processed_fields.add(field_key)
                        print(f'   [FORM] LocatorDD: "{label[:40]}" -> "{chosen_text[:30]}"')

                    except Exception as e:
                        print(f'   [FORM] Locator dropdown err: {str(e)[:80]}')
                        try:
                            await page.keyboard.press('Escape')
                        except Exception:
                            pass
            except Exception:
                pass

        return filled

    async def _fill_dropdowns_via_containers(self) -> int:
        """Strategy 1: Find LinkedIn form-element containers with dropdown triggers."""
        filled = 0
        try:
            containers = await self.page.query_selector_all(
                '.fb-dash-form-element, '
                '[data-test-form-builder-select-container]'
            )
            for container in containers:
                try:
                    if not await container.is_visible():
                        continue
                    label = await self._get_container_label(container)
                    field_key = f"dropdown:{label.strip().lower()}"
                    if field_key in self.processed_fields:
                        continue
                    result = await self._handle_single_dropdown_container(container)
                    if result:
                        filled += 1
                        self.processed_fields.add(field_key)
                except Exception as e:
                    print(f'   [FORM] Container dropdown err: {str(e)[:80]}')
                    try:
                        await self.page.keyboard.press('Escape')
                    except Exception:
                        pass
        except Exception:
            pass
        return filled

    async def _handle_single_dropdown_container(self, container: ElementHandle) -> bool:
        """Process a single .fb-dash-form-element dropdown container.
        Returns True if we successfully selected a value."""

        # Find the trigger element inside the container
        trigger = None
        for sel in [
            'select',
            '[role="combobox"]',
            '[aria-haspopup="listbox"]',
            'button[aria-haspopup]',
            '.artdeco-dropdown__trigger',
            'button',  # last resort — any button inside the form element
        ]:
            trigger = await container.query_selector(sel)
            if trigger and await trigger.is_visible():
                break
            trigger = None

        if not trigger:
            return False

        # Check current value — skip if already answered
        cur_text = await self._get_trigger_display_text(trigger)
        if cur_text.lower() not in PLACEHOLDER_TEXTS:
            return False  # already has a real selection

        # Get question label from the container
        label = await self._get_container_label(container)

        # If it's a native <select>, delegate to the native handler
        tag = (await trigger.evaluate('el => el.tagName')).lower()
        if tag == 'select':
            opts = await self._collect_select_options(trigger)
            if opts:
                opt_texts = [t for t, _ in opts]
                opt_values = [v for _, v in opts]
                chosen = self._pick_dropdown_answer(label, opt_texts, opt_values)
                if chosen and await self._set_native_select(trigger, chosen, opt_texts, opt_values):
                    print(f'   [FORM] Select(container): "{label[:40]}" -> "{chosen[:20]}"')
                    return True
            return False

        # React dropdown — open, select, verify
        return await self._open_and_select_react_dropdown(trigger, label)

    async def _fill_dropdowns_via_aria_triggers(self) -> int:
        """Strategy 2: Find standalone ARIA dropdown triggers not inside containers.

        Detects:  div[role="combobox"]  |  button[aria-haspopup="listbox"]
                  div:text("Select an option")  |  .artdeco-dropdown__trigger
        """
        filled = 0
        try:
            triggers = await self.page.query_selector_all(
                '[aria-haspopup="listbox"], '
                '[role="combobox"], '
                'button[aria-haspopup="listbox"], '
                'div[role="combobox"], '
                '.artdeco-dropdown__trigger'
            )
            for trigger in triggers:
                try:
                    if not await trigger.is_visible():
                        continue

                    # Skip if inside a container we already processed
                    in_container = await trigger.evaluate(
                        'el => !!el.closest(".fb-dash-form-element, '
                        '[data-test-form-builder-select-container]")'
                    )
                    if in_container:
                        continue

                    cur_text = await self._get_trigger_display_text(trigger)
                    if cur_text.lower() not in PLACEHOLDER_TEXTS:
                        continue

                    label = await self._label(trigger)
                    field_key = f"dropdown:{label.strip().lower()}"
                    if field_key in self.processed_fields:
                        continue

                    if await self._open_and_select_react_dropdown(trigger, label):
                        filled += 1
                        self.processed_fields.add(field_key)
                except Exception:
                    try:
                        await self.page.keyboard.press('Escape')
                    except Exception:
                        pass
        except Exception:
            pass
        return filled

    async def _get_trigger_display_text(self, trigger: ElementHandle) -> str:
        """Get the currently displayed text of a dropdown trigger."""
        try:
            # Try innerText first (works for React dropdowns showing "Select an option")
            text = (await trigger.inner_text()).strip()
            if text:
                return text
            # Fallback: value property (for <select> or input-based triggers)
            val = await trigger.evaluate('el => el.value || ""')
            return val.strip()
        except Exception:
            return ""

    async def _get_container_label(self, container: ElementHandle) -> str:
        """Extract the question label from a form-element container."""
        try:
            label_el = await container.query_selector(
                'label, legend, '
                '[data-test-form-element-label], '
                '.fb-dash-form-element__label, '
                'span.t-14.t-bold'
            )
            if label_el:
                text = (await label_el.inner_text()).strip()
                if text:
                    return text
            # Fallback: walk up to find label via JS
            return await container.evaluate("""
                el => {
                    let lbl = el.querySelector('label, legend, span.t-14');
                    if (lbl && lbl.innerText.trim()) return lbl.innerText.trim();
                    let prev = el.previousElementSibling;
                    if (prev && prev.innerText && prev.innerText.trim().length < 300)
                        return prev.innerText.trim();
                    return '';
                }
            """)
        except Exception:
            return ""

    async def _open_and_select_react_dropdown(
        self, trigger: ElementHandle, label: str
    ) -> bool:
        """Open a React/ARIA dropdown, select the best option, verify it stuck.
        Returns True on success.

        Selection priority (Problem 2):
          1. smart_defaults match
          2. Keyword-based Yes/No for: relocate / authorized / willing / experience
          3. AI fallback when api_key is provided
          4. Prefer "Yes" option
          5. First valid option
        """

        for attempt in range(2):  # retry once if selection doesn't stick
            option_els = await self._open_dropdown(trigger)
            if not option_els:
                if attempt == 0:
                    print(f'   [FORM] Dropdown "{label[:40]}" — could not open, retrying...')
                    await asyncio.sleep(0.4)
                    continue
                print(f'   [FORM] Dropdown "{label[:40]}" — failed to open after retry')
                return False

            # Build option map
            opt_map: List[Tuple[str, ElementHandle]] = []
            for oel in option_els:
                try:
                    t = (await oel.inner_text()).strip()
                    if t and t.lower() not in PLACEHOLDER_TEXTS:
                        opt_map.append((t, oel))
                except Exception:
                    continue

            if not opt_map:
                await self._close_dropdown()
                print(f'   [FORM] Dropdown "{label[:40]}" — no valid options found')
                return False

            opt_texts = [t for t, _ in opt_map]
            desired = self._pick_dropdown_answer(label, opt_texts, opt_texts)

            # AI fallback when smart_defaults gave no answer
            if not desired and attempt == 0:
                ai_ans = await self._ai_answer_field(label, "dropdown", opt_texts)
                if ai_ans:
                    desired = ai_ans

            # Find the best matching option element
            chosen_el = None
            chosen_text = ""
            if desired:
                dl = desired.lower()
                for t, el in opt_map:
                    if t.lower() == dl:
                        chosen_el = el; chosen_text = t; break
                if not chosen_el:
                    for t, el in opt_map:
                        if dl in t.lower() or t.lower() in dl:
                            chosen_el = el; chosen_text = t; break

            # Fallback: prefer "Yes", then index 1 (skip first placeholder if any), then [0]
            if not chosen_el:
                for t, el in opt_map:
                    if t.lower() in ('yes', 'y'):
                        chosen_el = el; chosen_text = t; break
            if not chosen_el:
                # Use index 1 if available (index 0 may be a secondary placeholder)
                chosen_idx = 1 if len(opt_map) > 1 else 0
                chosen_el = opt_map[chosen_idx][1]
                chosen_text = opt_map[chosen_idx][0]

            # Click the option
            try:
                await chosen_el.scroll_into_view_if_needed()
                await asyncio.sleep(0.05)
                await chosen_el.click()
                await asyncio.sleep(0.25)
            except Exception:
                try:
                    await chosen_el.evaluate('el => el.click()')
                    await asyncio.sleep(0.25)
                except Exception:
                    await self._close_dropdown()
                    continue

            # Verify the selection stuck
            verify_text = await self._get_trigger_display_text(trigger)
            if verify_text.lower() in PLACEHOLDER_TEXTS:
                if attempt == 0:
                    print(f'   [FORM] Dropdown "{label[:40]}" — selection didn\'t stick, retrying...')
                    await asyncio.sleep(0.3)
                    continue  # retry
                else:
                    print(f'   [FORM] Dropdown "{label[:40]}" — STILL placeholder after retry')
                    return False

            print(f'   [FORM] Dropdown: "{label[:40]}" -> "{chosen_text[:30]}"')
            return True

        return False

    async def _open_dropdown(self, trigger: ElementHandle) -> List[ElementHandle]:
        """Try multiple strategies to open a dropdown and return option elements.

        Strategies:
          1. scroll_into_view + direct click → wait_for_selector('[role="option"]')
          2. Focus + ArrowDown → wait_for_selector('[role="option"]')
          3. Click again + longer wait_for_selector
          4. JS mousedown+click events → wait_for_selector
        """
        page = self.page

        # -- Strategy 1: Scroll into view + direct click --
        try:
            await trigger.scroll_into_view_if_needed()
            await asyncio.sleep(0.05)
            await trigger.click()
            try:
                await page.wait_for_selector('[role="option"]', state="visible", timeout=2000)
            except Exception:
                pass
            options = await self._collect_visible_options()
            if options:
                return options
        except Exception:
            pass

        # -- Strategy 2: Focus + ArrowDown --
        try:
            await trigger.focus()
            await asyncio.sleep(0.1)
            await page.keyboard.press('ArrowDown')
            try:
                await page.wait_for_selector('[role="option"]', state="visible", timeout=2000)
            except Exception:
                pass
            options = await self._collect_visible_options()
            if options:
                return options
        except Exception:
            pass

        # -- Strategy 3: Click again + longer wait --
        try:
            await trigger.scroll_into_view_if_needed()
            await trigger.click()
            try:
                await page.wait_for_selector('[role="option"]', state="visible", timeout=3000)
            except Exception:
                await asyncio.sleep(0.8)
            options = await self._collect_visible_options()
            if options:
                return options
        except Exception:
            pass

        # -- Strategy 4: JS dispatch mousedown + click events --
        try:
            await trigger.evaluate("""
                el => {
                    el.dispatchEvent(new MouseEvent('mousedown', {bubbles: true}));
                    el.dispatchEvent(new MouseEvent('mouseup',   {bubbles: true}));
                    el.dispatchEvent(new MouseEvent('click',     {bubbles: true}));
                }
            """)
            try:
                await page.wait_for_selector('[role="option"]', state="visible", timeout=2000)
            except Exception:
                await asyncio.sleep(0.5)
            options = await self._collect_visible_options()
            if options:
                return options
        except Exception:
            pass

        return []

    async def _collect_visible_options(self) -> List[ElementHandle]:
        """Collect all visible [role="option"] elements anywhere on the page."""
        try:
            # Primary: standard ARIA options
            options = await self.page.query_selector_all('[role="option"]')
            visible = []
            for opt in options:
                try:
                    if await opt.is_visible():
                        visible.append(opt)
                except Exception:
                    continue
            if visible:
                return visible

            # Fallback: LinkedIn sometimes uses [role="listbox"] > div without role="option"
            listboxes = await self.page.query_selector_all('[role="listbox"]')
            for lb in listboxes:
                try:
                    if not await lb.is_visible():
                        continue
                    children = await lb.query_selector_all('div, li, span')
                    for child in children:
                        try:
                            text = (await child.inner_text()).strip()
                            if text and await child.is_visible() and text.lower() not in PLACEHOLDER_TEXTS:
                                visible.append(child)
                        except Exception:
                            continue
                    if visible:
                        return visible
                except Exception:
                    continue

            # Fallback: artdeco-dropdown__content items
            dropdown_items = await self.page.query_selector_all(
                '.artdeco-dropdown__content li, '
                '.artdeco-dropdown__content [role="option"], '
                '.artdeco-dropdown__content button'
            )
            for item in dropdown_items:
                try:
                    if await item.is_visible():
                        visible.append(item)
                except Exception:
                    continue
            return visible
        except Exception:
            return []

    async def _close_dropdown(self):
        """Close any open dropdown by pressing Escape."""
        try:
            await self.page.keyboard.press('Escape')
            await asyncio.sleep(0.2)
        except Exception:
            pass

    # ------------------------------------------------------------------
    #  RADIO BUTTONS
    # ------------------------------------------------------------------
    async def _fill_radio_buttons(self) -> int:
        filled = 0
        try:
            radios = await self.page.query_selector_all('input[type="radio"]')
            groups: Dict[str, List[ElementHandle]] = {}
            for r in radios:
                name = await r.get_attribute('name')
                if name:
                    groups.setdefault(name, []).append(r)

            for _, group in groups.items():
                try:
                    if any([await r.is_checked() for r in group]):
                        continue
                    label = await self._label(group[0])
                    field_key = f"radio:{label.strip().lower()}"
                    if field_key in self.processed_fields:
                        continue

                    opts: List[str] = []
                    for r in group:
                        rid = await r.get_attribute('id')
                        rl = ''
                        if rid:
                            lbl = await self.page.query_selector(f'label[for="{rid}"]')
                            if lbl:
                                rl = (await lbl.inner_text()).strip()
                        if not rl:
                            rl = await r.get_attribute('value') or ''
                        opts.append(rl)

                    idx = self._pick_radio_answer(label, opts)
                    if idx is None and self._ai_service:
                        # AI fallback for radio buttons
                        ai_ans = await self._ai_answer_field(label, "radio", opts)
                        if ai_ans:
                            al = ai_ans.lower()
                            for i, o in enumerate(opts):
                                if al in o.lower() or o.lower() in al:
                                    idx = i
                                    break
                            if idx is None:
                                idx = 0

                    if idx is not None and idx < len(group):
                        rid = await group[idx].get_attribute('id')
                        clicked = False
                        if rid:
                            lbl_el = await self.page.query_selector(f'label[for="{rid}"]')
                            if lbl_el:
                                await lbl_el.click()
                                clicked = True
                        if not clicked:
                            await group[idx].click()
                        await asyncio.sleep(0.15)
                        filled += 1
                        self.processed_fields.add(field_key)
                        print(f'   [FORM] Radio: "{label[:40]}" -> "{opts[idx][:20]}"')
                except Exception:
                    continue
        except Exception:
            pass
        return filled

    # ------------------------------------------------------------------
    #  CHECKBOXES
    # ------------------------------------------------------------------
    async def _fill_checkboxes(self) -> int:
        filled = 0
        try:
            for cb in await self.page.query_selector_all('input[type="checkbox"]'):
                try:
                    if await cb.is_checked():
                        continue
                    label = (await self._label(cb)).lower()
                    yes_words = ['certif', 'agree', 'consent', 'acknowledge', 'confirm',
                                 'understand', 'accurate', 'complete']
                    no_words = ['subscribe', 'marketing', 'newsletter', 'promotional']
                    if any(w in label for w in yes_words) and not any(w in label for w in no_words):
                        await cb.click()
                        await asyncio.sleep(0.2)
                        filled += 1
                except Exception:
                    continue
        except Exception:
            pass
        return filled

    # ==================================================================
    #  VALIDATION SWEEP — fix empty / invalid required fields
    # ==================================================================
    async def _fix_empty_required_inputs(self) -> int:
        fixed = 0
        try:
            for inp in await self.page.query_selector_all(
                'input[required], textarea[required], '
                'input[aria-required="true"], textarea[aria-required="true"]'
            ):
                try:
                    if not await inp.is_visible():
                        continue
                    cur = (await inp.input_value()).strip()
                    inp_type = (await inp.get_attribute('type') or 'text').lower()
                    inputmode = (await inp.get_attribute('inputmode') or '').lower()
                    label = await self._label(inp)
                    is_num = (inp_type == 'number' or inputmode == 'numeric'
                              or self._label_looks_numeric(label))

                    need_fix = False
                    if not cur:
                        need_fix = True
                    elif is_num and self.validate_field_value(label, cur, True) is None:
                        need_fix = True  # has value but non-numeric like "N/A"

                    if not need_fix:
                        continue

                    placeholder = await inp.get_attribute('placeholder') or ''
                    if is_num:
                        raw = self._resolve_numeric(label, placeholder)
                        val = self.validate_field_value(label, raw, True) or '1'
                    else:
                        raw = self._resolve_text(label, placeholder)
                        val = self.validate_field_value(label, raw, False)

                    if val:
                        await inp.fill('')
                        await asyncio.sleep(0.1)
                        await inp.fill(val)
                        await inp.evaluate(
                            'el => { el.dispatchEvent(new Event("input",{bubbles:true})); '
                            'el.dispatchEvent(new Event("change",{bubbles:true})); }'
                        )
                        await asyncio.sleep(0.2)
                        fixed += 1
                        print(f'   [FIX] Input: "{label[:40]}" = "{val[:20]}"')
                except Exception:
                    continue
        except Exception:
            pass
        return fixed

    async def _fix_unselected_dropdowns(self) -> int:
        fixed = 0
        try:
            # 1. Fix native <select> dropdowns
            for sel in await self.page.query_selector_all('select'):
                try:
                    if not await sel.is_visible():
                        continue
                    cur = await sel.evaluate(
                        'el => el.options[el.selectedIndex]'
                        ' ? el.options[el.selectedIndex].text.trim() : ""'
                    )
                    if cur.lower() not in PLACEHOLDER_TEXTS:
                        continue
                    label = await self._label(sel)
                    opts = await self._collect_select_options(sel)
                    if not opts:
                        continue
                    opt_texts  = [t for t, _ in opts]
                    opt_values = [v for _, v in opts]
                    chosen = self._pick_dropdown_answer(label, opt_texts, opt_values)
                    if chosen and await self._set_native_select(sel, chosen, opt_texts, opt_values):
                        fixed += 1
                        print(f'   [FIX] Select: "{label[:40]}" -> "{chosen[:20]}"')
                except Exception:
                    continue

            # 2. Fix React/ARIA custom dropdowns (the main fix for LinkedIn)
            fixed += await self._fill_custom_dropdowns()

            # 3. Last resort: scan for any remaining "Select an option" text on page
            fixed += await self._fix_remaining_select_an_option()
        except Exception:
            pass
        return fixed

    async def _fix_remaining_select_an_option(self) -> int:
        """Last-resort scan: find any visible element showing 'Select an option'
        that we haven't handled yet, and try to click+select."""
        fixed = 0
        try:
            # Find all elements whose text content is exactly "Select an option"
            candidates = await self.page.query_selector_all(
                'button, [role="combobox"], [aria-haspopup="listbox"], '
                'span, div'
            )
            for el in candidates:
                try:
                    if not await el.is_visible():
                        continue
                    text = (await el.inner_text()).strip().lower()
                    if text != 'select an option':
                        continue

                    # This element still says "Select an option" — try to fix it
                    label = await self._label(el)

                    # Check if this element IS the trigger (clickable)
                    tag = (await el.evaluate('el => el.tagName')).lower()
                    is_clickable = tag in ('button', 'select') or await el.evaluate(
                        'el => el.hasAttribute("role") || el.hasAttribute("aria-haspopup")'
                    )

                    trigger = el if is_clickable else None
                    if not trigger:
                        # Walk up to find clickable parent
                        js_handle = await el.evaluate_handle("""
                            el => {
                                let n = el.parentElement;
                                for (let i = 0; i < 5 && n; i++) {
                                    if (n.getAttribute('role') === 'combobox' ||
                                        n.getAttribute('aria-haspopup') === 'listbox' ||
                                        n.tagName === 'BUTTON' || n.tagName === 'SELECT') {
                                        return n;
                                    }
                                    n = n.parentElement;
                                }
                                return null;
                            }
                        """)
                        if not js_handle or await js_handle.evaluate('el => el === null'):
                            continue
                        trigger = js_handle.as_element()
                        if not trigger:
                            continue

                    if await self._open_and_select_react_dropdown(trigger, label):
                        fixed += 1
                except Exception:
                    try:
                        await self.page.keyboard.press('Escape')
                    except Exception:
                        pass
        except Exception:
            pass
        return fixed

    async def _fix_unselected_radios(self) -> int:
        """Fix any radio groups where nothing is selected yet."""
        return await self._fill_radio_buttons()

    # ==================================================================
    #  ANSWER RESOLUTION helpers
    # ==================================================================
    def _resolve_text(self, label: str, placeholder: str) -> Optional[str]:
        """Resolve text answer for label."""
        ll = (label + ' ' + placeholder).lower()
        p = self.user_profile
        if 'first name' in ll: return p.get('first_name', '')
        if 'last name' in ll:  return p.get('last_name', '')
        if 'email' in ll:      return p.get('email', '')
        if 'phone' in ll:      return p.get('phone_number', '') or p.get('phone', '')
        if 'city' in ll or 'location' in ll: return p.get('city', '')
        if 'state' in ll or 'province' in ll: return p.get('state', '')
        if 'zip' in ll or 'postal' in ll: return p.get('zip_code', '')
        if 'linkedin' in ll:   return p.get('linkedin_url', '')
        if 'github' in ll:     return p.get('github_url', '')
        if 'portfolio' in ll or 'website' in ll:
            return p.get('portfolio_url', '') or p.get('website', '')

        # Skill-specific
        for skill, yrs in p.get('skill_experience', {}).items():
            if skill.lower() in ll:
                return str(yrs)

        # Smart defaults
        for info in self.smart_defaults.values():
            if any(pat in ll for pat in info['patterns']):
                v = info['answer']
                if v:
                    return str(v)
        return None

    def _resolve_numeric(self, label: str, placeholder: str) -> Optional[str]:
        """Resolve numeric answer for label."""
        ll = (label + ' ' + placeholder).lower()
        p = self.user_profile

        # Skill-specific years
        for skill, yrs in p.get('skill_experience', {}).items():
            if skill.lower() in ll:
                return str(yrs)

        if 'years' in ll and 'experience' in ll:
            return str(p.get('years_experience', '3'))

        if any(k in ll for k in ['how soon', 'notice period', 'days notice', 'start work']):
            return str(p.get('notice_period_days', '0'))

        if any(k in ll for k in ['current ctc', 'your ctc', 'present ctc', 'current salary',
                                  'current compensation', 'annual ctc']):
            v = p.get('current_ctc', p.get('expected_salary', '0'))
            return str(v) if v else '0'

        if any(k in ll for k in ['expected ctc', 'expectation ctc', 'expected salary',
                                  'salary expectation', 'expected compensation']):
            v = p.get('expected_salary', '0')
            return str(v) if v else '0'

        if any(k in ll for k in ['salary', 'compensation', 'ctc', 'pay', 'package']):
            v = p.get('expected_salary', p.get('current_ctc', '0'))
            return str(v) if v else '0'

        if any(k in ll for k in ['cgpa', 'gpa', 'grade point']):
            return str(p.get('cgpa', '8.0'))

        if any(k in ll for k in ['months of internship', 'internship experience']):
            return str(p.get('internship_months', '6'))

        if any(k in ll for k in ['percentage', 'percent', 'marks']):
            return str(p.get('percentage', '75'))

        # Try smart defaults for anything that looks numeric
        for info in self.smart_defaults.values():
            if any(pat in ll for pat in info['patterns']):
                v = str(info['answer'])
                cleaned = re.sub(r'[^\d.]', '', v)
                if cleaned:
                    return cleaned

        return '1'  # absolute fallback for required numeric fields

    @staticmethod
    def _label_looks_numeric(label: str) -> bool:
        ll = label.lower()
        return any(kw in ll for kw in NUMERIC_LABEL_KEYWORDS)

    # ------------------------------------------------------------------
    #  DROPDOWN / RADIO ANSWER PICKING
    # ------------------------------------------------------------------
    def _pick_dropdown_answer(self, label: str, opt_texts: List[str],
                              opt_values: List[str]) -> Optional[str]:
        """Pick the best dropdown option value given label + available options.

        Priority:
          1. smart_defaults patterns
          2. Explicit Yes-forcing keywords (relocate / authorized / willing / experience)
          3. General Yes/No heuristic
          4. First real option fallback
        """
        ll = label.lower()

        # 1. Match smart defaults
        for info in self.smart_defaults.values():
            if any(pat in ll for pat in info['patterns']):
                ans = str(info['answer']).lower()
                for i, t in enumerate(opt_texts):
                    tl = t.lower()
                    if tl == ans or ans in tl or tl in ans:
                        return opt_values[i]

        # 2. Explicit Yes-forcing keywords (Problem 2 requirement)
        YES_FORCE_KEYWORDS = ['relocate', 'authorized', 'authorised', 'willing',
                              'experience', 'open to', 'work authorization',
                              'llm provider', 'llm', 'ai', 'workflow', 'integration']
        if any(kw in ll for kw in YES_FORCE_KEYWORDS):
            for i, t in enumerate(opt_texts):
                if t.lower() in ('yes', 'y'):
                    return opt_values[i]

        # 3. Yes/No heuristic for question-like labels
        if any(cue in ll for cue in YES_NO_QUESTION_CUES):
            for i, t in enumerate(opt_texts):
                if t.lower() in ('yes', 'y'):
                    return opt_values[i]

        # 4. Fallback — first real option (never placeholder)
        return opt_values[0] if opt_values else None

    def _pick_radio_answer(self, label: str, option_labels: List[str]) -> Optional[int]:
        ll = label.lower()
        for info in self.smart_defaults.values():
            if any(pat in ll for pat in info['patterns']):
                ans = str(info['answer']).lower()
                for i, t in enumerate(option_labels):
                    tl = t.lower()
                    if ans in tl or tl in ans:
                        return i
        # Prefer "Yes"
        for i, t in enumerate(option_labels):
            if t.lower() in ('yes', 'y', 'true', 'agree'):
                return i
        return 0 if option_labels else None
