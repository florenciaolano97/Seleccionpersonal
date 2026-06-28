import os
import re
import io
import json
import time
import uuid
import base64
import hashlib
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

import pandas as pd
import requests
import streamlit as st

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

APP_TITLE = "AI-RRHH | Alba Avatar Entrevistador"
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
HISTORY_FILE = DATA_DIR / "evaluaciones_rrhh.csv"

ROLE_PROFILES = {
    "Operario/a de inyección plástica": {
        "descripcion": "Producción en inyectoras, control visual inicial, rebabado, empaque, orden y seguridad.",
        "competencies": {
            "Experiencia industrial / producción": 0.20,
            "Seguridad industrial y EPP": 0.25,
            "Calidad visual": 0.15,
            "Disciplina operativa": 0.15,
            "Disponibilidad": 0.10,
            "Trabajo en equipo": 0.10,
            "Aprendizaje": 0.05,
        },
        "questions": [
            "Hola, soy Alba, tu entrevistadora virtual de Recursos Humanos. Para comenzar, contame tu experiencia previa en producción, inyección plástica, autopartes o líneas industriales.",
            "¿Qué elementos de protección personal usarías en una planta y qué harías si una máquina parece insegura?",
            "¿Qué defectos visuales buscarías en una pieza plástica antes de liberarla o empacarla?",
            "Describí una situación en la que tuviste que seguir una instrucción precisa o un estándar de trabajo.",
            "¿Tenés disponibilidad para turnos rotativos, noche o fines de semana según necesidad productiva?",
            "¿Cómo actuarías si ves que un compañero saltea un paso de seguridad para producir más rápido?",
        ],
    },
    "Control de calidad": {
        "descripcion": "Inspección visual/dimensional, registros, no conformidades y comunicación con producción.",
        "competencies": {
            "Calidad visual/dimensional": 0.25,
            "Registro y trazabilidad": 0.20,
            "Criterio ante no conformidades": 0.20,
            "Comunicación": 0.15,
            "Seguridad industrial y EPP": 0.10,
            "Aprendizaje": 0.10,
        },
        "questions": [
            "Hola, soy Alba, tu entrevistadora virtual de Recursos Humanos. Contame tu experiencia en control de calidad, mediciones, inspección visual o registros.",
            "¿Qué harías si encontrás una pieza fuera de especificación pero producción necesita cumplir el objetivo del turno?",
            "¿Usaste calibre, pie de rey, galgas, plantillas de control, planillas o sistemas de trazabilidad?",
            "¿Cómo documentarías una no conformidad para que sea útil y objetiva?",
            "¿Cómo comunicarías un problema de calidad a un operario o supervisor sin generar conflicto?",
        ],
    },
    "Mantenimiento / cambio de moldes": {
        "descripcion": "Soporte técnico a inyectoras, moldes, ajustes, mantenimiento preventivo y correctivo.",
        "competencies": {
            "Conocimiento técnico": 0.25,
            "Seguridad en intervención de máquinas": 0.25,
            "Diagnóstico de fallas": 0.20,
            "Mantenimiento preventivo": 0.15,
            "Trabajo con producción": 0.10,
            "Registro de intervenciones": 0.05,
        },
        "questions": [
            "Hola, soy Alba, tu entrevistadora virtual de Recursos Humanos. Contame tu experiencia en mantenimiento industrial, inyectoras, moldes, neumática, hidráulica o electricidad.",
            "¿Qué pasos de seguridad harías antes de intervenir una máquina?",
            "¿Cómo diagnosticarías una falla repetitiva en una inyectora o periférico?",
            "¿Participaste en cambios de molde, ajustes de proceso o mantenimiento preventivo?",
            "¿Qué harías si producción te presiona para reparar rápido salteando un paso de seguridad?",
        ],
    },
    "Depósito / logística interna": {
        "descripcion": "Recepción, stock, abastecimiento a línea, movimientos internos, despacho y registros.",
        "competencies": {
            "Orden, stock e inventario": 0.25,
            "Trazabilidad y registros": 0.20,
            "Seguridad en movimiento de materiales": 0.15,
            "Coordinación con producción": 0.15,
            "Responsabilidad": 0.15,
            "Aprendizaje": 0.10,
        },
        "questions": [
            "Hola, soy Alba, tu entrevistadora virtual de Recursos Humanos. Contame tu experiencia en depósito, logística, inventario, picking, recepción o despacho.",
            "¿Cómo evitarías errores de material o mezcla de lotes en una fábrica autopartista?",
            "¿Qué harías si una línea pide material urgente pero no coincide con el registro de stock?",
            "¿Tenés experiencia con remitos, planillas, códigos, FIFO, lectores o sistemas de stock?",
            "¿Cómo cuidás la seguridad al mover cargas o abastecer una línea?",
        ],
    },
    "Supervisor/a o líder de turno": {
        "descripcion": "Coordinación de personas, objetivos de producción, seguridad, calidad, comunicación y escalamiento.",
        "competencies": {
            "Liderazgo operativo": 0.20,
            "Gestión de seguridad y calidad": 0.20,
            "Planificación del turno": 0.15,
            "Comunicación y conflictos": 0.15,
            "Uso de indicadores": 0.15,
            "Desarrollo del equipo": 0.10,
            "Registro y escalamiento": 0.05,
        },
        "questions": [
            "Hola, soy Alba, tu entrevistadora virtual de Recursos Humanos. Contame tu experiencia coordinando personas, turnos, objetivos de producción o equipos industriales.",
            "¿Qué hacés si el equipo está atrasado y alguien propone saltear un control de calidad o seguridad?",
            "¿Cómo organizás prioridades al inicio de un turno?",
            "¿Qué indicadores usarías para saber si el turno fue bueno?",
            "Describí una situación en la que resolviste un conflicto entre compañeros.",
        ],
    },
}

