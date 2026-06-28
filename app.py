import os
import io
import re
import json
import time
import base64
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
import streamlit as st
from streamlit_mic_recorder import mic_recorder

try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except Exception:
    FASTER_WHISPER_AVAILABLE = False

try:
    from streamlit_webrtc import webrtc_streamer, WebRtcMode, VideoProcessorBase, RTCConfiguration
    import av
    import cv2
    WEBRTC_AVAILABLE = True
except Exception:
    WEBRTC_AVAILABLE = False

try:
    import mediapipe as mp
    # En algunas versiones/entornos Mediapipe se instala, pero no expone mp.solutions.face_detection.
    MEDIAPIPE_AVAILABLE = bool(getattr(getattr(mp, "solutions", None), "face_detection", None))
except Exception:
    mp = None
    MEDIAPIPE_AVAILABLE = False

APP_TITLE = "AI-RRHH | Alba entrevistadora virtual local"
DID_API_URL = "https://api.d-id.com/talks"
DEFAULT_DID_VOICE = "es-AR-ElenaNeural"
OLLAMA_URL_DEFAULT = "http://localhost:11434/api/generate"
DATA_DIR = Path("data")
AUDIO_DIR = DATA_DIR / "audios"
DATA_DIR.mkdir(exist_ok=True)
AUDIO_DIR.mkdir(exist_ok=True)
HISTORY_FILE = DATA_DIR / "entrevistas_alba_local.csv"

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
        "¿Usaste calibre, pie de rey, galgas, plantillas, planillas de control o sistemas de trazabilidad?",
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
    "Comunicación verbal": ["comunicar", "avisar", "explicar", "consultar", "equipo", "compañero", "supervisor", "respeto"],
    "Disponibilidad operativa": ["turno", "rotativo", "noche", "fines de semana", "disponibilidad", "horas extra", "franco"],
}

