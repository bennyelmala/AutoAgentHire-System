"""
Google Gemini LLM Service
Provides intelligent text generation, form filling, and decision-making capabilities.
"""
import os
import logging
from typing import Optional, Dict, Any, List
import google.generativeai as genai  # type: ignore
from google.generativeai.types import GenerationConfig  # type: ignore
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class GeminiService:
    """
    Service for interacting with Google Gemini API.
    Handles intelligent response generation for job applications.
    """
    
    def __init__(
        self, 
        api_key: Optional[str] = None,
        model_name: str = "gemini-2.5-flash",
        temperature: float = 0.7
    ):
        """
        Initialize Gemini service.
        
        Args:
            api_key: Google API key (defaults to env variable)
            model_name: Model to use (default: gemini-1.5-flash)
            temperature: Temperature for generation (0-1)
        """
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name
        self.temperature = temperature
        
        if not self.api_key:
            logger.warning("No Google API key provided. Gemini service will not work.")
            self.model = None
        else:
            try:
                genai.configure(api_key=self.api_key)  # type: ignore
                self.model = genai.GenerativeModel(model_name)  # type: ignore
                logger.info(f"Gemini service initialized with model: {model_name}")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini: {e}")
                self.model = None
    
    def generate_cover_letter(
        self,
        job_title: str,
        company: str,
        job_description: str,
        resume_text: str,
        user_name: str,
        additional_context: Optional[str] = None
    ) -> str:
        """
        Generate a personalized cover letter using Gemini.
        
        Args:
            job_title: Job title
            company: Company name
            job_description: Full job description
            resume_text: User's resume content
            user_name: User's full name
            additional_context: Any additional context
            
        Returns:
            Generated cover letter
        """
        if not self.model:
            return self._fallback_cover_letter(job_title, company, user_name)
        
        prompt = f"""
Generate a professional, personalized cover letter for the following job application.

**Job Details:**
- Position: {job_title}
- Company: {company}
- Job Description: {job_description[:1000]}

**Candidate Information:**
- Name: {user_name}
- Resume Summary: {resume_text[:1500]}

{f'**Additional Context:** {additional_context}' if additional_context else ''}

**Instructions:**
1. Write a compelling cover letter (250-350 words)
2. Highlight relevant skills from the resume that match the job requirements
3. Show enthusiasm for the role and company
4. Use a professional yet personable tone
5. Include specific examples of relevant experience
6. End with a strong call to action

**Format:**
Dear Hiring Manager,

[Cover letter body - 3-4 paragraphs]

Sincerely,
{user_name}
"""
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(  # type: ignore
                    temperature=self.temperature,
                    max_output_tokens=1024,
                )
            )
            
            cover_letter = response.text.strip()
            logger.info(f"Generated cover letter for {job_title} at {company}")
            return cover_letter
            
        except Exception as e:
            logger.error(f"Error generating cover letter: {e}")
            return self._fallback_cover_letter(job_title, company, user_name)
    
    def answer_application_question(
        self,
        question: str,
        job_context: Dict[str, Any],
        resume_text: str,
        max_words: Optional[int] = None
    ) -> str:
        """
        Generate intelligent answer to an application question.
        
        Args:
            question: The application question
            job_context: Job details (title, company, description)
            resume_text: User's resume
            max_words: Maximum word count for answer
            
        Returns:
            Generated answer
        """
        if not self.model:
            return self._fallback_answer(question)
        
        word_limit = f"\n- Keep answer under {max_words} words" if max_words else ""
        
        prompt = f"""
You are helping a job candidate answer an application question intelligently.

**Question:** {question}

**Job Context:**
- Position: {job_context.get('title', 'N/A')}
- Company: {job_context.get('company', 'N/A')}
- Description: {job_context.get('description', 'N/A')[:500]}

**Candidate's Background:**
{resume_text[:1000]}

**Instructions:**
- Answer the question directly and professionally
- Use information from the candidate's background when relevant
- Tailor the answer to the specific job and company{word_limit}
- Be honest and authentic
- Use a confident but not arrogant tone

Provide ONLY the answer text, no preamble or explanation.
"""
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(  # type: ignore
                    temperature=self.temperature,
                    max_output_tokens=512,
                )
            )
            
            answer = response.text.strip()
            logger.info(f"Generated answer for question: {question[:50]}...")
            return answer
            
        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            return self._fallback_answer(question)
    
    def evaluate_job_match(
        self,
        job_description: str,
        resume_text: str,
        required_skills: List[str],
        preferences: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluate how well a job matches the candidate's profile.
        
        Args:
            job_description: Full job description
            resume_text: Candidate's resume
            required_skills: List of required skills
            preferences: User preferences (location, remote, etc.)
            
        Returns:
            Match evaluation with score and reasoning
        """
        if not self.model:
            return {
                "match_score": 0.5,
                "reasoning": "Gemini API not available",
                "should_apply": False
            }
        
        prompt = f"""
Evaluate this job opportunity for the candidate.

**Job Description:**
{job_description[:1500]}

**Required Skills:**
{', '.join(required_skills)}

**Candidate Resume:**
{resume_text[:1500]}

**Candidate Preferences:**
- Location preference: {preferences.get('location', 'Any')}
- Remote preference: {preferences.get('remote_preference', 'Any')}
- Experience level: {preferences.get('experience_level', 'Any')}

**Task:**
Analyze the match between this job and the candidate. Consider:
1. Skills alignment
2. Experience level match
3. Location/remote work fit
4. Career growth potential
5. Company culture fit (if mentioned)

**Output Format (JSON):**
{{
    "match_score": <number between 0 and 1>,
    "reasoning": "<2-3 sentence explanation>",
    "should_apply": <true/false>,
    "strengths": ["strength1", "strength2"],
    "concerns": ["concern1", "concern2"]
}}

Respond with ONLY valid JSON, no other text.
"""
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(  # type: ignore
                    temperature=0.3,  # Lower temperature for more consistent output
                    max_output_tokens=512,
                )
            )
            
            import json
            # Try to parse JSON from response
            response_text = response.text.strip()
            # Remove markdown code blocks if present
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            
            result = json.loads(response_text)
            logger.info(f"Job match evaluated: score={result.get('match_score')}")
            return result
            
        except Exception as e:
            logger.error(f"Error evaluating job match: {e}")
            return {
                "match_score": 0.5,
                "reasoning": "Unable to evaluate match",
                "should_apply": False,
                "strengths": [],
                "concerns": ["Evaluation failed"]
            }
    
    def generate_resume_summary(self, resume_text: str) -> str:
        """
        Generate a concise summary of a resume.
        
        Args:
            resume_text: Full resume text
            
        Returns:
            Resume summary
        """
        if not self.model:
            logger.warning("Gemini model not initialized, using fallback summary")
            return "Resume processed successfully. Please configure GEMINI_API_KEY for AI-powered summaries."
        
        # Limit resume text to prevent token overflow
        max_chars = 3000
        truncated_text = resume_text[:max_chars]
        if len(resume_text) > max_chars:
            logger.info(f"Resume text truncated from {len(resume_text)} to {max_chars} characters")
        
        prompt = f"""
Analyze this resume and create a concise professional summary.

**Resume:**
{truncated_text}

**Task:**
Create a 3-4 sentence professional summary highlighting:
1. Key skills and expertise areas
2. Years of experience and seniority level (if mentioned)
3. Notable achievements or specializations
4. Primary career focus or domain

Provide ONLY the summary text in a professional tone, no preamble or markdown.
"""
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=GenerationConfig(
                    temperature=0.5,
                    max_output_tokens=256,
                    top_p=0.9,
                    top_k=40,
                )
            )
            
            if response and response.text:
                summary = response.text.strip()
                logger.info(f"Generated resume summary: {len(summary)} characters")
                return summary
            else:
                logger.warning("Empty response from Gemini API")
                return "Experienced professional with diverse skill set and proven track record."
            
        except Exception as e:
            logger.error(f"Error generating resume summary with Gemini: {e}", exc_info=True)
            # Return a generic but informative fallback
            return "Professional candidate with relevant experience and qualifications. AI summary generation temporarily unavailable."
    
    def _fallback_cover_letter(self, job_title: str, company: str, user_name: str) -> str:
        """Fallback cover letter when Gemini is unavailable."""
        return f"""Dear Hiring Manager,

I am writing to express my strong interest in the {job_title} position at {company}. With my background and experience, I am confident I would be a valuable addition to your team.

Throughout my career, I have developed strong skills that align well with this role. I am particularly excited about the opportunity to contribute to {company}'s mission and work with your talented team.

I would welcome the opportunity to discuss how my experience and skills can benefit your organization. Thank you for considering my application.

Sincerely,
{user_name}"""
    
    def _fallback_answer(self, question: str) -> str:
        """Fallback answer when Gemini is unavailable."""
        if "why" in question.lower():
            return "I am genuinely excited about this opportunity and believe my skills and experience make me a strong fit for this role."
        elif "experience" in question.lower():
            return "I have relevant experience that aligns well with the requirements of this position."
        else:
            return "Yes, I am interested and qualified for this position."


# Singleton instance
_gemini_service: Optional[GeminiService] = None


def get_gemini_service() -> GeminiService:
    """Get or create Gemini service singleton."""
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiService()
    return _gemini_service
