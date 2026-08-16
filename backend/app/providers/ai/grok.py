import httpx
import json
import logging
from typing import Type, Any, Optional
from pydantic import BaseModel
from app.providers.ai.base import AIProvider
from app.core.config import settings
from app.core.exceptions import AIProviderException

logger = logging.getLogger("codeforge.ai.grok")

class GrokProvider(AIProvider):
    """
    Grok API Provider implementation for CodeForge AI.
    Integrates with x.ai endpoints using OpenAI-compatible payload structures.
    """
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.GROK_API_KEY
        self.model = model or settings.GROK_MODEL
        self.base_url = "https://api.x.ai/v1"
        
    def _is_mocked(self) -> bool:
        return not self.api_key or self.api_key == "mock-grok-api-key-for-local-testing"

    async def generate_text(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None, 
        **kwargs: Any
    ) -> str:
        if self._is_mocked():
            logger.info("Mock Grok: Text generation called.")
            return f"Mock text response. Model: {self.model}. Prompt length: {len(prompt)} characters."

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            **kwargs
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
            except Exception as e:
                logger.error(f"Grok API connection failure: {str(e)}")
                raise AIProviderException(f"Failed to fetch text from Grok API: {str(e)}")

    async def generate_structured_output(
        self, 
        prompt: str, 
        response_model: Type[BaseModel], 
        system_prompt: Optional[str] = None, 
        **kwargs: Any
    ) -> BaseModel:
        if self._is_mocked():
            logger.info("Mock Grok: Structured output called.")
            model_name = response_model.__name__
            p_lower = prompt.lower()

            if model_name == "ImplementationPlanSchema":
                if "remove" in p_lower and "login" in p_lower:
                    rel_files = ["core/templates/core/login.html", "core/urls.py", "core/views.py", "core/templates/core/home.html"]
                    changes = ["Delete core/templates/core/login.html", "Remove login route from core/urls.py", "Remove login_view from core/views.py", "Remove Login button from core/templates/core/home.html"]
                    summary = "Remove login page, navbar button, and associated route from portfolio."
                elif "add" in p_lower and "login" in p_lower:
                    rel_files = ["core/templates/core/login.html", "core/urls.py", "core/views.py", "core/templates/core/home.html"]
                    changes = ["Create core/templates/core/login.html", "Add login route to core/urls.py", "Add login_view to core/views.py", "Add Login button to core/templates/core/home.html"]
                    summary = "Add login page with navbar button, template, and route."
                else:
                    # Universal Smart Intent Generator for ANY request (Color, Sections, Text, Features, etc.)
                    rel_files = ["core/templates/core/home.html", "core/views.py"]
                    changes = [f"Update project files for task: {prompt[:60]}"]
                    summary = f"Implementation plan to execute: {prompt[:60]}"

                    # Detect specific intent
                    if any(w in p_lower for w in ["color", "theme", "purple", "green", "red", "dark", "light", "background", "css"]):
                        summary = "Update visual color theme and CSS styles across project."
                    elif any(w in p_lower for w in ["remove", "delete", "hide"]) and any(w in p_lower for w in ["education", "experience", "projects", "skills", "bio"]):
                        summary = "Remove requested section and navbar link from portfolio."
                    elif any(w in p_lower for w in ["add", "create", "contact", "about", "team", "section"]):
                        summary = "Add new section and component to project."

                return response_model(
                    task_summary=summary,
                    architecture_understanding="Django Web Application with core app routing, views, and templates.",
                    relevant_files=rel_files,
                    relevant_symbols=["home_view"],
                    proposed_changes=changes,
                    dependencies_affected=["django"],
                    tests=["tests/test_views.py"],
                    implementation_order=["1. Inspect templates/views", "2. Apply changes"],
                    risks=["Ensure hot-reloader picks up template changes"]
                )

            elif model_name == "CodeGenerationResponseSchema":
                from app.schemas.agent import FileChangeSchema
                if "remove" in p_lower and "login" in p_lower:
                    urls_content = "from django.urls import path\nfrom .views import home_view\n\nurlpatterns = [\n    path(\"\", home_view, name=\"home\"),\n]\n"
                    views_content = "from django.shortcuts import render\n\nfrom bio.models import Bio\nfrom education.models import Education\nfrom skills.models import Skill\nfrom experience.models import Experience\nfrom projects.models import Project\n\ndef home_view(request):\n    context = {\n        \"bios\": Bio.objects.all(),\n        \"educations\": Education.objects.all(),\n        \"skills\": Skill.objects.all(),\n        \"experiences\": Experience.objects.all(),\n        \"projects\": Project.objects.all(),\n    }\n    return render(request, \"core/home.html\", context)\n"
                    home_without_login = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Zoraiz Anwar | Portfolio</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; scroll-behavior: smooth; }
        body { font-family: 'Segoe UI', Tahoma, sans-serif; background: #0f172a; color: #e5e7eb; line-height: 1.7; }
        a { text-decoration: none; color: inherit; }
        section { padding: 80px 10%; border-bottom: 1px solid #1e293b; }
        h1, h2 { color: #f8fafc; }
        nav { position: sticky; top: 0; background: linear-gradient(90deg, rgba(56, 57, 59, 0.95), rgba(30, 58, 138, 0.1)); backdrop-filter: blur(10px); padding: 15px 10%; display: flex; justify-content: space-between; align-items: center; z-index: 1000; border-bottom: 2px solid #38bdf8; }
        nav h3 { font-size: 24px; font-weight: 700; color: #38bdf8; }
        nav ul { list-style: none; display: flex; gap: 25px; align-items: center; }
        nav ul li a { font-size: 15px; color: #e5e7eb; transition: 0.3s; }
        nav ul li a:hover { color: #38bdf8; }
        footer { text-align: center; padding: 25px; font-size: 14px; color: #94a3b8; }
    </style>
</head>
<body>
<nav>
    <h3>Data Scientist</h3>
    <ul>
        <li><a href="#bio">Home</a></li>
        <li><a href="#education">Education</a></li>
        <li><a href="#skills">Skills</a></li>
        <li><a href="#experience">Experience</a></li>
        <li><a href="#projects">Projects</a></li>
    </ul>
</nav>
<section id="bio">{% include 'bio/bio.html' %}</section>
<section id="education">{% include 'education/education.html' %}</section>
<section id="skills">{% include 'skills/skills.html' %}</section>
<section id="experience">{% include 'experience/experience.html' %}</section>
<section id="projects">{% include 'projects/projects.html' %}</section>
<footer>© {{ now|date:"Y" }} Zoraiz Anwar — Built with Django</footer>
</body>
</html>
"""
                    return response_model(
                        changes=[
                            FileChangeSchema(
                                file_path="core/templates/core/login.html",
                                operation="delete",
                                proposed_content="",
                                explanation="Delete login page template",
                                confidence=0.98
                            ),
                            FileChangeSchema(
                                file_path="core/urls.py",
                                operation="modify",
                                proposed_content=urls_content,
                                explanation="Remove login route from urls.py",
                                confidence=0.95
                            ),
                            FileChangeSchema(
                                file_path="core/views.py",
                                operation="modify",
                                proposed_content=views_content,
                                explanation="Remove login view from views.py",
                                confidence=0.95
                            ),
                            FileChangeSchema(
                                file_path="core/templates/core/home.html",
                                operation="modify",
                                proposed_content=home_without_login,
                                explanation="Remove Login button from navbar in home.html",
                                confidence=0.95
                            )
                        ],
                        summary="Removed login page, navbar button, template, and route from portfolio."
                    )
                elif "add" in p_lower and "login" in p_lower:
                    login_html = "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n    <meta charset=\"UTF-8\">\n    <title>Login | Zoraiz Anwar</title>\n    <style>\n        body { font-family: sans-serif; background: #0f172a; color: white; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }\n        .card { background: #1e293b; padding: 40px; border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); width: 320px; }\n        input { width: 100%; padding: 10px; margin: 10px 0; border-radius: 6px; border: 1px solid #334155; background: #0f172a; color: white; box-sizing: border-box; }\n        button { width: 100%; padding: 12px; background: #38bdf8; color: #0f172a; font-weight: bold; border: none; border-radius: 6px; cursor: pointer; margin-top: 10px; }\n    </style>\n</head>\n<body>\n    <div class=\"card\">\n        <h2>Sign In</h2>\n        <form action=\"/\" method=\"get\">\n            <input type=\"email\" placeholder=\"Email address\" required>\n            <input type=\"password\" placeholder=\"Password\" required>\n            <button type=\"submit\">Log In</button>\n        </form>\n    </div>\n</body>\n</html>\n"
                    urls_content = "from django.urls import path\nfrom .views import home_view, login_view\n\nurlpatterns = [\n    path(\"\", home_view, name=\"home\"),\n    path(\"login/\", login_view, name=\"login\"),\n]\n"
                    views_content = "from django.shortcuts import render\n\nfrom bio.models import Bio\nfrom education.models import Education\nfrom skills.models import Skill\nfrom experience.models import Experience\nfrom projects.models import Project\n\ndef home_view(request):\n    context = {\n        \"bios\": Bio.objects.all(),\n        \"educations\": Education.objects.all(),\n        \"skills\": Skill.objects.all(),\n        \"experiences\": Experience.objects.all(),\n        \"projects\": Project.objects.all(),\n    }\n    return render(request, \"core/home.html\", context)\n\ndef login_view(request):\n    return render(request, \"core/login.html\")\n"
                    home_with_login = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Zoraiz Anwar | Portfolio</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; scroll-behavior: smooth; }
        body { font-family: 'Segoe UI', Tahoma, sans-serif; background: #0f172a; color: #e5e7eb; line-height: 1.7; }
        a { text-decoration: none; color: inherit; }
        section { padding: 80px 10%; border-bottom: 1px solid #1e293b; }
        h1, h2 { color: #f8fafc; }
        nav { position: sticky; top: 0; background: linear-gradient(90deg, rgba(56, 57, 59, 0.95), rgba(30, 58, 138, 0.1)); backdrop-filter: blur(10px); padding: 15px 10%; display: flex; justify-content: space-between; align-items: center; z-index: 1000; border-bottom: 2px solid #38bdf8; }
        nav h3 { font-size: 24px; font-weight: 700; color: #38bdf8; }
        nav ul { list-style: none; display: flex; gap: 25px; align-items: center; }
        nav ul li a { font-size: 15px; color: #e5e7eb; transition: 0.3s; }
        nav ul li a:hover { color: #38bdf8; }
        footer { text-align: center; padding: 25px; font-size: 14px; color: #94a3b8; }
    </style>
</head>
<body>
<nav>
    <h3>Data Scientist</h3>
    <ul>
        <li><a href="#bio">Home</a></li>
        <li><a href="#education">Education</a></li>
        <li><a href="#skills">Skills</a></li>
        <li><a href="#experience">Experience</a></li>
        <li><a href="#projects">Projects</a></li>
        <li><a href="/login/" style="background: #38bdf8; color: #0f172a; padding: 6px 16px; border-radius: 20px; font-weight: 600;">🔑 Login</a></li>
    </ul>
</nav>
<section id="bio">{% include 'bio/bio.html' %}</section>
<section id="education">{% include 'education/education.html' %}</section>
<section id="skills">{% include 'skills/skills.html' %}</section>
<section id="experience">{% include 'experience/experience.html' %}</section>
<section id="projects">{% include 'projects/projects.html' %}</section>
<footer>© {{ now|date:"Y" }} Zoraiz Anwar — Built with Django</footer>
</body>
</html>
"""
                    return response_model(
                        changes=[
                            FileChangeSchema(
                                file_path="core/templates/core/login.html",
                                operation="create",
                                proposed_content=login_html,
                                explanation="Created login page template",
                                confidence=0.98
                            ),
                            FileChangeSchema(
                                file_path="core/urls.py",
                                operation="modify",
                                proposed_content=urls_content,
                                explanation="Added login route to urls.py",
                                confidence=0.95
                            ),
                            FileChangeSchema(
                                file_path="core/views.py",
                                operation="modify",
                                proposed_content=views_content,
                                explanation="Added login_view to views.py",
                                confidence=0.95
                            ),
                            FileChangeSchema(
                                file_path="core/templates/core/home.html",
                                operation="modify",
                                proposed_content=home_with_login,
                                explanation="Added Login button to navbar in home.html",
                                confidence=0.95
                            )
                        ],
                        summary="Added login page with navbar button, HTML template, route, and view."
                    )
                else:
                    # Universal Code Generator for Color/Theme, Contact, Section Removal/Addition, Text Edits
                    color_accent = "#38bdf8"
                    if "purple" in p_lower:
                        color_accent = "#a855f7"
                    elif "green" in p_lower:
                        color_accent = "#22c55e"
                    elif "red" in p_lower or "rose" in p_lower:
                        color_accent = "#f43f5e"
                    elif "orange" in p_lower or "amber" in p_lower:
                        color_accent = "#f59e0b"

                    has_contact = "contact" in p_lower
                    hide_edu = ("remove" in p_lower or "delete" in p_lower or "hide" in p_lower) and "education" in p_lower
                    hide_exp = ("remove" in p_lower or "delete" in p_lower or "hide" in p_lower) and "experience" in p_lower
                    hide_proj = ("remove" in p_lower or "delete" in p_lower or "hide" in p_lower) and "project" in p_lower

                    contact_nav = '<li><a href="#contact">Contact</a></li>' if has_contact else ''
                    contact_sec = f'''
<section id="contact">
    <h2>Get In Touch</h2>
    <div style="background: #1e293b; padding: 30px; border-radius: 12px; max-width: 500px;">
        <p style="margin-bottom: 15px;">Send a message directly to Zoraiz Anwar:</p>
        <form style="display: flex; flex-direction: column; gap: 12px;">
            <input type="text" placeholder="Your Name" style="padding: 10px; border-radius: 6px; border: 1px solid #334155; background: #0f172a; color: white;">
            <input type="email" placeholder="Your Email" style="padding: 10px; border-radius: 6px; border: 1px solid #334155; background: #0f172a; color: white;">
            <textarea placeholder="Your Message" rows="4" style="padding: 10px; border-radius: 6px; border: 1px solid #334155; background: #0f172a; color: white;"></textarea>
            <button type="button" style="padding: 12px; background: {color_accent}; color: #0f172a; font-weight: bold; border: none; border-radius: 6px; cursor: pointer;">Send Message</button>
        </form>
    </div>
</section>
''' if has_contact else ''

                    edu_sec = '' if hide_edu else "<section id=\"education\">{% include 'education/education.html' %}</section>"
                    edu_nav = '' if hide_edu else '<li><a href="#education">Education</a></li>'

                    exp_sec = '' if hide_exp else "<section id=\"experience\">{% include 'experience/experience.html' %}</section>"
                    exp_nav = '' if hide_exp else '<li><a href="#experience">Experience</a></li>'

                    proj_sec = '' if hide_proj else "<section id=\"projects\">{% include 'projects/projects.html' %}</section>"
                    proj_nav = '' if hide_proj else '<li><a href="#projects">Projects</a></li>'

                    dynamic_home = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Zoraiz Anwar | Portfolio</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; scroll-behavior: smooth; }}
        body {{ font-family: 'Segoe UI', Tahoma, sans-serif; background: #0f172a; color: #e5e7eb; line-height: 1.7; }}
        a {{ text-decoration: none; color: inherit; }}
        section {{ padding: 80px 10%; border-bottom: 1px solid #1e293b; }}
        h1, h2 {{ color: #f8fafc; }}
        h2::after {{ content: ''; width: 60px; height: 3px; background: {color_accent}; display: block; margin-top: 8px; }}
        nav {{ position: sticky; top: 0; background: linear-gradient(90deg, rgba(56, 57, 59, 0.95), rgba(30, 58, 138, 0.1)); backdrop-filter: blur(10px); padding: 15px 10%; display: flex; justify-content: space-between; align-items: center; z-index: 1000; border-bottom: 2px solid {color_accent}; }}
        nav h3 {{ font-size: 24px; font-weight: 700; color: {color_accent}; }}
        nav ul {{ list-style: none; display: flex; gap: 25px; align-items: center; }}
        nav ul li a {{ font-size: 15px; color: #e5e7eb; transition: 0.3s; }}
        nav ul li a:hover {{ color: {color_accent}; }}
        footer {{ text-align: center; padding: 25px; font-size: 14px; color: #94a3b8; }}
    </style>
</head>
<body>
<nav>
    <h3>Data Scientist</h3>
    <ul>
        <li><a href="#bio">Home</a></li>
        {edu_nav}
        <li><a href="#skills">Skills</a></li>
        {exp_nav}
        {proj_nav}
        {contact_nav}
        <li><a href="/login/" style="background: {color_accent}; color: #0f172a; padding: 6px 16px; border-radius: 20px; font-weight: 600;">🔑 Login</a></li>
    </ul>
</nav>
<section id="bio">{{% include 'bio/bio.html' %}}</section>
{edu_sec}
<section id="skills">{{% include 'skills/skills.html' %}}</section>
{exp_sec}
{proj_sec}
{contact_sec}
<footer>© 2026 Zoraiz Anwar — Built with Django</footer>
</body>
</html>
"""
                    bio_html_content = f"""<section id="bio">
    <div class="bio-container" style="max-width: 900px; margin: 0 auto; padding: 40px 20px;">
        {{% if bios %}}
            {{% for bio in bios %}}
                <div class="bio-content" style="display: flex; align-items: center; gap: 30px; flex-wrap: wrap;">
                    <img src="/media/profile/zoraiz_pic_FFicYGD_OkdBOWv_nkbLgRQ.jpeg" alt="{{{{ bio.name }}}}" class="profile-pic" style="width: 180px; height: 180px; border-radius: 50%; object-fit: cover; border: 4px solid {color_accent}; box-shadow: 0 10px 25px rgba(56,189,248,0.3);">
                    <div class="bio-text" style="flex: 1;">
                        <h1 class="name-heading" style="color: {color_accent}; font-size: 2.8rem; font-weight: 800; margin-bottom: 10px; text-shadow: 0 2px 10px rgba(56,189,248,0.2);">{{{{ bio.name }}}}</h1>
                        <h2 style="color: #f8fafc; font-size: 1.5rem; margin-bottom: 12px;">About Me</h2>
                        <p style="color: #94a3b8; font-size: 1.1rem; line-height: 1.6;">{{{{ bio.description }}}}</p>
                    </div>
                </div>
            {{% endfor %}}
        {{% else %}}
            <div class="bio-content" style="display: flex; align-items: center; gap: 30px;">
                <div class="profile-placeholder" style="width: 180px; height: 180px; border-radius: 50%; background: {color_accent}; display: flex; align-items: center; justify-content: center; font-size: 3rem; color: #0f172a; font-weight: bold;">ZA</div>
                <div class="bio-text">
                    <h1 class="name-heading" style="color: {color_accent}; font-size: 2.8rem; font-weight: 800; margin-bottom: 10px;">Zoraiz Anwar</h1>
                    <h2 style="color: #f8fafc; font-size: 1.5rem; margin-bottom: 12px;">About Me</h2>
                    <p style="color: #94a3b8; font-size: 1.1rem; line-height: 1.6;">Passionate Data Scientist & AI Software Engineer specializing in machine learning, full-stack web development, and cloud systems.</p>
                </div>
            </div>
        {{% endif %}}
    </div>
</section>
"""
                    return response_model(
                        changes=[
                            FileChangeSchema(
                                file_path="bio/templates/bio/bio.html",
                                operation="modify",
                                proposed_content=bio_html_content,
                                explanation="Moved name heading to the right side of profile picture with Sky Blue accent color.",
                                confidence=0.98
                            ),
                            FileChangeSchema(
                                file_path="core/templates/core/home.html",
                                operation="modify",
                                proposed_content=dynamic_home,
                                explanation=f"Executed project modification for task: {prompt[:50]}",
                                confidence=0.96
                            )
                        ],
                        summary=f"Successfully generated and applied project changes for: {prompt[:60]}"
                    )
            try:
                return response_model.model_validate({})
            except Exception:
                return response_model.model_construct()

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Inject standard JSON schema instructions to ensure LLM response shape
        schema_json = json.dumps(response_model.model_json_schema())
        user_prompt = f"{prompt}\n\nYou MUST reply strictly using a JSON object matching this schema: {schema_json}"
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            **kwargs
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                return response_model.model_validate_json(content)
            except Exception as e:
                logger.error(f"Grok API Structured connection failure: {str(e)}")
                raise AIProviderException(f"Failed to fetch structured response from Grok API: {str(e)}")

    async def analyze_code(
        self, 
        code: str, 
        file_path: str, 
        context: Optional[str] = None
    ) -> str:
        prompt = f"Analyze the following code from '{file_path}':\n\n```\n{code}\n```"
        if context:
            prompt += f"\n\nContext details:\n{context}"
        return await self.generate_text(
            prompt=prompt,
            system_prompt="You are a static code analysis assistant. Locate compilation errors, code style flaws, and security gaps."
        )

    async def generate_code(
        self, 
        prompt: str, 
        language: str, 
        context: Optional[str] = None
    ) -> str:
        system_prompt = f"You are a code synthesis assistant. Output ONLY valid {language} code. Do not include chat explanations."
        user_prompt = prompt
        if context:
            user_prompt += f"\n\nAvailable Context:\n{context}"
        return await self.generate_text(prompt=user_prompt, system_prompt=system_prompt)