KEYWORDS = {
    "Experiencia industrial / producción": ["producción", "línea", "linea", "inyectora", "inyección", "plástico", "autopart", "molde", "operario", "rebaba"],
    "Seguridad industrial y EPP": ["epp", "seguridad", "guantes", "lentes", "protección", "procedimiento", "riesgo", "bloqueo", "5s"],
    "Calidad visual": ["calidad", "defecto", "rebaba", "fisura", "mancha", "deformación", "visual", "rechazo", "inspección"],
    "Disciplina operativa": ["instrucción", "procedimiento", "estándar", "cumplir", "orden", "supervisor", "responsable"],
    "Disponibilidad": ["turno", "rotativo", "noche", "fines de semana", "disponibilidad", "horas extra"],
    "Trabajo en equipo": ["equipo", "compañero", "comunicación", "respeto", "ayuda", "colaborar"],
    "Aprendizaje": ["aprender", "capacitación", "adaptar", "mejora", "formación", "entrenamiento"],
    "Calidad visual/dimensional": ["calidad", "dimensional", "calibre", "pie de rey", "galga", "medición", "tolerancia"],
    "Registro y trazabilidad": ["registro", "planilla", "trazabilidad", "lote", "sistema", "documentar", "código"],
    "Criterio ante no conformidades": ["no conformidad", "rechazar", "bloquear", "separar", "cuarentena", "escalar", "detener"],
    "Comunicación": ["comunicar", "avisar", "explicar", "respeto", "claro", "supervisor", "operario"],
    "Conocimiento técnico": ["mecánica", "eléctrica", "neumática", "hidráulica", "sensor", "plc", "mantenimiento", "molde"],
    "Seguridad en intervención de máquinas": ["bloqueo", "energía cero", "lockout", "seguridad", "epp", "parada", "procedimiento"],
    "Diagnóstico de fallas": ["diagnóstico", "falla", "causa", "síntoma", "prueba", "raíz", "corregir"],
    "Mantenimiento preventivo": ["preventivo", "lubricación", "rutina", "checklist", "correctivo", "orden de trabajo"],
    "Trabajo con producción": ["producción", "operario", "supervisor", "prioridad", "línea", "coordinar"],
    "Registro de intervenciones": ["registro", "orden de trabajo", "reporte", "historial", "intervención"],
    "Orden, stock e inventario": ["stock", "inventario", "depósito", "orden", "ubicación", "conteo", "picking", "fifo"],
    "Trazabilidad y registros": ["trazabilidad", "lote", "remito", "código", "registro", "etiqueta"],
    "Seguridad en movimiento de materiales": ["seguridad", "carga", "autoelevador", "zorra", "apiladora", "epp", "pasillo"],
    "Coordinación con producción": ["producción", "línea", "abastecer", "supervisor", "material", "coordinar"],
    "Responsabilidad": ["responsable", "puntual", "asistencia", "cumplir", "compromiso", "presentismo"],
    "Liderazgo operativo": ["lider", "lideré", "supervisor", "equipo", "coordiné", "personas", "turno"],
    "Gestión de seguridad y calidad": ["seguridad", "calidad", "procedimiento", "epp", "no conformidad", "estándar"],
    "Planificación del turno": ["planificar", "prioridad", "turno", "objetivo", "recursos", "organizar"],
    "Comunicación y conflictos": ["conflicto", "comunicación", "escuchar", "feedback", "corregir", "acuerdo"],
    "Uso de indicadores": ["indicador", "kpi", "scrap", "rechazo", "productividad", "eficiencia", "oee"],
    "Desarrollo del equipo": ["capacitar", "entrenar", "desarrollar", "acompañar", "enseñar", "feedback"],
    "Registro y escalamiento": ["registro", "escalar", "reporte", "parte", "novedad", "turno"],
}

