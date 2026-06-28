import os
import re
import io
import json
import time
import base64
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
import requests
import streamlit as st
from streamlit.components.v1 import html

try:
    from streamlit_mic_recorder import mic_recorder
    MIC_AVAILABLE = True
except Exception:
    MIC_AVAILABLE = False

try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except Exception:
    WHISPER_AVAILABLE = False

APP_TITLE = "AI-RRHH | Alba entrevista virtual"
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

SENSITIVE_TOPICS = ["edad", "fecha de nacimiento", "estado civil", "embarazo", "hijos", "religión", "política", "sindicato", "orientación sexual", "salud", "discapacidad", "nacionalidad", "raza", "domicilio exacto", "obra social"]


def get_secret(name: str, default: str = "") -> str:
    try:
        if name in st.secrets:
            return str(st.secrets[name]).strip()
    except Exception:
        pass
    return os.getenv(name, default).strip()


def clean_url(url: str) -> str:
    url = (url or "").strip().replace("[img]", "").replace("[/img]", "")
    m = re.search(r"https://[^\s\]]+\.(?:jpg|jpeg|png|webp)", url, flags=re.I)
    return m.group(0) if m else url


def valid_image_url(url: str) -> bool:
    return bool(re.match(r"^https://.+\.(jpg|jpeg|png|webp)(\?.*)?$", (url or "").strip(), re.I))


def auth_header_basic(api_key: str) -> Dict[str, str]:
    # D-ID acepta Basic <base64(user:pass)>. Si pegás user:pass, lo codificamos.
    key = (api_key or "").strip()
    if not key:
        return {}
    if key.lower().startswith("basic "):
        return {"Authorization": key}
    encoded = base64.b64encode(key.encode("utf-8")).decode("utf-8")
    return {"Authorization": f"Basic {encoded}"}


def create_did_talk(text: str, did_api_key: str, source_url: str, voice_id: str) -> str:
    source_url = clean_url(source_url)
    if not did_api_key:
        raise ValueError("Falta D_ID_API_KEY.")
    if not valid_image_url(source_url):
        raise ValueError("D_ID_SOURCE_URL debe ser una URL pública HTTPS y terminar en .jpg/.jpeg/.png/.webp")

    headers = {**auth_header_basic(did_api_key), "Content-Type": "application/json"}
    payload = {
        "source_url": source_url,
        "script": {
            "type": "text",
            "input": text,
            "provider": {"type": "microsoft", "voice_id": voice_id or DEFAULT_DID_VOICE},
        },
        "config": {"fluent": True, "pad_audio": 0.2},
    }
    r = requests.post(DID_API_URL, headers=headers, json=payload, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"D-ID error {r.status_code}: {r.text}")
    talk_id = r.json().get("id")
    if not talk_id:
        raise RuntimeError(f"D-ID no devolvió id: {r.text}")

    for _ in range(40):
        time.sleep(1.5)
        g = requests.get(f"{DID_API_URL}/{talk_id}", headers=auth_header_basic(did_api_key), timeout=30)
        if g.status_code >= 400:
            raise RuntimeError(f"D-ID status error {g.status_code}: {g.text}")
        data = g.json()
        if data.get("status") == "done" and data.get("result_url"):
            return data["result_url"]
        if data.get("status") == "error":
            raise RuntimeError(f"D-ID status error: {data}")
    raise TimeoutError("D-ID tardó demasiado en generar el video. Probá de nuevo.")


@st.cache_resource(show_spinner=False)
def load_whisper_model(model_size: str):
    if not WHISPER_AVAILABLE:
        return None
    return WhisperModel(model_size, device="cpu", compute_type="int8")


def transcribe_audio(audio_bytes: bytes, model_size: str = "base") -> str:
    if not audio_bytes:
        return ""
    model = load_whisper_model(model_size)
    if model is None:
        raise RuntimeError("Falta faster-whisper. Instalá requirements.txt.")
    audio_path = AUDIO_DIR / f"respuesta_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
    audio_path.write_bytes(audio_bytes)
    segments, _ = model.transcribe(str(audio_path), language="es")
    return " ".join([seg.text.strip() for seg in segments]).strip()