RED_FLAGS = [
    r"no uso epp", r"sin epp", r"no respeto procedimiento", r"salte(o|ar) seguridad",
    r"no acepto indicaciones", r"no sigo instrucciones", r"llego tarde siempre",
    r"no puedo turnos", r"no trabajo de noche", r"no puedo rotar"
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
    """Limpia URLs pegadas desde Postimages/Cloudinary y evita errores de D-ID/Streamlit.
    Acepta URL directa, BBCode [img]...[/img] o texto con una URL embebida.
    """
    value = (value or "").strip().strip('"').strip("'")
    if not value:
        return ""
    # Si pegaron BBCode de Postimages, extrae solo la URL directa de la imagen.
    img_match = re.search(r"\[img\](https?://[^\[]+)\[/img\]", value, re.I)
    if img_match:
        value = img_match.group(1).strip()
    else:
        url_match = re.search(r"https?://\S+", value)
        if url_match:
            value = url_match.group(0).strip()
    # Limpieza de caracteres frecuentes al copiar/pegar.
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
        raise RuntimeError("D_ID_SOURCE_URL inválida. Pegá una URL pública HTTPS directa que termine en .jpg, .jpeg, .png o .webp. Ejemplo: https://i.postimg.cc/.../alba.jpg")
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
        raise RuntimeError("faster-whisper no está instalado. Ejecutá: pip install faster-whisper")
    return WhisperModel(model_size, device=device, compute_type=compute_type)


def transcribe_local(audio_bytes: bytes, suffix: str, model_size: str, device: str, compute_type: str) -> str:
    if not audio_bytes:
        return ""
    suffix = suffix if suffix.startswith(".") else ".webm"
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


def local_score(text: str) -> Dict:
    low = text.lower()
    comp_scores = {}
    for comp, words in KEYWORDS.items():
        hits = sum(1 for w in words if w.lower() in low)
        length_bonus = min(len(text.split()) / 90, 1) * 20
        comp_scores[comp] = int(min((hits / 5) * 80 + length_bonus, 100))
    red = []
    for pat in RED_FLAGS:
        if re.search(pat, low):
            red.append(pat)
    avg = int(sum(comp_scores.values()) / len(comp_scores)) if comp_scores else 0
    if red or avg < 50:
        rec = "RECHAZAR PRIMERA INSTANCIA"
    elif avg >= 72:
        rec = "APROBAR PRIMERA INSTANCIA"
    else:
        rec = "REVISIÓN HUMANA"
    strengths = [f"{k}: {v}/100" for k, v in comp_scores.items() if v >= 70]
    risks = [f"{k}: evidencia insuficiente ({v}/100)" for k, v in comp_scores.items() if v < 45]
    if red:
        risks.append("Alertas detectadas: " + ", ".join(red))
    return {"score": avg, "recommendation": rec, "competency_scores": comp_scores, "strengths": strengths, "risks": risks}


def ollama_evaluate(transcript: str, role: str, model: str, url: str) -> Dict:
    base = local_score(transcript)
    prompt = f"""
Actuá como especialista de RRHH industrial. Evaluá esta respuesta de entrevista para el puesto {role}.
No uses ni infieras edad, salud, género, estado civil, nacionalidad, religión, política ni datos familiares.
Respondé SOLO JSON válido con: recommendation, score, strengths, risks, rationale, follow_up_question.
Recomendaciones permitidas: APROBAR PRIMERA INSTANCIA, REVISIÓN HUMANA, RECHAZAR PRIMERA INSTANCIA.
Respuesta del candidato:
{transcript}
"""
    out = call_ollama(prompt, model, url)
    if out:
        try:
            match = re.search(r"\{.*\}", out, re.S)
            data = json.loads(match.group(0) if match else out)
            data.setdefault("competency_scores", base["competency_scores"])
            return data
        except Exception:
            pass
    return {
        **base,
        "rationale": "Evaluación local por reglas porque Ollama no respondió o no devolvió JSON válido.",
        "follow_up_question": "Gracias. ¿Podrías darme un ejemplo concreto relacionado con seguridad, calidad o trabajo en equipo?",
    }


def next_question_with_ollama(history: List[Dict], role: str, model: str, url: str, fallback: str) -> str:
    transcript = "\n".join([f"Alba: {h['question']}\nCandidato: {h['answer']}" for h in history])
    prompt = f"""
Sos Alba, entrevistadora virtual de RRHH para una empresa autopartista plástica.
Puesto: {role}.
Con base en este historial, generá UNA sola repregunta breve, profesional y concreta.
No preguntes datos sensibles. No hagas preguntas sobre edad, salud, familia, religión, política, sindicato o estado civil.
Historial:
{transcript}
"""
    out = call_ollama(prompt, model, url)
    if out:
        return out.split("\n")[0].strip().strip('"')[:450]
    return fallback


if WEBRTC_AVAILABLE:
    class SafeVideoProcessor(VideoProcessorBase):
        def __init__(self):
            self.frame_count = 0
            self.face_detected_count = 0
            self.last_face_present = False
            self.mp_face = None
            self.face_detector_ready = False

            # Detector opcional y seguro. Si Mediapipe falla, la cámara igual funciona.
            if MEDIAPIPE_AVAILABLE:
                try:
                    face_detection_module = getattr(getattr(mp, "solutions", None), "face_detection", None)
                    if face_detection_module is not None:
                        self.mp_face = face_detection_module.FaceDetection(
                            model_selection=0,
                            min_detection_confidence=0.5,
                        )
                        self.face_detector_ready = True
                except Exception:
                    self.mp_face = None
                    self.face_detector_ready = False

        def recv(self, frame):
            img = frame.to_ndarray(format="bgr24")
            self.frame_count += 1

            if self.mp_face is not None and self.frame_count % 5 == 0:
                try:
                    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    res = self.mp_face.process(rgb)
                    face_present = bool(getattr(res, "detections", None))
                    self.last_face_present = face_present
                    if face_present:
                        self.face_detected_count += 1
                except Exception:
                    self.last_face_present = False

            label = "Camara activa"
            if self.face_detector_ready:
                label += " | rostro detectado" if self.last_face_present else " | sin rostro detectado"
            cv2.putText(img, label, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2)
            return av.VideoFrame.from_ndarray(img, format="bgr24")


st.set_page_config(page_title=APP_TITLE, page_icon="🎙️", layout="wide")

st.markdown("""
<style>
.main-card{border:1px solid #E7EAF3;border-radius:18px;padding:18px;background:#fff;box-shadow:0 8px 30px rgba(20,30,60,.06)}
.alba-bubble{border-left:5px solid #6757ff;background:#eef1ff;border-radius:18px;padding:18px;font-size:18px;line-height:1.5}
.user-bubble{background:#eaf4ff;border-radius:18px;padding:18px;font-size:17px;line-height:1.5}
.safe-note{background:#fff8df;border-radius:12px;padding:12px;border-left:4px solid #d4a000}
</style>
""", unsafe_allow_html=True)

if "step" not in st.session_state:
    st.session_state.step = 0
if "history" not in st.session_state:
    st.session_state.history = []
if "current_video_url" not in st.session_state:
    st.session_state.current_video_url = ""
if "current_question" not in st.session_state:
    st.session_state.current_question = ""
if "last_transcript" not in st.session_state:
    st.session_state.last_transcript = ""

with st.sidebar:
    st.header("Configuración")
    role = st.selectbox("Puesto", list(ROLE_QUESTIONS.keys()))
    did_api_key = st.text_input("D_ID_API_KEY", value=get_secret("D_ID_API_KEY"), type="password")
    did_source_url_raw = st.text_input("D_ID_SOURCE_URL", value=get_secret("D_ID_SOURCE_URL"), help="Pegá solo la URL directa de la imagen. Debe empezar con https:// y terminar en .jpg/.jpeg/.png/.webp")
    did_source_url = normalize_image_url(did_source_url_raw)
    if did_source_url_raw and did_source_url != did_source_url_raw.strip():
        st.info(f"URL limpiada automáticamente: {did_source_url}")
    if did_source_url and not is_valid_public_image_url(did_source_url):
        st.error("La URL de imagen no es válida para D-ID. Debe ser HTTPS y terminar en .jpg, .jpeg, .png o .webp.")
    did_voice = st.text_input("Voz D-ID", value=get_secret("D_ID_VOICE_ID", DEFAULT_DID_VOICE))
    st.divider()
    st.subheader("Transcripción local")
    whisper_model = st.selectbox("Modelo Whisper local", ["tiny", "base", "small", "medium"], index=1)
    whisper_device = st.selectbox("Dispositivo", ["cpu", "cuda"], index=0)
    compute_type = st.selectbox("Compute type", ["int8", "float32", "float16"], index=0)
    st.caption("Para CPU usá base + int8. La primera transcripción puede tardar porque descarga el modelo.")
    st.divider()
    st.subheader("Ollama local")
    use_ollama = st.toggle("Usar Ollama para diálogo/evaluación", value=True)
    ollama_model = st.text_input("Modelo Ollama", value="llama3.1")
    ollama_url = st.text_input("URL Ollama", value=OLLAMA_URL_DEFAULT)
    st.caption("Ejecutá en terminal: ollama pull llama3.1  /  ollama serve")

questions = ROLE_QUESTIONS[role]
if not st.session_state.current_question:
    st.session_state.current_question = questions[0]

st.title("Alba — entrevista con avatar, cámara y diálogo local")
st.caption("Sin OpenAI API: transcripción con Faster Whisper local + diálogo/evaluación con Ollama local. D-ID se usa solo para el avatar hablando.")

if not FASTER_WHISPER_AVAILABLE:
    st.warning("No está instalado faster-whisper. Instalá dependencias con: pip install -r requirements.txt")
if not WEBRTC_AVAILABLE:
    st.warning("No está instalado streamlit-webrtc. La cámara puede no funcionar.")
if not did_api_key or not did_source_url or not is_valid_public_image_url(did_source_url):
    st.warning("Para que Alba hable con labios sincronizados completá D_ID_API_KEY y una D_ID_SOURCE_URL válida. Usá una URL directa HTTPS que termine en .jpg/.jpeg/.png/.webp.")

progress = min((st.session_state.step + 1) / len(questions), 1.0)
st.progress(progress)

col1, col2 = st.columns([1.25, 1])
with col1:
    st.subheader("🎥 Cámara del candidato")
    st.markdown("<div class='main-card'>", unsafe_allow_html=True)
    if WEBRTC_AVAILABLE:
        rtc_config = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})
        ctx = webrtc_streamer(
            key="candidate-camera",
            mode=WebRtcMode.SENDRECV,
            rtc_configuration=rtc_config,
            video_processor_factory=SafeVideoProcessor if WEBRTC_AVAILABLE else None,
            media_stream_constraints={"video": True, "audio": False},
            async_processing=True,
        )
        camera_active = bool(ctx.state.playing)
    else:
        camera_active = st.camera_input("Activá cámara") is not None
    st.markdown("</div>", unsafe_allow_html=True)

    st.subheader("🎬 Avatar hablando")
    q = st.session_state.current_question
    if st.button("Generar / reproducir pregunta con Alba", type="primary", use_container_width=True):
        if not did_api_key or not did_source_url or not is_valid_public_image_url(did_source_url):
            st.error("Falta D_ID_API_KEY o la D_ID_SOURCE_URL no es válida. Pegá una URL directa HTTPS terminada en .jpg/.jpeg/.png/.webp.")
        else:
            with st.spinner("Generando video de Alba con D-ID..."):
                try:
                    st.session_state.current_video_url = create_did_video(q, did_api_key, did_source_url, did_voice)
                except Exception as e:
                    st.error(str(e))
    if st.session_state.current_video_url:
        st.video(st.session_state.current_video_url)
    else:
        preview_url = did_source_url if is_valid_public_image_url(did_source_url) else "https://i.postimg.cc/jSwybb4C/4m0Obqg3KQUKRm1IAm-Ja-Hh-PB3qsae-Ih-TWs-Sc-JW3OMD5R-tsn-TJUy-W-xu-J4W1POFJAj-PGBQyh-Ik48GC4PNg-RGD7z.jpg"
        st.image(preview_url)

