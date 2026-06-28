import os
import re
import time
import json
import base64
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import requests
import streamlit as st

APP_TITLE = "AI-RRHH | Alba entrevista virtual estable"
DID_API_URL = "https://api.d-id.com/talks"
DEFAULT_VOICE = "es-AR-ElenaNeural"
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
HISTORY_FILE = DATA_DIR / "evaluaciones_alba.csv"

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
        "¿Cómo registrarías una intervención para que sirva al turno siguiente?",
        "¿Qué harías si producción te presiona para reparar rápido salteando un paso de seguridad?",
    ],
}

COMPETENCIES = {
    "Seguridad industrial y EPP": ["epp", "seguridad", "guantes", "lentes", "protección", "riesgo", "procedimiento", "bloqueo", "accidente"],
    "Experiencia industrial/autopartista": ["producción", "inyectora", "inyección", "plástico", "autoparte", "autopartista", "línea", "máquina", "molde"],
    "Calidad y atención al detalle": ["calidad", "defecto", "rebaba", "control", "inspección", "pieza", "no conformidad", "medición"],
    "Disciplina operativa": ["instrucción", "procedimiento", "estándar", "cumplir", "orden", "supervisor", "responsable"],
    "Trabajo en equipo y comunicación": ["equipo", "compañero", "comunicar", "avisar", "respeto", "supervisor", "ayuda"],
    "Disponibilidad operativa": ["turno", "rotativo", "noche", "fines de semana", "disponibilidad", "horas extra"],
}

RED_FLAGS = [
    ("Seguridad", ["no uso epp", "sin epp", "no respeto", "saltear seguridad", "anular alarma", "trabajo sin protección"]),
    ("Conducta", ["me peleo", "discuto con todos", "llego tarde siempre", "falto mucho", "no acepto indicaciones"]),
    ("Disponibilidad", ["no puedo turnos", "no puedo rotar", "no trabajo de noche", "no fines de semana"]),
]

SENSITIVE = ["edad", "embarazo", "hijos", "religión", "sindicato", "política", "salud", "discapacidad", "estado civil", "domicilio"]


def get_secret(name: str, default: str = "") -> str:
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.getenv(name, default)


def clean_source_url(url: str) -> str:
    url = (url or "").strip()
    if url and not url.startswith("http"):
        url = "https://" + url
    return url


def is_valid_image_url(url: str) -> bool:
    return bool(re.match(r"^https://.+\.(jpg|jpeg|png|webp)(\?.*)?$", url.strip(), re.I))


def did_headers(api_key: str) -> Dict[str, str]:
    token = base64.b64encode(api_key.encode("utf-8")).decode("utf-8")
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


def create_did_video(text: str, api_key: str, source_url: str, voice_id: str = DEFAULT_VOICE) -> str:
    payload = {
        "source_url": source_url,
        "script": {
            "type": "text",
            "input": text,
            "provider": {"type": "microsoft", "voice_id": voice_id},
        },
        "config": {"fluent": True, "pad_audio": 0.2},
    }
    r = requests.post(DID_API_URL, headers=did_headers(api_key), json=payload, timeout=30)
    if r.status_code >= 300:
        raise RuntimeError(f"D-ID error {r.status_code}: {r.text[:800]}")
    talk_id = r.json().get("id")
    if not talk_id:
        raise RuntimeError(f"D-ID no devolvió id: {r.text[:800]}")
    for _ in range(60):
        time.sleep(2)
        g = requests.get(f"{DID_API_URL}/{talk_id}", headers=did_headers(api_key), timeout=30)
        data = g.json()
        if data.get("status") == "done" and data.get("result_url"):
            return data["result_url"]
        if data.get("status") == "error":
            raise RuntimeError(f"D-ID falló: {json.dumps(data, ensure_ascii=False)[:1000]}")
    raise TimeoutError("D-ID tardó demasiado en generar el video.")


def score_answer(text: str) -> Dict:
    t = (text or "").lower()
    scores = {}
    for comp, words in COMPETENCIES.items():
        hits = sum(1 for w in words if w in t)
        detail_bonus = min(len(t.split()) / 90, 1) * 25
        scores[comp] = min(100, int(hits * 18 + detail_bonus))
    alerts = []
    for group, phrases in RED_FLAGS:
        for p in phrases:
            if p in t:
                alerts.append(f"{group}: '{p}'")
    sensitive = [x for x in SENSITIVE if x in t]
    return {"scores": scores, "alerts": alerts, "sensitive": sensitive}


