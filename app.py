import os
import io
import time
import json
import base64
import tempfile
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
import requests
import streamlit as st
from openai import OpenAI
from streamlit_mic_recorder import mic_recorder

try:
    from streamlit_webrtc import webrtc_streamer, VideoHTMLAttributes, WebRtcMode
    WEBRTC_AVAILABLE = True
except Exception:
    WEBRTC_AVAILABLE = False

APP_TITLE = "AI-RRHH | Alba entrevistadora virtual"
DID_API_URL = "https://api.d-id.com/talks"
DID_VOICE_ID = "es-AR-ElenaNeural"
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
HISTORY_FILE = os.path.join(DATA_DIR, "entrevistas_alba.csv")
AUDIO_DIR = os.path.join(DATA_DIR, "audios")
os.makedirs(AUDIO_DIR, exist_ok=True)

QUESTIONS = [
    "Hola, soy Alba, tu entrevistadora virtual de Recursos Humanos. Para comenzar, contame tu experiencia previa en producción, inyección plástica, autopartes o líneas industriales.",
    "¿Qué elementos de protección personal usarías y qué harías si una máquina parece insegura?",
    "Contame una situación en la que hayas tenido que seguir una instrucción precisa o un estándar de trabajo.",
    "¿Qué defectos visuales buscarías en una pieza plástica antes de liberarla o empacarla?",
    "¿Tenés disponibilidad para turnos rotativos, noche o fines de semana según necesidad productiva?",
    "¿Cómo actuarías si ves que un compañero saltea un paso de seguridad para producir más rápido?",
]

EVAL_COMPETENCIES = [
    "Experiencia industrial/autopartista",
    "Seguridad y uso de EPP",
    "Calidad y atención al detalle",
    "Disciplina operativa",
    "Comunicación verbal",
    "Disponibilidad operativa",
]

SAFE_NONVERBAL_CRITERIA = [
    "Cámara encendida durante la respuesta",
    "Audio comprensible",
    "Respuesta ordenada y entendible",
    "No se observan interrupciones técnicas graves",
]


def get_secret(name: str, default: str = "") -> str:
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.getenv(name, default)


def client_openai(api_key: str) -> Optional[OpenAI]:
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def did_headers(api_key: str) -> Dict[str, str]:
    # D-ID API key is usually copied as username:password and must be Basic base64(username:password)
    raw = api_key.strip()
    if raw.lower().startswith("basic "):
        auth = raw
    else:
        encoded = base64.b64encode(raw.encode("utf-8")).decode("utf-8")
        auth = f"Basic {encoded}"
    return {"Authorization": auth, "Content-Type": "application/json"}


def create_did_talk(text: str, api_key: str, source_url: str, voice_id: str = DID_VOICE_ID) -> Dict:
    payload = {
        "source_url": source_url,
        "script": {
            "type": "text",
            "input": text,
            "provider": {"type": "microsoft", "voice_id": voice_id},
        },
        "config": {
            "fluent": True,
            "pad_audio": 0.2,
            "stitch": True,
        },
    }
    r = requests.post(DID_API_URL, headers=did_headers(api_key), json=payload, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"D-ID error {r.status_code}: {r.text}")
    return r.json()


def poll_did_talk(talk_id: str, api_key: str, timeout_seconds: int = 120) -> Dict:
    url = f"{DID_API_URL}/{talk_id}"
    started = time.time()
    last = {}
    while time.time() - started < timeout_seconds:
        r = requests.get(url, headers=did_headers(api_key), timeout=30)
        if r.status_code >= 400:
            raise RuntimeError(f"D-ID polling error {r.status_code}: {r.text}")
        data = r.json()
        last = data
        if data.get("status") == "done" and data.get("result_url"):
            return data
        if data.get("status") in ["error", "rejected"]:
            raise RuntimeError(f"D-ID status {data.get('status')}: {json.dumps(data, ensure_ascii=False)}")
        time.sleep(2)
    raise TimeoutError(f"D-ID tardó demasiado. Último estado: {json.dumps(last, ensure_ascii=False)}")


