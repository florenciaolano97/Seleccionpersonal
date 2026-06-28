import base64
import hashlib
import io
import json
import os
import re
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any

import pandas as pd
import requests
import streamlit as st

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

try:
    import docx
except Exception:
    docx = None

try:
    from streamlit_mic_recorder import mic_recorder
except Exception:
    mic_recorder = None

APP_TITLE = "Alba Recruiter AI | Screening + entrevista universal"
DATA_DIR = Path("data")
UPLOAD_DIR = DATA_DIR / "uploads"
AUDIO_DIR = DATA_DIR / "audio"
DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)
AUDIO_DIR.mkdir(exist_ok=True)
HISTORY_FILE = DATA_DIR / "historial_candidatos.csv"

# =========================================================
# CONFIGURACIÓN UNIVERSAL
# =========================================================
INDUSTRIES = [
    "Industria / Manufactura", "Tecnología / IT", "Administración / Finanzas",
    "Comercial / Ventas", "Atención al cliente", "Logística / Supply Chain", "Salud",
    "Educación", "Construcción", "Gastronomía / Hotelería", "Retail",
    "Servicios profesionales", "Energía / Minería", "Agro", "Banca / Seguros", "Otro"
]

LEVELS = [
    "Operativo/a", "Técnico/a", "Administrativo/a", "Analista / Junior", "Semi Senior",
    "Senior", "Coordinación / Liderazgo", "Jefatura / Supervisión", "Gerencia", "Dirección"
]

DEFAULT_COMPETENCIES = {
    "Adecuación a requisitos excluyentes": 0.18,
    "Experiencia relevante para el puesto": 0.16,
    "Conocimientos técnicos / funcionales": 0.14,
    "Comunicación y claridad": 0.10,
    "Resolución de problemas": 0.10,
    "Trabajo en equipo": 0.08,
    "Responsabilidad y confiabilidad": 0.08,
    "Adaptabilidad y aprendizaje": 0.08,
    "Orientación a resultados": 0.08,
}

KEYWORDS = {
    "Adecuación a requisitos excluyentes": ["requisito", "disponibilidad", "licencia", "certificación", "certificacion", "idioma", "horario", "movilidad", "formación", "formacion"],
    "Experiencia relevante para el puesto": ["experiencia", "trabajé", "trabaje", "puesto", "empresa", "tarea", "función", "funcion", "responsabilidad", "proyecto", "sector"],
    "Conocimientos técnicos / funcionales": ["sistema", "herramienta", "proceso", "técnico", "tecnico", "procedimiento", "método", "metodo", "análisis", "analisis", "software", "máquina", "maquina", "excel", "sap", "crm", "erp"],
    "Comunicación y claridad": ["comunicar", "explicar", "claro", "cliente", "reunión", "reunion", "feedback", "escuchar", "coordinar", "presentar"],
    "Resolución de problemas": ["problema", "resolver", "solución", "solucion", "mejora", "causa", "prioridad", "decidí", "decidi", "analicé", "analice"],
    "Trabajo en equipo": ["equipo", "compañero", "compañera", "colaborar", "ayudar", "coordinar", "respeto", "grupo", "apoyo"],
    "Responsabilidad y confiabilidad": ["responsable", "cumplir", "puntual", "seguimiento", "orden", "compromiso", "confianza", "registro", "control"],
    "Adaptabilidad y aprendizaje": ["aprender", "adaptar", "cambio", "capacitación", "capacitacion", "nuevo", "mejorar", "flexible", "desafío", "desafio"],
    "Orientación a resultados": ["objetivo", "resultado", "indicador", "meta", "cumplimiento", "productividad", "venta", "cliente", "calidad", "plazo"],
}

PROTECTED_OR_NON_DECISION_DATA = [
    "edad", "fecha de nacimiento", "dni", "documento", "teléfono", "telefono", "email",
    "domicilio", "dirección", "direccion", "estado civil", "embarazo", "hijos",
    "religión", "religion", "política", "politica", "partido político", "sindicato",
    "orientación sexual", "orientacion sexual", "salud", "discapacidad", "nacionalidad",
    "raza", "etnia", "obra social", "antecedentes médicos", "licencia médica"
]

