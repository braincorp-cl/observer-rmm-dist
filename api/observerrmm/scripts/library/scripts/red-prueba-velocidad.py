#!/usr/bin/env python3
"""Mide latencia, variacion (jitter) y, si se le da una URL, ancho de banda de bajada.

Reemplaza los tres scripts distintos del catalogo original (uno con una libreria de
Python externa, uno en PowerShell y uno que descargaba iperf desde internet) por una
unica medicion que no instala nada y corre igual en las tres plataformas.

Que mide SIEMPRE, sin depender de nada externo: la latencia del camino real entre el
equipo y la infraestructura de ObserverRMM, abriendo varias conexiones TCP al host de
la API que el propio agente tiene configurado. Reporta minimo, mediana, maximo y
variacion, porque un promedio esconde justo lo que se siente como tirones en
escritorio remoto y cortes en llamadas.

Que mide SOLO si se le pasa una URL: el ancho de banda de bajada. No hay una URL por
defecto a proposito - no existe un archivo grande, estable y sin autenticacion en la
infraestructura del producto contra el cual medir, y clavar el de un tercero volveria
a meter la dependencia externa que este script vino a sacar. Pasale la URL de un
asset de release del CDN, o de cualquier archivo bajo control del cliente.

Uso:
    red-prueba-velocidad.py [URL_de_descarga] [MiB_maximos]

Ejemplos:
    red-prueba-velocidad.py
    red-prueba-velocidad.py https://agents.observer.cl/releases/download/v2.15.0/observeragent-linux-amd64
    red-prueba-velocidad.py https://ejemplo.cl/archivo.bin 25

Sale con 1 si no logra medir la latencia (host inalcanzable).
"""

import json
import platform
import socket
import ssl
import sys
import time

# El agente pasa el stdout por strings.ToValidUTF8(s, "") (agent/utils.go:401), que BORRA
# toda secuencia UTF-8 invalida. En Windows el Python embebido escribe stdout en cp1252
# (medido en un Windows 11 real: sys.stdout.encoding == "cp1252"), donde un acento es un
# solo byte que no es UTF-8 valido => los acentos desaparecian de la salida sin dejar
# rastro. En Linux y macOS stdout ya es UTF-8 y esto es un no-op.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


ES_WINDOWS = platform.system() == "Windows"

CLAVE_REGISTRO = r"SOFTWARE\ObserverRMM"
CONFIG_UNIX = "/etc/observeragent"

MIB = 1024 * 1024
MIB_POR_DEFECTO = 10
MIB_MAXIMO = 200
INTENTOS_LATENCIA = 8
TIEMPO_ESPERA = 20
UMBRAL_JITTER_MS = 100


def leer_host_api():
    """Host de la API segun la configuracion del agente."""
    if ES_WINDOWS:
        try:
            import winreg

            clave = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, CLAVE_REGISTRO)
            valor = winreg.QueryValueEx(clave, "ApiURL")[0]
            clave.Close()
            return str(valor).strip()
        except Exception:
            return None

    try:
        with open(CONFIG_UNIX, "r") as archivo:
            crudo = json.load(archivo)
    except Exception:
        return None
    for clave, valor in crudo.items():
        if str(clave).lower() == "apiurl":
            return str(valor).strip()
    return None


def medir_latencia(anfitrion, puerto=443):
    muestras = []
    for _ in range(INTENTOS_LATENCIA):
        inicio = time.time()
        try:
            conexion = socket.create_connection((anfitrion, puerto), TIEMPO_ESPERA)
            conexion.close()
        except Exception:
            continue
        muestras.append((time.time() - inicio) * 1000)
        # Sin pausa las mediciones se apilan y el resultado sale optimista.
        time.sleep(0.2)
    return muestras


def mediana(valores):
    ordenados = sorted(valores)
    medio = len(ordenados) // 2
    if len(ordenados) % 2 == 1:
        return ordenados[medio]
    return (ordenados[medio - 1] + ordenados[medio]) / 2.0


def partir_url(url):
    """Devuelve (anfitrion, puerto, ruta, es_tls) sin usar urllib.

    urllib arrastra los proxies del entorno y sigue redirecciones, y aca lo que
    interesa es cronometrar el socket, no reproducir un navegador.
    """
    resto = url
    es_tls = True
    if resto.startswith("https://"):
        resto = resto[len("https://") :]
    elif resto.startswith("http://"):
        resto = resto[len("http://") :]
        es_tls = False
    else:
        return None

    if "/" in resto:
        autoridad, ruta = resto.split("/", 1)
        ruta = "/" + ruta
    else:
        autoridad, ruta = resto, "/"

    puerto = 443 if es_tls else 80
    if ":" in autoridad:
        autoridad, puerto_texto = autoridad.rsplit(":", 1)
        try:
            puerto = int(puerto_texto)
        except ValueError:
            return None

    if not autoridad:
        return None
    return autoridad, puerto, ruta, es_tls