def generate_avatar_video(question: str, did_key: str, source_url: str) -> str:
    talk = create_did_talk(question, did_key, source_url)
    talk_id = talk.get("id")
    if not talk_id:
        raise RuntimeError(f"D-ID no devolvió id: {talk}")
    done = poll_did_talk(talk_id, did_key)
    return done["result_url"]


def save_audio_bytes(audio_data: Dict, candidate_code: str, q_index: int) -> Optional[str]:
    if not audio_data or "bytes" not in audio_data:
        return None
    ext = "wav"
    mime = audio_data.get("mime_type") or "audio/wav"
    if "webm" in mime:
        ext = "webm"
    elif "mp3" in mime:
        ext = "mp3"
    path = os.path.join(AUDIO_DIR, f"{candidate_code}_pregunta_{q_index+1}.{ext}")
    with open(path, "wb") as f:
        f.write(audio_data["bytes"])
    return path


def transcribe_audio(audio_path: str, openai_key: str) -> str:
    client = client_openai(openai_key)
    if client is None:
        raise RuntimeError("Falta OPENAI_API_KEY para transcribir audio.")
    with open(audio_path, "rb") as f:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            language="es",
        )
    return result.text


def evaluate_answers(candidate_code: str, role_name: str, answers: List[Dict], camera_on: bool, openai_key: str) -> Dict:
    combined = "\n\n".join([f"Pregunta: {a['question']}\nRespuesta: {a['answer']}" for a in answers])
    if not openai_key:
        return local_basic_eval(combined, camera_on)
    client = client_openai(openai_key)
    prompt = f"""
Sos un especialista de Recursos Humanos para preselección inicial en una empresa autopartista plástica.
Evaluá SOLO evidencia laboral de las respuestas. No uses datos sensibles como edad, salud, embarazo, religión, política, estado civil, familia, nacionalidad, orientación sexual, discapacidad o domicilio.

Puesto: {role_name}
Candidato: {candidate_code}
Cámara encendida declarada por sistema: {camera_on}

Respuestas:
{combined}

Devolvé exclusivamente JSON válido con:
recommendation: APROBAR PRIMERA INSTANCIA | REVISIÓN HUMANA | RECHAZAR PRIMERA INSTANCIA
score: entero 0-100
confidence: Baja | Media | Alta
competency_scores: objeto con puntajes 0-100 para {EVAL_COMPETENCIES}
verbal_observations: lista breve sobre claridad, orden y especificidad de respuestas. No evalúes acento, apariencia ni emoción.
nonverbal_observations: lista breve SOLO con observables seguros: cámara encendida, continuidad técnica, audio comprensible. No infieras personalidad, emociones, salud ni honestidad por gestos.
strengths: lista breve
risks: lista breve
rationale: fundamento laboral claro y auditable
human_review_required: boolean
"""
    response = client.responses.create(model="gpt-4.1-mini", input=prompt, temperature=0.2)
    raw = response.output_text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`").replace("json", "", 1).strip()
    try:
        return json.loads(raw)
    except Exception:
        return {"recommendation": "REVISIÓN HUMANA", "score": 0, "confidence": "Baja", "rationale": raw, "human_review_required": True}


def local_basic_eval(text: str, camera_on: bool) -> Dict:
    t = text.lower()
    score = 35
    if any(w in t for w in ["epp", "guantes", "lentes", "seguridad", "protección"]):
        score += 20
    if any(w in t for w in ["inyección", "inyectora", "autoparte", "producción", "línea"]):
        score += 20
    if any(w in t for w in ["calidad", "defecto", "rebaba", "control", "pieza"]):
        score += 15
    if camera_on:
        score += 5
    score = min(score, 100)
    if score >= 75:
        rec = "APROBAR PRIMERA INSTANCIA"
    elif score < 55:
        rec = "RECHAZAR PRIMERA INSTANCIA"
    else:
        rec = "REVISIÓN HUMANA"
    return {
        "recommendation": rec,
        "score": score,
        "confidence": "Media",
        "competency_scores": {},
        "verbal_observations": ["Evaluación local básica por palabras clave. Para análisis completo configurá OPENAI_API_KEY."],
        "nonverbal_observations": ["Cámara encendida declarada." if camera_on else "No se confirmó cámara encendida."],
        "strengths": [],
        "risks": [],
        "rationale": "Resultado preliminar por reglas locales. La decisión final debe ser humana.",
        "human_review_required": rec == "REVISIÓN HUMANA",
    }


def next_followup_question(last_question: str, last_answer: str, role_name: str, openai_key: str) -> str:
    if not openai_key:
        return "Gracias. Para profundizar, ¿podés darme un ejemplo concreto relacionado con seguridad, calidad o trabajo en equipo?"
    client = client_openai(openai_key)
    prompt = f"""
Sos Alba, entrevistadora virtual de RRHH para una empresa autopartista plástica.
Puesto: {role_name}
Última pregunta: {last_question}
Respuesta del candidato: {last_answer}

Generá UNA repregunta breve, cálida y profesional para profundizar solo si la respuesta fue incompleta o genérica.
No preguntes datos sensibles. No menciones edad, familia, salud, religión, política, sindicato, nacionalidad, domicilio exacto ni estado civil.
Máximo 35 palabras.
"""
    response = client.responses.create(model="gpt-4.1-mini", input=prompt, temperature=0.3)
    return response.output_text.strip()


def append_history(row: Dict):
    df_new = pd.DataFrame([row])
    if os.path.exists(HISTORY_FILE):
        df_old = pd.read_csv(HISTORY_FILE)
        df = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df = df_new
    df.to_csv(HISTORY_FILE, index=False)
    return df


def init_state():
    defaults = {
        "q_index": 0,
        "answers": [],
        "video_urls": {},
        "current_transcript": "",
        "last_audio_path": "",
        "camera_on": False,
        "evaluation": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


st.set_page_config(page_title=APP_TITLE, layout="wide", page_icon="🎙️")
init_state()

st.markdown("""
<style>
.main .block-container {padding-top: 1rem; max-width: 1500px;}
.alba-card {border: 1px solid #e6e8f5; border-radius: 18px; padding: 18px; background: #ffffff; box-shadow: 0 6px 24px rgba(20, 20, 70, .08);}
.chat-bubble {background: #eef1ff; border-left: 5px solid #635bff; padding: 18px; border-radius: 18px; margin-bottom: 14px; font-size: 1.05rem;}
.user-bubble {background: #eaf4ff; padding: 18px; border-radius: 18px; margin-bottom: 14px; font-size: 1.05rem;}
.safe-note {background: #f6fff8; border-left: 5px solid #19a05b; padding: 12px 16px; border-radius: 10px;}
.warning-note {background: #fff8e5; border-left: 5px solid #d89b00; padding: 12px 16px; border-radius: 10px;}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.title("⚙️ Configuración")
    did_key = st.text_input("D_ID_API_KEY", value=get_secret("D_ID_API_KEY"), type="password")
    source_url = st.text_input("D_ID_SOURCE_URL", value=get_secret("D_ID_SOURCE_URL"))
    openai_key = st.text_input("OPENAI_API_KEY", value=get_secret("OPENAI_API_KEY"), type="password")
    st.divider()
    role_name = st.selectbox("Puesto", ["Operario/a de inyección plástica", "Control de calidad", "Depósito / logística", "Mantenimiento", "Supervisor/a de turno"])
    candidate_code = st.text_input("Código / nombre candidato", value="CAND-001")
    st.divider()
    st.caption("La cámara y el audio requieren permisos del navegador. Usá Chrome o Edge.")

st.title("🎙️ Alba — entrevista con avatar, cámara y diálogo por voz")
st.caption("Flujo: Alba habla → candidato responde con cámara/micrófono → transcripción → repregunta o evaluación final.")

st.markdown("""
<div class='warning-note'>
<b>Importante:</b> la app puede registrar cámara/audio y analizar contenido verbal. Para evitar sesgos, el análisis no verbal se limita a observables técnicos seguros: cámara encendida, audio comprensible y continuidad. No se infieren emociones, salud, honestidad ni personalidad por gestos.
</div>
""", unsafe_allow_html=True)

if not did_key or not source_url:
    st.warning("Para que Alba hable con labios sincronizados, completá D_ID_API_KEY y D_ID_SOURCE_URL en el panel izquierdo.")
if not openai_key:
    st.warning("Para transcripción automática y repreguntas inteligentes, completá OPENAI_API_KEY. Sin eso, podés escribir la respuesta manualmente.")

progress = (st.session_state.q_index + 1) / len(QUESTIONS)
st.progress(progress)

q_index = st.session_state.q_index
current_question = QUESTIONS[q_index]

col_avatar, col_chat = st.columns([1.25, 1])

with col_avatar:
    st.subheader("🎥 Cámara del candidato")
    st.markdown("<div class='safe-note'>Pedí consentimiento antes de grabar. La cámara sirve para confirmar presencia y condiciones técnicas, no para inferir emociones.</div>", unsafe_allow_html=True)

    if WEBRTC_AVAILABLE:
        ctx = webrtc_streamer(
            key="candidate_camera",
            mode=WebRtcMode.SENDRECV,
            video_html_attrs=VideoHTMLAttributes(autoPlay=True, controls=True, muted=True),
            media_stream_constraints={"video": True, "audio": False},
        )
        st.session_state.camera_on = bool(ctx and ctx.state.playing)
    else:
        st.info("No está instalado streamlit-webrtc. Instalá requirements.txt para cámara en vivo.")
        camera_photo = st.camera_input("Foto de verificación técnica")
        st.session_state.camera_on = camera_photo is not None

    st.subheader("🤖 Avatar Alba hablando")
    if q_index not in st.session_state.video_urls:
        if st.button("🎬 Generar video de Alba para esta pregunta", type="primary", use_container_width=True):
            try:
                with st.spinner("Generando video real con D-ID. Puede tardar unos segundos..."):
                    st.session_state.video_urls[q_index] = generate_avatar_video(current_question, did_key, source_url)
                st.rerun()
            except Exception as e:
                st.error(str(e))
    else:
        st.video(st.session_state.video_urls[q_index])
        if st.button("🔁 Regenerar video", use_container_width=True):
            st.session_state.video_urls.pop(q_index, None)
            st.rerun()

with col_chat:
    st.subheader(f"💬 Conversación — Pregunta {q_index + 1} de {len(QUESTIONS)}")
    st.markdown(f"<div class='chat-bubble'><b>Alba:</b><br>{current_question}</div>", unsafe_allow_html=True)

    for item in st.session_state.answers:
        st.markdown(f"<div class='chat-bubble'><b>Alba:</b><br>{item['question']}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='user-bubble'><b>Candidato:</b><br>{item['answer']}</div>", unsafe_allow_html=True)

st.divider()
st.subheader("🎤 Respuesta del candidato")

left, right = st.columns([1, 1.25])
with left:
    st.markdown("**Opción A — responder hablando**")
    audio = mic_recorder(
        start_prompt="🎙️ Grabar respuesta",
        stop_prompt="⏹️ Detener grabación",
        just_once=False,
        use_container_width=True,
        key=f"mic_{q_index}",
    )
    if audio:
        st.audio(audio["bytes"])
        audio_path = save_audio_bytes(audio, candidate_code, q_index)
        st.session_state.last_audio_path = audio_path or ""
        if st.button("📝 Transcribir automáticamente", type="primary", use_container_width=True):
            try:
                with st.spinner("Transcribiendo audio..."):
                    st.session_state.current_transcript = transcribe_audio(audio_path, openai_key)
                st.rerun()
            except Exception as e:
                st.error(str(e))

with right:
    st.markdown("**Opción B — revisar o escribir respuesta**")
    response_text = st.text_area(
        "Respuesta del candidato",
        value=st.session_state.current_transcript,
        height=190,
        placeholder="La transcripción aparecerá acá. También podés escribir manualmente la respuesta.",
    )

col1, col2, col3 = st.columns([1, 1, 1])
with col1:
    if st.button("Guardar respuesta y continuar diálogo", type="primary", use_container_width=True):
        if not response_text.strip():
            st.error("Primero grabá/transcribí o escribí la respuesta.")
        else:
            st.session_state.answers.append({
                "question": current_question,
                "answer": response_text.strip(),
                "audio_path": st.session_state.last_audio_path,
                "camera_on": st.session_state.camera_on,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
            })
            st.session_state.current_transcript = ""
            st.session_state.last_audio_path = ""
            if st.session_state.q_index < len(QUESTIONS) - 1:
                # If answer is generic, insert one adaptive follow-up by replacing next fixed question only when useful
                if openai_key and len(response_text.split()) < 35:
                    follow = next_followup_question(current_question, response_text, role_name, openai_key)
                    QUESTIONS[min(st.session_state.q_index + 1, len(QUESTIONS) - 1)] = follow
                st.session_state.q_index += 1
            st.rerun()
with col2:
    if st.button("Volver pregunta anterior", use_container_width=True):
        if st.session_state.q_index > 0:
            st.session_state.q_index -= 1
            st.rerun()
with col3:
    if st.button("Reiniciar entrevista", use_container_width=True):
        for key in ["q_index", "answers", "video_urls", "current_transcript", "last_audio_path", "evaluation"]:
            st.session_state.pop(key, None)
        init_state()
        st.rerun()

st.divider()
st.subheader("✅ Evaluación de Alba para RRHH")

if st.button("Evaluar entrevista completa", type="primary", use_container_width=True):
    if not st.session_state.answers:
        st.error("Todavía no hay respuestas para evaluar.")
    else:
        with st.spinner("Evaluando respuestas..."):
            st.session_state.evaluation = evaluate_answers(candidate_code, role_name, st.session_state.answers, st.session_state.camera_on, openai_key)
            row = {
                "fecha": datetime.now().isoformat(timespec="seconds"),
                "candidato": candidate_code,
                "puesto": role_name,
                "recomendacion": st.session_state.evaluation.get("recommendation"),
                "puntaje": st.session_state.evaluation.get("score"),
                "confianza": st.session_state.evaluation.get("confidence"),
                "camara_encendida": st.session_state.camera_on,
                "respuestas_json": json.dumps(st.session_state.answers, ensure_ascii=False),
                "evaluacion_json": json.dumps(st.session_state.evaluation, ensure_ascii=False),
            }
            append_history(row)

if st.session_state.evaluation:
    ev = st.session_state.evaluation
    a, b, c = st.columns(3)
    a.metric("Recomendación", ev.get("recommendation", ""))
    b.metric("Puntaje", f"{ev.get('score', 0)}/100")
    c.metric("Confianza", ev.get("confidence", ""))
    st.markdown("### Fundamento")
    st.write(ev.get("rationale", ""))
    st.markdown("### Observaciones verbales")
    for item in ev.get("verbal_observations", []):
        st.write(f"- {item}")
    st.markdown("### Observaciones no verbales seguras")
    for item in ev.get("nonverbal_observations", []):
        st.write(f"- {item}")
    st.markdown("### Fortalezas")
    for item in ev.get("strengths", []):
        st.write(f"- {item}")
    st.markdown("### Riesgos / brechas")
    for item in ev.get("risks", []):
        st.write(f"- {item}")
    st.json(ev, expanded=False)

st.caption("La decisión final siempre debe quedar en RRHH/jefatura. La IA asiste, no reemplaza la decisión humana.")