RED_FLAGS = {
    "conducta_laboral": [r"no acepto indicaciones", r"me pele(o|é)", r"discuto con todos", r"falto mucho", r"llego tarde siempre", r"no sigo instrucciones"],
    "seguridad_o_normas": [r"no respeto procedimiento", r"no uso epp", r"sin protecci", r"salte(o|ar) controles", r"anulo alarmas", r"no cumplo normas"],
    "incompatibilidad_excluyente": [r"no tengo disponibilidad", r"no puedo viajar", r"no puedo turnos", r"no manejo", r"no tengo licencia", r"no tengo experiencia"],
}

QUESTION_BANK = [
    "Contame brevemente tu experiencia laboral más relacionada con este puesto.",
    "¿Qué tareas concretas realizaste que se parezcan a las responsabilidades de esta posición?",
    "¿Qué conocimientos técnicos, herramientas o sistemas dominás para este puesto?",
    "Contame una situación en la que tuviste que resolver un problema laboral. ¿Qué hiciste y qué resultado obtuviste?",
    "¿Cómo te organizás cuando tenés varias prioridades al mismo tiempo?",
    "Describí una situación en la que trabajaste en equipo para lograr un objetivo.",
    "¿Cómo reaccionás cuando recibís una corrección o feedback sobre tu trabajo?",
    "¿Qué te motiva de esta posición y por qué creés que podrías aportar valor?",
]

# =========================================================
# HELPERS
# =========================================================
def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_secret(name: str, default: str = "") -> str:
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.getenv(name, default)


def stable_code(raw: str) -> str:
    base = raw.strip() if raw else str(time.time())
    return "CAND-" + hashlib.sha256(base.encode("utf-8")).hexdigest()[:10].upper()


def normalize_url(url: str) -> str:
    url = (url or "").strip().replace("[img]", "").replace("[/img]", "")
    if "https://" in url and not url.startswith("https://"):
        url = url[url.find("https://"):]
    if " " in url:
        url = url.split()[0]
    return url