PROTECTED_TOPICS = ["edad", "fecha de nacimiento", "embarazo", "hijos", "religión", "sindicato", "orientación sexual", "salud", "discapacidad", "nacionalidad", "raza", "etnia", "estado civil", "domicilio exacto"]
RED_FLAG_PATTERNS = {
    "seguridad": [r"no uso epp", r"no usar epp", r"sin epp", r"saltear seguridad", r"anul(o|ar) alarma", r"trabajo sin protecci"],
    "conducta": [r"me pele(e|o)", r"discuto con todos", r"falto mucho", r"llego tarde siempre", r"no acepto indicaciones"],
    "disponibilidad": [r"no puedo turnos", r"no puedo rotar", r"no trabajo de noche", r"no har[ií]a horas extra"],
}

# ========================
# Configuración
# ========================

def get_secret(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, "")
        if value:
            return str(value)
    except Exception:
        pass
    return os.getenv(name, default)


def init_state():
    defaults = {
        "transcript": [],
        "question_index": 0,
        "avatar_videos": {},
        "last_result": None,
        "did_api_key_ui": get_secret("D_ID_API_KEY"),
        "did_source_url_ui": get_secret("D_ID_SOURCE_URL"),
        "openai_api_key_ui": get_secret("OPENAI_API_KEY"),
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def stable_candidate_code(raw: str) -> str:
    raw = (raw or "").strip() or str(uuid.uuid4())
    return "CAND-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:10].upper()


def is_public_image_url(url: str) -> bool:
    """D-ID necesita una URL pública HTTPS directa a imagen. Acepta URLs con querystring."""
    u = (url or "").strip()
    if not u.startswith("https://"):
        return False
    path = urlparse(u).path.lower()
    return path.endswith((".jpg", ".jpeg", ".png", ".webp"))


def normalize_did_api_key(api_key: str) -> str:
    key = (api_key or "").strip()
    if key.lower().startswith("basic "):
        key = key.split(" ", 1)[1].strip()
    return key


def did_headers(api_key: str) -> dict:
    return {
        "Authorization": f"Basic {normalize_did_api_key(api_key)}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

# ========================
# D-ID Avatar real hablando
# ========================

def create_did_talk(text: str, source_url: str, api_key: str, voice_id: str) -> str:
    if not normalize_did_api_key(api_key):
        raise ValueError("Falta D_ID_API_KEY. Pegala en el panel de configuración o en .streamlit/secrets.toml")
    if not is_public_image_url(source_url):
        raise ValueError("D_ID_SOURCE_URL debe ser una URL pública HTTPS directa a una imagen .jpg, .jpeg, .png o .webp")

    payload = {
        "source_url": source_url.strip(),
        "script": {
            "type": "text",
            "input": text,
            "provider": {
                "type": "microsoft",
                "voice_id": voice_id,
            },
        },
        "config": {
            "fluent": True,
            "pad_audio": 0.0,
            "stitch": True,
        },
        "name": "Alba",
    }
    r = requests.post("https://api.d-id.com/talks", headers=did_headers(api_key), json=payload, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"D-ID rechazó la solicitud ({r.status_code}): {r.text}")
    data = r.json()
    talk_id = data.get("id")
    if not talk_id:
        raise RuntimeError(f"D-ID no devolvió id de video: {data}")
    return talk_id


def poll_did_talk(talk_id: str, api_key: str, max_wait_seconds: int = 150) -> tuple[str, dict]:
    url = f"https://api.d-id.com/talks/{talk_id}"
    start = time.time()
    last_data = {}
    while time.time() - start < max_wait_seconds:
        r = requests.get(url, headers=did_headers(api_key), timeout=45)
        if r.status_code >= 400:
            raise RuntimeError(f"Error consultando D-ID ({r.status_code}): {r.text}")
        data = r.json()
        last_data = data
        status = data.get("status")
        if status == "done":
            result_url = data.get("result_url")
            if not result_url:
                raise RuntimeError(f"D-ID terminó pero no devolvió result_url: {data}")
            return result_url, data
        if status == "error":
            raise RuntimeError(f"D-ID devolvió error: {json.dumps(data, ensure_ascii=False)}")
        time.sleep(2)
    raise TimeoutError(f"D-ID tardó demasiado. Última respuesta: {json.dumps(last_data, ensure_ascii=False)}")


def generate_avatar_video(text: str, source_url: str, api_key: str, voice_id: str) -> tuple[str, str, dict]:
    talk_id = create_did_talk(text, source_url, api_key, voice_id)
    result_url, raw = poll_did_talk(talk_id, api_key)
    return result_url, talk_id, raw


def test_did_connection(api_key: str) -> tuple[bool, str]:
    if not normalize_did_api_key(api_key):
        return False, "Falta D_ID_API_KEY."
    try:
        r = requests.get("https://api.d-id.com/credits", headers=did_headers(api_key), timeout=30)
        if r.status_code >= 400:
            return False, f"D-ID respondió {r.status_code}: {r.text}"
        return True, "Conexión correcta con D-ID."
    except Exception as e:
        return False, str(e)

# ========================
# Evaluación RRHH
# ========================

def safe_lower(text: str) -> str:
    return (text or "").lower().strip()


def detect_red_flags(text: str):
    t = safe_lower(text)
    out = []
    for group, patterns in RED_FLAG_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, t):
                out.append(f"{group}: {pat}")
    return out


def detect_sensitive(text: str):
    t = safe_lower(text)
    return [x for x in PROTECTED_TOPICS if x in t]


def score_competency(competency: str, text: str) -> int:
    words = KEYWORDS.get(competency, [])
    t = safe_lower(text)
    hits = sum(1 for w in words if w in t)
    keyword_score = min(hits / 5, 1) * 70
    length_bonus = min(len(text.split()) / 140, 1) * 15
    example_bonus = 15 if any(x in t for x in ["por ejemplo", "una vez", "situación", "caso", "experiencia"]) else 0
    return int(round(min(keyword_score + length_bonus + example_bonus, 100)))


def transcript_text(transcript: list[dict]) -> str:
    lines = []
    for i, item in enumerate(transcript, 1):
        lines.append(f"Pregunta {i}: {item.get('question','')}\nRespuesta {i}: {item.get('answer','')}")
    return "\n\n".join(lines)


def local_evaluate(role_name: str, cv_text: str, answers_text: str) -> dict:
    profile = ROLE_PROFILES[role_name]
    full_text = f"CV:\n{cv_text}\n\nENTREVISTA:\n{answers_text}"
    red_flags = detect_red_flags(full_text)
    sensitive = detect_sensitive(full_text)
    comp_scores = {}
    weighted = 0
    for comp, weight in profile["competencies"].items():
        score = score_competency(comp, full_text)
        comp_scores[comp] = score
        weighted += score * weight
    final_score = int(round(weighted))
    critical = any("seguridad" in x or "conducta" in x for x in red_flags)
    turno = any("disponibilidad" in x for x in red_flags)
    if critical:
        recommendation = "RECHAZAR PRIMERA INSTANCIA"
        confidence = "Alta"
    elif final_score >= 70 and not turno:
        recommendation = "APROBAR PRIMERA INSTANCIA"
        confidence = "Alta" if final_score >= 82 else "Media"
    elif final_score < 55:
        recommendation = "RECHAZAR PRIMERA INSTANCIA"
        confidence = "Media"
    else:
        recommendation = "REVISIÓN HUMANA"
        confidence = "Media"
    strengths = [f"{c}: evidencia favorable ({s}/100)" for c, s in comp_scores.items() if s >= 70][:6]
    risks = [f"{c}: evidencia insuficiente ({s}/100)" for c, s in comp_scores.items() if s < 45][:6]
    if red_flags:
        risks.append("Alertas detectadas: " + "; ".join(red_flags))
    if sensitive:
        risks.append("Datos sensibles detectados, no usarlos para decidir: " + ", ".join(sensitive))
    if recommendation.startswith("APROBAR"):
        rationale = "El perfil muestra evidencias suficientes para avanzar a una instancia humana/técnica. La decisión final debe quedar en RR.HH."
    elif recommendation.startswith("RECHAZAR"):
        rationale = "El perfil no reúne evidencia suficiente o presenta alertas laborales relevantes para esta primera instancia. Debe validarse por RR.HH."
    else:
        rationale = "El caso queda en zona intermedia y requiere revisión humana antes de tomar una decisión final."
    return {
        "recommendation": recommendation,
        "score": final_score,
        "confidence": confidence,
        "competency_scores": comp_scores,
        "strengths": strengths,
        "risks": risks,
        "rationale": rationale,
        "red_flags": red_flags,
        "sensitive_data_detected": sensitive,
        "model_used": "motor_local_reglas",
    }


def ai_evaluate(role_name: str, cv_text: str, answers_text: str, model: str, openai_api_key: str) -> tuple[dict | None, str | None]:
    if not openai_api_key or OpenAI is None:
        return None, "No hay OPENAI_API_KEY configurada."
    profile = ROLE_PROFILES[role_name]
    client = OpenAI(api_key=openai_api_key)
    schema = {
        "recommendation": "APROBAR PRIMERA INSTANCIA | REVISIÓN HUMANA | RECHAZAR PRIMERA INSTANCIA",
        "score": "integer 0-100",
        "confidence": "Baja | Media | Alta",
        "competency_scores": {"competencia": "integer 0-100"},
        "strengths": ["fortalezas laborales"],
        "risks": ["brechas o riesgos laborales"],
        "rationale": "fundamento claro y auditable",
        "red_flags": ["alertas críticas"],
        "sensitive_data_detected": ["datos sensibles si aparecen"],
        "model_used": model,
    }
    prompt = f"""
Sos un asistente de RR.HH. para preselección inicial en fábrica autopartista plástica.

Puesto: {role_name}
Descripción: {profile['descripcion']}
Competencias y ponderaciones: {profile['competencies']}

Reglas obligatorias:
- Evaluá SOLO evidencias laborales relacionadas con el puesto.
- No uses edad, sexo, embarazo, salud, discapacidad, nacionalidad, religión, política, sindicalización, orientación sexual, estado civil, datos familiares ni domicilio exacto.
- Si aparecen datos sensibles, listalos pero no los uses para puntuar.
- La IA no decide final; la decisión final es humana.
- Si hay duda o evidencia mixta, usá REVISIÓN HUMANA.
- Devolvé exclusivamente JSON válido con esta estructura: {json.dumps(schema, ensure_ascii=False)}

CV:
{cv_text}

Entrevista:
{answers_text}
"""
    try:
        response = client.responses.create(model=model, input=prompt, temperature=0.2)
        raw = getattr(response, "output_text", "") or response.model_dump_json()
        match = re.search(r"\{.*\}", raw, re.S)
        if match:
            raw = match.group(0)
        data = json.loads(raw)
        data["model_used"] = model
        return data, None
    except Exception as e:
        return None, str(e)

# ========================
# Archivos / exportación
# ========================

def append_history(row: dict) -> pd.DataFrame:
    df_new = pd.DataFrame([row])
    if HISTORY_FILE.exists():
        df_old = pd.read_csv(HISTORY_FILE)
        df_all = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df_all = df_new
    df_all.to_csv(HISTORY_FILE, index=False)
    return df_all


def read_history() -> pd.DataFrame:
    return pd.read_csv(HISTORY_FILE) if HISTORY_FILE.exists() else pd.DataFrame()


def excel_bytes(df: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Evaluaciones", index=False)
    return output.getvalue()

# ========================
# UI
# ========================

st.set_page_config(page_title="Alba Avatar RRHH", page_icon="🤖", layout="wide")
init_state()

st.markdown("""
<style>
.block-container {padding-top: 1rem;}
.hero {background: linear-gradient(135deg,#0f172a,#312e81); color:white; padding:1rem 1.2rem; border-radius:18px; margin-bottom:1rem;}
.card {background:white; border:1px solid #e5e7eb; border-radius:18px; padding:1rem; box-shadow:0 8px 24px rgba(15,23,42,.06);}
.alba {background:#eef2ff; border-left:4px solid #6366f1; padding:.8rem 1rem; border-radius:16px; margin:.5rem 0;}
.cand {background:#eff6ff; border-left:4px solid #3b82f6; padding:.8rem 1rem; border-radius:16px; margin:.5rem 0;}
.ok {border-left:5px solid #16a34a; background:#f0fdf4; padding:1rem; border-radius:12px;}
.warn {border-left:5px solid #f59e0b; background:#fffbeb; padding:1rem; border-radius:12px;}
.bad {border-left:5px solid #dc2626; background:#fef2f2; padding:1rem; border-radius:12px;}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Configuración")
    st.caption("Podés pegar los datos acá o guardarlos en .streamlit/secrets.toml")
    st.session_state.did_api_key_ui = st.text_input("D_ID_API_KEY", value=st.session_state.did_api_key_ui, type="password", help="Pegá la API key de D-ID. Si viene con 'Basic ', también sirve.")
    st.session_state.did_source_url_ui = st.text_input("D_ID_SOURCE_URL", value=st.session_state.did_source_url_ui, placeholder="https://.../alba.jpg", help="URL pública HTTPS directa a una imagen frontal del avatar.")
    voice_id = st.selectbox("Voz humana", ["es-AR-ElenaNeural", "es-AR-TomasNeural", "es-ES-ElviraNeural", "es-MX-DaliaNeural"], index=0)
    st.session_state.openai_api_key_ui = st.text_input("OPENAI_API_KEY opcional", value=st.session_state.openai_api_key_ui, type="password")
    model_name = st.text_input("Modelo OpenAI", value="gpt-4.1-mini")
    use_ai_eval = st.toggle("Usar IA para evaluación final si hay OpenAI", value=True)
    st.divider()
    if st.button("Probar conexión D-ID"):
        ok, msg = test_did_connection(st.session_state.did_api_key_ui)
        if ok:
            st.success(msg)
        else:
            st.error(msg)
    st.caption("Importante: D-ID usa /talks, no /translations.")

st.title("Alba — Avatar entrevistador")
st.caption("Streamlit + D-ID: genera un video real de Alba hablando para cada pregunta.")

api_key = st.session_state.did_api_key_ui
source_url = st.session_state.did_source_url_ui
configured = bool(normalize_did_api_key(api_key)) and is_public_image_url(source_url)

if not configured:
    st.warning("Falta configurar D_ID_API_KEY y/o D_ID_SOURCE_URL. Pegalos en el panel izquierdo. La URL debe ser pública HTTPS y terminar en .jpg/.jpeg/.png/.webp")
    with st.expander("Ejemplo de .streamlit/secrets.toml", expanded=True):
        st.code('''OPENAI_API_KEY = "sk-..."
D_ID_API_KEY = "tu_key_de_did"
D_ID_SOURCE_URL = "https://tu-dominio.com/alba.jpg"''', language="toml")

col_a, col_b, col_c = st.columns([1.1, 1, 1])
with col_a:
    candidate_name = st.text_input("Candidato/a", value="")
with col_b:
    role_name = st.selectbox("Puesto", list(ROLE_PROFILES.keys()))
with col_c:
    interviewer = st.text_input("Responsable RRHH", value="")

candidate_code = stable_candidate_code(candidate_name)
profile = ROLE_PROFILES[role_name]
questions = profile["questions"]
q_idx = st.session_state.question_index
current_question = questions[q_idx]

st.markdown(f"<div class='hero'><b>Puesto:</b> {role_name}<br><b>Objetivo:</b> {profile['descripcion']}<br><b>Progreso:</b> pregunta {q_idx + 1} de {len(questions)}</div>", unsafe_allow_html=True)
progress = (q_idx + 1) / len(questions)
st.progress(progress)

left, right = st.columns([1.15, 0.85])

with left:
    st.subheader("🎥 Avatar hablando")
    video_key = hashlib.sha256(f"{role_name}|{q_idx}|{voice_id}|{source_url}|{current_question}".encode()).hexdigest()
    if video_key in st.session_state.avatar_videos:
        st.video(st.session_state.avatar_videos[video_key])
    elif source_url:
        st.image(source_url, caption="Imagen base de Alba. Al generar video, se verá hablando con labios sincronizados.", use_container_width=True)
    else:
        st.info("Cuando pegues D_ID_SOURCE_URL se verá la imagen base de Alba.")

    st.markdown(f"<div class='alba'><b>Alba pregunta:</b><br>{current_question}</div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🎬 Generar video real de esta pregunta", type="primary", disabled=not configured, use_container_width=True):
            try:
                with st.spinner("D-ID está generando el video de Alba. Puede tardar 10 a 60 segundos..."):
                    result_url, talk_id, raw = generate_avatar_video(current_question, source_url, api_key, voice_id)
                st.session_state.avatar_videos[video_key] = result_url
                st.success(f"Video generado correctamente. ID: {talk_id}")
                st.rerun()
            except Exception as e:
                st.error(str(e))
                st.info("Revisá que la key sea válida y que la imagen tenga URL pública directa. No sirve un archivo local ni una URL privada.")
    with col2:
        if st.button("↻ Rehacer video", disabled=not configured, use_container_width=True):
            st.session_state.avatar_videos.pop(video_key, None)
            st.rerun()

with right:
    st.subheader("💬 Conversación")
    st.markdown(f"<div class='alba'><b>Alba:</b><br>{current_question}</div>", unsafe_allow_html=True)
    for item in st.session_state.transcript:
        st.markdown(f"<div class='alba'><b>Alba:</b><br>{item['question']}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='cand'><b>Candidato/a:</b><br>{item['answer']}</div>", unsafe_allow_html=True)

st.divider()
col_r1, col_r2 = st.columns([2, 1])
with col_r1:
    answer = st.text_area("Respuesta del candidato", height=130, placeholder="Escribir respuesta...")
with col_r2:
    st.write("")
    st.write("")
    if st.button("Guardar respuesta y avanzar", type="primary", use_container_width=True):
        if not answer.strip():
            st.error("Primero escribí la respuesta del candidato.")
        else:
            st.session_state.transcript.append({"question": current_question, "answer": answer.strip()})
            if st.session_state.question_index < len(questions) - 1:
                st.session_state.question_index += 1
            st.rerun()
    if st.button("Volver pregunta anterior", use_container_width=True):
        if st.session_state.question_index > 0:
            st.session_state.question_index -= 1
            if st.session_state.transcript:
                st.session_state.transcript.pop()
            st.rerun()
    if st.button("Reiniciar entrevista", use_container_width=True):
        st.session_state.transcript = []
        st.session_state.question_index = 0
        st.session_state.last_result = None
        st.rerun()

st.divider()
st.subheader("📄 CV / antecedentes")
cv_text = st.text_area("Pegar CV o antecedentes relevantes", height=140)

st.subheader("🧠 Evaluación")
if st.button("Evaluar entrevista", type="primary"):
    if not st.session_state.transcript:
        st.error("Primero cargá al menos una respuesta.")
    else:
        txt = transcript_text(st.session_state.transcript)
        result = None
        error = None
        if use_ai_eval:
            result, error = ai_evaluate(role_name, cv_text, txt, model_name, st.session_state.openai_api_key_ui)
        if result is None:
            if error:
                st.warning(f"No se pudo usar OpenAI. Se usa motor local. Detalle: {error}")
            result = local_evaluate(role_name, cv_text, txt)
        st.session_state.last_result = result

result = st.session_state.last_result
if result:
    rec = result.get("recommendation", "")
    score = result.get("score", 0)
    confidence = result.get("confidence", "")
    c1, c2, c3 = st.columns(3)
    c1.metric("Recomendación", rec)
    c2.metric("Score", f"{score}/100")
    c3.metric("Confianza", confidence)
    css = "ok" if "APROBAR" in rec else "bad" if "RECHAZAR" in rec else "warn"
    st.markdown(f"<div class='{css}'><b>Fundamento:</b><br>{result.get('rationale','')}</div>", unsafe_allow_html=True)
    l, r = st.columns(2)
    with l:
        st.markdown("**Fortalezas**")
        for x in result.get("strengths", []) or ["Sin fortalezas suficientes."]:
            st.write("- " + x)
    with r:
        st.markdown("**Riesgos / brechas**")
        for x in result.get("risks", []) or ["Sin riesgos relevantes."]:
            st.write("- " + x)
    scores = pd.DataFrame([{"Competencia": k, "Puntaje": v} for k, v in result.get("competency_scores", {}).items()])
    if not scores.empty:
        st.dataframe(scores, use_container_width=True, hide_index=True)
        st.bar_chart(scores.set_index("Competencia"))

    decision_humana = st.selectbox("Decisión humana final obligatoria", ["Pendiente", "Avanza", "No avanza", "Revisión técnica", "Mantener en base"])
    motivo_humano = st.text_area("Motivo de decisión humana")
    if st.button("Guardar evaluación en historial"):
        row = {
            "fecha_hora": now_str(),
            "codigo_candidato": candidate_code,
            "candidato": candidate_name,
            "puesto": role_name,
            "entrevistador": interviewer,
            "recomendacion_ia": rec,
            "score": score,
            "confianza": confidence,
            "decision_humana": decision_humana,
            "motivo_humano": motivo_humano,
            "fundamento": result.get("rationale", ""),
            "fortalezas": " | ".join(result.get("strengths", [])),
            "riesgos": " | ".join(result.get("risks", [])),
            "cv_texto": cv_text,
            "entrevista": transcript_text(st.session_state.transcript),
            "json_resultado": json.dumps(result, ensure_ascii=False),
        }
        df_all = append_history(row)
        st.success(f"Guardado. Total registros: {len(df_all)}")

st.divider()
st.subheader("📊 Historial")
hist = read_history()
if hist.empty:
    st.info("Todavía no hay evaluaciones guardadas.")
else:
    st.dataframe(hist, use_container_width=True)
    st.download_button("Descargar historial Excel", data=excel_bytes(hist), file_name="historial_evaluaciones_rrhh.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.download_button("Descargar historial CSV", data=hist.to_csv(index=False).encode("utf-8"), file_name="historial_evaluaciones_rrhh.csv", mime="text/csv")
