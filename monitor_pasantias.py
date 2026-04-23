"""
Monitor de Pasantías - UTN FRC
================================
Revisa la página de pasantías rentadas de la SEU UTN-FRC
y te manda un email cuando aparece una nueva.

Configuración: editá las variables de la sección CONFIG más abajo.
"""

import requests
from bs4 import BeautifulSoup
import smtplib
import json
import os
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# ─────────────────────────────────────────────
#  CONFIG — editá estos valores antes de correr
# ─────────────────────────────────────────────
GMAIL_USER     = os.getenv("GMAIL_USER")
GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD")
DESTINATARIO   = os.getenv("DESTINATARIO")

URL_PASANTIAS  = "https://seu.frc.utn.edu.ar/?pIs=1286"
ARCHIVO_ESTADO = "pasantias_vistas.json"    # Guarda las pasantías ya conocidas

# ─────────────────────────────────────────────

def extraer_campo(bloque, *nombres):
    """Busca un campo por nombre dentro de un bloque de texto."""
    for nombre in nombres:
        patron = rf"{re.escape(nombre)}\s*[:\-]?\s*(.+?)(?=\n[A-ZÁÉÍÓÚÑ ]+\s*:|$)"
        match = re.search(patron, bloque, re.IGNORECASE | re.DOTALL)
        if match:
            valor = match.group(1).strip()
            valor = re.sub(r"\s+", " ", valor)
            return valor[:300]
    return ""
 
 
