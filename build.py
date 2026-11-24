#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build.py — Genera generador_cpe_zte.html a partir de:
  - plantillas/*.txt   (fuente de verdad de los comandos)
  - motor.js           (lógica pura, sin DOM)
  - prueba/entrada_SanMiguel.json (botón "Cargar ejemplo")

El HTML resultante es autónomo: todo el CSS y el JavaScript van embebidos.
No usa CDN, fuentes externas, fetch() ni frameworks.

Uso:
    python build.py

Para cambiar un comando: editar la plantilla y volver a ejecutar este script.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
DIR_PLANTILLAS = RAIZ / "plantillas"
ARCHIVO_MOTOR = RAIZ / "motor.js"
ARCHIVO_EJEMPLO = RAIZ / "prueba" / "entrada_SanMiguel.json"
ARCHIVO_SALIDA = RAIZ / "generador_cpe_zte.html"

# Perfil activo. Hoy solo existe ZTE / HA / fibra. La estructura queda
# preparada para elegir otros conjuntos de plantillas en el futuro.
PERFIL = {
    "marca": "ZTE",
    "topologia": "HA",
    "enlace": "fibra",
    "region": "Perú",
}

# Metadatos de las 4 LANs. Se usan para generar el formulario y los valores
# por defecto (los del Excel de SanMiguel).
LANS = [
    {
        "n": 1,
        "titulo": "LAN CAC",
        "vlan": "10",
        "nombre": "LAN_CAC",
        "gw": "172.22.46.254",
        "prefijo": "24",
        "mascara": "255.255.255.0",
        "off_prin": "-2",
        "off_sec": "-1",
        "nota": "",
    },
    {
        "n": 2,
        "titulo": "WFClaro",
        "vlan": "1020",
        "nombre": "LAN_WFCLARO",
        "gw": "172.26.64.129",
        "prefijo": "25",
        "mascara": "255.255.255.128",
        "off_prin": "1",
        "off_sec": "2",
        "nota": "",
    },
    {
        "n": 3,
        "titulo": "WFCitrix",
        "vlan": "1021",
        "nombre": "LAN_WFCITRIX",
        "gw": "172.26.96.33",
        "prefijo": "27",
        "mascara": "255.255.255.224",
        "off_prin": "1",
        "off_sec": "2",
        "nota": "",
    },
    {
        "n": 4,
        "titulo": "WFGestión/APs",
        "vlan": "1023",
        "nombre": "LAN_WFGESTION",
        "gw": "172.22.103.17",
        "prefijo": "28",
        "mascara": "255.255.255.240",
        "off_prin": "2",
        "off_sec": "3",
        "nota": "LAN4 usa +2/+3 en el Excel original; confirmar convención.",
    },
]


def leer_texto(ruta: Path) -> str:
    """Lee UTF-8 y normaliza a saltos de línea LF (sin BOM)."""
    with open(ruta, "r", encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n").replace("\r", "\n")


def cargar_plantillas() -> dict[str, str]:
    """Carga todas las plantillas .txt usando el nombre sin extensión como clave."""
    plantillas: dict[str, str] = {}
    for ruta in sorted(DIR_PLANTILLAS.glob("*.txt")):
        plantillas[ruta.stem] = leer_texto(ruta)
    if not plantillas:
        raise SystemExit("No se encontraron plantillas en " + str(DIR_PLANTILLAS))
    return plantillas


def json_para_script(obj: object) -> str:
    """JSON compacto y seguro para incrustar dentro de <script>."""
    texto = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    # Evita cerrar el <script> si algún texto contuviera "</".
    texto = texto.replace("</", "<\\/")
    # Separa los caracteres que algunos motores tratan como fin de línea.
    texto = texto.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return texto


def tarjeta_lan(lan: dict[str, str | int]) -> str:
    """HTML de una tarjeta LAN del formulario."""
    n = lan["n"]
    nota = ""
    if lan["nota"]:
        nota = '<div class="nota">' + str(lan["nota"]) + "</div>"
    return f"""
      <fieldset class="lan" data-tarjeta-lan="{n}">
        <legend>LAN{n} · {lan['titulo']}</legend>
        <label class="check-lan" for="LAN{n}_INCLUDE">
          <input type="checkbox" id="LAN{n}_INCLUDE" data-var="LAN{n}_INCLUDE" checked>
          Incluir LAN{n} en el script
        </label>
        <div class="campos" data-campos-lan="{n}">
          <div class="campo">
            <label for="VLAN_LAN{n}">VLAN_LAN{n}</label>
            <input id="VLAN_LAN{n}" data-var="VLAN_LAN{n}" type="number" min="1" max="4094" step="1" placeholder="{lan['vlan']}">
          </div>
          <div class="campo">
            <label for="NAME_LAN{n}">NAME_LAN{n}</label>
            <input id="NAME_LAN{n}" data-var="NAME_LAN{n}" type="text" placeholder="{lan['nombre']}" autocomplete="off">
          </div>
          <div class="campo">
            <label for="LAN{n}_GW">LAN{n}_GW (VIP VRRP)</label>
            <input id="LAN{n}_GW" data-var="LAN{n}_GW" type="text" inputmode="decimal" placeholder="{lan['gw']}" autocomplete="off">
          </div>
          <div class="campo">
            <label for="LAN{n}_MASK">LAN{n}_MASK</label>
            <input id="LAN{n}_MASK" data-var="LAN{n}_MASK" type="text"
                   placeholder="{lan['prefijo']} · /{lan['prefijo']} · {lan['mascara']}" autocomplete="off">
            <small class="ayuda-msg" data-mascara-msg="{n}">= {lan['mascara']}</small>
          </div>
          <div class="campo">
            <label for="LAN{n}_OFF_PRIN">LAN{n}_OFF_PRIN</label>
            <input id="LAN{n}_OFF_PRIN" data-var="LAN{n}_OFF_PRIN" type="number" step="1" placeholder="{lan['off_prin']}">
          </div>
          <div class="campo">
            <label for="LAN{n}_OFF_SEC">LAN{n}_OFF_SEC</label>
            <input id="LAN{n}_OFF_SEC" data-var="LAN{n}_OFF_SEC" type="number" step="1" placeholder="{lan['off_sec']}">
          </div>
        </div>
        <small class="ayuda-msg excluida" data-excluida="{n}">Esta LAN está excluida del script.</small>
        {nota}
      </fieldset>"""


def valores_por_defecto() -> dict[str, str]:
    """Valores iniciales del formulario (los del Excel, sin datos del CAC)."""
    valores = {}
    for lan in LANS:
        n = lan["n"]
        valores[f"VLAN_LAN{n}"] = str(lan["vlan"])
        valores[f"NAME_LAN{n}"] = str(lan["nombre"])
        valores[f"LAN{n}_GW"] = str(lan["gw"])
        valores[f"LAN{n}_MASK"] = str(lan["prefijo"])
        valores[f"LAN{n}_OFF_PRIN"] = str(lan["off_prin"])
        valores[f"LAN{n}_OFF_SEC"] = str(lan["off_sec"])
    return valores


CSS = r"""
:root{
  --fondo:#f1f5f9; --panel:#ffffff; --texto:#0f172a; --suave:#64748b;
  --borde:#cbd5e1; --azul:#1d4ed8; --azul-claro:#dbeafe;
  --verde:#15803d; --ambar:#b45309; --rojo:#b91c1c;
  --mono:Consolas,"Courier New",monospace;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{
  font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  background:var(--fondo);color:var(--texto);font-size:14px;line-height:1.45;
}
h1{font-size:19px;margin:0}
h2{font-size:15px;margin:0 0 6px}
.cabecera{
  display:flex;justify-content:space-between;align-items:flex-start;gap:12px;
  flex-wrap:wrap;padding:14px 18px;background:#0f172a;color:#e2e8f0;
}
.cabecera .sub{margin:2px 0 0;color:#94a3b8;font-size:12px}
.badge{font-size:11px;background:#1d4ed8;color:#fff;border-radius:999px;padding:2px 8px;vertical-align:middle}
.acciones{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
button{
  cursor:pointer;border:1px solid var(--borde);background:#fff;color:var(--texto);
  border-radius:6px;padding:6px 10px;font:inherit;
}
button:hover{background:#f8fafc}
button.primario{background:var(--azul);border-color:var(--azul);color:#fff}
button.primario:hover{background:#1e40af}
button.sec{background:#1e293b;border-color:#334155;color:#e2e8f0}
button.sec:hover{background:#334155}
button:disabled{opacity:.55;cursor:not-allowed}
.layout{
  display:grid;grid-template-columns:minmax(340px,430px) minmax(0,1fr);
  gap:16px;padding:16px;max-width:1800px;margin:0 auto;align-items:start;
}
.panel{background:var(--panel);border:1px solid var(--borde);border-radius:10px}
#formulario{padding:14px;max-height:calc(100vh - 110px);overflow:auto;position:sticky;top:12px}
fieldset{border:1px solid var(--borde);border-radius:8px;margin:0 0 12px;padding:10px 12px}
legend{font-weight:600;padding:0 6px}
.campos{display:grid;grid-template-columns:1fr 1fr;gap:8px 10px}
.campo{display:flex;flex-direction:column;gap:3px;min-width:0}
.campo.ancho{grid-column:1/-1}
label{font-size:12px;color:var(--suave);font-weight:600}
input[type=text],input[type=number]{
  width:100%;padding:6px 8px;border:1px solid var(--borde);border-radius:6px;
  font:inherit;background:#fff;color:var(--texto);
}
input:focus{outline:2px solid var(--azul-claro);border-color:var(--azul)}
.check{display:flex;align-items:center;gap:8px;font-weight:600;color:var(--texto);margin:2px 0 8px}
.check input{width:auto}
.check-lan{display:flex;align-items:center;gap:8px;font-weight:700;color:var(--texto);margin:0 0 8px}
.check-lan input{width:auto}
.lan.excluida{opacity:.62;background:#f8fafc}
.lan .excluida{display:none;color:var(--ambar)}
.lan.excluida .excluida{display:block}
textarea{
  width:100%;padding:8px;border:1px solid var(--borde);border-radius:6px;
  font-family:var(--mono);font-size:12px;background:#fff;color:var(--texto);resize:vertical;
}
.tabla-scroll{overflow-x:auto;margin-top:8px}
.tabla-scroll .tabla{min-width:980px}
.acciones-linea{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}
.nota{
  background:#eff6ff;border-left:4px solid var(--azul);padding:6px 10px;
  border-radius:4px;font-size:12px;margin:6px 0;
}
.ayuda-linea{display:flex;gap:6px;margin-top:8px}
.ayuda-linea input{flex:1;min-width:0}
.ayuda-msg{font-size:11px;color:var(--suave);display:block;margin-top:4px}
.ayuda-msg.ok{color:var(--verde)}
.ayuda-msg.mal{color:var(--rojo)}
.ayuda-msg.aviso{color:var(--ambar)}
details.avanzado{margin-top:4px}
details.avanzado summary{cursor:pointer;font-weight:600;padding:4px 0}
.globales{display:grid;grid-template-columns:1fr 1fr;gap:6px 12px;font-size:12px;color:var(--suave)}
.globales strong{color:var(--texto)}
#resultados{padding:12px;min-width:0;display:flex;flex-direction:column;gap:10px}
.barra-resultados{display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap}
.pestanas{display:flex;gap:4px;flex-wrap:wrap}
.pestana{border-radius:6px;padding:5px 10px;font-size:13px}
.pestana.activa{background:var(--azul);border-color:var(--azul);color:#fff}
.estado{font-size:12px;color:var(--suave)}
.estado.ok{color:var(--verde)}
.estado.mal{color:var(--rojo)}
#avisos{display:flex;flex-direction:column;gap:4px}
.aviso{padding:6px 10px;border-radius:6px;border-left:4px solid;font-size:12px}
.aviso.error{background:#fef2f2;border-color:var(--rojo)}
.aviso.aviso{background:#fffbeb;border-color:var(--ambar)}
.aviso.ok{background:#f0fdf4;border-color:var(--verde)}
.barra-tab{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:4px 0 8px}
.barra-tab .ayuda-msg{margin:0}
.bloque{border:1px solid var(--borde);border-radius:8px;margin:10px 0;overflow:hidden}
.bloque.con-error .bloque-cab{background:#fef2f2}
.bloque-cab{
  display:flex;justify-content:space-between;gap:8px;align-items:center;
  padding:8px 10px;background:#f8fafc;border-bottom:1px solid var(--borde);flex-wrap:wrap;
}
.bloque-cab .meta{color:var(--suave);font-size:12px;font-weight:400}
.botones{display:flex;gap:6px;flex-wrap:wrap}
.botones button{font-size:12px;padding:4px 8px}
pre.salida{
  margin:0;padding:10px;max-height:360px;overflow:auto;background:#0f172a;color:#e2e8f0;
  font-family:var(--mono);font-size:12px;line-height:1.35;white-space:pre;tab-size:2;
}
mark.faltante{background:#dc2626;color:#fff;padding:0 2px;border-radius:2px}
.tabla{width:100%;border-collapse:collapse;font-size:12px;margin-top:6px}
.tabla th,.tabla td{border:1px solid var(--borde);padding:4px 8px;text-align:left;vertical-align:top}
.tabla th{background:#f1f5f9}
.tabla tbody tr:nth-child(even){background:#f8fafc}
.tabla tr.fila-mal td{background:#fef2f2}
.tabla tr.grupo td{background:#e2e8f0;font-weight:600}
.tabla td.valor{font-family:var(--mono)}
.oculto{display:none!important}
@media (max-width:1050px){
  .layout{grid-template-columns:1fr}
  #formulario{position:static;max-height:none}
}
@media (max-width:560px){
  .campos{grid-template-columns:1fr}
  .globales{grid-template-columns:1fr}
}
"""


HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Generador CPE ZTE · HA + fibra</title>
<style>
@@CSS@@
</style>
</head>
<body>
<header class="cabecera">
  <div>
    <h1>Generador CPE ZTE <span class="badge">HA · fibra</span></h1>
    <p class="sub" id="perfil">Perfil ZTE / HA / fibra · funciona sin conexión · sin dependencias</p>
  </div>
  <div class="acciones">
    <button type="button" id="btn-generar" class="primario">Generar</button>
    <button type="button" id="btn-ejemplo" class="sec">Cargar ejemplo SanMiguel</button>
    <button type="button" id="btn-limpiar" class="sec">Limpiar</button>
    <button type="button" id="btn-guardar" class="sec">Guardar datos (JSON)</button>
    <button type="button" id="btn-cargar" class="sec">Cargar datos (JSON)</button>
    <input type="file" id="archivo-json" accept=".json,application/json" hidden>
  </div>
</header>

<main class="layout">
  <section class="panel" id="formulario">
    <fieldset>
      <legend>General</legend>
      <div class="campos">
        <div class="campo">
          <label for="CAC">CAC</label>
          <input id="CAC" data-var="CAC" type="text" placeholder="SanMiguel" autocomplete="off">
        </div>
        <div class="campo">
          <label for="CID_PRIN">CID_PRIN</label>
          <input id="CID_PRIN" data-var="CID_PRIN" type="text" inputmode="numeric" placeholder="27034814" autocomplete="off">
        </div>
        <div class="campo">
          <label for="CID_SEC">CID_SEC</label>
          <input id="CID_SEC" data-var="CID_SEC" type="text" inputmode="numeric" placeholder="27034827" autocomplete="off">
        </div>
        <div class="campo">
          <label for="BW_MB">BW_MB (Mbps)</label>
          <input id="BW_MB" data-var="BW_MB" type="number" min="1" step="1" placeholder="350">
        </div>
      </div>
      <div class="nota">La descripción WAN usa BW_MB automáticamente: <code>RPVFM &lt;BW_MB&gt; Mbps</code>.</div>
    </fieldset>

    <fieldset>
      <legend>WAN Principal</legend>
      <div class="campos">
        <div class="campo">
          <label for="WAN_IP_PRIN">WAN_IP_PRIN</label>
          <input id="WAN_IP_PRIN" data-var="WAN_IP_PRIN" type="text" inputmode="decimal" placeholder="172.19.246.34" autocomplete="off">
        </div>
        <div class="campo">
          <label for="LOOPBACK_PRIN">LOOPBACK_PRIN</label>
          <input id="LOOPBACK_PRIN" data-var="LOOPBACK_PRIN" type="text" inputmode="decimal" placeholder="10.249.132.130" autocomplete="off">
        </div>
        <div class="campo">
          <label for="VLAN_WAN_PRIN">VLAN_WAN_PRIN</label>
          <input id="VLAN_WAN_PRIN" data-var="VLAN_WAN_PRIN" type="number" min="1" max="4094" step="1" placeholder="850">
        </div>
      </div>
      <div class="nota">La IP del CPE se calcula como red+2 del bloque /30, sin importar qué IP del bloque se ingrese.</div>
    </fieldset>

    <fieldset>
      <legend>WAN Contingencia</legend>
      <div class="campos">
        <div class="campo">
          <label for="WAN_IP_SEC">WAN_IP_SEC</label>
          <input id="WAN_IP_SEC" data-var="WAN_IP_SEC" type="text" inputmode="decimal" placeholder="10.31.220.20" autocomplete="off">
        </div>
        <div class="campo">
          <label for="LOOPBACK_SEC">LOOPBACK_SEC</label>
          <input id="LOOPBACK_SEC" data-var="LOOPBACK_SEC" type="text" inputmode="decimal" placeholder="10.249.132.131" autocomplete="off">
        </div>
        <div class="campo">
          <label for="VLAN_WAN_SEC">VLAN_WAN_SEC</label>
          <input id="VLAN_WAN_SEC" data-var="VLAN_WAN_SEC" type="number" min="1" max="4094" step="1" placeholder="850">
        </div>
      </div>
    </fieldset>

    <fieldset>
      <legend>LANs</legend>
@@LAN_CARDS@@
    </fieldset>

    <fieldset id="autocompletar-lans">
      <legend>Autocompletar LANs desde interfaces (opcional)</legend>
      <div class="nota">Pega las líneas de <code>display ip interface brief</code> del Huawei. Acepta IP/prefijo o IP + máscara (por ejemplo 255.255.255.0). La IP pegada se toma como VIP VRRP; la VLAN sale de <code>VlanifN</code>, <code>VlanN</code> o del subinterface <code>.N</code>.</div>
      <textarea id="pegar-interfaces" rows="6" spellcheck="false"
        placeholder="vlan10     172.22.86.252   255.255.255.0    up up up&#10;vlan1020   172.26.65.194   255.255.255.192  up up up&#10;vlan1021   172.26.96.162   255.255.255.224  up up up&#10;vlan1023   172.22.103.83   255.255.255.240  up up up"></textarea>
      <div class="acciones-linea">
        <button type="button" id="btn-analizar-interfaces" class="sec">Analizar</button>
        <button type="button" id="btn-aplicar-interfaces" class="primario" disabled>Aplicar a LANs</button>
        <button type="button" id="btn-limpiar-interfaces" class="sec">Limpiar</button>
      </div>
      <small id="mensaje-interfaces" class="ayuda-msg">Opcional: analiza antes de aplicar.</small>
      <div id="preview-interfaces" class="tabla-scroll oculto"></div>
    </fieldset>

    <fieldset>
      <legend>Switch Juniper (opcional)</legend>
      <label class="check" for="incluir_switch">
        <input type="checkbox" id="incluir_switch" data-var="incluir_switch">
        Incluir switch Juniper
      </label>
      <div class="campos">
        <div class="campo">
          <label for="SW_NAME">SW_NAME</label>
          <input id="SW_NAME" data-var="SW_NAME" type="text" placeholder="SW_CAC_SAN_MIGUEL_VC1_2_3" autocomplete="off" disabled>
        </div>
        <div class="campo">
          <label for="SW_IP">SW_IP</label>
          <input id="SW_IP" data-var="SW_IP" type="text" inputmode="decimal" placeholder="172.22.46.5" autocomplete="off" disabled>
        </div>
      </div>
      <small class="ayuda-msg">El nombre y la IP se agregan solo como encabezado/comentario del script.</small>
    </fieldset>

    <details class="avanzado">
      <summary>Parámetros globales avanzados (solo informativo)</summary>
      <div class="globales">
        <div><strong>AS</strong><br>64516 (iBGP) · 12252 (eBGP)</div>
        <div><strong>Comunidades</strong><br>12252:200 · 12252:201</div>
        <div><strong>NTP</strong><br>172.19.72.24 · 172.19.72.25 · 172.19.112.157 · 172.19.112.158</div>
        <div><strong>TACACS+</strong><br>172.19.216.49 · 172.19.216.44</div>
        <div><strong>SNMP</strong><br>comunidad netadmro · hosts 172.19.216.x / 10.95.x</div>
        <div><strong>Syslog</strong><br>172.19.216.51</div>
        <div><strong>Claves</strong><br>definidas dentro de las plantillas (TACACS, usuarios, BGP, switch)</div>
        <div><strong>Región</strong><br>Perú (futuro: objeto GLOBALES[region])</div>
      </div>
      <p class="ayuda-msg">No editable por ahora. En el futuro estos valores se separarán en GLOBALES[region].</p>
    </details>
  </section>

  <section class="panel" id="resultados">
    <div class="barra-resultados">
      <div class="pestanas" role="tablist">
        <button type="button" class="pestana activa" data-tab="principal" role="tab">Principal</button>
        <button type="button" class="pestana" data-tab="contingencia" role="tab">Contingencia</button>
        <button type="button" class="pestana" data-tab="switch" role="tab">Switch</button>
        <button type="button" class="pestana" data-tab="derivadas" role="tab">Valores derivados</button>
      </div>
      <div id="estado" class="estado">Listo.</div>
    </div>

    <div id="avisos"></div>

    <div id="panel-principal" class="panel-tab">
      <div class="barra-tab">
        <button type="button" class="primario" data-copiar-todo="principal">Copiar todo el router (1+2+3)</button>
        <button type="button" class="sec" data-descargar-todo="principal">Descargar Principal completo (.txt)</button>
        <span class="ayuda-msg">El archivo completo incluye 1+2+3+4.</span>
      </div>
      <div data-bloques="principal"></div>
    </div>

    <div id="panel-contingencia" class="panel-tab oculto">
      <div class="barra-tab">
        <button type="button" class="primario" data-copiar-todo="contingencia">Copiar todo el router (1+2+3)</button>
        <button type="button" class="sec" data-descargar-todo="contingencia">Descargar Contingencia completo (.txt)</button>
        <span class="ayuda-msg">El archivo completo incluye 1+2+3+4.</span>
      </div>
      <div data-bloques="contingencia"></div>
    </div>

    <div id="panel-switch" class="panel-tab oculto">
      <div class="barra-tab">
        <button type="button" class="primario" data-descargar-todo="switch" disabled>Descargar switch completo (.txt)</button>
        <span class="ayuda-msg">Un solo archivo con el script del switch.</span>
      </div>
      <div id="switch-vacio" class="nota">Marca "Incluir switch Juniper" para generar este script.</div>
      <article class="bloque oculto" id="bloque-switch">
        <div class="bloque-cab">
          <div><strong>Switch Juniper</strong> <span class="meta" data-meta="switch">—</span></div>
          <div class="botones">
            <button type="button" data-copiar="switch">Copiar</button>
            <button type="button" data-descargar="switch">Descargar .txt</button>
          </div>
        </div>
        <pre class="salida" data-salida="switch"></pre>
      </article>
    </div>

    <div id="panel-derivadas" class="panel-tab oculto">
      <div class="nota">Tabla de solo lectura. Verifica estos valores antes de copiar los scripts.</div>
      <table class="tabla">
        <thead><tr><th>Valor</th><th>Resultado</th></tr></thead>
        <tbody id="tabla-derivadas"></tbody>
      </table>
    </div>
  </section>
</main>

<script>
const PLANTILLAS = @@PLANTILLAS@@;
const EJEMPLO = @@EJEMPLO@@;
const PERFIL_ACTIVO = @@PERFIL@@;
const DEFAULTS = @@DEFAULTS@@;
</script>
<script>
@@MOTOR@@
</script>
<script>
@@UI@@
</script>
</body>
</html>
"""


UI_JS = r"""
(function () {
  'use strict';

  var CLAVE_LS = 'generador_cpe_zte_v2';
  var ULTIMO = null;
  var FILAS_INTERFACES = [];

  // Filas de la tabla de valores derivados. "grupo" crea una fila de título.
  var FILAS_DERIVADAS = [
    { grupo: 'WAN Principal' },
    { clave: 'WAN_NET_PRIN', etiqueta: 'Red /30' },
    { clave: 'WAN_PE_PRIN', etiqueta: 'IP del PE' },
    { clave: 'WAN_CPE_PRIN', etiqueta: 'IP del CPE' },
    { grupo: 'WAN Contingencia' },
    { clave: 'WAN_NET_SEC', etiqueta: 'Red /30' },
    { clave: 'WAN_PE_SEC', etiqueta: 'IP del PE' },
    { clave: 'WAN_CPE_SEC', etiqueta: 'IP del CPE' },
    { grupo: 'Ancho de banda' },
    { clave: 'BW_KBPS', etiqueta: 'BW_KBPS' },
    { clave: 'SHAPE_BPS', etiqueta: 'SHAPE_BPS' },
    { clave: 'CBS_KB', etiqueta: 'CBS_KB' },
    { grupo: 'LAN1' },
    { clave: 'LAN1_VIP', etiqueta: 'VIP VRRP' },
    { clave: 'LAN1_NET', etiqueta: 'Red' },
    { clave: 'LAN1_PREFIX', etiqueta: 'Prefijo' },
    { clave: 'LAN1_MASK', etiqueta: 'Máscara' },
    { clave: 'LAN1_WILDCARD', etiqueta: 'Wildcard' },
    { clave: 'LAN1_IP_PRIN', etiqueta: 'IP Principal' },
    { clave: 'LAN1_IP_SEC', etiqueta: 'IP Contingencia' },
    { grupo: 'LAN2' },
    { clave: 'LAN2_VIP', etiqueta: 'VIP VRRP' },
    { clave: 'LAN2_NET', etiqueta: 'Red' },
    { clave: 'LAN2_PREFIX', etiqueta: 'Prefijo' },
    { clave: 'LAN2_MASK', etiqueta: 'Máscara' },
    { clave: 'LAN2_WILDCARD', etiqueta: 'Wildcard' },
    { clave: 'LAN2_IP_PRIN', etiqueta: 'IP Principal' },
    { clave: 'LAN2_IP_SEC', etiqueta: 'IP Contingencia' },
    { grupo: 'LAN3' },
    { clave: 'LAN3_VIP', etiqueta: 'VIP VRRP' },
    { clave: 'LAN3_NET', etiqueta: 'Red' },
    { clave: 'LAN3_PREFIX', etiqueta: 'Prefijo' },
    { clave: 'LAN3_MASK', etiqueta: 'Máscara' },
    { clave: 'LAN3_WILDCARD', etiqueta: 'Wildcard' },
    { clave: 'LAN3_IP_PRIN', etiqueta: 'IP Principal' },
    { clave: 'LAN3_IP_SEC', etiqueta: 'IP Contingencia' },
    { grupo: 'LAN4' },
    { clave: 'LAN4_VIP', etiqueta: 'VIP VRRP' },
    { clave: 'LAN4_NET', etiqueta: 'Red' },
    { clave: 'LAN4_PREFIX', etiqueta: 'Prefijo' },
    { clave: 'LAN4_MASK', etiqueta: 'Máscara' },
    { clave: 'LAN4_WILDCARD', etiqueta: 'Wildcard' },
    { clave: 'LAN4_IP_PRIN', etiqueta: 'IP Principal' },
    { clave: 'LAN4_IP_SEC', etiqueta: 'IP Contingencia' },
    { grupo: 'LANs incluidas' },
    { clave: 'TRUNK_LAN_VLANS', etiqueta: 'VLANs del trunk' }
  ];

  function $(id) {
    return document.getElementById(id);
  }

  function q(selector) {
    return document.querySelector(selector);
  }

  function qa(selector) {
    return Array.prototype.slice.call(document.querySelectorAll(selector));
  }

  function escaparHtml(texto) {
    return String(texto).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function resaltarFaltantes(texto) {
    return escaparHtml(texto).replace(/\{\{(\w+)\}\}/g, '<mark class="faltante">{{$1}}</mark>');
  }

  function leerEntrada() {
    var e = {};
    qa('[data-var]').forEach(function (el) {
      var clave = el.getAttribute('data-var');
      if (el.type === 'checkbox') e[clave] = el.checked;
      else e[clave] = el.value.trim();
    });
    return e;
  }

  function esCheckLan(clave) {
    return /^LAN[1-4]_INCLUDE$/.test(clave);
  }

  function esCampoMascara(clave) {
    return /^LAN[1-4]_MASK$/.test(clave);
  }

  function escribirEntrada(e) {
    qa('[data-var]').forEach(function (el) {
      var clave = el.getAttribute('data-var');
      if (el.type === 'checkbox') {
        // Los JSON de la v1 no traen LANn_INCLUDE: se asumen incluidas.
        el.checked = esCheckLan(clave) && e[clave] === undefined ? true : !!e[clave];
        return;
      }
      var valor = e[clave];
      if (esCampoMascara(clave) && (valor === null || valor === undefined || valor === '')) {
        // Compatibilidad con LANn_PREFIX de la v1.
        valor = e[clave.replace('_MASK', '_PREFIX')];
      }
      if (valor !== null && valor !== undefined) {
        el.value = valor;
      } else {
        el.value = '';
      }
    });
    sincronizarSwitch();
    sincronizarLans();
    sincronizarMascaras();
  }

  function aplicarDefaults() {
    qa('[data-var]').forEach(function (el) {
      if (el.type === 'checkbox') {
        el.checked = esCheckLan(el.getAttribute('data-var'));
      } else {
        el.value = '';
      }
    });
    Object.keys(DEFAULTS).forEach(function (clave) {
      var el = q('[data-var="' + clave + '"]');
      if (el) el.value = DEFAULTS[clave];
    });
    sincronizarSwitch();
    sincronizarLans();
    sincronizarMascaras();
  }

  function sincronizarSwitch() {
    var chk = q('[data-var="incluir_switch"]');
    var activo = !!(chk && chk.checked);
    qa('[data-var="SW_NAME"],[data-var="SW_IP"]').forEach(function (el) {
      el.disabled = !activo;
    });
  }

  function sincronizarLans() {
    for (var n = 1; n <= 4; n++) {
      var chk = q('[data-var="LAN' + n + '_INCLUDE"]');
      var tarjeta = q('[data-tarjeta-lan="' + n + '"]');
      var campos = q('[data-campos-lan="' + n + '"]');
      if (!chk || !tarjeta || !campos) continue;
      var activa = chk.checked;
      tarjeta.classList.toggle('excluida', !activa);
      Array.prototype.slice.call(campos.querySelectorAll('input, select, textarea')).forEach(function (el) {
        el.disabled = !activa;
      });
    }
  }

  function actualizarAyudaMascara(n) {
    var input = q('[data-var="LAN' + n + '_MASK"]');
    var ayuda = q('[data-mascara-msg="' + n + '"]');
    if (!input || !ayuda) return;
    var m = Motor.parsearMascara(input.value);
    if (!m) {
      ayuda.textContent = 'Máscara no válida: usa 24, /24 o 255.255.255.0.';
      ayuda.className = 'ayuda-msg mal';
      return;
    }
    var esperado = (Motor.MASCARAS_ESPERADAS && Motor.MASCARAS_ESPERADAS[n]) || 24;
    var texto = '= ' + m.mascara;
    if (m.prefijo !== esperado) texto += ' · esperada /' + esperado;
    ayuda.textContent = texto;
    ayuda.className = 'ayuda-msg' + (m.prefijo !== esperado ? ' aviso' : '');
  }

  function sincronizarMascaras() {
    for (var n = 1; n <= 4; n++) actualizarAyudaMascara(n);
  }

  function crearTarjetas() {
    Motor.ROLES.forEach(function (rol) {
      var panel = $('panel-' + rol.id);
      if (!panel) return;
      var contenedor = panel.querySelector('[data-bloques]');
      if (!contenedor) return;
      Motor.BLOQUES.forEach(function (b) {
        var clave = rol.id + '-' + b.n;
        var articulo = document.createElement('article');
        articulo.className = 'bloque';
        articulo.id = 'bloque-' + clave;
        articulo.innerHTML =
          '<div class="bloque-cab">' +
            '<div><strong>' + b.titulo + '</strong> ' +
              '<span class="meta" data-meta="' + clave + '">—</span></div>' +
            '<div class="botones">' +
              '<button type="button" data-copiar="' + clave + '">Copiar</button>' +
              '<button type="button" data-descargar="' + clave + '">Descargar .txt</button>' +
            '</div>' +
          '</div>' +
          '<pre class="salida" data-salida="' + clave + '"></pre>';
        contenedor.appendChild(articulo);
      });
    });
  }

  function pintarAvisos(res) {
    var contenedor = $('avisos');
    contenedor.innerHTML = '';
    var hayError = false;
    var hayAviso = false;

    if (res.faltantes.length) {
      hayError = true;
      var divFaltan = document.createElement('div');
      divFaltan.className = 'aviso error';
      divFaltan.textContent = 'Faltan valores o plantillas para: ' + res.faltantes.join(', ');
      contenedor.appendChild(divFaltan);
    }

    res.avisos.forEach(function (a) {
      var div = document.createElement('div');
      div.className = 'aviso ' + (a.nivel === 'error' ? 'error' : (a.nivel === 'ok' ? 'ok' : 'aviso'));
      div.textContent = a.mensaje;
      contenedor.appendChild(div);
      if (a.nivel === 'error') hayError = true;
      if (a.nivel === 'aviso') hayAviso = true;
    });

    if (!res.faltantes.length && !hayError && !hayAviso) {
      var ok = document.createElement('div');
      ok.className = 'aviso ok';
      ok.textContent = 'Todo válido. Los scripts están listos para copiar o descargar.';
      contenedor.appendChild(ok);
    } else if (!hayError && hayAviso) {
      var info = document.createElement('div');
      info.className = 'aviso ok';
      info.textContent = 'Generado con avisos. Revisa la tabla de valores derivados antes de copiar.';
      contenedor.appendChild(info);
    }
  }

  function pintarBloques(res) {
    Motor.ROLES.forEach(function (rol) {
      Motor.BLOQUES.forEach(function (b) {
        var clave = rol.id + '-' + b.n;
        var bloque = res.bloques[rol.id][b.n];
        var pre = q('[data-salida="' + clave + '"]');
        var meta = q('[data-meta="' + clave + '"]');
        var articulo = $('bloque-' + clave);
        if (pre) pre.innerHTML = resaltarFaltantes(bloque.texto);
        if (meta) {
          meta.textContent = bloque.lineas + ' líneas' + (bloque.ok ? ' · listo' : ' · revisar');
        }
        if (articulo) articulo.classList.toggle('con-error', !bloque.ok);
      });
    });
  }

  function pintarSwitch(res) {
    var vacio = $('switch-vacio');
    var articulo = $('bloque-switch');
    var btnDescargar = q('[data-descargar-todo="switch"]');
    if (btnDescargar) btnDescargar.disabled = !res.switch;
    if (!res.switch) {
      if (vacio) vacio.classList.remove('oculto');
      if (articulo) articulo.classList.add('oculto');
      return;
    }
    if (vacio) vacio.classList.add('oculto');
    if (articulo) articulo.classList.remove('oculto');
    var pre = q('[data-salida="switch"]');
    var meta = q('[data-meta="switch"]');
    if (pre) pre.innerHTML = resaltarFaltantes(res.switch.texto);
    if (meta) {
      meta.textContent = res.switch.lineas + ' líneas' + (res.switch.ok ? ' · listo' : ' · revisar');
    }
    if (articulo) articulo.classList.toggle('con-error', !res.switch.ok);
  }

  function pintarDerivadas(vars) {
    var tbody = $('tabla-derivadas');
    if (!tbody) return;
    tbody.innerHTML = '';
    FILAS_DERIVADAS.forEach(function (fila) {
      var tr = document.createElement('tr');
      if (fila.grupo) {
        tr.className = 'grupo';
        var tdGrupo = document.createElement('td');
        tdGrupo.colSpan = 2;
        tdGrupo.textContent = fila.grupo;
        tr.appendChild(tdGrupo);
      } else {
        var tdEtiqueta = document.createElement('td');
        tdEtiqueta.textContent = fila.etiqueta;
        var tdValor = document.createElement('td');
        tdValor.className = 'valor';
        var valor = vars[fila.clave];
        tdValor.textContent = (valor === null || valor === undefined || valor === '') ? '—' : String(valor);
        tr.appendChild(tdEtiqueta);
        tr.appendChild(tdValor);
      }
      tbody.appendChild(tr);
    });
  }

  function actualizarEstado(res) {
    var estado = $('estado');
    if (!estado) return;
    var bloques = 0;
    var lineas = 0;
    Motor.ROLES.forEach(function (rol) {
      Motor.BLOQUES.forEach(function (b) {
        bloques++;
        lineas += res.bloques[rol.id][b.n].lineas;
      });
    });
    if (res.switch) {
      bloques++;
      lineas += res.switch.lineas;
    }
    if (!res.ok) {
      estado.className = 'estado mal';
      estado.textContent = 'Faltan datos para generar.';
    } else if (res.avisos.some(function (a) { return a.nivel === 'error'; })) {
      estado.className = 'estado mal';
      estado.textContent = bloques + ' bloques · ' + lineas + ' líneas · con avisos';
    } else {
      estado.className = 'estado ok';
      estado.textContent = bloques + ' bloques · ' + lineas + ' líneas · listo';
    }
  }

  function guardarLocal(entrada) {
    try {
      localStorage.setItem(CLAVE_LS, JSON.stringify(entrada));
    } catch (e) {
      /* localStorage puede estar bloqueado en file://; se ignora. */
    }
  }

  function actualizar() {
    var entrada = leerEntrada();
    var res = Motor.buildScripts(entrada, PLANTILLAS, {});
    ULTIMO = res;
    pintarAvisos(res);
    pintarBloques(res);
    pintarSwitch(res);
    pintarDerivadas(res.vars);
    actualizarEstado(res);
    guardarLocal(entrada);
  }

  function avisoBoton(btn, texto) {
    if (!btn) return;
    if (!btn.dataset.textoOriginal) btn.dataset.textoOriginal = btn.textContent;
    btn.textContent = texto;
    btn.disabled = true;
    setTimeout(function () {
      btn.textContent = btn.dataset.textoOriginal;
      btn.disabled = false;
    }, 1400);
  }

  function copiarConFallback(texto, btn) {
    var area = document.createElement('textarea');
    area.value = texto;
    area.setAttribute('readonly', '');
    area.style.position = 'fixed';
    area.style.top = '-1000px';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    var exito = false;
    try {
      exito = document.execCommand('copy');
    } catch (e) {
      exito = false;
    }
    document.body.removeChild(area);
    avisoBoton(btn, exito ? 'Copiado' : 'No se pudo copiar');
  }

  function copiarTexto(texto, btn) {
    if (!texto) {
      avisoBoton(btn, 'Sin contenido');
      return;
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(texto).then(function () {
        avisoBoton(btn, 'Copiado');
      }).catch(function () {
        copiarConFallback(texto, btn);
      });
    } else {
      copiarConFallback(texto, btn);
    }
  }

  function descargarTexto(nombre, texto) {
    var blob = new Blob([texto], { type: 'text/plain;charset=utf-8' });
    var url = URL.createObjectURL(blob);
    var enlace = document.createElement('a');
    enlace.href = url;
    enlace.download = nombre;
    document.body.appendChild(enlace);
    enlace.click();
    document.body.removeChild(enlace);
    setTimeout(function () { URL.revokeObjectURL(url); }, 1500);
  }

  function obtenerBloque(clave) {
    if (!ULTIMO) return null;
    if (clave === 'switch') return ULTIMO.switch;
    var partes = clave.split('-');
    var rol = partes[0];
    var n = Number(partes[1]);
    return ULTIMO.bloques[rol] ? ULTIMO.bloques[rol][n] : null;
  }

  function activarTab(id) {
    qa('.pestana').forEach(function (b) {
      b.classList.toggle('activa', b.getAttribute('data-tab') === id);
    });
    qa('.panel-tab').forEach(function (p) {
      p.classList.toggle('oculto', p.id !== 'panel-' + id);
    });
  }

  function limpiarInterfaces() {
    FILAS_INTERFACES = [];
    var preview = $('preview-interfaces');
    if (preview) {
      preview.innerHTML = '';
      preview.classList.add('oculto');
    }
    var msg = $('mensaje-interfaces');
    if (msg) {
      msg.textContent = 'Opcional: analiza antes de aplicar.';
      msg.className = 'ayuda-msg';
    }
    var btn = $('btn-aplicar-interfaces');
    if (btn) btn.disabled = true;
  }

  function ipDesdeFila(fila, lan, rolOffset) {
    if (!lan) return '—';
    var ip = Motor.ipToInt(fila.ip);
    if (ip === null) return '—';
    var e = leerEntrada();
    var off = Number(e['LAN' + lan + '_OFF_' + rolOffset]);
    if (!isFinite(off) || Math.floor(off) !== off) return '—';
    return Motor.intToIp((ip + off) >>> 0);
  }

  function filaTieneDuplicado(indice) {
    var fila = FILAS_INTERFACES[indice];
    if (!fila || !fila.lan) return false;
    return FILAS_INTERFACES.some(function (otra, j) {
      return j !== indice && otra.lan === fila.lan;
    });
  }

  function renderPreviewInterfaces() {
    var preview = $('preview-interfaces');
    var btn = $('btn-aplicar-interfaces');
    if (!preview) return;
    if (!FILAS_INTERFACES.length) {
      preview.innerHTML = '';
      preview.classList.add('oculto');
      if (btn) btn.disabled = true;
      return;
    }

    var html = '<table class="tabla"><thead><tr>' +
      '<th>#</th><th>Interfaz</th><th>VLAN</th><th>IP</th><th>Prefijo</th><th>Máscara</th>' +
      '<th>Red</th><th>VIP</th><th>IP Principal</th><th>IP Contingencia</th><th>Asignar a</th>' +
      '</tr></thead><tbody>';

    FILAS_INTERFACES.forEach(function (fila, i) {
      var duplicado = filaTieneDuplicado(i);
      html += '<tr' + (duplicado ? ' class="fila-mal"' : '') + '>' +
        '<td>' + (i + 1) + '</td>' +
        '<td>' + escaparHtml(fila.interfaz) + '</td>' +
        '<td>' + (fila.vlan === null ? '—' : escaparHtml(fila.vlan)) + '</td>' +
        '<td>' + escaparHtml(fila.ip) + '</td>' +
        '<td>/' + fila.prefijo + '</td>' +
        '<td>' + escaparHtml(fila.mascara) + '</td>' +
        '<td>' + escaparHtml(fila.red) + '</td>' +
        '<td>' + escaparHtml(fila.ip) + '</td>' +
        '<td>' + escaparHtml(ipDesdeFila(fila, fila.lan, 'PRIN')) + '</td>' +
        '<td>' + escaparHtml(ipDesdeFila(fila, fila.lan, 'SEC')) + '</td>' +
        '<td><select data-fila-lan="' + i + '">' +
          '<option value="">—</option>' +
          [1, 2, 3, 4].map(function (n) {
            return '<option value="' + n + '"' + (fila.lan === n ? ' selected' : '') + '>LAN' + n + '</option>';
          }).join('') +
        '</select></td>' +
        '</tr>';
    });
    html += '</tbody></table>';
    preview.innerHTML = html;
    preview.classList.remove('oculto');
    if (btn) btn.disabled = false;

    preview.querySelectorAll('[data-fila-lan]').forEach(function (sel) {
      sel.addEventListener('change', function () {
        var i = Number(sel.getAttribute('data-fila-lan'));
        var n = Number(sel.value);
        FILAS_INTERFACES[i].lan = n || null;
        renderPreviewInterfaces();
      });
    });
  }

  function analizarInterfaces() {
    var area = $('pegar-interfaces');
    var msg = $('mensaje-interfaces');
    if (!area || !msg) return;
    var res = Motor.parsearInterfaces(area.value);
    FILAS_INTERFACES = Motor.sugerirAsignacion(res.filas, leerEntrada());

    if (res.errores.length) {
      msg.className = 'ayuda-msg mal';
      msg.textContent = 'No se pudieron analizar ' + res.errores.length + ' línea(s): ' +
        res.errores.map(function (e) { return 'línea ' + e.linea; }).join(', ') + '.';
    } else if (res.advertencias.length) {
      msg.className = 'ayuda-msg aviso';
      msg.textContent = 'Analizado con ' + res.advertencias.length + ' advertencia(s). Revisa la vista previa.';
    } else {
      msg.className = 'ayuda-msg ok';
      msg.textContent = 'Analizadas ' + FILAS_INTERFACES.length + ' interfaz(es). Revisa y aplica.';
    }

    var no24 = FILAS_INTERFACES.filter(function (f) { return f.prefijo !== 24; }).length;
    if (!res.errores.length && no24) {
      msg.textContent += ' ' + no24 + ' máscara(s) distinta(s) de /24.';
    }

    if (!FILAS_INTERFACES.length) {
      msg.className = 'ayuda-msg mal';
      msg.textContent = 'No se encontraron líneas válidas con interfaz e IP/prefijo.';
    }
    renderPreviewInterfaces();
  }

  function aplicarInterfaces() {
    var msg = $('mensaje-interfaces');
    if (!FILAS_INTERFACES.length) return;

    var asignadas = {};
    var error = '';
    FILAS_INTERFACES.forEach(function (fila, i) {
      if (!fila.lan) return;
      if (asignadas[fila.lan] !== undefined) {
        error = 'LAN' + fila.lan + ' está asignada a más de una línea (filas ' +
          (asignadas[fila.lan] + 1) + ' y ' + (i + 1) + ').';
      } else {
        asignadas[fila.lan] = i;
      }
    });
    if (error) {
      if (msg) { msg.className = 'ayuda-msg mal'; msg.textContent = error; }
      return;
    }

    var aplicadas = 0;
    Object.keys(asignadas).forEach(function (clave) {
      var lan = Number(clave);
      var fila = FILAS_INTERFACES[asignadas[clave]];
      if (fila.vlan !== null) {
        var v = q('[data-var="VLAN_LAN' + lan + '"]');
        if (v) v.value = fila.vlan;
      }
      var gw = q('[data-var="LAN' + lan + '_GW"]');
      if (gw) gw.value = fila.ip;
      var mask = q('[data-var="LAN' + lan + '_MASK"]');
      if (mask) mask.value = '/' + fila.prefijo;
      var chk = q('[data-var="LAN' + lan + '_INCLUDE"]');
      if (chk) chk.checked = true;
      aplicadas++;
    });

    sincronizarLans();
    sincronizarMascaras();
    actualizar();
    if (msg) {
      msg.className = 'ayuda-msg ok';
      msg.textContent = 'Aplicadas ' + aplicadas + ' LAN(s). Revisa los valores derivados.';
    }
  }

  // ------------------------------------------------------------------
  // Eventos
  // ------------------------------------------------------------------

  q('#formulario').addEventListener('input', function (ev) {
    var el = ev.target;
    var clave = el && el.getAttribute ? el.getAttribute('data-var') : '';
    if (esCampoMascara(clave)) actualizarAyudaMascara(Number(clave.charAt(3)));
    actualizar();
  });
  q('#formulario').addEventListener('change', function (ev) {
    var el = ev.target;
    var clave = el && el.getAttribute ? el.getAttribute('data-var') : '';
    if (esCheckLan(clave)) sincronizarLans();
    if (esCampoMascara(clave)) actualizarAyudaMascara(Number(clave.charAt(3)));
    sincronizarSwitch();
    actualizar();
  });

  q('#resultados').addEventListener('click', function (ev) {
    var btn = ev.target.closest ? ev.target.closest('button') : null;
    if (!btn) return;

    if (btn.hasAttribute('data-tab')) {
      activarTab(btn.getAttribute('data-tab'));
      return;
    }

    if (btn.hasAttribute('data-copiar')) {
      var bloque = obtenerBloque(btn.getAttribute('data-copiar'));
      if (bloque) copiarTexto(bloque.texto, btn);
      return;
    }

    if (btn.hasAttribute('data-descargar')) {
      var b = obtenerBloque(btn.getAttribute('data-descargar'));
      if (b) descargarTexto(b.archivo, b.texto);
      return;
    }

    if (btn.hasAttribute('data-copiar-todo')) {
      var rol = btn.getAttribute('data-copiar-todo');
      if (ULTIMO && ULTIMO.bloques[rol]) {
        copiarTexto(Motor.unirBloques(ULTIMO.bloques[rol], [1, 2, 3]), btn);
      }
      return;
    }

    if (btn.hasAttribute('data-descargar-todo')) {
      var rolTodo = btn.getAttribute('data-descargar-todo');
      if (rolTodo === 'switch') {
        if (ULTIMO && ULTIMO.switch) {
          descargarTexto(ULTIMO.switch.archivo, ULTIMO.switch.texto);
        }
      } else if (ULTIMO && ULTIMO.bloques[rolTodo]) {
        var nombreTodo = 'rCAC_' + (ULTIMO.entrada.CAC || 'CAC') + '_' +
          (rolTodo === 'principal' ? 'Principal' : 'Contingencia') + '_completo.txt';
        descargarTexto(nombreTodo, Motor.unirBloques(ULTIMO.bloques[rolTodo], [1, 2, 3, 4]));
      }
      return;
    }
  });

  q('#btn-generar').addEventListener('click', function () {
    actualizar();
    q('#resultados').scrollIntoView({ behavior: 'smooth', block: 'start' });
  });

  q('#btn-ejemplo').addEventListener('click', function () {
    escribirEntrada(EJEMPLO);
    actualizar();
  });

  q('#btn-limpiar').addEventListener('click', function () {
    aplicarDefaults();
    actualizar();
  });

  q('#btn-guardar').addEventListener('click', function () {
    var e = leerEntrada();
    descargarTexto('datos_cpe_' + (e.CAC || 'CAC') + '.json', JSON.stringify(e, null, 2) + '\n');
  });

  q('#btn-cargar').addEventListener('click', function () {
    q('#archivo-json').click();
  });

  q('#archivo-json').addEventListener('change', function (ev) {
    var archivo = ev.target.files && ev.target.files[0];
    if (!archivo) return;
    var lector = new FileReader();
    lector.onload = function () {
      try {
        var datos = JSON.parse(String(lector.result));
        escribirEntrada(datos);
        actualizar();
      } catch (err) {
        alert('JSON inválido: ' + err.message);
      }
    };
    lector.readAsText(archivo, 'utf-8');
    ev.target.value = '';
  });

  q('#btn-analizar-interfaces').addEventListener('click', analizarInterfaces);
  q('#btn-aplicar-interfaces').addEventListener('click', aplicarInterfaces);
  q('#btn-limpiar-interfaces').addEventListener('click', function () {
    var area = $('pegar-interfaces');
    if (area) area.value = '';
    limpiarInterfaces();
  });

  // ------------------------------------------------------------------
  // Inicio
  // ------------------------------------------------------------------

  if (q('#perfil') && typeof PERFIL_ACTIVO !== 'undefined') {
    q('#perfil').textContent =
      'Perfil ' + PERFIL_ACTIVO.marca + ' / ' + PERFIL_ACTIVO.topologia + ' / ' +
      PERFIL_ACTIVO.enlace + ' · ' + PERFIL_ACTIVO.region +
      ' · funciona sin conexión · sin dependencias';
  }

  crearTarjetas();
  aplicarDefaults();
  limpiarInterfaces();

  try {
    var guardado = localStorage.getItem(CLAVE_LS);
    if (guardado) escribirEntrada(JSON.parse(guardado));
  } catch (e) {
    /* Si localStorage falla o el JSON guardado está corrupto, se usan los defaults. */
  }

  sincronizarSwitch();
  actualizar();
})();
"""


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    plantillas = cargar_plantillas()
    motor_js = leer_texto(ARCHIVO_MOTOR)
    ejemplo = json.loads(leer_texto(ARCHIVO_EJEMPLO))
    defaults = valores_por_defecto()

    if "</script" in motor_js.lower():
        raise SystemExit("motor.js contiene </script y no se puede incrustar tal cual.")
    if "</script" in UI_JS.lower():
        raise SystemExit("La interfaz contiene </script y no se puede incrustar tal cual.")

    lan_cards = "\n".join(tarjeta_lan(lan) for lan in LANS)

    html = (
        HTML.replace("@@CSS@@", CSS)
        .replace("@@LAN_CARDS@@", lan_cards)
        .replace("@@PLANTILLAS@@", json_para_script(plantillas))
        .replace("@@EJEMPLO@@", json_para_script(ejemplo))
        .replace("@@PERFIL@@", json_para_script(PERFIL))
        .replace("@@DEFAULTS@@", json_para_script(defaults))
        .replace("@@MOTOR@@", motor_js)
        .replace("@@UI@@", UI_JS)
    )

    with open(ARCHIVO_SALIDA, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)

    print("Plantillas leídas:", len(plantillas))
    print("Generado:", ARCHIVO_SALIDA)
    print("Tamaño:", f"{ARCHIVO_SALIDA.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
