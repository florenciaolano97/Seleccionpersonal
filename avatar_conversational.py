"""
avatar_conversational.py — Avatar Conversacional Inteligente para ALBA v2
============================================================================
Agente de entrevista en tiempo real que combina:
  • Memoria de conversación
  • Evaluación semántica con LLM
  • Follow-ups dinámicos adaptativos
  • Integración con D-ID para avatar parlante (streaming)

Uso:
    from avatar_conversational import AlbaConversationalAvatar
    agent = AlbaConversationalAvatar(company_id=1, interview_id=42)
    welcome = agent.start_session()
    question = agent.get_next_question()
    result = agent.process_answer(answer_text, question)
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class AlbaConversationalAvatar:
    """Agente de entrevista conversacional en tiempo real."""

    def __init__(
        self,
        company_id: int,
        interview_id: int,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
    ):
        self.company_id = company_id
        self.interview_id = interview_id
        self.history: list[dict] = []
        self.current_question_index = 0
        self.questions: list[dict] = []
        self._load_questions()
        self._load_settings()
        self._init_ai(api_key, model)

    def _init_ai(self, api_key: str | None, model: str):
        try:
            from ai_engine import AlbaAIEngine
            self.ai = AlbaAIEngine(api_key=api_key, model=model)
        except Exception:
            self.ai = None

    def _load_questions(self):
        # Stub: en producción se conecta a la BD de ALBA
        self.questions = []

    def _load_settings(self):
        # Stub: en producción carga avatar_settings de la BD
        self.settings = {
            "display_name": "ALBA",
            "welcome_text": "Voy a hacerte algunas preguntas. Tomate tu tiempo.",
            "source_url": "",
            "voice_provider": "microsoft",
            "voice_id": "es-AR-ElenaNeural",
        }

    # ------------------------------------------------------------------
    # FLUJO DE ENTREVISTA
    # ------------------------------------------------------------------
    def start_session(self, candidate_name: str = "Candidato/a", job_title: str = "la posición") -> str:
        """Genera el mensaje de bienvenida y la primera pregunta."""
        welcome = (
            f"Hola {candidate_name}, soy {self.settings['display_name']}, "
            f"tu entrevistadora virtual para {job_title}. "
            f"{self.settings['welcome_text']}"
        )
        self.history.append({"role": "assistant", "content": welcome})
        return welcome

    def get_next_question(self) -> dict | None:
        if self.current_question_index < len(self.questions):
            q = self.questions[self.current_question_index]
            self.current_question_index += 1
            return q
        return None

    def process_answer(self, answer_text: str, question: dict) -> dict:
        """Procesa la respuesta, evalúa con IA y genera follow-up si es necesario."""
        self.history.append({"role": "user", "content": answer_text})

        evaluation = {"score": None, "summary": "IA no disponible"}
        if self.ai:
            try:
                evaluation = self.ai.evaluate_response(question, answer_text)
            except Exception:
                pass

        follow_up = None
        if evaluation.get("score") is not None and float(evaluation.get("score", 0)) < 3.0:
            follow_up = self._generate_follow_up(question, answer_text)

        return {
            "evaluation": evaluation,
            "follow_up": follow_up,
            "finished": self.current_question_index >= len(self.questions) and not follow_up,
        }

    def _generate_follow_up(self, question: dict, answer_text: str) -> str:
        if self.ai:
            try:
                system = "Sos ALBA, una entrevistadora amable pero exigente. Pedí una aclaración breve."
                prompt = (
                    f'La respuesta a "{question.get("question_text", "")}" fue insuficiente.\n\n'
                    f"RESPUESTA: {answer_text[:1000]}\n\n"
                    f"Generá UNA pregunta de follow-up breve (máx 20 palabras)."
                )
                result = self.ai._call(
                    [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    json_mode=False,
                )
                return str(result)
            except Exception:
                pass
        return "¿Podrías contarme más detalles sobre qué acciones concretas tomaste?"

    def generate_closing(self) -> str:
        return (
            "Muchas gracias por tu tiempo. La entrevista ha finalizado. "
            "RR. HH. revisará tus respuestas y se contactará contigo."
        )

    # ------------------------------------------------------------------
    # PERSISTENCIA
    # ------------------------------------------------------------------
    def save_transcript(self) -> str:
        """Guarda el transcript en formato legible."""
        lines = []
        for m in self.history:
            speaker = "ALBA" if m["role"] == "assistant" else "Candidato/a"
            lines.append(f"{speaker}: {m['content']}")
        return "\n\n".join(lines)

    def get_transcript_dict(self) -> list[dict]:
        """Devuelve el historial como lista de dicts."""
        return list(self.history)
