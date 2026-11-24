/*
 * motor.js — Lógica del generador de scripts CPE ZTE (HA + fibra).
 *
 * No usa DOM: funciona igual en el navegador (window.MotorCPE) y en Node
 * (require('./motor.js')). Toda la aritmética de IP se hace con enteros de
 * 32 bits para evitar errores de substring de octetos.
 *
 * Comentarios en español. Funciones pequeñas y sin dependencias.
 */
(function (root, factory) {
  'use strict';
  var api = factory();
  if (typeof module === 'object' && module.exports) {
    module.exports = api;
  } else {
    // Se exponen ambos nombres para que la interfaz use "Motor".
    root.Motor = api;
    root.MotorCPE = api;
  }
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  /* ------------------------------------------------------------------ */
  /* Utilidades de IP                                                    */
  /* ------------------------------------------------------------------ */

  // Convierte "a.b.c.d" a entero sin signo de 32 bits. Devuelve null si no es válida.
  function ipToInt(ip) {
    if (typeof ip !== 'string') return null;
    var partes = ip.trim().split('.');
    if (partes.length !== 4) return null;
    var n = 0;
    for (var i = 0; i < 4; i++) {
      if (!/^\d{1,3}$/.test(partes[i])) return null;
      var octeto = Number(partes[i]);
      if (octeto < 0 || octeto > 255) return null;
      n = n * 256 + octeto;
    }
    return n >>> 0;
  }

  // Convierte un entero de 32 bits a "a.b.c.d".
  function intToIp(n) {
    if (typeof n !== 'number' || !isFinite(n)) return null;
    n = n >>> 0;
    return [
      (n >>> 24) & 255,
      (n >>> 16) & 255,
      (n >>> 8) & 255,
      n & 255
    ].join('.');
  }

  // Máscara de prefijo /p como entero de 32 bits.
  function prefixToMask(p) {
    if (p === null || p === undefined || p === '') return null;
    p = Number(p);
    if (!isFinite(p) || Math.floor(p) !== p || p < 0 || p > 32) return null;
    if (p === 0) return 0;
    return (0xFFFFFFFF << (32 - p)) >>> 0;
  }

  // Acepta 24, "/24" o "255.255.255.0" y devuelve
  // { prefijo, mascara, texto } o null si no es una máscara contigua válida.
  function parsearMascara(valor) {
    if (valor === null || valor === undefined) return null;
    var s = String(valor).trim();
    if (s === '') return null;

    var prefijo = null;
    if (/^\/?\d{1,2}$/.test(s)) {
      prefijo = Number(s.replace('/', ''));
      if (prefijo < 0 || prefijo > 32) return null;
    } else {
      var ip = ipToInt(s);
      if (ip === null) return null;
      // Una máscara contigua tiene la forma 111...1100...00.
      // Su inversa debe ser 2^k - 1 (o 0 para /32).
      var inversa = (~ip) >>> 0;
      if ((inversa & (inversa + 1)) !== 0) return null;
      prefijo = 0;
      var m = ip;
      while (m) {
        prefijo++;
        m = (m << 1) >>> 0;
      }
    }

    var mascaraInt = prefixToMask(prefijo);
    if (mascaraInt === null) return null;
    return { prefijo: prefijo, mascara: intToIp(mascaraInt), texto: s };
  }

  // Wildcard (máscara inversa) a partir de una máscara entera.
  function maskToWildcard(mask) {
    if (typeof mask !== 'number' || !isFinite(mask)) return null;
    return (~mask) >>> 0;
  }

  // Devuelve true si el texto es una IPv4 válida.
  function esIpValida(ip) {
    return ipToInt(ip) !== null;
  }

  // Prefijo esperado para la máscara de cada LAN. Se usa solo para advertir:
  // una LAN puede usar otra máscara, pero la interfaz lo señala.
  var MASCARAS_ESPERADAS = { 1: 24, 2: 26, 3: 27, 4: 28 };

  /* ------------------------------------------------------------------ */
  /* Normalización de la entrada                                         */
  /* ------------------------------------------------------------------ */

  // Texto limpio (sin espacios en los extremos). null/undefined -> "".
  function texto(valor) {
    if (valor === null || valor === undefined) return '';
    return String(valor).trim();
  }

  // Entero o null. Acepta números y cadenas numéricas.
  function aEntero(valor) {
    if (valor === null || valor === undefined || valor === '') return null;
    var n = Number(valor);
    if (!isFinite(n) || Math.floor(n) !== n) return null;
    return n;
  }

  // Normaliza el objeto que llega del formulario o de un JSON.
  function normalizarEntrada(entrada) {
    var e = entrada || {};
    var out = {
      CAC: texto(e.CAC),
      CID_PRIN: texto(e.CID_PRIN),
      CID_SEC: texto(e.CID_SEC),
      BW_MB: aEntero(e.BW_MB),
      WAN_IP_PRIN: texto(e.WAN_IP_PRIN),
      LOOPBACK_PRIN: texto(e.LOOPBACK_PRIN),
      VLAN_WAN_PRIN: texto(e.VLAN_WAN_PRIN),
      WAN_IP_SEC: texto(e.WAN_IP_SEC),
      LOOPBACK_SEC: texto(e.LOOPBACK_SEC),
      VLAN_WAN_SEC: texto(e.VLAN_WAN_SEC),
      incluir_switch: !!e.incluir_switch,
      SW_NAME: texto(e.SW_NAME),
      SW_IP: texto(e.SW_IP)
    };
    for (var n = 1; n <= 4; n++) {
      out['VLAN_LAN' + n] = texto(e['VLAN_LAN' + n]);
      out['NAME_LAN' + n] = texto(e['NAME_LAN' + n]);
      out['LAN' + n + '_GW'] = texto(e['LAN' + n + '_GW']);

      // Por defecto todas las LAN se incluyen. Los JSON de la v1 no traen
      // LANn_INCLUDE y deben seguir funcionando.
      out['LAN' + n + '_INCLUDE'] = e['LAN' + n + '_INCLUDE'] === undefined
        ? true
        : !!e['LAN' + n + '_INCLUDE'];

      // Campo nuevo LANn_MASK: acepta 24, /24 o 255.255.255.0. Si no viene,
      // se acepta LANn_PREFIX de los JSON de la v1.
      var mascaraCruda = texto(e['LAN' + n + '_MASK']);
      if (!mascaraCruda) mascaraCruda = texto(e['LAN' + n + '_PREFIX']);
      var mascara = parsearMascara(mascaraCruda);
      out['LAN' + n + '_MASK'] = mascaraCruda;
      out['LAN' + n + '_PREFIX'] = mascara ? mascara.prefijo : null;

      out['LAN' + n + '_OFF_PRIN'] = aEntero(e['LAN' + n + '_OFF_PRIN']);
      out['LAN' + n + '_OFF_SEC'] = aEntero(e['LAN' + n + '_OFF_SEC']);
    }
    return out;
  }

  /* ------------------------------------------------------------------ */
  /* Variables derivadas                                                 */
  /* ------------------------------------------------------------------ */

  // Calcula todas las variables derivadas a partir de la entrada.
  function deriveVars(entradaCruda) {
    var e = normalizarEntrada(entradaCruda);
    var v = {};

    // Entradas que usan las plantillas (se copian tal cual).
    v.CAC = e.CAC;
    v.CID_PRIN = e.CID_PRIN;
    v.CID_SEC = e.CID_SEC;
    v.BW_MB = e.BW_MB;
    v.WAN_IP_PRIN = e.WAN_IP_PRIN;
    v.WAN_IP_SEC = e.WAN_IP_SEC;
    v.LOOPBACK_PRIN = e.LOOPBACK_PRIN;
    v.LOOPBACK_SEC = e.LOOPBACK_SEC;
    v.VLAN_WAN_PRIN = e.VLAN_WAN_PRIN;
    v.VLAN_WAN_SEC = e.VLAN_WAN_SEC;

    // WAN: bloque /30 -> red, IP del PE y IP del CPE.
    [['PRIN', e.WAN_IP_PRIN], ['SEC', e.WAN_IP_SEC]].forEach(function (par) {
      var sufijo = par[0];
      var ip = ipToInt(par[1]);
      if (ip === null) {
        v['WAN_NET_' + sufijo] = null;
        v['WAN_PE_' + sufijo] = null;
        v['WAN_CPE_' + sufijo] = null;
        return;
      }
      var red = (ip & 0xFFFFFFFC) >>> 0;
      v['WAN_NET_' + sufijo] = intToIp(red);
      v['WAN_PE_' + sufijo] = intToIp((red + 1) >>> 0);
      v['WAN_CPE_' + sufijo] = intToIp((red + 2) >>> 0);
    });

    // Ancho de banda.
    if (e.BW_MB !== null && e.BW_MB >= 0) {
      v.BW_KBPS = e.BW_MB * 1024;
      v.SHAPE_BPS = v.BW_KBPS * 1000 + 1000;
      v.CBS_KB = Math.floor(e.BW_MB * 0.1875);
    } else {
      v.BW_KBPS = null;
      v.SHAPE_BPS = null;
      v.CBS_KB = null;
    }

    // LANs.
    var vlansActivas = [];
    for (var n = 1; n <= 4; n++) {
      var vlan = e['VLAN_LAN' + n];
      var nombre = e['NAME_LAN' + n];
      var incluir = e['LAN' + n + '_INCLUDE'];
      var prefijo = e['LAN' + n + '_PREFIX'];
      var offPrin = e['LAN' + n + '_OFF_PRIN'];
      var offSec = e['LAN' + n + '_OFF_SEC'];
      var gw = ipToInt(e['LAN' + n + '_GW']);
      var mascara = prefijo === null ? null : prefixToMask(prefijo);

      v['VLAN_LAN' + n] = vlan;
      v['NAME_LAN' + n] = nombre;
      v['LAN' + n + '_INCLUDE'] = incluir;
      v['LAN' + n] = incluir; // usado por las directivas {{#LANn}}
      v['LAN' + n + '_PREFIX'] = prefijo;
      v['LAN' + n + '_OFF_PRIN'] = offPrin;
      v['LAN' + n + '_OFF_SEC'] = offSec;
      v['LAN' + n + '_VIP'] = gw !== null ? intToIp(gw) : null;
      v['LAN' + n + '_MASK'] = mascara !== null ? intToIp(mascara) : null;
      v['LAN' + n + '_WILDCARD'] = mascara !== null ? intToIp(maskToWildcard(mascara)) : null;
      v['LAN' + n + '_NET'] = (gw !== null && mascara !== null)
        ? intToIp((gw & mascara) >>> 0)
        : null;
      v['LAN' + n + '_IP_PRIN'] = (gw !== null && offPrin !== null)
        ? intToIp((gw + offPrin) >>> 0)
        : null;
      v['LAN' + n + '_IP_SEC'] = (gw !== null && offSec !== null)
        ? intToIp((gw + offSec) >>> 0)
        : null;

      if (incluir && vlan !== '') vlansActivas.push(vlan);
    }

    // Variables auxiliares para las directivas condicionales y el trunk.
    v.ANY_LAN = vlansActivas.length > 0;
    v.TRUNK_LAN_VLANS = vlansActivas.join(',');

    return v;
  }

  /* ------------------------------------------------------------------ */
  /* Motor de reemplazo                                                  */
  /* ------------------------------------------------------------------ */

  // Procesa las directivas {{#LAN1}}...{{/LAN1}} (y ANY_LAN) antes del
  // reemplazo de variables. No hay anidamiento: cada bloque es plano.
  // Devuelve { texto, errores }; si queda una directiva suelta, se reporta.
  function aplicarCondicionales(plantilla, vars) {
    var errores = [];
    var texto = String(plantilla === null || plantilla === undefined ? '' : plantilla);
    var regex = /\{\{#(LAN[1-4]|ANY_LAN)\}\}([\s\S]*?)\{\{\/\1\}\}\n?/g;

    texto = texto.replace(regex, function (marcador, nombre, contenido) {
      return vars && vars[nombre] ? contenido : '';
    });

    var restos = texto.match(/\{\{[#/][A-Za-z0-9_]+\}\}/g);
    if (restos) {
      restos.forEach(function (resto) {
        if (errores.indexOf(resto) === -1) errores.push(resto);
      });
    }
    return { texto: texto, errores: errores };
  }

  // Reemplaza {{VARIABLE}} conservando saltos de línea y sangrías.
  // Devuelve { texto, faltantes, ok }. Si falta un valor, deja el marcador
  // intacto y lo reporta (nunca falla en silencio).
  function renderTemplate(plantilla, vars) {
    var faltantes = [];
    var salida = String(plantilla === null || plantilla === undefined ? '' : plantilla)
      .replace(/\{\{(\w+)\}\}/g, function (marcador, nombre) {
        var valor = vars ? vars[nombre] : undefined;
        if (valor === undefined || valor === null || valor === '') {
          if (faltantes.indexOf(nombre) === -1) faltantes.push(nombre);
          return marcador;
        }
        return String(valor);
      });
    return { texto: salida, faltantes: faltantes, ok: faltantes.length === 0 };
  }

  // Cuenta líneas reales (ignora el salto final de la plantilla).
  function contarLineas(t) {
    if (!t) return 0;
    var s = String(t).replace(/\n$/, '');
    return s === '' ? 0 : s.split('\n').length;
  }

  // Une bloques con una línea en blanco entre ellos y salto final.
  function unirBloques(bloques, numeros) {
    var lista = numeros || [1, 2, 3];
    var partes = [];
    lista.forEach(function (n) {
      var b = bloques && bloques[n];
      if (b && b.texto) partes.push(String(b.texto).replace(/\n$/, ''));
    });
    return partes.length ? partes.join('\n\n') + '\n' : '';
  }

  /* ------------------------------------------------------------------ */
  /* Validaciones (solo avisan, no bloquean la generación)               */
  /* ------------------------------------------------------------------ */

  function validar(e, v) {
    var avisos = [];
    function add(nivel, campo, mensaje) {
      avisos.push({ nivel: nivel, campo: campo, mensaje: mensaje });
    }

    // Datos generales.
    if (!e.CAC) {
      add('error', 'CAC', 'El CAC es obligatorio.');
    } else if (/\s/.test(e.CAC)) {
      add('error', 'CAC', 'El CAC no debe contener espacios (se usa en hostname y VLAN).');
    }
    if (!/^\d+$/.test(e.CID_PRIN)) add('error', 'CID_PRIN', 'CID_PRIN debe contener solo dígitos.');
    if (!/^\d+$/.test(e.CID_SEC)) add('error', 'CID_SEC', 'CID_SEC debe contener solo dígitos.');
    if (e.BW_MB === null || e.BW_MB <= 0) {
      add('error', 'BW_MB', 'BW_MB debe ser un entero mayor que cero.');
    }

    // WAN.
    [['PRIN', e.WAN_IP_PRIN, e.LOOPBACK_PRIN, e.VLAN_WAN_PRIN],
     ['SEC', e.WAN_IP_SEC, e.LOOPBACK_SEC, e.VLAN_WAN_SEC]].forEach(function (fila) {
      var sufijo = fila[0];
      var ip = ipToInt(fila[1]);
      if (ip === null) {
        add('error', 'WAN_IP_' + sufijo, 'WAN_IP_' + sufijo + ' no es una IPv4 válida.');
      } else {
        var pos = ip & 3;
        if (pos === 0) {
          add('aviso', 'WAN_IP_' + sufijo,
            'WAN_IP_' + sufijo + ' es la dirección de red del /30; se usará red+2 como IP del CPE.');
        } else if (pos === 3) {
          add('aviso', 'WAN_IP_' + sufijo,
            'WAN_IP_' + sufijo + ' es la dirección de broadcast del /30; se usará red+2 como IP del CPE.');
        }
      }
      if (!esIpValida(fila[2])) {
        add('error', 'LOOPBACK_' + sufijo, 'LOOPBACK_' + sufijo + ' no es una IPv4 válida.');
      }
      if (!vlanValida(fila[3])) {
        add('error', 'VLAN_WAN_' + sufijo, 'VLAN_WAN_' + sufijo + ' debe estar entre 1 y 4094.');
      }
    });

    var netPrin = ipToInt(v.WAN_NET_PRIN);
    var netSec = ipToInt(v.WAN_NET_SEC);
    if (netPrin !== null && netSec !== null) {
      if (netPrin === netSec) {
        add('error', 'WAN', 'IP WAN DUPLICADA: Principal y Contingencia pertenecen al mismo bloque /30.');
      } else {
        add('ok', 'WAN', 'WAN OK: Principal y Contingencia usan bloques /30 distintos.');
      }
    }
    if (e.LOOPBACK_PRIN && e.LOOPBACK_SEC) {
      if (e.LOOPBACK_PRIN === e.LOOPBACK_SEC) {
        add('error', 'LOOPBACK', 'IP LOOPBACK DUPLICADA: Principal y Contingencia usan la misma IP.');
      } else {
        add('ok', 'LOOPBACK', 'LOOPBACK OK: Principal y Contingencia usan IPs distintas.');
      }
    }

    // LANs (solo las incluidas).
    var vlansLan = {};
    var redes = [];
    var lansActivas = 0;
    for (var n = 1; n <= 4; n++) {
      if (!e['LAN' + n + '_INCLUDE']) continue;
      lansActivas++;

      var etiqueta = 'LAN' + n;
      var vlan = aEntero(e['VLAN_LAN' + n]);
      var gw = ipToInt(e['LAN' + n + '_GW']);
      var prefijo = e['LAN' + n + '_PREFIX'];
      var mascara = prefijo === null ? null : prefixToMask(prefijo);
      var offPrin = e['LAN' + n + '_OFF_PRIN'];
      var offSec = e['LAN' + n + '_OFF_SEC'];

      if (!vlanValida(e['VLAN_LAN' + n])) {
        add('error', 'VLAN_LAN' + n, 'VLAN_LAN' + n + ' debe estar entre 1 y 4094.');
      } else if (vlansLan[vlan]) {
        add('error', 'VLAN_LAN' + n,
          'VLAN_LAN' + n + ' (' + vlan + ') se repite con VLAN_LAN' + vlansLan[vlan] + '.');
      } else {
        vlansLan[vlan] = n;
      }

      if (!e['NAME_LAN' + n]) {
        add('aviso', 'NAME_LAN' + n, 'NAME_LAN' + n + ' está vacío.');
      }
      if (gw === null) {
        add('error', 'LAN' + n + '_GW', 'LAN' + n + '_GW no es una IPv4 válida.');
      }
      if (prefijo === null) {
        add('error', 'LAN' + n + '_MASK',
          'LAN' + n + '_MASK debe ser 24, /24 o una máscara IPv4 contigua (ej. 255.255.255.0).');
      } else if (prefijo < 8 || prefijo > 30) {
        add('error', 'LAN' + n + '_MASK', 'LAN' + n + '_MASK debe estar entre /8 y /30.');
      } else if (prefijo !== MASCARAS_ESPERADAS[n]) {
        add('aviso', 'LAN' + n + '_MASK',
          etiqueta + ' usa /' + prefijo + '; la máscara esperada es /' +
          MASCARAS_ESPERADAS[n] + '.');
      }
      if (offPrin === null || offSec === null) {
        add('error', 'LAN' + n + '_OFF', 'Los desplazamientos de ' + etiqueta + ' deben ser enteros.');
      }

      if (gw !== null && mascara !== null) {
        var red = (gw & mascara) >>> 0;
        var broadcast = (red | (~mascara)) >>> 0;
        var ipPrin = ipToInt(v['LAN' + n + '_IP_PRIN']);
        var ipSec = ipToInt(v['LAN' + n + '_IP_SEC']);
        redes.push({ n: n, red: red, prefijo: prefijo });

        [['PRIN', ipPrin], ['SEC', ipSec]].forEach(function (par) {
          var rol = par[0];
          var ip = par[1];
          if (ip === null) {
            add('error', 'LAN' + n + '_IP_' + rol,
              'LAN' + n + '_IP_' + rol + ' no se pudo calcular (revisar gateway/desplazamiento).');
            return;
          }
          if (((ip & mascara) >>> 0) !== red) {
            add('error', 'LAN' + n + '_IP_' + rol,
              'LAN' + n + '_IP_' + rol + ' (' + intToIp(ip) + ') queda fuera de la subred.');
          }
          if (ip === red || ip === broadcast) {
            add('error', 'LAN' + n + '_IP_' + rol,
              'LAN' + n + '_IP_' + rol + ' (' + intToIp(ip) + ') es red o broadcast.');
          }
          if (ip === gw) {
            add('error', 'LAN' + n + '_IP_' + rol,
              'LAN' + n + '_IP_' + rol + ' coincide con el VIP VRRP.');
          }
        });
        if (ipPrin !== null && ipSec !== null && ipPrin === ipSec) {
          add('error', 'LAN' + n + '_IP',
            'LAN' + n + ': la IP del Principal y la del Secundario son iguales.');
        }
      }
    }

    if (lansActivas === 0) {
      add('error', 'LAN', 'Activa al menos una LAN (LAN1…LAN4) para generar la configuración.');
    }

    // Subredes LAN solapadas (aviso, no bloquea).
    for (var i = 0; i < redes.length; i++) {
      for (var j = i + 1; j < redes.length; j++) {
        var a = redes[i];
        var b = redes[j];
        var m = prefixToMask(Math.min(a.prefijo, b.prefijo));
        if (m !== null && ((a.red & m) >>> 0) === ((b.red & m) >>> 0)) {
          add('aviso', 'LAN' + a.n,
            'Las subredes de LAN' + a.n + ' y LAN' + b.n + ' se solapan.');
        }
      }
    }

    // Switch opcional.
    if (e.incluir_switch) {
      if (!e.SW_NAME) add('aviso', 'SW_NAME', 'El switch está incluido pero SW_NAME está vacío.');
      if (!e.SW_IP) {
        add('aviso', 'SW_IP', 'El switch está incluido pero SW_IP está vacío.');
      } else if (!esIpValida(e.SW_IP)) {
        add('aviso', 'SW_IP', 'SW_IP no es una IPv4 válida.');
      }
    }

    return avisos;
  }

  function vlanValida(valor) {
    var n = aEntero(valor);
    return n !== null && n >= 1 && n <= 4094;
  }

  /* ------------------------------------------------------------------ */
  /* Autocompletar LANs desde "display ip interface brief"               */
  /* ------------------------------------------------------------------ */

  // Parsea líneas tipo:
  //   GigabitEthernet0/0/4.10   172.22.89.254/24  up  up
  //   Vlanif10                  172.22.46.254/24  up  up
  //   vlan1020                  172.26.65.194     255.255.255.192  up up up
  // La IP puede venir con /prefijo o seguida de una máscara IPv4.
  // Devuelve { filas, errores, advertencias }.
  function parsearInterfaces(texto) {
    var filas = [];
    var errores = [];
    var advertencias = [];
    var lineas = String(texto === null || texto === undefined ? '' : texto).split(/\r?\n/);

    lineas.forEach(function (linea, indice) {
      var t = linea.trim();
      if (!t) return;
      if (/^Interface\b/i.test(t) || /^[-=]+$/.test(t)) return;
      if (/\bunassigned\b/i.test(t)) return;

      var m = t.match(
        /^(\S+)\s+(\d{1,3}(?:\.\d{1,3}){3})(?:\s*\/\s*(\d{1,2})\b|\s+(\d{1,3}(?:\.\d{1,3}){3})\b)/
      );
      if (!m) {
        errores.push({
          linea: indice + 1,
          texto: t,
          mensaje: 'No se reconoció "interfaz IP/prefijo" ni "interfaz IP máscara".'
        });
        return;
      }

      var interfaz = m[1];
      var ip = m[2];
      var ipInt = ipToInt(ip);
      if (ipInt === null) {
        errores.push({ linea: indice + 1, texto: t, mensaje: 'La IPv4 no es válida.' });
        return;
      }

      var prefijo;
      if (m[3] !== undefined) {
        prefijo = Number(m[3]);
        if (prefijo > 32) {
          errores.push({ linea: indice + 1, texto: t, mensaje: 'El prefijo debe estar entre 0 y 32.' });
          return;
        }
      } else {
        var mascaraDatos = parsearMascara(m[4]);
        if (mascaraDatos === null) {
          errores.push({
            linea: indice + 1,
            texto: t,
            mensaje: 'La máscara IPv4 no es una máscara contigua.'
          });
          return;
        }
        prefijo = mascaraDatos.prefijo;
      }

      var vlan = null;
      var mVlan = interfaz.match(/^Vlan(?:if)?\s*(\d+)$/i);
      if (mVlan) {
        vlan = Number(mVlan[1]);
      } else {
        var mSub = interfaz.match(/\.(\d+)$/);
        if (mSub) vlan = Number(mSub[1]);
      }

      var mascaraInt = prefixToMask(prefijo);
      var redInt = (ipInt & mascaraInt) >>> 0;
      var broadcastInt = (redInt | (~mascaraInt)) >>> 0;

      var fila = {
        linea: indice + 1,
        interfaz: interfaz,
        vlan: vlan,
        ip: ip,
        prefijo: prefijo,
        mascara: intToIp(mascaraInt),
        red: intToIp(redInt),
        broadcast: intToIp(broadcastInt),
        wildcard: intToIp(maskToWildcard(mascaraInt))
      };

      if (prefijo < 8 || prefijo > 30) {
        advertencias.push({
          linea: indice + 1,
          texto: t,
          mensaje: 'El prefijo /' + prefijo + ' está fuera del rango LAN /8–/30.'
        });
      }
      if (vlan === null) {
        advertencias.push({
          linea: indice + 1,
          texto: t,
          mensaje: 'No se detectó VLAN en la interfaz; se conservará la VLAN actual de la LAN.'
        });
      }
      filas.push(fila);
    });

    // VLAN repetidas.
    var porVlan = {};
    filas.forEach(function (fila) {
      if (fila.vlan === null) return;
      if (porVlan[fila.vlan]) {
        fila.duplicada = true;
        advertencias.push({
          linea: fila.linea,
          texto: fila.interfaz,
          mensaje: 'La VLAN ' + fila.vlan + ' aparece más de una vez.'
        });
      } else {
        porVlan[fila.vlan] = fila;
      }
    });

    return { filas: filas, errores: errores, advertencias: advertencias };
  }

  // Asigna las filas a LAN1…LAN4: primero por VLAN coincidente y luego por
  // orden en las LAN libres. Devuelve copias con la propiedad "lan".
  function sugerirAsignacion(filas, entrada) {
    var e = entrada || {};
    var usadas = {};
    var resultado = (filas || []).map(function (fila) {
      var copia = {};
      Object.keys(fila).forEach(function (k) { copia[k] = fila[k]; });
      copia.lan = null;
      return copia;
    });

    resultado.forEach(function (fila) {
      if (fila.vlan === null) return;
      for (var n = 1; n <= 4; n++) {
        if (usadas[n]) continue;
        if (String(e['VLAN_LAN' + n] || '').trim() === String(fila.vlan)) {
          fila.lan = n;
          usadas[n] = true;
          return;
        }
      }
    });

    resultado.forEach(function (fila) {
      if (fila.lan !== null) return;
      for (var n = 1; n <= 4; n++) {
        if (!usadas[n]) {
          fila.lan = n;
          usadas[n] = true;
          return;
        }
      }
    });

    return resultado;
  }

  /* ------------------------------------------------------------------ */
  /* Construcción de los scripts                                         */
  /* ------------------------------------------------------------------ */

  // Bloques de cada router. La clave coincide con el nombre del archivo
  // de plantilla: <rol>_<clave>.txt
  var BLOQUES = [
    { n: 1, clave: '1_GESTION_Y_PUERTOS', titulo: '1 · Gestión y Puertos' },
    { n: 2, clave: '2_POLITICAS_Y_ENRUTAMIENTO', titulo: '2 · Políticas y Enrutamiento' },
    { n: 3, clave: '3_INTEGRACION', titulo: '3 · Integración' },
    { n: 4, clave: '4_VERIFICACION', titulo: '4 · Verificación' }
  ];

  var ROLES = [
    { id: 'principal', etiqueta: 'Principal', sufijo: 'Principal' },
    { id: 'contingencia', etiqueta: 'Contingencia', sufijo: 'Contingencia' }
  ];

  // Genera todos los bloques a partir de la entrada y del conjunto de plantillas.
  // El parámetro "plantillas" permite en el futuro elegir otro perfil
  // (marca/topología/enlace) sin tocar la interfaz.
  function buildScripts(entradaCruda, plantillas, opciones) {
    var e = normalizarEntrada(entradaCruda);
    var vars = deriveVars(e);
    var avisos = validar(e, vars);
    var bloques = {};
    var faltantesGlobal = [];

    function acumular(lista) {
      (lista || []).forEach(function (x) {
        if (faltantesGlobal.indexOf(x) === -1) faltantesGlobal.push(x);
      });
    }

    function renderConCondicionales(plantilla) {
      var cond = aplicarCondicionales(plantilla, vars);
      var res = renderTemplate(cond.texto, vars);
      if (cond.errores.length) {
        res.faltantes = res.faltantes.concat(cond.errores.map(function (x) {
          return 'CONDICIONAL:' + x;
        }));
        res.ok = false;
      }
      return res;
    }

    ROLES.forEach(function (rol) {
      bloques[rol.id] = {};
      BLOQUES.forEach(function (b) {
        var clave = rol.id + '_' + b.clave;
        var plantilla = plantillas ? plantillas[clave] : undefined;
        var res;
        if (plantilla === undefined) {
          res = { texto: '', faltantes: ['PLANTILLA:' + clave], ok: false };
        } else {
          res = renderConCondicionales(plantilla);
        }
        acumular(res.faltantes);
        bloques[rol.id][b.n] = {
          n: b.n,
          titulo: b.titulo,
          clave: clave,
          archivo: 'rCAC_' + (e.CAC || 'CAC') + '_' + rol.sufijo + '_' + b.clave + '.txt',
          texto: res.texto,
          faltantes: res.faltantes,
          ok: res.ok && plantilla !== undefined,
          lineas: contarLineas(res.texto)
        };
      });
    });

    // Switch Juniper (opcional). El nombre y la IP solo van como encabezado.
    var switchScript = null;
    if (e.incluir_switch) {
      var plantillaSwitch = plantillas ? plantillas['switch_juniper'] : undefined;
      var resSwitch = plantillaSwitch === undefined
        ? { texto: '', faltantes: ['PLANTILLA:switch_juniper'], ok: false }
        : renderConCondicionales(plantillaSwitch);
      acumular(resSwitch.faltantes);
      var encabezado =
        '# Switch: ' + (e.SW_NAME || '(sin nombre)') + '\n' +
        '# IP de gestión: ' + (e.SW_IP || '(sin IP)') + '\n\n';
      switchScript = {
        titulo: 'Switch Juniper',
        clave: 'switch_juniper',
        archivo: 'switch_' + (e.SW_NAME || e.CAC || 'CAC') + '.txt',
        texto: encabezado + resSwitch.texto,
        faltantes: resSwitch.faltantes,
        ok: resSwitch.ok && plantillaSwitch !== undefined,
        lineas: contarLineas(encabezado + resSwitch.texto)
      };
    }

    return {
      entrada: e,
      vars: vars,
      avisos: avisos,
      bloques: bloques,
      switch: switchScript,
      faltantes: faltantesGlobal,
      ok: faltantesGlobal.length === 0
    };
  }

  return {
    // IP
    ipToInt: ipToInt,
    intToIp: intToIp,
    prefixToMask: prefixToMask,
    parsearMascara: parsearMascara,
    maskToWildcard: maskToWildcard,
    esIpValida: esIpValida,
    // Entrada / derivadas
    normalizarEntrada: normalizarEntrada,
    deriveVars: deriveVars,
    // Render
    aplicarCondicionales: aplicarCondicionales,
    renderTemplate: renderTemplate,
    contarLineas: contarLineas,
    unirBloques: unirBloques,
    // Autocompletar LANs
    parsearInterfaces: parsearInterfaces,
    sugerirAsignacion: sugerirAsignacion,
    // Validación y construcción
    validar: validar,
    buildScripts: buildScripts,
    // Metadatos
    BLOQUES: BLOQUES,
    ROLES: ROLES,
    MASCARAS_ESPERADAS: MASCARAS_ESPERADAS
  };
});