def score_answers(answers: List[str]) -> Dict:
    text = "\n".join(answers).lower()
    scores = {}
    for comp, words in KEYWORDS.items():
        hits = sum(1 for w in words if w.lower() in text)
        scores[comp] = min(100, int((hits / max(4, len(words) * 0.35)) * 100))
    red_flags = []
    for pat in RED_FLAGS:
        if re.search(pat, text):
            red_flags.append(pat)
    sensitive = [s for s in SENSITIVE_TOPICS if s in text]
    global_score = int(sum(scores.values()) / len(scores)) if scores else 0
    if any("no puedo" in rf or "sin epp" in rf or "no uso" in rf for rf in red_flags):
        rec = "RECHAZAR PRIMERA INSTANCIA"
    elif global_score >= 70:
        rec = "AVANZAR A ENTREVISTA HUMANA"
    elif global_score >= 45:
        rec = "REVISIÓN HUMANA"
    else:
        rec = "RECHAZAR PRIMERA INSTANCIA"
    return {"score": global_score, "scores": scores, "red_flags": red_flags, "sensitive": sensitive, "recommendation": rec}


def generate_followup_rule_based(role: str, answers: List[str], current_idx: int) -> str:
    # Sin APIs: repregunta simple basada en brechas detectadas.
    last = (answers[-1] if answers else "").lower()
    if len(last.split()) < 10:
        return "Necesito un poco más de detalle para evaluarte mejor. ¿Podrías contarme un ejemplo concreto, qué hiciste vos y cuál fue el resultado?"
    if "epp" not in last and "seguridad" in ROLE_QUESTIONS[role][current_idx].lower():
        return "Gracias. Para profundizar, ¿qué EPP usarías específicamente y a quién avisarías si detectás una condición insegura?"
    if current_idx + 1 < len(ROLE_QUESTIONS[role]):
        return ROLE_QUESTIONS[role][current_idx + 1]
    return "Gracias. Para cerrar, ¿hay algo más de tu experiencia laboral que consideres importante para este puesto?"


def live_camera_html():
    # No usa streamlit-webrtc: evita el error removeChild. Es solo vista previa en vivo del candidato.
    html_code = """
    <div style="border-radius:16px; overflow:hidden; border:1px solid #e5e7eb; background:#111827; padding:12px;">
      <video id="cam" autoplay playsinline muted style="width:100%; border-radius:12px; background:#111827;"></video>
      <div style="display:flex; gap:10px; margin-top:10px; align-items:center; font-family:Arial;">
        <button onclick="startCam()" style="padding:10px 16px; border-radius:10px; border:0; background:#5b46ff; color:white; font-weight:700;">START cámara</button>
        <button onclick="stopCam()" style="padding:10px 16px; border-radius:10px; border:1px solid #ef4444; background:white; color:#ef4444; font-weight:700;">STOP</button>
        <span id="status" style="color:#d1d5db; font-size:14px;">Permití cámara y micrófono cuando el navegador lo solicite.</span>
      </div>
    </div>
    <script>
      let stream = null;
      async function startCam(){
        const status = document.getElementById('status');
        try {
          stream = await navigator.mediaDevices.getUserMedia({video:true, audio:true});
          document.getElementById('cam').srcObject = stream;
          status.innerText = 'Cámara y micrófono activos.';
        } catch(e){
          status.innerText = 'No se pudo activar cámara/micrófono: ' + e.message;
        }
      }
      function stopCam(){
        if(stream){ stream.getTracks().forEach(t => t.stop()); }
        document.getElementById('cam').srcObject = null;
        document.getElementById('status').innerText = 'Cámara detenida.';
      }
    </script>
    """
    html(html_code, height=520)