with col2:
    st.subheader("💬 Conversación")
    st.markdown(f"<div class='alba-bubble'><b>Alba:</b><br>{q}</div>", unsafe_allow_html=True)
    for item in st.session_state.history[-4:]:
        st.markdown(f"<div class='user-bubble'><b>Candidato:</b><br>{item['answer']}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='alba-bubble'><b>Alba:</b><br>{item.get('next_question','')}</div>", unsafe_allow_html=True)

st.divider()
st.subheader("🎙️ Respuesta del candidato")
left, right = st.columns([1, 1.25])
with left:
    audio = mic_recorder(
        start_prompt="🎙️ Grabar respuesta",
        stop_prompt="⏹️ Detener grabación",
        just_once=False,
        use_container_width=True,
        key=f"mic_{st.session_state.step}_{len(st.session_state.history)}",
    )
    if audio and audio.get("bytes"):
        st.audio(audio["bytes"])
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        audio_path = AUDIO_DIR / f"respuesta_{timestamp}.webm"
        audio_path.write_bytes(audio["bytes"])
        st.caption(f"Audio guardado localmente: {audio_path}")
        if st.button("Transcribir automáticamente", type="primary", use_container_width=True):
            with st.spinner("Transcribiendo con Faster Whisper local..."):
                try:
                    text = transcribe_local(audio["bytes"], ".webm", whisper_model, whisper_device, compute_type)
                    st.session_state.last_transcript = text
                except Exception as e:
                    st.error(str(e))

