"""
ai_engine.py — Motor de Inteligencia Artificial Semántica para ALBA v2
=====================================================================
Este módulo reemplaza el keyword-matching tradicional con análisis de
lenguaje natural mediante LLM (OpenAI GPT-4o-mini por defecto).

Incluye:
  • Análisis semántico de CVs (skills, gaps, red flags, logros)
  • Matching inteligente búsqueda ↔ candidato con justificación narrativa
  • Generación dinámica de preguntas STAR personalizadas por brechas
  • Evaluación de respuestas con análisis STAR estructurado
  • Generación de informes ejecutivos para hiring managers

Uso:
    from ai_engine import AlbaAIEngine
    engine = AlbaAIEngine(api_key="sk-...")
    result = engine.calculate_semantic_match(job_dict, cv_text)
"""

from __future__ import annotations

import json
import os
from typing import Any

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


def get_secret_value(key: str, default: str = "") -> str:
    """Helper para leer secrets (compatible con Streamlit)."""
    try:
        import streamlit as st
        value = st.secrets.get(key)
        if value is not None:
            return str(value).strip()
        for section in ("openai", "app", "default"):
            try:
                sec = st.secrets.get(section, {})
                if isinstance(sec, dict) and key in sec:
                    return str(sec[key]).strip()
            except Exception:
                continue
    except Exception:
        pass
    return os.environ.get(key, default)