def init_state(role: str):
    st.session_state.setdefault("q_idx", 0)
    st.session_state.setdefault("conversation", [])
    st.session_state.setdefault("answers", [])
    st.session_state.setdefault("last_video_url", "")
    if not st.session_state["conversation"]:
        first = ROLE_QUESTIONS[role][0]
        st.session_state["conversation"].append(("Alba", first))


st.set_page_config(page_title=APP_TITLE, page_icon="🎥", layout="wide")
st.title("Alba — Entrevista virtual con avatar")
st.caption("Versión estable para Streamlit Cloud: cámara en vivo por navegador + grabación de voz + transcripción local + avatar D-ID. No usa OpenAI API.")

st.markdown("""
<style>
.block-container{padding-top:1rem; max-width:1400px;}
.card{background:#f4f6ff; border-left:5px solid #635bff; padding:18px; border-radius:18px; margin-bottom:12px;}
.candidate{background:#e8f2ff; border-left:5px solid #60a5fa; padding:18px; border-radius:18px; margin-bottom:12px;}
.warn{background:#fff7d6; color:#8a5a00; padding:14px; border-radius:12px;}
.err{background:#ffe2e2; color:#b91c1c; padding:14px; border-radius:12px;}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("Configuración")
    role = st.selectbox("Puesto", list(ROLE_QUESTIONS.keys()))
    did_api_key = st.text_input("D_ID_API_KEY", value=get_secret("D_ID_API_KEY"), type="password")
    did_source_url = st.text_input("D_ID_SOURCE_URL", value=get_secret("D_ID_SOURCE_URL", "https://i.postimg.cc/jSwybb4C/4m0Obqg3KQUKRm1IAm-Ja-Hh-PB3qsae-Ih-TWs-Sc-JW3OMD5R-tsn-TJUy-W-xu-J4W1POFJAj-PGBQyh-Ik48GC4PNg-RGD7z.jpg"))
    voice_id = st.text_input("Voz D-ID / Microsoft", value=DEFAULT_DID_VOICE)
    whisper_size = st.selectbox("Modelo transcripción local", ["tiny", "base", "small"], index=1)
    st.divider()
    st.info("Esta versión no usa streamlit-webrtc para evitar el error removeChild en Streamlit Cloud.")

init_state(role)
progress = (st.session_state.q_idx + 1) / len(ROLE_QUESTIONS[role])
st.progress(min(progress, 1.0))

left, right = st.columns([1.25, 1])

with left:
    st.subheader("🎥 Cámara del candidato")
    st.warning("Tocá START cámara. Esto funciona como vista en vivo del candidato. La respuesta se graba abajo con el micrófono.")
    live_camera_html()

    st.subheader("🎬 Avatar Alba hablando")
    current_question = st.session_state.conversation[-1][1] if st.session_state.conversation else ROLE_QUESTIONS[role][0]
    if st.button("Generar / reproducir pregunta con Alba", type="primary", use_container_width=True):
        try:
            with st.spinner("Generando video hablado con D-ID..."):
                st.session_state.last_video_url = create_did_talk(current_question, did_api_key, did_source_url, voice_id)
        except Exception as e:
            st.error(str(e))
    if st.session_state.last_video_url:
        st.video(st.session_state.last_video_url)
    else:
        st.image(clean_url(did_source_url), caption="Imagen base de Alba. Al generar video, se verá hablando con labios sincronizados.", use_column_width=True)

with right:
    st.subheader("💬 Conversación")
    for speaker, msg in st.session_state.conversation:
        cls = "card" if speaker == "Alba" else "candidate"
        st.markdown(f"<div class='{cls}'><b>{speaker}:</b><br>{msg}</div>", unsafe_allow_html=True)

st.divider()
st.subheader("🎙️ Respuesta del candidato")

col_a, col_b = st.columns([1, 1.2])
with col_a:
    if not MIC_AVAILABLE:
        st.error("Falta streamlit-mic-recorder. Instalá requirements.txt y reiniciá la app.")
        audio = None
    else:
        audio = mic_recorder(
            start_prompt="🎙️ Grabar respuesta",
            stop_prompt="⏹️ Detener grabación",
            just_once=False,
            use_container_width=True,
            key=f"mic_{st.session_state.q_idx}_{len(st.session_state.answers)}",
        )
        if audio and audio.get("bytes"):
            st.audio(audio["bytes"], format=audio.get("mime_type", "audio/wav"))
            if st.button("Transcribir automáticamente", type="primary", use_container_width=True):
                try:
                    with st.spinner("Transcribiendo en local..."):
                        st.session_state.draft_answer = transcribe_audio(audio["bytes"], whisper_size)
                except Exception as e:
                    st.error(f"No se pudo transcribir: {e}")
with col_b:
    answer = st.text_area(
        "Respuesta transcripta / manual",
        value=st.session_state.get("draft_answer", ""),
        height=150,
        placeholder="La transcripción aparecerá acá. También podés escribir o corregir manualmente.",
    )

c1, c2, c3 = st.columns([1.2, 1, 1])
with c1:
    if st.button("Guardar respuesta y continuar diálogo", type="primary", use_container_width=True):
        if not answer.strip():
            st.warning("Primero grabá/transcribí o escribí la respuesta.")
        else:
            st.session_state.answers.append(answer.strip())
            st.session_state.conversation.append(("Candidato", answer.strip()))
            next_question = generate_followup_rule_based(role, st.session_state.answers, st.session_state.q_idx)
            if st.session_state.q_idx < len(ROLE_QUESTIONS[role]) - 1:
                st.session_state.q_idx += 1
            st.session_state.conversation.append(("Alba", next_question))
            st.session_state.draft_answer = ""
            st.session_state.last_video_url = ""
            st.rerun()
with c2:
    if st.button("Volver pregunta anterior", use_container_width=True):
        if st.session_state.q_idx > 0:
            st.session_state.q_idx -= 1
            st.rerun()
with c3:
    if st.button("Reiniciar entrevista", use_container_width=True):
        for k in ["q_idx", "conversation", "answers", "last_video_url", "draft_answer"]:
            st.session_state.pop(k, None)
        st.rerun()

st.divider()
st.subheader("📋 Informe de Alba")
if st.button("Generar informe de preselección", use_container_width=True):
    result = score_answers(st.session_state.answers)
    st.session_state.report = result

if "report" in st.session_state:
    r = st.session_state.report
    st.metric("Recomendación", r["recommendation"])
    st.metric("Puntaje global", f"{r['score']}/100")
    st.markdown("### Puntaje por competencia")
    df = pd.DataFrame([{"Competencia": k, "Puntaje": v} for k, v in r["scores"].items()])
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.bar_chart(df.set_index("Competencia"))

    st.markdown("### Fundamento claro para RRHH")
    if r["recommendation"].startswith("AVANZAR"):
        st.success("Alba recomienda avanzar porque las respuestas muestran evidencia suficiente vinculada al puesto, especialmente en competencias laborales evaluadas. La decisión final debe ser validada por RRHH y/o jefatura.")
    elif r["recommendation"] == "REVISIÓN HUMANA":
        st.warning("Alba recomienda revisión humana porque la evidencia es parcial, ambigua o no alcanza para tomar una decisión automática segura. RRHH debe revisar el caso y, si corresponde, profundizar con entrevista técnica.")
    else:
        st.error("Alba recomienda no avanzar en primera instancia porque la evidencia laboral es insuficiente para el puesto o se detectaron brechas/alertas vinculadas a requisitos operativos. RRHH debe validar antes de comunicar cualquier decisión.")

    if r["red_flags"]:
        st.markdown("### Alertas detectadas")
        for rf in r["red_flags"]:
            st.write(f"- Patrón de alerta: `{rf}`")
    if r["sensitive"]:
        st.markdown("### Datos sensibles detectados")
        st.warning("Estos datos no deben usarse para decidir: " + ", ".join(r["sensitive"]))

    st.markdown("### Respuestas registradas")
    for i, a in enumerate(st.session_state.answers, 1):
        st.write(f"**Respuesta {i}:** {a}")