with right:
    answer = st.text_area(
        "Respuesta transcripta / editable",
        value=st.session_state.last_transcript,
        height=180,
        placeholder="La transcripción aparecerá acá. También podés escribir o corregir la respuesta manualmente.",
    )

st.markdown("<div class='safe-note'>La evaluación no infiere emociones, personalidad ni rasgos sensibles por la cámara. Solo registra observables técnicos seguros: cámara activa, audio comprensible y respuesta ordenada.</div>", unsafe_allow_html=True)

c1, c2, c3 = st.columns([1, 1, 1])
with c1:
    if st.button("Guardar respuesta y continuar diálogo", type="primary", use_container_width=True):
        if not answer.strip():
            st.error("Primero grabá/transcribí o escribí una respuesta.")
        else:
            eval_data = ollama_evaluate(answer, role, ollama_model, ollama_url) if use_ollama else local_score(answer)
            fallback_next = questions[min(st.session_state.step + 1, len(questions)-1)] if st.session_state.step + 1 < len(questions) else "Gracias. Ya tengo la información principal. El equipo de RRHH revisará la entrevista."
            if use_ollama and st.session_state.step < len(questions)-1:
                next_q = next_question_with_ollama(st.session_state.history + [{"question": q, "answer": answer}], role, ollama_model, ollama_url, fallback_next)
            else:
                next_q = fallback_next
            st.session_state.history.append({
                "timestamp": now_str(),
                "role": role,
                "question": q,
                "answer": answer,
                "next_question": next_q,
                "camera_active": "sí" if camera_active else "no",
                "evaluation": eval_data,
            })
            st.session_state.step = min(st.session_state.step + 1, len(questions)-1)
            st.session_state.current_question = next_q
            st.session_state.current_video_url = ""
            st.session_state.last_transcript = ""
            st.rerun()
