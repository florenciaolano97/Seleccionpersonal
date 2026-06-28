import os
import re
import io
import json
import time
import base64
import tempfile
import threading
import wave
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import requests
import streamlit as st

try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except Exception:
    FASTER_WHISPER_AVAILABLE = False

try:
    from streamlit_webrtc import (
        webrtc_streamer,
        WebRtcMode,
        VideoProcessorBase,
        AudioProcessorBase,
        RTCConfiguration,
    )
    import av
    import cv2
    WEBRTC_AVAILABLE = True
except Exception:
    WEBRTC_AVAILABLE = False

try:
    import mediapipe as mp
    MEDIAPIPE_AVAILABLE = bool(getattr(getattr(mp, "solutions", None), "face_detection", None))
except Exception:
    mp = None
    MEDIAPIPE_AVAILABLE = False

APP_TITLE = "AI-RRHH | Alba videollamada de selección"
DID_API_URL = "https://api.d-id.com/talks"
DEFAULT_DID_VOICE = "es-AR-ElenaNeural"
OLLAMA_URL_DEFAULT = "http://localhost:11434/api/generate"
DATA_DIR = Path("data")
AUDIO_DIR = DATA_DIR / "audios"
DATA_DIR.mkdir(exist_ok=True)
AUDIO_DIR.mkdir(exist_ok=True)

ROLE_QUESTIONS = {
    "Operario/a de inyección plástica": [
        "Hola, soy Alba, tu entrevistadora virtual de Recursos Humanos. Para comenzar, contame tu experiencia previa en producción, inyección plástica, autopartes o líneas industriales.",
        "¿Qué elementos de protección personal usarías y qué harías si una máquina parece insegura?",
        "Contame una situación en la que hayas tenido que seguir una instrucción precisa o un estándar de trabajo.",
        "¿Qué defectos visuales buscarías en una pieza plástica antes de liberarla o empacarla?",
        "¿Tenés disponibilidad para turnos rotativos, noche o fines de semana según necesidad productiva?",
        "¿Cómo actuarías si ves que un compañero saltea un paso de seguridad para producir más rápido?",
    ],
    "Control de calidad": [
        "Hola, soy Alba. Para comenzar, contame tu experiencia en control de calidad, inspección visual, medición o registros.",
        "¿Qué harías si encontrás una pieza fuera de especificación pero producción necesita cumplir el objetivo del turno?",
        "¿Usaste calibre, pie de rey, galgas, plantillas de control, planillas o sistemas de trazabilidad?",
        "¿Cómo documentarías una no conformidad para que sea útil y objetiva?",
        "¿Cómo comunicarías un problema de calidad a producción sin generar conflicto?",
        "¿Qué harías si no estás seguro de si un defecto es aceptable o no?",
    ],
    "Mantenimiento / cambio de moldes": [
        "Hola, soy Alba. Para comenzar, contame tu experiencia en mantenimiento industrial, inyectoras, moldes, neumática, hidráulica o electricidad.",
        "¿Qué pasos de seguridad harías antes de intervenir una máquina?",
        "¿Cómo diagnosticarías una falla repetitiva en una inyectora o periférico?",
        "¿Participaste en cambios de molde, ajustes de proceso o mantenimiento preventivo?",
        "¿Cómo registrás una intervención para que sirva al turno siguiente?",
        "¿Qué harías si producción te presiona para reparar rápido salteando un paso de seguridad?",
    ],
}

COMPETENCIES = [
    "Experiencia industrial/autopartista",
    "Seguridad y EPP",
    "Calidad y atención al detalle",
    "Disciplina operativa",
    "Comunicación verbal",
    "Disponibilidad operativa",
]

KEYWORDS = {
    "Experiencia industrial/autopartista": ["producción", "linea", "línea", "fábrica", "industria", "inyección", "inyectora", "plástico", "autoparte", "autopartista", "operario", "máquina", "molde"],
    "Seguridad y EPP": ["epp", "guantes", "lentes", "protección", "seguridad", "procedimiento", "riesgo", "accidente", "bloqueo", "detener", "avisar", "supervisor"],
    "Calidad y atención al detalle": ["calidad", "defecto", "rebaba", "fisura", "mancha", "deformación", "control", "inspección", "no conformidad", "medición", "calibre"],
    "Disciplina operativa": ["instrucción", "procedimiento", "estándar", "cumplir", "orden", "puntual", "responsable", "supervisor", "pasos"],
    "Comunicación verbal": ["comunicar", "avisar", "explicar", "consultar", "equipo", "compañero", "supervisor", "respeto", "ejemplo"],
    "Disponibilidad operativa": ["turno", "rotativo", "noche", "fines de semana", "disponibilidad", "horas extra", "franco"],
}