def final_report(role: str, answers: List[Dict]) -> Dict:
    joined = "\n".join(a.get("answer", "") for a in answers)
    ev = score_answer(joined)
    scores = ev["scores"]
    avg = int(sum(scores.values()) / max(len(scores), 1))
    critical = any(a.startswith("Seguridad") or a.startswith("Conducta") for a in ev["alerts"])
    if critical:
        rec = "RECHAZAR PRIMERA INSTANCIA"
    elif avg >= 70:
        rec = "AVANZAR A ENTREVISTA HUMANA/TÉCNICA"
    elif avg >= 50:
        rec = "REVISIÓN HUMANA OBLIGATORIA"
    else:
        rec = "RECHAZAR PRIMERA INSTANCIA"
    strengths = [f"{k}: evidencia favorable ({v}/100)" for k, v in scores.items() if v >= 65]
    gaps = [f"{k}: evidencia insuficiente ({v}/100)" for k, v in scores.items() if v < 50]
    rationale_parts = []
    if rec.startswith("AVANZAR"):
        rationale_parts.append("El perfil presenta evidencia laboral suficiente para continuar, especialmente por el nivel de detalle y compatibilidad con los requisitos del puesto.")
    elif rec.startswith("REVISIÓN"):
        rationale_parts.append("El perfil queda en zona intermedia: hay respuestas con elementos útiles, pero no alcanza evidencia suficiente para decidir automáticamente.")
    else:
        rationale_parts.append("El perfil no reúne evidencia suficiente para avanzar o presenta alertas que requieren criterio humano antes de continuar.")
    if ev["alerts"]:
        rationale_parts.append("Alertas detectadas: " + "; ".join(ev["alerts"]))
    if ev["sensitive"]:
        rationale_parts.append("Se detectaron datos sensibles/no pertinentes que NO deben usarse para decidir: " + ", ".join(ev["sensitive"]))
    return {
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "puesto": role,
        "recomendacion": rec,
        "puntaje_global": avg,
        "puntajes": scores,
        "fortalezas": strengths or ["No se identificaron fortalezas suficientemente respaldadas."],
        "brechas": gaps or ["No se identificaron brechas críticas."],
        "alertas": ev["alerts"],
        "datos_sensibles": ev["sensitive"],
        "fundamento": " ".join(rationale_parts),
    }


def save_history(report: Dict, answers: List[Dict]):
    row = report.copy()
    row["respuestas"] = json.dumps(answers, ensure_ascii=False)
    row["puntajes"] = json.dumps(report["puntajes"], ensure_ascii=False)
    df = pd.DataFrame([row])
    if HISTORY_FILE.exists():
        old = pd.read_csv(HISTORY_FILE)
        df = pd.concat([old, df], ignore_index=True)
    df.to_csv(HISTORY_FILE, index=False)
    return df


st.set_page_config(page_title=APP_TITLE, page_icon="🏭", layout="wide")
st.title("🏭 Alba — Entrevistador virtual RRHH")
st.caption("Versión estable para Streamlit Cloud: avatar real con D-ID + respuestas por texto + informe completo. Sin WebRTC ni dependencias pesadas.")

if "answers" not in st.session_state:
    st.session_state.answers = []
if "q_index" not in st.session_state:
    st.session_state.q_index = 0
if "last_video" not in st.session_state:
    st.session_state.last_video = ""

with st.sidebar:
    st.header("Configuración")
    role = st.selectbox("Puesto", list(ROLE_QUESTIONS.keys()))
    did_key = st.text_input("D_ID_API_KEY", value=get_secret("D_ID_API_KEY"), type="password")
    did_source = st.text_input(
        "D_ID_SOURCE_URL",
        value=clean_source_url(get_secret("D_ID_SOURCE_URL", "https://i.postimg.cc/jSwybb4C/4m0Obqg3KQUKRm1IAm-Ja-Hh-PB3qsae-Ih-TWs-Sc-JW3OMD5R-tsn-TJUy-W-xu-J4W1POFJAj-PGBQyh-Ik48GC4PNg-RGD7z.jpg")),
    )
    voice = st.text_input("Voz D-ID", value=DEFAULT_VOICE)
    st.divider()
    if st.button("Reiniciar entrevista"):
        st.session_state.answers = []
        st.session_state.q_index = 0
        st.session_state.last_video = ""
        st.rerun()