with c2:
    if st.button("Volver pregunta anterior", use_container_width=True):
        if st.session_state.history:
            st.session_state.history.pop()
            st.session_state.step = max(st.session_state.step - 1, 0)
            st.session_state.current_question = questions[st.session_state.step]
            st.session_state.current_video_url = ""
            st.rerun()
with c3:
    if st.button("Reiniciar entrevista", use_container_width=True):
        st.session_state.step = 0
        st.session_state.history = []
        st.session_state.current_question = questions[0]
        st.session_state.current_video_url = ""
        st.session_state.last_transcript = ""
        st.rerun()

st.divider()
st.subheader("📊 Evaluación acumulada")
if st.session_state.history:
    all_text = "\n".join([h["answer"] for h in st.session_state.history])
    final_eval = ollama_evaluate(all_text, role, ollama_model, ollama_url) if use_ollama else local_score(all_text)
    m1, m2 = st.columns(2)
    m1.metric("Recomendación preliminar", final_eval.get("recommendation", ""))
    m2.metric("Score preliminar", f"{final_eval.get('score', 0)}/100")
    st.write("**Fundamento:**", final_eval.get("rationale", "Evaluación preliminar local."))
    st.write("**Fortalezas:**", final_eval.get("strengths", []))
    st.write("**Riesgos/Brechas:**", final_eval.get("risks", []))

    rows = []
    for i, h in enumerate(st.session_state.history, start=1):
        rows.append({
            "fecha": h["timestamp"], "pregunta_n": i, "puesto": h["role"], "pregunta": h["question"],
            "respuesta": h["answer"], "camara_activa": h["camera_active"],
            "recomendacion_parcial": h["evaluation"].get("recommendation", ""),
            "score_parcial": h["evaluation"].get("score", ""),
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button("Descargar entrevista CSV", df.to_csv(index=False).encode("utf-8"), "entrevista_alba.csv", "text/csv")
    st.download_button("Descargar entrevista JSON", json.dumps(st.session_state.history, ensure_ascii=False, indent=2).encode("utf-8"), "entrevista_alba.json", "application/json")