RED_FLAGS = [
    r"no uso epp", r"sin epp", r"no respeto procedimiento", r"salte(o|ar) seguridad",
    r"no acepto indicaciones", r"no sigo instrucciones", r"llego tarde siempre",
    r"no puedo turnos", r"no trabajo de noche", r"no puedo rotar", r"no avis(o|aría)",
]

SENSITIVE_TOPICS = [
    "edad", "fecha de nacimiento", "estado civil", "embarazo", "hijos", "religión", "política", "sindicato",
    "orientación sexual", "salud", "discapacidad", "nacionalidad", "raza", "domicilio exacto", "obra social",
]


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_secret(name: str, default: str = "") -> str:
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.getenv(name, default)


def normalize_image_url(value: str) -> str:
    value = (value or "").strip().strip('"').strip("'")
    if not value:
        return ""
    img_match = re.search(r"\[img\](https?://[^\[]+)\[/img\]", value, re.I)
    if img_match:
        value = img_match.group(1).strip()
    else:
        url_match = re.search(r"https?://\S+", value)
        if url_match:
            value = url_match.group(0).strip()
    value = value.replace("]", "").replace("[/img", "").strip()
    value = value.split()[0].strip() if value.split() else value
    return value


def is_valid_public_image_url(value: str) -> bool:
    value = normalize_image_url(value)
    return bool(re.match(r"^https://.+\.(jpg|jpeg|png|webp)(\?.*)?$", value, re.I))


def did_headers(api_key: str) -> Dict[str, str]:
    raw = api_key.strip()
    if raw.lower().startswith("basic "):
        auth = raw
    else:
        auth = "Basic " + base64.b64encode(raw.encode("utf-8")).decode("utf-8")
    return {"Authorization": auth, "Content-Type": "application/json"}


def create_did_video(text: str, api_key: str, source_url: str, voice_id: str) -> str:
    source_url = normalize_image_url(source_url)
    if not is_valid_public_image_url(source_url):
        raise RuntimeError("D_ID_SOURCE_URL inválida. Pegá una URL pública HTTPS directa terminada en .jpg, .jpeg, .png o .webp.")
    payload = {
        "source_url": source_url,
        "script": {
            "type": "text",
            "input": text,
            "provider": {"type": "microsoft", "voice_id": voice_id},
        },
        "config": {"fluent": True, "pad_audio": 0.2, "stitch": True},
    }
    r = requests.post(DID_API_URL, headers=did_headers(api_key), json=payload, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"D-ID error {r.status_code}: {r.text}")
    talk_id = r.json().get("id")
    if not talk_id:
        raise RuntimeError(f"D-ID no devolvió id: {r.text}")
    status_url = f"{DID_API_URL}/{talk_id}"
    started = time.time()
    while time.time() - started < 150:
        s = requests.get(status_url, headers=did_headers(api_key), timeout=30)
        if s.status_code >= 400:
            raise RuntimeError(f"D-ID polling error {s.status_code}: {s.text}")
        data = s.json()
        if data.get("status") == "done" and data.get("result_url"):
            return data["result_url"]
        if data.get("status") in ["error", "rejected"]:
            raise RuntimeError(f"D-ID rechazó el video: {json.dumps(data, ensure_ascii=False)}")
        time.sleep(2)
    raise TimeoutError("D-ID tardó demasiado en generar el video.")


@st.cache_resource(show_spinner=False)
def load_whisper_model(model_size: str, device: str, compute_type: str):
    if not FASTER_WHISPER_AVAILABLE:
        raise RuntimeError("faster-whisper no está instalado. Ejecutá: pip install -r requirements.txt")
    return WhisperModel(model_size, device=device, compute_type=compute_type)


def transcribe_local(audio_bytes: bytes, suffix: str, model_size: str, device: str, compute_type: str) -> str:
    if not audio_bytes:
        return ""
    suffix = suffix if suffix.startswith(".") else ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name
    try:
        model = load_whisper_model(model_size, device, compute_type)
        segments, _ = model.transcribe(tmp_path, language="es", vad_filter=True)
        return " ".join([seg.text.strip() for seg in segments]).strip()
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


def call_ollama(prompt: str, model: str, url: str, timeout: int = 90) -> Optional[str]:
    try:
        r = requests.post(url, json={"model": model, "prompt": prompt, "stream": False}, timeout=timeout)
        if r.status_code >= 400:
            return None
        return r.json().get("response", "").strip()
    except Exception:
        return None


def detect_sensitive_data(text: str) -> List[str]:
    low = text.lower()
    return [topic for topic in SENSITIVE_TOPICS if topic in low]