questions = ROLE_QUESTIONS[role]
q_index = min(st.session_state.q_index, len(questions) - 1)
question = questions[q_index]
progress = (q_index + 1) / len(questions)
st.progress(progress)

if not did_key:
    st.warning("Falta D_ID_API_KEY. Pegala en el panel izquierdo.")
if not is_valid_image_url(did_source):
    st.warning("D_ID_SOURCE_URL debe ser una URL pública HTTPS terminada en .jpg/.jpeg/.png/.webp")

col1, col2 = st.columns([1.15, 1])
with col1:
    st.subheader("🎬 Avatar hablando")
    if st.button("Generar / reproducir pregunta con Alba", use_container_width=True, type="primary"):
        if not did_key or not is_valid_image_url(did_source):
            st.error("Configurá D_ID_API_KEY y D_ID_SOURCE_URL correctamente.")
        else:
            with st.spinner("Alba está generando el video hablado..."):
                try:
                    st.session_state.last_video = create_did_video(question, did_key, did_source, voice)
                except Exception as e:
                    st.error(str(e))
    if st.session_state.last_video:
        st.video(st.session_state.last_video)
    else:
        st.image(did_source, caption="Imagen base del avatar. Al generar, se verá hablando.", use_container_width=True)

with col2:
    st.subheader("💬 Conversación")
    for item in st.session_state.answers:
        st.markdown(f"**Alba:** {item['question']}")
        st.info(f"**Candidato:** {item['answer']}")
    st.markdown(f"**Alba — Pregunta {q_index + 1} de {len(questions)}:**")
    st.info(question)

st.divider()
st.subheader("✍️ Respuesta del candidato")
st.caption("Para evitar errores de instalación en Streamlit Cloud, esta versión estable usa respuesta escrita. La videollamada completa requiere una app React/Next.js o una integración WebRTC dedicada.")
answer = st.text_area("Escribir respuesta", height=140, placeholder="Escribí acá la respuesta del candidato...")

c1, c2, c3 = st.columns(3)
with c1:
    if st.button("Guardar y avanzar", type="primary", use_container_width=True):
        if not answer.strip():
            st.error("Primero cargá una respuesta.")
        else:
            st.session_state.answers.append({"question": question, "answer": answer.strip()})
            st.session_state.q_index = min(st.session_state.q_index + 1, len(questions))
            st.session_state.last_video = ""
            st.rerun()
with c2:
    if st.button("Volver pregunta anterior", use_container_width=True):
        if st.session_state.q_index > 0:
            st.session_state.q_index -= 1
            st.session_state.last_video = ""
            st.rerun()
with c3:
    finish = st.button("Finalizar y generar informe", use_container_width=True)

if finish or st.session_state.q_index >= len(questions):
    if not st.session_state.answers:
        st.error("No hay respuestas para evaluar.")
    else:
        report = final_report(role, st.session_state.answers)
        st.divider()
        st.subheader("📋 Informe final de Alba")
        st.metric("Recomendación", report["recomendacion"])
        st.metric("Puntaje global", f"{report['puntaje_global']}/100")
        st.markdown("### Fundamento")
        st.write(report["fundamento"])
        left, right = st.columns(2)
        with left:
            st.markdown("### Fortalezas")
            for x in report["fortalezas"]:
                st.write("- " + x)
        with right:
            st.markdown("### Brechas / riesgos")
            for x in report["brechas"]:
                st.write("- " + x)
            for x in report["alertas"]:
                st.error(x)
        st.markdown("### Puntaje por competencia")
        st.dataframe(pd.DataFrame([{"Competencia": k, "Puntaje": v} for k, v in report["puntajes"].items()]), hide_index=True, use_container_width=True)
        if st.button("Guardar informe en historial"):
            hist = save_history(report, st.session_state.answers)
            st.success(f"Informe guardado. Total registros: {len(hist)}")
        st.download_button("Descargar informe JSON", json.dumps(report, ensure_ascii=False, indent=2), file_name="informe_alba.json", mime="application/json")