def descargar(url, bytes_maximos):
    """Descarga hasta `bytes_maximos` y devuelve (bytes_leidos, segundos, estado)."""
    partes = partir_url(url)
    if partes is None:
        return 0, 0, "la URL no es valida (debe empezar con http:// o https://)"
    anfitrion, puerto, ruta, es_tls = partes

    try:
        conexion = socket.create_connection((anfitrion, puerto), TIEMPO_ESPERA)
    except Exception as error:
        return 0, 0, "no se pudo conectar a {}:{} ({})".format(anfitrion, puerto, error)

    if es_tls:
        try:
            contexto = ssl.create_default_context()
            conexion = contexto.wrap_socket(conexion, server_hostname=anfitrion)
        except Exception as error:
            conexion.close()
            return 0, 0, "fallo TLS con {} ({})".format(anfitrion, error)

    try:
        peticion = (
            "GET {} HTTP/1.1\r\n"
            "Host: {}\r\n"
            "User-Agent: ObserverRMM-PruebaDeEnlace\r\n"
            # identity: sin esto el servidor puede comprimir y la cifra medida
            # dejaria de ser el ancho de banda real del enlace.
            "Accept-Encoding: identity\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).format(ruta, anfitrion)
        conexion.sendall(peticion.encode("ascii"))

        # Se leen las cabeceras aparte para no contarlas como payload y para poder
        # detectar un 401/404, que de otro modo se mediria como "descarga exitosa"
        # de unos pocos cientos de bytes.
        cabeceras = b""
        while b"\r\n\r\n" not in cabeceras:
            trozo = conexion.recv(1)
            if not trozo:
                break
            cabeceras += trozo
            if len(cabeceras) > 65536:
                break

        primera = cabeceras.split(b"\r\n", 1)[0].decode("ascii", "replace")
        if " 200 " not in primera:
            return 0, 0, "el servidor respondio: {}".format(primera.strip())

        leidos = 0
        inicio = time.time()
        limite = inicio + TIEMPO_ESPERA
        while leidos < bytes_maximos and time.time() < limite:
            trozo = conexion.recv(65536)
            if not trozo:
                break
            leidos += len(trozo)
        transcurrido = time.time() - inicio

        if leidos == 0:
            return 0, 0, "el servidor respondio 200 pero no envio cuerpo"
        return leidos, transcurrido, "ok"
    except Exception as error:
        return 0, 0, "error durante la descarga ({})".format(error)
    finally:
        try:
            conexion.close()
        except Exception:
            pass


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else None
    mib = MIB_POR_DEFECTO
    if len(sys.argv) > 2:
        try:
            mib = int(sys.argv[2])
        except ValueError:
            print("El segundo argumento debe ser un numero de MiB:", sys.argv[2])
            return 1
        mib = max(1, min(mib, MIB_MAXIMO))

    anfitrion = leer_host_api()
    if not anfitrion:
        print("No se pudo leer el host de la API desde la configuracion del agente.")
        print("Sin ese dato no hay contra que medir la latencia.")
        return 1

    print("Prueba de enlace - {}".format(platform.node()))
    print("  sistema: {} {}".format(platform.system(), platform.release()))
    print("  destino: {} (host de la API del agente)".format(anfitrion))

    print("")
    print("== Latencia (TCP 443, {} intentos) ==".format(INTENTOS_LATENCIA))
    muestras = medir_latencia(anfitrion)
    if not muestras:
        print(
            "  Sin respuesta: {} no es alcanzable en el puerto 443.".format(anfitrion)
        )
        return 1

    variacion = max(muestras) - min(muestras)
    print("  minimo:    {:.1f} ms".format(min(muestras)))
    print("  mediana:   {:.1f} ms".format(mediana(muestras)))
    print("  maximo:    {:.1f} ms".format(max(muestras)))
    print("  variacion: {:.1f} ms".format(variacion))
    print(
        "  perdidas:  {} de {}".format(
            INTENTOS_LATENCIA - len(muestras), INTENTOS_LATENCIA
        )
    )

    if variacion > UMBRAL_JITTER_MS:
        print("")
        print("  AVISO: variacion alta. Es lo que se siente como tirones en escritorio")
        print("         remoto y cortes en llamadas, aunque el ancho de banda de bien.")

    print("")
    print("== Bajada ==")
    if not url:
        print("  No se midio: no se paso una URL de descarga.")
        print("  Pasale como primer argumento la URL de un archivo grande -por")
        print("  ejemplo un asset de release del CDN- para medir el ancho de banda.")
    else:
        print("  origen: {}".format(url))
        leidos, transcurrido, estado = descargar(url, mib * MIB)
        if estado != "ok" or transcurrido <= 0:
            print("  No se pudo medir: {}".format(estado))
        else:
            megabits = (leidos * 8) / 1000000.0
            mbps = megabits / transcurrido
            print("  descargado: {:.2f} MiB".format(leidos / float(MIB)))
            print("  tiempo:     {:.2f} s".format(transcurrido))
            print("  velocidad:  {:.2f} Mbps".format(mbps))
            if leidos < mib * MIB:
                print("  Nota: el archivo era mas chico que el limite pedido, asi que")
                print("  la cifra sale de una transferencia corta y es menos estable.")
            print("")
            print("BAJADA_MBPS={:.2f}".format(mbps))

    print("")
    print("LATENCIA_MS={:.1f}".format(mediana(muestras)))
    print("JITTER_MS={:.1f}".format(variacion))
    return 0


if __name__ == "__main__":
    sys.exit(main())