def local_score(text: str) -> Dict:
    low = text.lower()
    comp_scores = {}
    evidence = {}
    for comp, words in KEYWORDS.items():
        hits_words = [w for w in words if w.lower() in low]
        length_bonus = min(len(text.split()) / 90, 1) * 20
        comp_scores[comp] = int(min((len(hits_words) / 5) * 80 + length_bonus, 100))
        evidence[comp] = hits_words[:8]
    red = []
    for pat in RED_FLAGS:
        if re.search(pat, low):
            red.append(pat)
    sensitive = detect_sensitive_data(text)
    avg = int(sum(comp_scores.values()) / len(comp_scores)) if comp_scores else 0
    if red or avg < 50:
        rec = "RECHAZAR PRIMERA INSTANCIA"
        confidence = "Media" if red else "Baja/Media"
    elif avg >= 72:
        rec = "APROBAR PRIMERA INSTANCIA"
        confidence = "Media" if avg < 82 else "Alta"
    else:
        rec = "REVISIÓN HUMANA"
        confidence = "Media"
    strengths = [f"{k}: evidencia favorable ({v}/100). Palabras/evidencias: {', '.join(evidence[k]) or 'no aplica'}" for k, v in comp_scores.items() if v >= 70]
    risks = [f"{k}: evidencia insuficiente ({v}/100)." for k, v in comp_scores.items() if v < 45]
    if red:
        risks.append("Alertas críticas detectadas en la respuesta: " + ", ".join(red))
    if sensitive:
        risks.append("El texto contiene datos sensibles/no pertinentes. No se usan para decidir: " + ", ".join(sensitive))
    return {
        "score": avg,
        "recommendation": rec,
        "confidence": confidence,
        "competency_scores": comp_scores,
        "evidence": evidence,
        "strengths": strengths,
        "risks": risks,
        "red_flags": red,
        "sensitive_data_detected": sensitive,
    }


def ollama_evaluate(transcript: str, role: str, model: str, url: str, video_observations: Dict) -> Dict:
    base = local_score(transcript)
    prompt = f"""
Actuá como especialista senior de RRHH industrial para una empresa autopartista plástica.
Evaluá la entrevista acumulada para el puesto: {role}.

Reglas obligatorias:
- No uses ni infieras edad, salud, género, estado civil, nacionalidad, religión, política, sindicato, orientación sexual, familia ni datos sensibles.
- No evalúes emociones, belleza, personalidad por gestos, tono de piel, rasgos físicos ni apariencia.
- Los observables de video solo sirven como condiciones de entrevista: cámara activa, presencia visible, estabilidad técnica, audio/transcripción. No los uses para inferir capacidad laboral.
- La decisión final siempre debe ser humana.

Transcripción del candidato:
{transcript}

Observables técnicos seguros de la entrevista:
{json.dumps(video_observations, ensure_ascii=False)}

Respondé SOLO JSON válido con estas claves:
recommendation, score, confidence, strengths, risks, rationale, decision_explanation, follow_up_question.
Recomendaciones permitidas: APROBAR PRIMERA INSTANCIA, REVISIÓN HUMANA, RECHAZAR PRIMERA INSTANCIA.
La clave decision_explanation debe explicar claramente por qué avanzar, rechazar o dejar en revisión humana, con evidencias laborales concretas.
"""
    out = call_ollama(prompt, model, url)
    if out:
        try:
            match = re.search(r"\{.*\}", out, re.S)
            data = json.loads(match.group(0) if match else out)
            data.setdefault("competency_scores", base["competency_scores"])
            data.setdefault("evidence", base["evidence"])
            data.setdefault("red_flags", base["red_flags"])
            data.setdefault("sensitive_data_detected", base["sensitive_data_detected"])
            return data
        except Exception:
            pass
    base["rationale"] = build_local_rationale(base, video_observations)
    base["decision_explanation"] = base["rationale"]
    base["follow_up_question"] = "Gracias. ¿Podrías darme un ejemplo concreto relacionado con seguridad, calidad o trabajo en equipo?"
    return base


def next_question_with_ollama(history: List[Dict], role: str, model: str, url: str, fallback: str) -> str:
    transcript = "\n".join([f"Alba: {h['question']}\nCandidato: {h['answer']}" for h in history])
    prompt = f"""
Sos Alba, entrevistadora virtual de RRHH para una empresa autopartista plástica.
Puesto: {role}.
Con base en este historial, generá UNA sola repregunta breve, profesional y concreta.
Debe profundizar en seguridad, calidad, experiencia real, disponibilidad o criterio operativo según lo que falte.
No preguntes datos sensibles. No hagas preguntas sobre edad, salud, familia, religión, política, sindicato, nacionalidad o estado civil.
Historial:
{transcript}
"""
    out = call_ollama(prompt, model, url)
    if out:
        cleaned = out.split("\n")[0].strip().strip('"')
        return cleaned[:500]
    return fallback