def obtener_pasantias():
    """Descarga la página y extrae los datos completos de cada pasantía."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        resp = requests.get(URL_PASANTIAS, headers=headers, timeout=15)
        resp.encoding = "ISO-8859-1"
    except Exception as e:
        print(f"[ERROR] No se pudo acceder a la página: {e}")
        return []
 
    soup = BeautifulSoup(resp.text, "html.parser")
    texto = soup.get_text("\n")
 
    patron_arm = r"(A\.R\.M\.\s*\d+/\d+)"
    partes = re.split(patron_arm, texto)
 
    pasantias = []
    for i in range(1, len(partes) - 1, 2):
        codigo = re.sub(r"\s+", " ", partes[i]).strip()
        bloque = partes[i + 1] if i + 1 < len(partes) else ""
 
        empresa      = extraer_campo(bloque, "NOMBRE DE LA EMPRESA/ORGANISMO", "NOMBRE DE LA EMPRESA")
        ciudad       = extraer_campo(bloque, "CIUDAD")
        carrera      = extraer_campo(bloque, "ESTUDIANTE DE LA CARRERA", "SOLICITA")
        conocimient  = extraer_campo(bloque, "CONOCIMIENTOS")
        requisitos   = extraer_campo(bloque, "OTROS REQUISITOS")
        asignacion   = extraer_campo(bloque, "ASIGNACIÓN ESTÍMULO", "ASIGNACION ESTIMULO")
        horario      = extraer_campo(bloque, "HORARIO DE TRABAJO")
        puesto       = extraer_campo(bloque, "PUESTO/ÁREA A CUBRIR", "PUESTO/AREA A CUBRIR", "CARGO A CUBRIR")
        lugar        = extraer_campo(bloque, "LUGAR DE TRABAJO")
        modalidad    = extraer_campo(bloque, "MODALIDAD")
        beneficios   = extraer_campo(bloque, "BENEFICIOS")
        duracion     = extraer_campo(bloque, "DURACIÓN", "DURACION")
 
        email_match  = re.search(r"Enviar CV a:\s*([\w._%+\-]+@[\w.\-]+\.\w+)", bloque, re.IGNORECASE)
        email_cv     = email_match.group(1) if email_match else ""
 
        pasantias.append({
            "codigo": codigo, "empresa": empresa, "ciudad": ciudad,
            "carrera": carrera, "conocimientos": conocimient,
            "requisitos": requisitos, "asignacion": asignacion,
            "horario": horario, "puesto": puesto, "lugar": lugar,
            "modalidad": modalidad, "beneficios": beneficios,
            "duracion": duracion, "email_cv": email_cv,
        })
 
    return pasantias
 
 
def cargar_estado():
    if os.path.exists(ARCHIVO_ESTADO):
        with open(ARCHIVO_ESTADO, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()
 
 
def guardar_estado(codigos):
    with open(ARCHIVO_ESTADO, "w", encoding="utf-8") as f:
        json.dump(list(codigos), f, ensure_ascii=False, indent=2)
 
 
def fila_dato(icono, etiqueta, valor):
    if not valor:
        return ""
    return f"""
    <tr>
      <td style="padding:5px 10px; color:#555; font-size:13px; white-space:nowrap; vertical-align:top;">
        {icono} <strong>{etiqueta}</strong>
      </td>
      <td style="padding:5px 10px; font-size:13px; color:#222;">{valor}</td>
    </tr>"""
 
 
def card_pasantia(p):
    filas = (
        fila_dato("🎓", "Carrera",       p["carrera"])       +
        fila_dato("💼", "Puesto",        p["puesto"])        +
        fila_dato("📍", "Ciudad",        p["ciudad"])        +
        fila_dato("🏠", "Modalidad",     p["modalidad"])     +
        fila_dato("📌", "Lugar",         p["lugar"])         +
        fila_dato("🕐", "Horario",       p["horario"])       +
        fila_dato("📅", "Duración",      p["duracion"])      +
        fila_dato("💰", "Asignación",    p["asignacion"])    +
        fila_dato("🧠", "Conocimientos", p["conocimientos"]) +
        fila_dato("✅", "Requisitos",    p["requisitos"])    +
        fila_dato("🎁", "Beneficios",    p["beneficios"])
    )
 
    contacto = ""
    if p["email_cv"]:
        contacto = f"""
        <div style="margin-top:12px;">
          <a href="mailto:{p['email_cv']}"
             style="background:#1a73e8; color:white; padding:8px 18px;
                    text-decoration:none; border-radius:4px; font-size:13px; display:inline-block;">
            📧 Enviar CV — {p['email_cv']}
          </a>
        </div>"""
 
    return f"""
    <div style="border:1px solid #ddd; border-radius:8px; padding:18px 20px;
                margin-bottom:20px; background:#fff; box-shadow:0 1px 4px rgba(0,0,0,0.07);">
      <div style="font-size:11px; color:#1a73e8; font-weight:bold; letter-spacing:1px; margin-bottom:4px;">
        {p['codigo']}
      </div>
      <div style="font-size:18px; font-weight:bold; color:#111; margin-bottom:14px;">
        {p['empresa'] or 'Nueva pasantía'}
        {(' <span style="font-size:14px; font-weight:normal; color:#666;">· ' + p['ciudad'] + '</span>') if p['ciudad'] else ''}
      </div>
      <table style="width:100%; border-collapse:collapse;">
        {filas}
      </table>
      {contacto}
    </div>"""
 
 
def enviar_email(nuevas):
    cantidad = len(nuevas)
    asunto = f"🎓 {cantidad} pasantía{'s' if cantidad > 1 else ''} nueva{'s' if cantidad > 1 else ''} — UTN FRC"
 
    cards = "".join(card_pasantia(p) for p in nuevas)
 
    cuerpo_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333; background:#f0f2f5; padding:20px; margin:0;">
      <div style="max-width:640px; margin:0 auto;">
 
        <div style="background:#1a73e8; color:white; padding:22px 26px; border-radius:8px 8px 0 0;">
          <h2 style="margin:0; font-size:20px;">📋 Nuevas Pasantías — UTN FRC</h2>
          <p style="margin:6px 0 0; opacity:0.85; font-size:13px;">
            {cantidad} nueva{'s' if cantidad > 1 else ''} detectada{'s' if cantidad > 1 else ''} · {datetime.now().strftime('%d/%m/%Y a las %H:%M')}
          </p>
        </div>
 
        <div style="padding:20px 0;">
          {cards}
        </div>
 
        <div style="text-align:center; padding-bottom:24px;">
          <a href="{URL_PASANTIAS}"
             style="background:#1a73e8; color:white; padding:11px 26px;
                    text-decoration:none; border-radius:5px; font-size:14px; display:inline-block;">
            Ver todas las pasantías →
          </a>
        </div>
 
        <p style="color:#aaa; font-size:11px; text-align:center;">
          Monitor automático de pasantías UTN FRC
        </p>
      </div>
    </body>
    </html>
    """
 
    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"]    = GMAIL_USER
    msg["To"]      = DESTINATARIO
    msg.attach(MIMEText(cuerpo_html, "html"))
 
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.sendmail(GMAIL_USER, DESTINATARIO, msg.as_string())
        print(f"[OK] Email enviado a {DESTINATARIO}")
    except Exception as e:
        print(f"[ERROR] No se pudo enviar el email: {e}")
        raise
 
 
def main():
    print(f"[{datetime.now().strftime('%d/%m/%Y %H:%M')}] Revisando pasantías UTN FRC...")
 
    pasantias_actuales = obtener_pasantias()
    if not pasantias_actuales:
        print("[AVISO] No se encontraron pasantías (posible error de red o cambio en la web).")
        return
 
    codigos_actuales = {p["codigo"] for p in pasantias_actuales}
    codigos_vistos   = cargar_estado()
 
    if not codigos_vistos:
        guardar_estado(codigos_actuales)
        print(f"[INICIO] Primera ejecución. Se guardaron {len(codigos_actuales)} pasantías como base.")
        print("Códigos encontrados:", sorted(codigos_actuales))
        return
 
    nuevos_codigos = codigos_actuales - codigos_vistos
    if nuevos_codigos:
        nuevas = [p for p in pasantias_actuales if p["codigo"] in nuevos_codigos]
        print(f"[NUEVO] Se encontraron {len(nuevas)} pasantía(s) nueva(s): {nuevos_codigos}")
        enviar_email(nuevas)
    else:
        print(f"[SIN CAMBIOS] {len(codigos_actuales)} pasantías, ninguna nueva.")
 
    guardar_estado(codigos_actuales)
 
 
if __name__ == "__main__":
    main()