def is_valid_image_url(url: str) -> bool:
    u = normalize_url(url).lower()
    return u.startswith("https://") and any(u.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"])


def safe_lower(text: str) -> str:
    return (text or "").lower().strip()


def tokenize_requirements(text: str) -> List[str]:
    raw = re.split(r"[,;\n\-•]+", text or "")
    items = []
    for x in raw:
        x = re.sub(r"\s+", " ", x).strip().lower()
        if len(x) >= 3:
            items.append(x)
    return items[:80]


def detect_protected_data(text: str) -> List[str]:
    t = safe_lower(text)
    return sorted(set([x for x in PROTECTED_OR_NON_DECISION_DATA if x in t]))


def detect_red_flags(text: str) -> List[str]:
    t = safe_lower(text)
    findings = []
    for group, patterns in RED_FLAGS.items():
        for pat in patterns:
            if re.search(pat, t):
                findings.append(group)
                break
    return sorted(set(findings))


def keyword_hits(text: str, words: List[str]) -> int:
    t = safe_lower(text)
    return sum(1 for w in words if safe_lower(w) and safe_lower(w) in t)


def score_competency(comp: str, text: str, custom_keywords: List[str]) -> int:
    words = KEYWORDS.get(comp, []) + custom_keywords
    hits = keyword_hits(text, words)
    length_bonus = min(len(text.split()) / 180, 1.0) * 18
    evidence_bonus = 12 if any(x in safe_lower(text) for x in ["por ejemplo", "una vez", "logré", "logre", "resultado", "situación", "situacion"]) else 0
    return int(round(min((hits / 7) * 70 + length_bonus + evidence_bonus, 100)))


def recommendation_from_score(score: int, red_flags: List[str], must_have_match: float) -> Tuple[str, str]:
    if "conducta_laboral" in red_flags or "seguridad_o_normas" in red_flags:
        return "RECHAZAR PRIMERA INSTANCIA", "Alerta crítica laboral o de normas detectada."
    if must_have_match < 0.35:
        return "RECHAZAR PRIMERA INSTANCIA", "Baja coincidencia con requisitos excluyentes declarados."
    if score >= 75 and must_have_match >= 0.60:
        return "AVANZAR A ENTREVISTA CON ALBA", "Alta coincidencia con el perfil buscado."
    if score >= 58:
        return "REVISIÓN HUMANA", "Coincidencia parcial o evidencia insuficiente para decisión automática."
    return "RECHAZAR PRIMERA INSTANCIA", "Puntaje global insuficiente para avanzar."


def evaluate_text(text: str, job_title: str, responsibilities: str, must_haves: str, nice_to_haves: str) -> Dict[str, Any]:
    text = text or ""
    must_items = tokenize_requirements(must_haves)
    nice_items = tokenize_requirements(nice_to_haves)
    job_words = tokenize_requirements(job_title + "\n" + responsibilities)

    matched_must = [m for m in must_items if any(tok in safe_lower(text) for tok in re.findall(r"[a-záéíóúñ0-9+#.]{3,}", m))]
    must_match = len(matched_must) / max(len(must_items), 1)

    comp_scores = {}
    weighted = 0
    for comp, weight in DEFAULT_COMPETENCIES.items():
        custom = job_words + must_items + nice_items
        score = score_competency(comp, text, custom)
        if comp == "Adecuación a requisitos excluyentes":
            score = int(round(score * 0.45 + must_match * 100 * 0.55))
        comp_scores[comp] = score
        weighted += score * weight

    global_score = int(round(weighted))
    red_flags = detect_red_flags(text)
    protected = detect_protected_data(text)
    recommendation, reason = recommendation_from_score(global_score, red_flags, must_match)

    strengths = [f"{c}: evidencia favorable ({s}/100)" for c, s in comp_scores.items() if s >= 70][:6]
    gaps = [f"{c}: evidencia baja o no demostrada ({s}/100)" for c, s in comp_scores.items() if s < 55][:6]

    if matched_must:
        strengths.insert(0, "Requisitos detectados en CV/respuestas: " + "; ".join(matched_must[:5]))
    missing_must = [m for m in must_items if m not in matched_must]
    if missing_must:
        gaps.insert(0, "Requisitos no encontrados o no demostrados: " + "; ".join(missing_must[:5]))

    return {
        "score": global_score,
        "recommendation": recommendation,
        "reason": reason,
        "must_have_match": round(must_match * 100, 1),
        "matched_must_haves": matched_must,
        "missing_must_haves": missing_must,
        "competency_scores": comp_scores,
        "strengths": strengths,
        "gaps": gaps,
        "red_flags": red_flags,
        "protected_data_detected": protected,
        "method": "motor_local_explicable_sin_datos_sensibles_para_decision",
    }


def final_report(candidate: Dict[str, Any], screening: Dict[str, Any], interview: Dict[str, Any] = None) -> str:
    interview = interview or {}
    final_score = screening.get("score", 0)
    if interview:
        final_score = int(round(screening.get("score", 0) * 0.55 + interview.get("score", 0) * 0.45))
    if final_score >= 75 and screening.get("recommendation") != "RECHAZAR PRIMERA INSTANCIA":
        final_decision = "AVANZAR"
    elif final_score >= 58 and screening.get("recommendation") != "RECHAZAR PRIMERA INSTANCIA":
        final_decision = "REVISIÓN HUMANA"
    else:
        final_decision = "RECHAZAR PRIMERA INSTANCIA"

    lines = []
    lines.append(f"Decisión sugerida: {final_decision}")
    lines.append(f"Puntaje final: {final_score}/100")
    lines.append("")
    lines.append("Fundamento principal:")
    lines.append(f"- Screening CV: {screening.get('recommendation')} ({screening.get('score')}/100). {screening.get('reason')}")
    if interview:
        lines.append(f"- Entrevista Alba: {interview.get('recommendation')} ({interview.get('score')}/100). {interview.get('reason')}")
    else:
        lines.append("- Entrevista Alba: pendiente o no realizada.")
    lines.append("")
    lines.append("Fortalezas observadas:")
    strengths = (screening.get("strengths") or []) + (interview.get("strengths") or [])
    for s in strengths[:8] or ["No se identificaron fortalezas suficientes con evidencia laboral."]:
        lines.append(f"- {s}")
    lines.append("")
    lines.append("Brechas / riesgos:")
    gaps = (screening.get("gaps") or []) + (interview.get("gaps") or [])
    for g in gaps[:8] or ["No se identificaron brechas críticas."]:
        lines.append(f"- {g}")
    if screening.get("red_flags") or interview.get("red_flags"):
        lines.append("- Alertas detectadas: " + "; ".join(sorted(set(screening.get("red_flags", []) + interview.get("red_flags", [])))))
    lines.append("")
    lines.append("Nota de compliance:")
    lines.append("Los datos administrativos del candidato, como DNI, teléfono, fecha de nacimiento o edad, pueden registrarse para gestión, pero no se utilizan para puntuar, rankear ni decidir. Los datos sensibles de la empresa no se requieren ni se exponen en la herramienta.")
    return "\n".join(lines)


def extract_text_from_file(uploaded_file) -> str:
    name = uploaded_file.name.lower()
    data = uploaded_file.read()
    uploaded_file.seek(0)
    try:
        if name.endswith(".txt"):
            return data.decode("utf-8", errors="ignore")
        if name.endswith(".pdf") and PdfReader is not None:
            reader = PdfReader(io.BytesIO(data))
            parts = []
            for page in reader.pages[:8]:
                parts.append(page.extract_text() or "")
            return "\n".join(parts)
        if name.endswith(".docx") and docx is not None:
            d = docx.Document(io.BytesIO(data))
            return "\n".join(p.text for p in d.paragraphs)
    except Exception as e:
        return f"[Error leyendo archivo: {e}]"
    return "[Formato no soportado o dependencia no instalada. Usar PDF, DOCX o TXT.]"


def bytes_to_download(df: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Ranking", index=False)
    return output.getvalue()


def append_history(row: Dict[str, Any]) -> pd.DataFrame:
    new = pd.DataFrame([row])
    if HISTORY_FILE.exists():
        old = pd.read_csv(HISTORY_FILE)
        all_df = pd.concat([old, new], ignore_index=True)
    else:
        all_df = new
    all_df.to_csv(HISTORY_FILE, index=False)
    return all_df

# =========================================================
# D-ID AVATAR
# =========================================================
def did_auth_header(api_key: str) -> Dict[str, str]:
    # D-ID acepta Basic <base64(username:password)>.
    # Si el usuario pega username:password, lo codificamos.
    # Si pega una key ya codificada, igualmente permitimos modo Basic directo.
    key = (api_key or "").strip()
    if ":" in key:
        token = base64.b64encode(key.encode("utf-8")).decode("utf-8")
    else:
        token = key
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


def create_did_talk(api_key: str, source_url: str, text: str, voice_id: str) -> Tuple[str, str]:
    if not api_key:
        return "", "Falta D_ID_API_KEY."
    if not is_valid_image_url(source_url):
        return "", "D_ID_SOURCE_URL debe ser una URL pública HTTPS y terminar en .jpg/.jpeg/.png/.webp"
    payload = {
        "source_url": normalize_url(source_url),
        "script": {
            "type": "text",
            "input": text,
            "provider": {"type": "microsoft", "voice_id": voice_id or "es-AR-ElenaNeural"},
        },
        "config": {"fluent": True, "pad_audio": 0.2},
    }
    try:
        r = requests.post("https://api.d-id.com/talks", headers=did_auth_header(api_key), json=payload, timeout=60)
        if r.status_code not in [200, 201]:
            return "", f"D-ID error {r.status_code}: {r.text}"
        talk_id = r.json().get("id", "")
        if not talk_id:
            return "", f"D-ID no devolvió id: {r.text}"
        return talk_id, ""
    except Exception as e:
        return "", str(e)


def poll_did_video(api_key: str, talk_id: str, max_wait: int = 90) -> Tuple[str, str]:
    start = time.time()
    while time.time() - start < max_wait:
        try:
            r = requests.get(f"https://api.d-id.com/talks/{talk_id}", headers=did_auth_header(api_key), timeout=30)
            if r.status_code != 200:
                return "", f"D-ID status error {r.status_code}: {r.text}"
            data = r.json()
            status = data.get("status")
            if status == "done":
                return data.get("result_url", ""), ""
            if status == "error":
                return "", json.dumps(data, ensure_ascii=False)
            time.sleep(3)
        except Exception as e:
            return "", str(e)
    return "", "Tiempo de espera agotado generando video."

# =========================================================
# UI
# =========================================================
st.set_page_config(page_title=APP_TITLE, page_icon="🤖", layout="wide")

st.markdown("""
<style>
.block-container {padding-top: 1rem;}
.alba-card {background:#eef2ff; border-left:5px solid #6c63ff; padding:1rem; border-radius:1rem; margin-bottom:0.8rem;}
.cand-card {background:#e8f3ff; padding:1rem; border-radius:1rem; margin-bottom:0.8rem;}
.ok {background:#ecfdf3; border-left:5px solid #16a34a; padding:1rem; border-radius:0.8rem;}
.warn {background:#fff7e6; border-left:5px solid #f59e0b; padding:1rem; border-radius:0.8rem;}
.bad {background:#fff0f0; border-left:5px solid #ef4444; padding:1rem; border-radius:0.8rem;}
</style>
""", unsafe_allow_html=True)

st.title(APP_TITLE)
st.caption("Versión estable Streamlit: screening masivo de CVs + entrevista con Alba por video + respuesta escrita o audio grabado. No usa datos sensibles para decidir.")

with st.sidebar:
    st.header("Configuración")
    d_id_api_key = st.text_input("D_ID_API_KEY", value=get_secret("D_ID_API_KEY", ""), type="password")
    d_id_source_url = st.text_input("D_ID_SOURCE_URL", value=get_secret("D_ID_SOURCE_URL", ""))
    voice_id = st.text_input("Voz D-ID Microsoft", value="es-AR-ElenaNeural")
    st.divider()
    st.info("Datos del candidato como DNI, edad, teléfono o fecha de nacimiento se registran solo para gestión administrativa. No se usan para decidir ni rankear.")

if "candidates" not in st.session_state:
    st.session_state.candidates = []
if "selected_idx" not in st.session_state:
    st.session_state.selected_idx = 0
if "conversation" not in st.session_state:
    st.session_state.conversation = []
if "question_idx" not in st.session_state:
    st.session_state.question_idx = 0

# =========================================================
# TABS
# =========================================================
tab_job, tab_bulk, tab_interview, tab_ranking, tab_history = st.tabs([
    "1. Puesto", "2. Carga masiva CV", "3. Entrevista con Alba", "4. Ranking e informes", "5. Historial"
])

with tab_job:
    st.subheader("Definición universal del puesto")
    col1, col2, col3 = st.columns(3)
    with col1:
        company_alias = st.text_input("Empresa / cliente (opcional)", placeholder="Ej.: Cliente A, Empresa X")
        industry = st.selectbox("Industria", INDUSTRIES)
    with col2:
        job_title = st.text_input("Nombre del puesto", value="Analista / Operario / Comercial / Administrativo")
        level = st.selectbox("Nivel", LEVELS)
    with col3:
        location_mode = st.selectbox("Modalidad", ["Presencial", "Híbrido", "Remoto", "Indistinto"])
        human_review_required = st.checkbox("Decisión humana final obligatoria", value=True)

    responsibilities = st.text_area("Responsabilidades principales", height=110, placeholder="Describir tareas y objetivos del puesto.")
    must_haves = st.text_area("Requisitos excluyentes", height=100, placeholder="Ej.: experiencia en ventas B2B, Excel avanzado, disponibilidad full time, licencia B1, inglés intermedio...")
    nice_to_haves = st.text_area("Requisitos deseables", height=80, placeholder="Ej.: SAP, industria similar, liderazgo, herramientas específicas...")

    st.markdown("### Preguntas de entrevista con Alba")
    default_questions = "\n".join(QUESTION_BANK)
    questions_text = st.text_area("Una pregunta por línea", value=default_questions, height=180)
    st.session_state.job = {
        "company_alias": company_alias,
        "industry": industry,
        "job_title": job_title,
        "level": level,
        "location_mode": location_mode,
        "responsibilities": responsibilities,
        "must_haves": must_haves,
        "nice_to_haves": nice_to_haves,
        "questions": [q.strip() for q in questions_text.splitlines() if q.strip()],
        "human_review_required": human_review_required,
    }

with tab_bulk:
    st.subheader("Carga masiva y screening inicial de CVs")
    st.write("Subí varios CVs en PDF, DOCX o TXT. La app extrae texto, evalúa coincidencia con el puesto y rankea automáticamente.")
    uploaded = st.file_uploader("CVs de candidatos", type=["pdf", "docx", "txt"], accept_multiple_files=True)

    if uploaded:
        st.caption("Opcional: completá datos administrativos si querés. No se usan para puntuar.")
        admin_rows = []
        for i, f in enumerate(uploaded):
            with st.expander(f"Datos administrativos — {f.name}", expanded=False):
                c1, c2, c3, c4 = st.columns(4)
                name = c1.text_input("Nombre", key=f"name_{i}", value=Path(f.name).stem[:60])
                dni = c2.text_input("DNI", key=f"dni_{i}")
                phone = c3.text_input("Teléfono", key=f"phone_{i}")
                email = c4.text_input("Email", key=f"email_{i}")
                c5, c6 = st.columns(2)
                birth = c5.text_input("Fecha nacimiento", key=f"birth_{i}")
                age = c6.text_input("Edad", key=f"age_{i}")
                admin_rows.append({"name": name, "dni": dni, "phone": phone, "email": email, "birth": birth, "age": age})

        if st.button("Analizar CVs y generar ranking inicial", type="primary", use_container_width=True):
            job = st.session_state.get("job", {})
            candidates = []
            progress = st.progress(0)
            for i, f in enumerate(uploaded):
                text = extract_text_from_file(f)
                screening = evaluate_text(
                    text,
                    job.get("job_title", ""),
                    job.get("responsibilities", ""),
                    job.get("must_haves", ""),
                    job.get("nice_to_haves", ""),
                )
                code = stable_code(admin_rows[i].get("name", "") + f.name)
                candidate = {
                    "code": code,
                    "file_name": f.name,
                    "admin": admin_rows[i],
                    "cv_text": text,
                    "screening": screening,
                    "interview_answers": [],
                    "interview_audio_files": [],
                    "interview": {},
                    "final_report": "",
                    "created_at": now_str(),
                }
                candidates.append(candidate)
                progress.progress((i + 1) / len(uploaded))
            candidates.sort(key=lambda c: c["screening"]["score"], reverse=True)
            st.session_state.candidates = candidates
            st.success(f"Se analizaron {len(candidates)} CVs.")

    candidates = st.session_state.get("candidates", [])
    if candidates:
        df = pd.DataFrame([{
            "Ranking": idx + 1,
            "Código": c["code"],
            "Nombre": c["admin"].get("name", ""),
            "Archivo": c["file_name"],
            "Puntaje CV": c["screening"].get("score"),
            "% Requisitos excluyentes": c["screening"].get("must_have_match"),
            "Recomendación inicial": c["screening"].get("recommendation"),
            "Motivo": c["screening"].get("reason"),
        } for idx, c in enumerate(candidates)])
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("Descargar ranking inicial Excel", bytes_to_download(df), "ranking_inicial_cvs.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with tab_interview:
    st.subheader("Entrevista con Alba")
    candidates = st.session_state.get("candidates", [])
    if not candidates:
        st.info("Primero cargá y analizá CVs en la pestaña 2. También podés crear un candidato manual pegando un CV como TXT.")
        manual_cv = st.text_area("CV / antecedentes manuales", height=180)
        manual_name = st.text_input("Nombre candidato manual")
        if st.button("Crear candidato manual") and manual_cv.strip():
            job = st.session_state.get("job", {})
            screening = evaluate_text(manual_cv, job.get("job_title", ""), job.get("responsibilities", ""), job.get("must_haves", ""), job.get("nice_to_haves", ""))
            st.session_state.candidates = [{
                "code": stable_code(manual_name), "file_name": "manual.txt", "admin": {"name": manual_name},
                "cv_text": manual_cv, "screening": screening, "interview_answers": [], "interview_audio_files": [], "interview": {}, "final_report": "", "created_at": now_str()
            }]
            st.rerun()
    else:
        options = [f"#{i+1} | {c['admin'].get('name','')} | {c['screening']['recommendation']} | {c['screening']['score']}/100" for i, c in enumerate(candidates)]
        selected_label = st.selectbox("Seleccionar candidato", options, index=min(st.session_state.selected_idx, len(options)-1))
        idx = options.index(selected_label)
        st.session_state.selected_idx = idx
        cand = candidates[idx]

        rec = cand["screening"]["recommendation"]
        if rec == "RECHAZAR PRIMERA INSTANCIA":
            st.warning("Este candidato fue marcado como rechazo inicial por CV. RRHH puede igualmente decidir entrevistarlo si lo considera necesario.")

        col_a, col_b = st.columns([1, 1])
        with col_a:
            st.markdown("### Avatar Alba")
            questions = st.session_state.get("job", {}).get("questions", QUESTION_BANK)
            q_idx = st.session_state.question_idx % max(len(questions), 1)
            current_question = questions[q_idx]
            st.markdown(f"<div class='alba-card'><b>Alba:</b><br>{current_question}</div>", unsafe_allow_html=True)
            if d_id_source_url:
                try:
                    st.image(normalize_url(d_id_source_url), caption="Imagen base. Al generar video, Alba hablará esta pregunta.")
                except Exception:
                    pass
            if st.button("Generar/reproducir pregunta con Alba", type="primary", use_container_width=True):
                with st.spinner("Generando video con D-ID..."):
                    talk_id, err = create_did_talk(d_id_api_key, d_id_source_url, current_question, voice_id)
                    if err:
                        st.error(err)
                    else:
                        video_url, err2 = poll_did_video(d_id_api_key, talk_id)
                        if err2:
                            st.error(err2)
                        else:
                            st.session_state.last_video_url = video_url
                if st.session_state.get("last_video_url"):
                    st.video(st.session_state.last_video_url)
            elif st.session_state.get("last_video_url"):
                st.video(st.session_state.last_video_url)

        with col_b:
            st.markdown("### Respuesta del candidato")
            st.write("Puede responder escribiendo o grabar audio. La respuesta escrita es la que se evalúa; el audio queda como evidencia/registro si se usa.")
            response_text = st.text_area("Respuesta escrita / transcripción manual", height=180, key=f"resp_{cand['code']}_{q_idx}")

            audio_saved_path = ""
            if mic_recorder is not None:
                audio = mic_recorder(start_prompt="🎙️ Grabar respuesta", stop_prompt="⏹️ Detener", just_once=True, key=f"mic_{cand['code']}_{q_idx}")
                if audio and "bytes" in audio:
                    audio_bytes = audio["bytes"]
                    audio_saved_path = str(AUDIO_DIR / f"{cand['code']}_pregunta_{q_idx+1}.wav")
                    with open(audio_saved_path, "wb") as af:
                        af.write(audio_bytes)
                    st.audio(audio_bytes)
                    st.caption("Audio guardado como evidencia. Para mantener estabilidad sin APIs, escribí o pegá la transcripción en el campo de respuesta.")
            else:
                audio_up = st.file_uploader("Subir audio de respuesta (opcional)", type=["wav", "mp3", "m4a"], key=f"aud_{cand['code']}_{q_idx}")
                if audio_up:
                    audio_saved_path = str(AUDIO_DIR / f"{cand['code']}_pregunta_{q_idx+1}_{audio_up.name}")
                    with open(audio_saved_path, "wb") as af:
                        af.write(audio_up.read())
                    st.audio(audio_saved_path)

            c1, c2, c3 = st.columns(3)
            if c1.button("Guardar respuesta y avanzar", use_container_width=True):
                if response_text.strip() or audio_saved_path:
                    cand["interview_answers"].append({"question": current_question, "answer": response_text, "datetime": now_str()})
                    if audio_saved_path:
                        cand["interview_audio_files"].append(audio_saved_path)
                    st.session_state.question_idx += 1
                    st.success("Respuesta guardada.")
                    st.rerun()
                else:
                    st.error("Escribí una respuesta o grabá/subí un audio.")
            if c2.button("Volver pregunta", use_container_width=True):
                st.session_state.question_idx = max(st.session_state.question_idx - 1, 0)
                st.rerun()
            if c3.button("Evaluar entrevista", use_container_width=True):
                answers_text = "\n\n".join([f"Pregunta: {a['question']}\nRespuesta: {a['answer']}" for a in cand["interview_answers"]])
                job = st.session_state.get("job", {})
                interview_eval = evaluate_text(answers_text, job.get("job_title", ""), job.get("responsibilities", ""), job.get("must_haves", ""), job.get("nice_to_haves", ""))
                cand["interview"] = interview_eval
                cand["final_report"] = final_report(cand, cand["screening"], interview_eval)
                st.success("Entrevista evaluada.")

        if cand.get("interview_answers"):
            st.markdown("### Conversación registrada")
            for a in cand["interview_answers"]:
                st.markdown(f"<div class='alba-card'><b>Alba:</b><br>{a['question']}</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='cand-card'><b>Candidato:</b><br>{a['answer'] or '[Respuesta por audio registrada]'}</div>", unsafe_allow_html=True)

with tab_ranking:
    st.subheader("Ranking final e informes")
    candidates = st.session_state.get("candidates", [])
    if not candidates:
        st.info("Todavía no hay candidatos cargados.")
    else:
        rows = []
        for c in candidates:
            if c.get("interview"):
                final_score = int(round(c["screening"]["score"] * 0.55 + c["interview"].get("score", 0) * 0.45))
                interview_score = c["interview"].get("score", 0)
            else:
                final_score = c["screening"]["score"]
                interview_score = None
            if final_score >= 75 and c["screening"].get("recommendation") != "RECHAZAR PRIMERA INSTANCIA":
                final_rec = "AVANZAR"
            elif final_score >= 58 and c["screening"].get("recommendation") != "RECHAZAR PRIMERA INSTANCIA":
                final_rec = "REVISIÓN HUMANA"
            else:
                final_rec = "RECHAZAR PRIMERA INSTANCIA"
            if not c.get("final_report"):
                c["final_report"] = final_report(c, c["screening"], c.get("interview", {}))
            rows.append({
                "Nombre": c["admin"].get("name", ""),
                "Código": c["code"],
                "Puntaje CV": c["screening"].get("score"),
                "Puntaje entrevista": interview_score,
                "Puntaje final": final_score,
                "Recomendación final": final_rec,
                "Informe": c["final_report"],
                "DNI (admin)": c["admin"].get("dni", ""),
                "Teléfono (admin)": c["admin"].get("phone", ""),
                "Email (admin)": c["admin"].get("email", ""),
                "Edad (admin)": c["admin"].get("age", ""),
            })
        df_final = pd.DataFrame(rows).sort_values("Puntaje final", ascending=False).reset_index(drop=True)
        df_final.insert(0, "Ranking", range(1, len(df_final) + 1))
        st.dataframe(df_final.drop(columns=["Informe"]), use_container_width=True, hide_index=True)
        st.download_button("Descargar ranking final Excel", bytes_to_download(df_final), "ranking_final_candidatos.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        st.markdown("### Informe completo por candidato")
        chosen = st.selectbox("Elegir informe", df_final["Nombre"].fillna("") + " | " + df_final["Código"])
        chosen_code = chosen.split(" | ")[-1]
        cand = next((c for c in candidates if c["code"] == chosen_code), None)
        if cand:
            st.text_area("Informe", value=cand.get("final_report", ""), height=420)
            if st.button("Guardar candidato en historial", type="primary"):
                row = df_final[df_final["Código"] == chosen_code].iloc[0].to_dict()
                row["fecha_hora"] = now_str()
                row["puesto"] = st.session_state.get("job", {}).get("job_title", "")
                row["industria"] = st.session_state.get("job", {}).get("industry", "")
                append_history(row)
                st.success("Guardado en historial.")

with tab_history:
    st.subheader("Historial")
    if HISTORY_FILE.exists():
        hist = pd.read_csv(HISTORY_FILE)
        st.dataframe(hist, use_container_width=True)
        st.download_button("Descargar historial CSV", hist.to_csv(index=False).encode("utf-8"), "historial_candidatos.csv", "text/csv")
    else:
        st.info("Todavía no hay historial guardado.")