def build_local_rationale(eval_data: Dict, video_obs: Dict) -> str:
    rec = eval_data.get("recommendation", "REVISIÓN HUMANA")
    score = eval_data.get("score", 0)
    comp = eval_data.get("competency_scores", {})
    risks = eval_data.get("risks", [])
    strengths = eval_data.get("strengths", [])

    if rec == "APROBAR PRIMERA INSTANCIA":
        decision = "Alba recomienda avanzar porque el puntaje global supera el umbral esperado y se observan evidencias laborales suficientes en competencias críticas para el puesto."
    elif rec == "RECHAZAR PRIMERA INSTANCIA":
        decision = "Alba recomienda no avanzar en esta primera instancia porque la evidencia aportada es insuficiente para los requisitos del puesto o aparecen alertas críticas relacionadas con seguridad, conducta operativa o disponibilidad."
    else:
        decision = "Alba recomienda revisión humana porque el caso queda en zona intermedia: hay información parcial, ambigua o insuficiente para resolver de forma automática."

    top = sorted(comp.items(), key=lambda x: x[1], reverse=True)[:3]
    low = sorted(comp.items(), key=lambda x: x[1])[:3]
    obs_txt = (
        f"Condiciones técnicas de entrevista: cámara activa={video_obs.get('camera_active')}, "
        f"presencia visible aproximada={video_obs.get('face_presence_ratio')}, "
        f"máximo de rostros detectados={video_obs.get('max_faces_detected')}. "
        "Estos datos solo describen condiciones técnicas de la entrevista y no se usan para inferir personalidad ni emociones."
    )
    return (
        f"{decision}\n\n"
        f"Puntaje global: {score}/100. Competencias más fuertes: {top}. Competencias con menor evidencia: {low}.\n\n"
        f"Fortalezas detectadas: {strengths or 'No se identificaron fortalezas suficientes.'}\n\n"
        f"Riesgos o brechas: {risks or 'No se identificaron riesgos relevantes.'}\n\n"
        f"{obs_txt}\n\n"
        "La decisión final debe ser validada por RRHH/jefatura con criterio humano y documentación de respaldo."
    )


def build_report(role: str, history: List[Dict], final_eval: Dict, video_obs: Dict) -> str:
    questions = "\n".join([f"{i+1}. Alba: {h['question']}\n   Candidato: {h['answer']}" for i, h in enumerate(history)])
    comp_lines = "\n".join([f"- {k}: {v}/100" for k, v in final_eval.get("competency_scores", {}).items()])
    strengths = "\n".join([f"- {s}" for s in final_eval.get("strengths", [])]) or "- No se identificaron fortalezas suficientes."
    risks = "\n".join([f"- {r}" for r in final_eval.get("risks", [])]) or "- No se identificaron riesgos relevantes."
    return f"""# Informe preliminar de entrevista con Alba

Fecha: {now_str()}
Puesto evaluado: {role}
Recomendación preliminar: {final_eval.get('recommendation', '')}
Score preliminar: {final_eval.get('score', '')}/100
Confianza: {final_eval.get('confidence', 'No informada')}

## 1. Criterio de decisión
- Aprobar primera instancia: evidencia suficiente en competencias críticas y ausencia de alertas críticas.
- Revisión humana: evidencia parcial, ambigua o caso intermedio.
- Rechazar primera instancia: evidencia insuficiente, alerta crítica laboral o incompatibilidad operativa relevante.

## 2. Explicación clara de la recomendación
{final_eval.get('decision_explanation') or final_eval.get('rationale') or build_local_rationale(final_eval, video_obs)}

## 3. Puntaje por competencia
{comp_lines}

## 4. Fortalezas laborales observadas
{strengths}

## 5. Riesgos, brechas o motivos de revisión
{risks}

## 6. Observables técnicos de la videollamada
- Cámara activa: {video_obs.get('camera_active')}
- Presencia visible aproximada durante la entrevista: {video_obs.get('face_presence_ratio')}
- Máximo de rostros detectados: {video_obs.get('max_faces_detected')}
- Frames procesados: {video_obs.get('frame_count')}

Nota: estos observables solo describen condiciones técnicas de la entrevista. No se utilizan para inferir emociones, personalidad, honestidad, inteligencia ni rasgos sensibles.

## 7. Transcripción de preguntas y respuestas
{questions}

## 8. Recomendación de acción humana
- Si la recomendación fue APROBAR: coordinar entrevista humana/técnica y validar referencias laborales.
- Si fue REVISIÓN HUMANA: revisar las respuestas con foco en las brechas detectadas y decidir si corresponde una repregunta o entrevista humana.
- Si fue RECHAZAR: validar que el motivo sea laboral, objetivo y documentable antes de cerrar el proceso.
"""