def get_openai_config() -> dict[str, Any]:
    key = get_secret_value("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
    return {
        "api_key": key,
        "model": get_secret_value("OPENAI_MODEL", "gpt-4o-mini"),
        "enabled": bool(key) and OPENAI_AVAILABLE,
    }


AI_ENGINE_NOTICE = (
    "El análisis semántico con IA evalúa significado, contexto y transferencia "
    "de habilidades. No reemplaza la decisión humana."
)


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


class AlbaAIEngine:
    """Motor de inteligencia artificial para análisis semántico de CV,
    matching de candidatos y evaluación de respuestas de entrevista."""

    def __init__(self, api_key: str | None = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key or get_openai_config()["api_key"]
        self.model = model
        if OPENAI_AVAILABLE and self.api_key:
            self.client = openai.OpenAI(api_key=self.api_key)
        else:
            self.client = None

    def _call(
        self,
        messages: list[dict],
        temperature: float = 0.2,
        max_tokens: int = 2000,
        json_mode: bool = True,
    ) -> dict | str:
        if not self.client:
            raise RuntimeError("OpenAI no está configurado.")
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = self.client.chat.completions.create(**kwargs)
        content = resp.choices[0].message.content or "{}"
        if json_mode:
            return json.loads(content)
        return content

    # ------------------------------------------------------------------
    # 1. ANÁLISIS DE CV
    # ------------------------------------------------------------------
    def analyze_cv(self, cv_text: str) -> dict:
        """Extrae información estructurada de un CV usando LLM."""
        system = (
            "Sos un reclutador senior de RR. HH. especializado en analizar CVs. "
            "Extraé la información en español y devolvé EXCLUSIVAMENTE un JSON válido."
        )
        prompt = f"""Analizá el siguiente CV y devolvé un JSON con esta estructura exacta:
{{
  "full_name": "Nombre completo",
  "email": "correo@ejemplo.com",
  "phone": "teléfono",
  "headline": "Título profesional breve (máx 150 chars)",
  "education_summary": "Resumen de formación académica",
  "experience_summary": "Resumen de experiencia laboral destacada",
  "skills_text": "Habilidades técnicas y blandas separadas por coma",
  "languages_text": "Idiomas y niveles",
  "seniority_estimate": "Junior|Semi Senior|Senior|Liderazgo",
  "key_achievements": ["Logro cuantificado 1", "Logro 2"],
  "career_gaps": ["Descripción de gap si existe"],
  "red_flags": ["Posible bandera roja"],
  "overall_assessment": "Evaluación general en 2 oraciones"
}}

CV:
{cv_text[:8000]}
"""
        result = self._call(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ]
        )
        return {
            "full_name": result.get("full_name", "Candidato sin identificar"),
            "email": normalize_email(result.get("email", "")),
            "phone": result.get("phone", ""),
            "headline": result.get("headline", "")[:500],
            "education_summary": result.get("education_summary", "")[:5000],
            "experience_summary": result.get("experience_summary", "")[:7000],
            "skills_text": result.get("skills_text", "")[:4000],
            "languages_text": result.get("languages_text", "")[:2000],
            "seniority_estimate": result.get("seniority_estimate", ""),
            "key_achievements": result.get("key_achievements", []),
            "career_gaps": result.get("career_gaps", []),
            "red_flags": result.get("red_flags", []),
            "overall_assessment": result.get("overall_assessment", ""),
        }

    # ------------------------------------------------------------------
    # 2. MATCHING SEMÁNTICO
    # ------------------------------------------------------------------
    def calculate_semantic_match(self, job: dict, cv_text: str) -> dict:
        """Calcula coincidencia semántica entre búsqueda y CV."""
        system = (
            "Sos un experto en selección de talento. Evaluá la coincidencia entre "
            "una búsqueda laboral y un CV usando razonamiento semántico. "
            "Devolvé EXCLUSIVAMENTE JSON válido."
        )
        prompt = f"""Evaluá la coincidencia entre esta búsqueda y el CV.

BÚSQUEDA:
Puesto: {job.get("title", "")}
Área: {job.get("area", "")}
Seniority: {job.get("seniority", "")}
Descripción: {job.get("description", "")[:2000]}
Responsabilidades: {job.get("responsibilities", "")[:1500]}
Requisitos excluyentes: {job.get("must_have", "")[:1500]}
Deseables: {job.get("desirable", "")[:1500]}
Competencias: {job.get("competencies", "")[:1500]}

CV:
{cv_text[:8000]}

Devolvé JSON con:
{{
  "total": 78.5,
  "recommendation": "AVANZA|REVISAR|BAJA COINCIDENCIA",
  "summary": "Explicación breve del puntaje",
  "reasons": ["Razón 1", "Razón 2"],
  "strengths": ["Fortaleza 1", "Fortaleza 2"],
  "gaps": ["Brecha 1", "Brecha 2"],
  "dimensions": [
    {{
      "key": "must_have",
      "label": "Requisitos excluyentes",
      "weight": 50,
      "required": true,
      "criteria_count": 5,
      "matched": ["término1", "término2"],
      "missing": ["término3"],
      "coverage": 0.75,
      "normalized_weight": 50.0,
      "points": 37.5
    }}
  ],
  "config": {{"preset_name": "IA Semántica", "groups": [], "thresholds": {{"advance":75,"review":50,"minimum_required_coverage":50}}}},
  "notice": "{AI_ENGINE_NOTICE}"
}}
"""
        result = self._call(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ]
        )
        if "total" not in result:
            raise ValueError("La IA no devolvió un puntaje válido.")
        result.setdefault("recommendation", "REVISAR")
        result.setdefault("summary", "Evaluación semántica completada.")
        result.setdefault("reasons", [])
        result.setdefault("strengths", [])
        result.setdefault("gaps", [])
        result.setdefault("dimensions", [])
        result.setdefault(
            "config",
            {
                "preset_name": "IA Semántica",
                "groups": [],
                "thresholds": {"advance": 75, "review": 50, "minimum_required_coverage": 50},
            },
        )
        result.setdefault("notice", AI_ENGINE_NOTICE)
        return result

    # ------------------------------------------------------------------
    # 3. PREGUNTAS DINÁMICAS
    # ------------------------------------------------------------------
    def generate_dynamic_questions(self, job: dict, cv_text: str) -> list[dict]:
        """Genera preguntas STAR personalizadas según gaps del candidato."""
        system = (
            "Sos un entrevistador experto en metodología STAR. Generá preguntas "
            "personalizadas para cubrir las brechas entre el CV y la búsqueda. "
            "Devolvé EXCLUSIVAMENTE JSON válido."
        )
        prompt = f"""Basándote en la búsqueda y el CV, generá 3 a 5 preguntas conductuales STAR.

BÚSQUEDA:
Puesto: {job.get("title", "")}
Requisitos: {job.get("must_have", "")[:1000]}
Competencias: {job.get("competencies", "")[:1000]}

CV:
{cv_text[:6000]}

Devolvé JSON: {{"questions": [{{"competency": "Nombre", "question": "Texto", "indicators": "ind1, ind2", "target_gap": "Brecha que cubre"}}]}}
"""
        result = self._call(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ]
        )
        return result.get("questions", [])

    # ------------------------------------------------------------------
    # 4. EVALUACIÓN DE RESPUESTAS
    # ------------------------------------------------------------------
    def evaluate_response(self, question: dict, answer_text: str) -> dict:
        """Evalúa una respuesta de entrevista con análisis STAR profundo."""
        system = (
            "Sos un evaluador senior de entrevistas por competencias. Analizá la respuesta "
            "usando la metodología STAR y devolvé EXCLUSIVAMENTE JSON válido."
        )
        prompt = f"""Evaluá esta respuesta de entrevista.

COMPETENCIA: {question.get("competency", "General")}
PREGUNTA: {question.get("question_text", "")}
INDICADORES ESPERADOS: {question.get("indicators_text", "")}
PUNTAJE MÁXIMO: {question.get("max_score", 5)}

RESPUESTA DEL CANDIDATO:
{answer_text[:4000]}

Devolvé JSON:
{{
  "score": 4.0,
  "maximum": 5,
  "summary": "Análisis breve",
  "matched_indicators": ["ind1", "ind2"],
  "missing_indicators": ["ind3"],
  "star_elements": ["Situación", "Tarea", "Acción", "Resultado"],
  "word_count": 120,
  "strengths": ["Fortaleza 1"],
  "gaps": ["Brecha 1"]
}}
"""
        result = self._call(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ]
        )
        result.setdefault("score", None)
        result.setdefault("maximum", float(question.get("max_score", 5)))
        result.setdefault("summary", "Evaluación asistida por IA.")
        result.setdefault("matched_indicators", [])
        result.setdefault("missing_indicators", [])
        result.setdefault("star_elements", [])
        result.setdefault("word_count", len((answer_text or "").split()))
        result.setdefault("strengths", [])
        result.setdefault("gaps", [])
        return result

    # ------------------------------------------------------------------
    # 5. INFORME EJECUTIVO
    # ------------------------------------------------------------------
    def generate_final_report(
        self, candidate_name: str, job_title: str, evaluations: list[dict]
    ) -> dict:
        """Genera informe ejecutivo final de entrevista."""
        system = "Sos un director de RR. HH. que redacta informes ejecutivos de selección."
        evaluations_text = "\n\n".join(
            [
                f"Pregunta: {e.get('question', '')}\nPuntaje: {e.get('score', 0)}/{e.get('maximum', 5)}\nAnálisis: {e.get('summary', '')}"
                for e in evaluations
            ]
        )
        prompt = f"""Redactá un informe ejecutivo para el hiring manager.

CANDIDATO: {candidate_name}
PUESTO: {job_title}

EVALUACIONES POR PREGUNTA:
{evaluations_text}

Devolvé JSON:
{{
  "average_score": 4.2,
  "traffic_light": "VERDE|AMARILLO|ROJO",
  "recommendation": "Recomendado/a|Recomendado/a con observaciones|No recomendado/a",
  "executive_summary": "Resumen ejecutivo en 3-4 oraciones",
  "key_strengths": ["Fortaleza 1", "Fortaleza 2"],
  "risk_areas": ["Riesgo 1"],
  "next_steps": ["Paso recomendado 1"]
}}
"""
        return self._call(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ]
        )