if WEBRTC_AVAILABLE:
    class InterviewVideoProcessor(VideoProcessorBase):
        def __init__(self):
            self.lock = threading.Lock()
            self.frame_count = 0
            self.face_detected_frames = 0
            self.last_face_count = 0
            self.max_faces_detected = 0
            self.mp_face = None
            self.face_detector_ready = False
            if MEDIAPIPE_AVAILABLE:
                try:
                    face_detection_module = getattr(getattr(mp, "solutions", None), "face_detection", None)
                    self.mp_face = face_detection_module.FaceDetection(model_selection=0, min_detection_confidence=0.5)
                    self.face_detector_ready = True
                except Exception:
                    self.mp_face = None
                    self.face_detector_ready = False

        def recv(self, frame):
            img = frame.to_ndarray(format="bgr24")
            with self.lock:
                self.frame_count += 1
                fc = self.frame_count

            if self.mp_face is not None and fc % 5 == 0:
                try:
                    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    res = self.mp_face.process(rgb)
                    detections = getattr(res, "detections", None) or []
                    face_count = len(detections)
                    with self.lock:
                        self.last_face_count = face_count
                        self.max_faces_detected = max(self.max_faces_detected, face_count)
                        if face_count > 0:
                            self.face_detected_frames += 1
                except Exception:
                    with self.lock:
                        self.last_face_count = 0

            with self.lock:
                last = self.last_face_count
                ready = self.face_detector_ready
            label = "Videollamada activa"
            if ready:
                label += f" | rostros detectados: {last}"
            cv2.putText(img, label, (18, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.78, (255, 255, 255), 2)
            return av.VideoFrame.from_ndarray(img, format="bgr24")

        def get_stats(self) -> Dict:
            with self.lock:
                processed_detection_steps = max(self.frame_count // 5, 1)
                ratio = self.face_detected_frames / processed_detection_steps
                return {
                    "frame_count": self.frame_count,
                    "face_presence_ratio": round(float(ratio), 2),
                    "last_face_count": self.last_face_count,
                    "max_faces_detected": self.max_faces_detected,
                }

    class InterviewAudioProcessor(AudioProcessorBase):
        def __init__(self):
            self.lock = threading.Lock()
            self.recording = False
            self.frames = []
            self.sample_rate = 48000

        def recv(self, frame):
            if self.recording:
                try:
                    arr = frame.to_ndarray()
                    self.sample_rate = int(getattr(frame, "sample_rate", 48000) or 48000)
                    # PyAV suele entregar planar: (channels, samples). Convertimos a mono.
                    if arr.ndim == 2:
                        if arr.shape[0] <= 8:
                            arr = arr.mean(axis=0)
                        else:
                            arr = arr.mean(axis=1)
                    arr = np.asarray(arr)
                    if arr.dtype != np.int16:
                        if np.issubdtype(arr.dtype, np.floating):
                            arr = np.clip(arr, -1.0, 1.0)
                            arr = (arr * 32767).astype(np.int16)
                        else:
                            arr = arr.astype(np.int16)
                    with self.lock:
                        self.frames.append(arr.copy())
                except Exception:
                    pass
            return frame

        def start(self):
            with self.lock:
                self.frames = []
                self.recording = True

        def stop(self) -> bytes:
            with self.lock:
                self.recording = False
                frames = list(self.frames)
                self.frames = []
                sr = self.sample_rate
            if not frames:
                return b""
            audio = np.concatenate(frames).astype(np.int16)
            bio = io.BytesIO()
            with wave.open(bio, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sr)
                wf.writeframes(audio.tobytes())
            return bio.getvalue()

        def is_recording(self) -> bool:
            with self.lock:
                return bool(self.recording)


st.set_page_config(page_title=APP_TITLE, page_icon="🎥", layout="wide")
st.markdown(
    """
<style>
.main-card{border:1px solid #E7EAF3;border-radius:18px;padding:18px;background:#fff;box-shadow:0 8px 30px rgba(20,30,60,.06)}
.alba-bubble{border-left:5px solid #6757ff;background:#eef1ff;border-radius:18px;padding:18px;font-size:18px;line-height:1.5}
.user-bubble{background:#eaf4ff;border-radius:18px;padding:18px;font-size:17px;line-height:1.5}
.safe-note{background:#fff8df;border-radius:12px;padding:12px;border-left:4px solid #d4a000}
.big-status{font-size:20px;font-weight:700;padding:12px 16px;border-radius:12px;background:#eef1ff;display:inline-block}
</style>
""",
    unsafe_allow_html=True,
)

for key, default in {
    "step": 0,
    "history": [],
    "current_video_url": "",
    "current_question": "",
    "last_transcript": "",
    "recorded_audio": b"",
    "recording_status": "idle",
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

with st.sidebar:
    st.header("Configuración")
    role = st.selectbox("Puesto", list(ROLE_QUESTIONS.keys()))
    did_api_key = st.text_input("D_ID_API_KEY", value=get_secret("D_ID_API_KEY"), type="password")
    did_source_url_raw = st.text_input(
        "D_ID_SOURCE_URL",
        value=get_secret("D_ID_SOURCE_URL", "https://i.postimg.cc/jSwybb4C/4m0Obqg3KQUKRm1IAm-Ja-Hh-PB3qsae-Ih-TWs-Sc-JW3OMD5R-tsn-TJUy-W-xu-J4W1POFJAj-PGBQyh-Ik48GC4PNg-RGD7z.jpg"),
        help="URL directa pública HTTPS terminada en .jpg/.jpeg/.png/.webp",
    )
    did_source_url = normalize_image_url(did_source_url_raw)
    did_voice = st.text_input("Voz D-ID", value=get_secret("D_ID_VOICE_ID", DEFAULT_DID_VOICE))
    st.divider()
    st.subheader("Transcripción local")
    whisper_model = st.selectbox("Modelo Whisper local", ["tiny", "base", "small", "medium"], index=1)
    whisper_device = st.selectbox("Dispositivo", ["cpu", "cuda"], index=0)
    compute_type = st.selectbox("Compute type", ["int8", "float32", "float16"], index=0)
    st.divider()
    st.subheader("Ollama local")
    use_ollama = st.toggle("Usar Ollama para diálogo/evaluación", value=True)
    ollama_model = st.text_input("Modelo Ollama", value="llama3.1")
    ollama_url = st.text_input("URL Ollama", value=OLLAMA_URL_DEFAULT)
    st.caption("Ejecutá: ollama pull llama3.1 / ollama serve")

questions = ROLE_QUESTIONS[role]
if not st.session_state.current_question:
    st.session_state.current_question = questions[0]

st.title("Alba — videollamada de selección")
st.caption("Modo Streamlit: cámara en vivo + grabación de respuesta + transcripción local + respuesta de Alba con D-ID. No usa OpenAI API.")

if not FASTER_WHISPER_AVAILABLE:
    st.error("Falta faster-whisper. Instalá con: pip install -r requirements.txt")
if not WEBRTC_AVAILABLE:
    st.error("Falta streamlit-webrtc. Instalá con: pip install -r requirements.txt")
if did_source_url and not is_valid_public_image_url(did_source_url):
    st.error("D_ID_SOURCE_URL inválida: debe ser HTTPS y terminar en .jpg, .jpeg, .png o .webp.")

progress = min((st.session_state.step + 1) / len(questions), 1.0)
st.progress(progress)

col_video, col_chat = st.columns([1.25, 1])
with col_video:
    st.subheader("🎥 Videollamada del candidato")
    ctx = None
    camera_active = False
    video_obs = {"camera_active": "no", "face_presence_ratio": 0, "max_faces_detected": 0, "frame_count": 0}
    if WEBRTC_AVAILABLE:
        st.info("Si aparece un error del navegador, recargá la página con Ctrl+F5 y luego tocá START.")
        rtc_config = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})
        ctx = webrtc_streamer(
            key="candidate_video_call_v11",
            mode=WebRtcMode.SENDRECV,
            rtc_configuration=rtc_config,
            video_processor_factory=InterviewVideoProcessor,
            audio_processor_factory=InterviewAudioProcessor,
            media_stream_constraints={"video": True, "audio": True},
            async_processing=False,
        )
        camera_active = bool(ctx.state.playing)
        if ctx.video_processor:
            video_obs.update(ctx.video_processor.get_stats())
        video_obs["camera_active"] = "sí" if camera_active else "no"

    if ctx and ctx.state.playing:
        st.success("Videollamada activa. El candidato puede ver la cámara y responder hablando.")
    else:
        st.warning("Tocá START y permití cámara + micrófono para iniciar la videollamada.")

    st.subheader("🎬 Alba hablando")
    q = st.session_state.current_question
    if st.button("Generar / reproducir pregunta con Alba", type="primary", use_container_width=True):
        if not did_api_key or not did_source_url or not is_valid_public_image_url(did_source_url):
            st.error("Falta D_ID_API_KEY o D_ID_SOURCE_URL válida.")
        else:
            with st.spinner("Generando video de Alba con D-ID..."):
                try:
                    st.session_state.current_video_url = create_did_video(q, did_api_key, did_source_url, did_voice)
                except Exception as e:
                    st.error(str(e))
    if st.session_state.current_video_url:
        st.video(st.session_state.current_video_url)
    else:
        st.image(did_source_url if is_valid_public_image_url(did_source_url) else "https://i.postimg.cc/jSwybb4C/4m0Obqg3KQUKRm1IAm-Ja-Hh-PB3qsae-Ih-TWs-Sc-JW3OMD5R-tsn-TJUy-W-xu-J4W1POFJAj-PGBQyh-Ik48GC4PNg-RGD7z.jpg")

with col_chat:
    st.subheader("💬 Conversación")
    for item in st.session_state.history[-5:]:
        st.markdown(f"<div class='alba-bubble'><b>Alba:</b><br>{item['question']}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='user-bubble'><b>Candidato:</b><br>{item['answer']}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='alba-bubble'><b>Alba:</b><br>{st.session_state.current_question}</div>", unsafe_allow_html=True)

st.divider()
st.subheader("🎙️ Respuesta del candidato en videollamada")

rec_cols = st.columns([1, 1, 1, 1])
with rec_cols[0]:
    if st.button("🔴 Iniciar grabación", type="primary", use_container_width=True):
        if ctx and ctx.audio_processor:
            ctx.audio_processor.start()
            st.session_state.recording_status = "recording"
            st.session_state.recorded_audio = b""
            st.toast("Grabación iniciada")
        else:
            st.error("Primero iniciá la videollamada con START y permití micrófono.")
with rec_cols[1]:
    if st.button("⏹️ Detener", use_container_width=True):
        if ctx and ctx.audio_processor:
            data = ctx.audio_processor.stop()
            st.session_state.recorded_audio = data
            st.session_state.recording_status = "stopped"
            if data:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                path = AUDIO_DIR / f"respuesta_{ts}.wav"
                path.write_bytes(data)
                st.success(f"Grabación guardada: {path}")
            else:
                st.warning("No se capturó audio. Revisá permisos de micrófono.")
        else:
            st.error("No hay sesión de audio activa.")
with rec_cols[2]:
    if st.button("📝 Transcribir", use_container_width=True):
        if not st.session_state.recorded_audio:
            st.error("Primero grabá una respuesta.")
        else:
            with st.spinner("Transcribiendo con Faster Whisper local..."):
                try:
                    st.session_state.last_transcript = transcribe_local(st.session_state.recorded_audio, ".wav", whisper_model, whisper_device, compute_type)
                    st.success("Transcripción lista")
                except Exception as e:
                    st.error(str(e))
with rec_cols[3]:
    if st.button("🤖 Enviar y que Alba responda", use_container_width=True):
        st.session_state.submit_answer = True

if st.session_state.recording_status == "recording":
    st.markdown("<span class='big-status'>🔴 Grabando respuesta del candidato...</span>", unsafe_allow_html=True)

if st.session_state.recorded_audio:
    st.audio(st.session_state.recorded_audio, format="audio/wav")

answer = st.text_area(
    "Transcripción editable de la respuesta",
    value=st.session_state.last_transcript,
    height=140,
    placeholder="La transcripción aparecerá acá. También podés corregirla antes de enviarla.",
)

st.markdown(
    "<div class='safe-note'>Evaluación no verbal segura: la app solo registra condiciones técnicas de la videollamada, como cámara activa y presencia visible aproximada. No infiere emociones, personalidad, honestidad ni aptitud por la apariencia o gestos.</div>",
    unsafe_allow_html=True,
)

if st.session_state.get("submit_answer"):
    st.session_state.submit_answer = False
    if not answer.strip():
        st.error("Primero grabá/transcribí o escribí una respuesta.")
    else:
        current_video_obs = video_obs.copy()
        eval_data = ollama_evaluate(answer, role, ollama_model, ollama_url, current_video_obs) if use_ollama else local_score(answer)
        fallback_next = questions[min(st.session_state.step + 1, len(questions)-1)] if st.session_state.step + 1 < len(questions) else "Gracias. Ya tengo la información principal. El equipo de RRHH revisará la entrevista."
        if use_ollama and st.session_state.step < len(questions) - 1:
            next_q = next_question_with_ollama(st.session_state.history + [{"question": st.session_state.current_question, "answer": answer}], role, ollama_model, ollama_url, fallback_next)
        else:
            next_q = fallback_next
        st.session_state.history.append({
            "timestamp": now_str(),
            "role": role,
            "question": st.session_state.current_question,
            "answer": answer,
            "camera_active": current_video_obs.get("camera_active"),
            "video_observations": current_video_obs,
            "evaluation": eval_data,
        })
        st.session_state.step = min(st.session_state.step + 1, len(questions) - 1)
        st.session_state.current_question = next_q
        st.session_state.current_video_url = ""
        st.session_state.last_transcript = ""
        st.session_state.recorded_audio = b""
        # Genera automáticamente el próximo video de Alba si está configurado D-ID.
        if did_api_key and did_source_url and is_valid_public_image_url(did_source_url):
            with st.spinner("Alba está generando la siguiente pregunta hablada..."):
                try:
                    st.session_state.current_video_url = create_did_video(next_q, did_api_key, did_source_url, did_voice)
                except Exception as e:
                    st.warning(f"No se pudo generar el video de la siguiente pregunta: {e}")
        st.rerun()

st.divider()
nav1, nav2 = st.columns([1, 1])
with nav1:
    if st.button("⬅️ Volver pregunta anterior", use_container_width=True):
        if st.session_state.history:
            st.session_state.history.pop()
            st.session_state.step = max(st.session_state.step - 1, 0)
            st.session_state.current_question = questions[st.session_state.step]
            st.session_state.current_video_url = ""
            st.session_state.last_transcript = ""
            st.session_state.recorded_audio = b""
            st.rerun()
with nav2:
    if st.button("🔄 Reiniciar entrevista", use_container_width=True):
        st.session_state.step = 0
        st.session_state.history = []
        st.session_state.current_question = questions[0]
        st.session_state.current_video_url = ""
        st.session_state.last_transcript = ""
        st.session_state.recorded_audio = b""
        st.rerun()

st.divider()
st.subheader("📊 Informe preliminar de Alba")
if st.session_state.history:
    all_text = "\n".join([h["answer"] for h in st.session_state.history])
    # Consolidamos observables de video de todas las respuestas.
    obs_list = [h.get("video_observations", {}) for h in st.session_state.history]
    consolidated_obs = {
        "camera_active": "sí" if any(o.get("camera_active") == "sí" for o in obs_list) else "no",
        "face_presence_ratio": round(float(np.mean([o.get("face_presence_ratio", 0) for o in obs_list])) if obs_list else 0, 2),
        "max_faces_detected": max([o.get("max_faces_detected", 0) for o in obs_list] or [0]),
        "frame_count": sum([o.get("frame_count", 0) for o in obs_list]),
    }
    final_eval = ollama_evaluate(all_text, role, ollama_model, ollama_url, consolidated_obs) if use_ollama else local_score(all_text)
    final_eval.setdefault("rationale", build_local_rationale(final_eval, consolidated_obs))
    final_eval.setdefault("decision_explanation", final_eval.get("rationale"))

    m1, m2, m3 = st.columns(3)
    m1.metric("Recomendación", final_eval.get("recommendation", ""))
    m2.metric("Score", f"{final_eval.get('score', 0)}/100")
    m3.metric("Confianza", final_eval.get("confidence", "No informada"))

    st.markdown("### Explicación de la decisión")
    st.write(final_eval.get("decision_explanation") or final_eval.get("rationale") or build_local_rationale(final_eval, consolidated_obs))

    st.markdown("### Puntaje por competencia")
    comp_df = pd.DataFrame([{"Competencia": k, "Puntaje": v} for k, v in final_eval.get("competency_scores", {}).items()])
    if not comp_df.empty:
        st.dataframe(comp_df, use_container_width=True, hide_index=True)
        st.bar_chart(comp_df.set_index("Competencia"))

    st.markdown("### Fortalezas")
    for s in final_eval.get("strengths", []) or ["No se identificaron fortalezas suficientes."]:
        st.write(f"- {s}")

    st.markdown("### Riesgos / brechas")
    for r in final_eval.get("risks", []) or ["No se identificaron riesgos relevantes."]:
        st.write(f"- {r}")

    report_text = build_report(role, st.session_state.history, final_eval, consolidated_obs)
    st.download_button("Descargar informe completo TXT", report_text.encode("utf-8"), "informe_alba_rrhh.txt", "text/plain", use_container_width=True)

    rows = []
    for i, h in enumerate(st.session_state.history, start=1):
        rows.append({
            "fecha": h["timestamp"],
            "pregunta_n": i,
            "puesto": h["role"],
            "pregunta": h["question"],
            "respuesta": h["answer"],
            "camara_activa": h.get("camera_active", ""),
            "observables_video": json.dumps(h.get("video_observations", {}), ensure_ascii=False),
            "recomendacion_parcial": h["evaluation"].get("recommendation", ""),
            "score_parcial": h["evaluation"].get("score", ""),
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button("Descargar entrevista CSV", df.to_csv(index=False).encode("utf-8"), "entrevista_alba.csv", "text/csv")
    st.download_button("Descargar entrevista JSON", json.dumps(st.session_state.history, ensure_ascii=False, indent=2).encode("utf-8"), "entrevista_alba.json", "application/json")
else:
    st.info("Todavía no hay respuestas guardadas. Iniciá la videollamada, generá la pregunta de Alba, grabá la respuesta y enviá para continuar el diálogo.")
