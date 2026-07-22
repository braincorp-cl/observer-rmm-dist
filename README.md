# observer-rmm-dist

Plataforma Observer RMM — repo consolidado de BrainCorp: código de producto
(backend Django en `api/observerrmm/`, capa Go NATS, frontend Vue/Quasar en
`web/`) + despliegue con Ansible.

**Versión actual: 1.4.1** · [Releases](https://github.com/braincorp-cl/observer-rmm-dist/releases) · [Agente](https://github.com/braincorp-cl/observer-agent-dist/releases) (v2.10.8)

El despliegue reemplaza el script monolítico `install.sh` con 6 roles Ansible
independientes que soportan dos modos:

- **all-in-one**: todos los componentes en un único host. **Modo soportado y
  documentado hoy** (esta guía).
- **multi-host**: cada componente en su propio host. **Por hacer** — la topología
  está prevista en el playbook (`inventory/production.yml` es una plantilla), pero
  aún no está validada de punta a punta. No usar en producción todavía.

## Requisitos

- **Nodo de control** (la máquina desde donde ejecuta Ansible; puede ser su laptop):
  - ansible-core **>= 2.18** (lo exige la colección `community.general` incluida)
  - Python 3.11+ — en Kali/Debian/Ubuntu recientes instale dentro de un **venv**
    (PEP 668; ver Paso 2)
  - Node.js 22.x + npm (el playbook compila el frontend SPA en el nodo de control)
  - `git`, acceso SSH al servidor
- **Servidor target**:
  - Ubuntu 22.04 LTS o 24.04 LTS, limpio (greenfield)
  - 2+ vCPU, 4+ GB RAM (8+ GB recomendado), 40+ GB disco
  - Acceso SSH con un usuario con `sudo`
  - Puertos 80 y 443 accesibles desde donde vivan los agentes/operadores
- **DNS**: registros de los 3 FQDN apuntando al servidor (§4). Puede ser DNS **interno**
  (split-horizon); en modo `acme` solo el **dominio raíz** debe estar en GoDaddy, y
  únicamente para el desafío DNS-01 (§5).

---

# Guía de instalación en producción — modo All-in-One

Instala **todos** los servicios (PostgreSQL 15, Redis, MeshCentral, API Django +
NATS + Celery, y nginx + TLS) en **un solo servidor**. Ansible se ejecuta desde su
nodo de control y se conecta por SSH al servidor.

> Convención de esta guía: el dominio de ejemplo es `ejemplo.cl`. Reemplácelo por su
> dominio real en todos los pasos.

## Paso 1 — Preparar el servidor target

1. **Instale Ubuntu 22.04 LTS** (o 24.04) recién instalado. Selecciones recomendadas
   del instalador:
   - **Idioma (Language):** English
   - **Keyboard layout / variant:** Spanish (Latin American)
   - **Tipo de instalación:** Ubuntu Server (minimized)
   - **Install OpenSSH Server:** sí

2. **Tras el primer boot**, fije la zona horaria:
   ```bash
   sudo timedatectl set-timezone America/Santiago   # ajuste a su zona
   ```

3. Actualice repositorios e instale los paquetes base del administrador:
   ```bash
   sudo apt update
   sudo apt install -y \
     dialog vim tasksel apt-utils logrotate net-tools iputils-ping \
     bind9-dnsutils procps psmisc bash-completion plocate \
     curl wget traceroute sosreport lsof rsync
   ```

4. **Solo si es una VM sobre vSphere**, instale VMware Tools:
   ```bash
   sudo apt install -y open-vm-tools
   sudo systemctl enable --now open-vm-tools
   ```

5. Actualice todo el sistema:
   ```bash
   sudo apt upgrade -y
   ```

6. Para que el instalador (Ansible) corra sin pedir password, deje el grupo `sudo`
   con `NOPASSWD:ALL` en `/etc/sudoers` (edite con `sudo visudo`):
   ```bash
   sudo grep '^%sudo' /etc/sudoers
   # %sudo   ALL=(ALL:ALL) NOPASSWD:ALL
   ```
   > Alternativa más restrictiva: dejar el sudo con password y ejecutar el playbook
   > con `-K`. El `NOPASSWD` simplifica el greenfield; puede endurecerlo tras el install.

7. Cree el usuario que ejecuta los servicios (esta guía usa `observer`):
   ```bash
   sudo useradd -G sudo -c "Observer RMM User" -m -d /home/observer -s /bin/bash observer
   sudo passwd observer
   ```

8. Registre los 3 FQDN del ambiente en `/etc/hosts` (resolución local por loopback).
   Con el dominio de ejemplo `ejemplo.cl` y los FQDN `rmm.` / `mesh.` / `api.ejemplo.cl`,
   reemplace la línea de `127.0.1.1` (deje el hostname del host al inicio):
   ```bash
   # antes:
   127.0.1.1 <hostname>
   # después:
   127.0.1.1 <hostname> rmm.ejemplo.cl mesh.ejemplo.cl api.ejemplo.cl
   ```

9. Reinicie para cargar el sistema parchado:
   ```bash
   sudo shutdown -r now
   ```

> El acceso SSH por clave desde el nodo de control (`ssh-keygen` + `ssh-copy-id`) se
> configura en el **Paso 2**.

## Paso 2 — Preparar el nodo de control

Todo esto ocurre en **el equipo del técnico** (control-plane).

**2.a — Acceso SSH por clave al servidor** (preparado en el Paso 1):

```bash
# Genere una llave si no tiene (ejemplo RSA):
ssh-keygen -t rsa -b 2048

# Copie la llave pública al usuario 'observer' del servidor:
ssh-copy-id observer@<IP_DEL_SERVIDOR>

# Verifique acceso + sudo sin password (debe imprimir OK):
ssh observer@<IP_DEL_SERVIDOR> "sudo -n true && echo OK || echo 'sudo pedirá password'"
```

**2.b — Clon dedicado + dependencias.** Use un **clon dedicado por ambiente** (no
reutilice el checkout de dev/staging para producción): así cada ambiente tiene su propio
inventario, vault y `.vault_pass`, y no hay riesgo de disparar el playbook contra el
inventario equivocado.

```bash
# 1. Clonar el repo en una ruta dedicada al ambiente
git clone https://github.com/braincorp-cl/observer-rmm-dist.git
cd observer-rmm-dist

# 2. Crear un venv e instalar las dependencias de Python.
#    En Kali/Debian/Ubuntu recientes el pip "a sistema" falla con
#    'externally-managed-environment' (PEP 668) → el venv es la vía soportada.
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Instalar las colecciones de Ansible
ansible-galaxy collection install -r requirements.yml

# 4. Verificar el toolchain (el frontend SPA se compila en el nodo de control)
ansible --version   # ansible-core >= 2.18
node --version      # referencia: v22.x
npm --version
```

> Reactive el venv (`source .venv/bin/activate`) en cada shell nueva antes de correr
> Ansible para este ambiente. Si el prompt no muestra `(.venv)`, está usando el ansible
> del sistema.

## Paso 3 — Configurar el inventario

Cree el archivo `inventory/produccion.yml` con el contenido de abajo. En All-in-One
los cinco grupos apuntan al **mismo** host; entre sí los servicios se hablan por
loopback dentro del servidor.

```yaml
---
# inventory/produccion.yml — All-in-One sobre un único servidor vía SSH
all:
  vars:
    ansible_user: observer
    ansible_python_interpreter: /usr/bin/python3

    # --- Dominios (REQUERIDOS) ---
    observer_domain: api.ejemplo.cl        # backend / API
    observer_app_domain: rmm.ejemplo.cl    # consola web (frontend SPA)
    observer_mesh_domain: mesh.ejemplo.cl  # MeshCentral (control remoto)
    observer_base_domain: ejemplo.cl       # dominio raíz (para el wildcard TLS)

    # --- TLS ---
    observer_cert_mode: acme               # 'acme' (wildcard vía DNS GoDaddy) o 'byo'
    observer_acme_email: ops@ejemplo.cl    # email de registro Let's Encrypt

    # (La URL ofuscada del panel /admin de Django la genera el playbook automáticamente
    #  en la primera corrida — ya no se define aquí; ver Paso 6.)

    # --- Proxy reverso corporativo delante de nginx (OPCIONAL) ---
    # Descomente SOLO si publica detrás de un proxy reverso (ej. Nginx Proxy Manager).
    # Activa el módulo real_ip para que los logs/auditoría registren la IP real del
    # cliente (no la del proxy) e ignora X-Forwarded-For spoofeado. Ponga la IP LAN del
    # proxy. Acepta un valor o una lista. Ver sección "Publicación tras NPM" más abajo.
    # observer_trusted_proxy_ip: "10.20.0.254"

    # --- Tuning de PostgreSQL — AJUSTAR A LA RAM DEL SERVIDOR ---
    # El sizing dependiente de RAM se define AQUÍ (en el inventario), NO en group_vars.
    # Regla: shared_buffers ~15-25% de RAM; effective_cache_size ~50-75% de RAM. En
    # all-in-one PG convive con Mesh/API/Redis/NATS → no le dé el 25% completo.
    # (Ejemplo abajo dimensionado para un servidor de ~16 GB.)
    pg_shared_buffers: "2GB"
    pg_effective_cache_size: "6GB"
    pg_maintenance_work_mem: "256MB"
    pg_autovacuum_work_mem: "256MB"
    pg_min_wal_size: "512MB"
    pg_max_wal_size: "2GB"
    observer_db_max_connections: 100
    # HugePages (recomendado si hay RAM): el rol DERIVA nr_hugepages de shared_buffers
    # y las reserva en dos capas — sysctl (runtime, best-effort) + grub (boot-time,
    # robusto). NO fije pg_vm_nr_hugepages a mano. Tras el primer deploy con HugePages,
    # REINICIE el servidor (Paso 8b) para que la reserva boot-time quede firme: el
    # runtime puede quedar parcial por fragmentación de memoria.
    # Para NO usar HugePages:  pg_huge_pages: "off"
    pg_huge_pages: "try"

  children:
    # En All-in-One los 5 grupos apuntan al MISMO host. La topología de conexión
    # (todo por loopback) va como HOST-VARS de 'servidor', NO en all.vars: así le gana
    # en precedencia a la expresión dinámica multi-host de los group_vars. Si fuera en
    # all.vars, group_vars la pisaría y observer_db_host resolvería a la IP del host →
    # rompería la conexión (pg_hba solo permite loopback).
    observer_db:
      hosts:
        servidor:
          ansible_host: <IP_DEL_SERVIDOR>
          observer_db_host: localhost
          observer_redis_host: localhost
          observer_mesh_host: localhost
          observer_nats_host: 127.0.0.1
    observer_redis:
      hosts: { servidor: { ansible_host: <IP_DEL_SERVIDOR> } }
    observer_mesh:
      hosts: { servidor: { ansible_host: <IP_DEL_SERVIDOR> } }
    observer_api:
      hosts: { servidor: { ansible_host: <IP_DEL_SERVIDOR> } }
    observer_proxy:
      hosts: { servidor: { ansible_host: <IP_DEL_SERVIDOR> } }
```

> ¿Ejecuta Ansible **en el propio servidor** (no desde un control node separado)? Use
> el inventario `inventory/all-in-one.yml` que ya viene en el repo (usa conexión local
> y no necesita el pin de host-vars de arriba).

## Paso 4 — Configurar DNS

Cree registros **A** de los 3 FQDN apuntando a la IP del servidor. Sirve DNS público o
**interno** (split-horizon); no hace falta que resuelvan públicamente para que el RMM
funcione — solo que los agentes/operadores los resuelvan a la IP del servidor.

| Registro          | Tipo | Valor            |
|-------------------|------|------------------|
| `api.ejemplo.cl`  | A    | `<IP_DEL_SERVIDOR>` |
| `rmm.ejemplo.cl`  | A    | `<IP_DEL_SERVIDOR>` |
| `mesh.ejemplo.cl` | A    | `<IP_DEL_SERVIDOR>` |

En modo TLS `acme` el certificado wildcard `*.ejemplo.cl` se emite por **DNS-01** contra
la API de GoDaddy: para eso el **dominio raíz `ejemplo.cl` debe estar gestionado en
GoDaddy** (el TXT `_acme-challenge` se crea ahí). Esto es independiente de dónde vivan
los registros A (pueden estar en el DNS interno).

## Paso 5 — Configurar TLS

- **`observer_cert_mode: acme`** (default, recomendado): acme.sh emite el wildcard
  `*.<observer_base_domain>` vía la API DNS de GoDaddy y configura la renovación
  automática por cron. Requiere las credenciales de GoDaddy en el vault del proxy
  (Paso 6). CA = Let's Encrypt.
- **`observer_cert_mode: byo`** (bring-your-own): usted aporta el certificado wildcard.
  Deje las credenciales de GoDaddy en `CHANGEME` y provea el cert/clave por su vía.

## Paso 6 — Configurar las credenciales (Ansible Vault)

El playbook **genera y cifra automáticamente** todas las contraseñas de los componentes
en la primera corrida (con `secrets.SystemRandom`) y las reutiliza idempotentemente en
las siguientes. Usted **no** define contraseñas a mano. Lo único que ingresa el humano
son las credenciales de **GoDaddy** (necesarias solo en modo TLS `acme`).

> Corra todo esto desde el clon del ambiente **con el venv activo** (`ansible-vault` vive
> en él): `cd <clon-del-ambiente> && source .venv/bin/activate`. Si el prompt no muestra
> `(.venv)`, actívelo antes de continuar.

```bash
# 1. Definir el password de vault del ambiente en .vault_pass (gitignorado). GUÁRDELO en
#    su gestor: es la ÚNICA copia y sin él no se descifra ni se despliega nada. El playbook
#    lo usa para cifrar/descifrar todos los vault.yml.
openssl rand -base64 32 > .vault_pass && chmod 600 .vault_pass

# 2. Poner las credenciales de GoDaddy (solo en modo acme). Copie la plantilla y edite
#    vault_godaddy_key / vault_godaddy_secret con su API key/secret real
#    (https://developer.godaddy.com/keys). El playbook lo cifra por usted si lo deja en claro.
cp group_vars/observer_proxy/vault.yml.example group_vars/observer_proxy/vault.yml
$EDITOR group_vars/observer_proxy/vault.yml
```

Eso es todo lo que hace el humano. Al ejecutar el playbook (Paso 7):

- Genera y cifra `group_vars/observer_api/vault.yml`, `observer_db/vault.yml` y
  `observer_mesh/vault.yml` con contraseñas aleatorias fuertes (incluida la `observer_admin_url`
  ofuscada del panel /admin de Django). La contraseña de la BD de MeshCentral se genera una
  vez y se escribe idéntica en `observer_db` y `observer_mesh`.
- Cifra `group_vars/observer_proxy/vault.yml` (GoDaddy) si lo dejó en claro.
- Al terminar imprime en claro, en el **Resumen de acceso** (Paso 8), las contraseñas de
  `observeradmin` (consola RMM) y `meshcentral_admin` (MeshCentral) para el primer login.

| Secreto | Origen |
|---|---|
| `vault_observer_admin_password` (login `observeradmin`) | **autogenerado** — se muestra al final |
| `vault_django_secret_key` | **autogenerado** |
| `observer_admin_url` (ruta ofuscada de `/admin`) | **autogenerado** |
| `vault_observer_db_password` | **autogenerado** |
| `vault_observer_mesh_db_password` (db↔mesh, idénticas) | **autogenerado** |
| `vault_observer_mesh_password` (login `meshcentral_admin`) | **autogenerado** — se muestra al final |
| `vault_godaddy_key` / `vault_godaddy_secret` | **humano** (solo modo `acme`) |

> **Rotar contraseñas:** borre `group_vars/observer_api/vault.yml`,
> `group_vars/observer_db/vault.yml` y `group_vars/observer_mesh/vault.yml`, y vuelva a
> ejecutar el playbook (regenerará credenciales nuevas). En modo `byo` (usted aporta el
> certificado) puede omitir por completo el Paso 2 de GoDaddy.

## Paso 7 — Ejecutar el playbook

```bash
ansible-playbook install.yml -i inventory/produccion.yml
```

- Con `.vault_pass` presente (Paso 6) **no** necesita `--ask-vault-pass` (lo toma de
  `ansible.cfg`). Agregue `-K` si el usuario `observer` pide password para `sudo`.
- Ansible compila el frontend en el nodo de control y luego despliega los 6 roles en
  orden de dependencias. La primera corrida tarda varios minutos (compila Python desde
  fuente, instala PostgreSQL 15 PGDG, MeshCentral, etc.).
- El playbook es idempotente: puede volver a correrlo sin problema.
- Al terminar, revise el **PLAY RECAP**: debe decir `failed=0`. (Si envuelve el comando
  en un script, capture el exit de `ansible-playbook`, no el del wrapper.)

## Paso 8 — Anotar las credenciales de acceso

Al terminar, el playbook imprime un **Resumen de acceso** con las URLs y las
credenciales iniciales en claro (replica el cierre del `install.sh` original):

```
============================================================
  Observer RMM — instalación completa
============================================================
  Consola RMM (web):   https://rmm.ejemplo.cl
  API backend:         https://api.ejemplo.cl
  MeshCentral:         https://mesh.ejemplo.cl
------------------------------------------------------------
  Consola RMM  (https://rmm.ejemplo.cl)
    usuario:  observeradmin
    password: <su vault_observer_admin_password>
    (se le pedirá configurar 2FA/TOTP en el primer login web)

  MeshCentral  (https://mesh.ejemplo.cl)
    usuario:  meshcentral_admin
    password: <su vault_observer_mesh_password>
============================================================
```

> 🔐 Guarde estas credenciales en un gestor seguro y **limpie la salida del terminal**
> después de leerlas. Son las mismas que definió en el vault; se muestran una vez para
> comodidad del primer acceso.

## Paso 8b — Reinicio para HugePages boot-time (si activó HugePages)

Si dejó `pg_huge_pages: "try"`, **reinicie el servidor una vez** tras el primer deploy:

```bash
ssh observer@<IP_DEL_SERVIDOR> sudo reboot
```

Esto activa la reserva de HugePages en el **arranque** (vía el drop-in de grub que
escribió el rol), que es la forma robusta: el kernel las aparta antes del userspace,
sin depender de encontrar memoria contigua en runtime. Hasta el reboot rige solo la
reserva runtime (sysctl), que en pools grandes puede quedar **parcial** por
fragmentación. Verifique tras el reboot:

```bash
ssh observer@<IP_DEL_SERVIDOR> 'grep -o "hugepages=[0-9]*" /proc/cmdline; \
  grep HugePages_Total /proc/meminfo; systemctl is-active postgresql@15-main'
```

Debe verse `hugepages=<N>` en el cmdline, `HugePages_Total = <N>` y PostgreSQL `active`.

## Paso 9 — Verificación post-install

```bash
ansible-playbook healthcheck.yml -i inventory/produccion.yml
```

Comprueba PostgreSQL, Redis, MeshCentral, el API y el proxy. Todo debe pasar (`failed=0`).

## Paso 10 — Primer acceso

1. Abra `https://rmm.ejemplo.cl` e ingrese con `observeradmin` y su password.
2. Configure el **2FA (TOTP)** cuando se lo pida (obligatorio).
3. A `https://mesh.ejemplo.cl` puede entrar como `meshcentral_admin`, pero el control
   remoto desde la consola RMM (botón "Tomar control") funciona vía SSO sin login manual.

## Publicación tras un proxy reverso corporativo (NPM double-proxy)

Si no expone el servidor directo a Internet sino detrás de un proxy reverso (aquí, **Nginx
Proxy Manager**), Observer sigue **terminando su propio TLS** en el servidor (no lo
desactive) y el proxy hace **re-encrypt** hacia él por HTTPS. Así el servidor queda
publicable directo a futuro sin rehacer nada. Cadena:

```
Internet ──HTTPS(cert del NPM)──► NPM ──HTTPS(cert wildcard de Observer)──► servidor:443
```

### Un Proxy Host por FQDN (los 3 apuntan al servidor, puerto 443)

| Campo | `rmm.ejemplo.cl` (consola) | `api.ejemplo.cl` (API) | `mesh.ejemplo.cl` (MeshCentral) |
|---|---|---|---|
| Scheme | https | https | https |
| Forward Hostname | el **FQDN** (no la IP) | el **FQDN** | el **FQDN** |
| Forward Port | 443 | 443 | 443 |
| Block Common Exploits | ON | ON | ON |
| **Websockets Support** | ON | **ON** | **ON** |
| SSL | cert LE propio del NPM (puede ser multi-dominio api+rmm+mesh) | idem | idem |

**Custom Nginx Configuration** por host (alta carga / sesiones largas):

- `api.*` — `client_max_body_size 300m;` `proxy_read_timeout 86400;` `proxy_send_timeout 86400;`
- `mesh.*` — `proxy_read_timeout 86400;` `proxy_send_timeout 86400;`
- `rmm.*` — nada extra.

### Gotchas verificados (no saltárselos)

1. **DNS interno en el NPM (crítico).** El NPM debe resolver `rmm/api/mesh.ejemplo.cl` a la
   IP LAN del servidor (split-horizon o `/etc/hosts` del NPM). Si resuelve el DNS público
   apunta **a sí mismo → loop**. Con el FQDN resuelto a la IP interna, el SNI matchea el
   wildcard y el cert valida limpio (no necesita "Ignore invalid SSL").
2. **`client_max_body_size` en el NPM.** Su default (~1M) es menor que los 300M del API →
   sin el override, subidas/exports grandes dan **413** en el borde.
3. **Timeouts de WebSocket.** El toggle "Websockets Support" arma los headers Upgrade, pero
   el `proxy_read_timeout` default (~60s) corta las sesiones largas → el "Tomar control" de
   Mesh y el realtime del dashboard se caen. De ahí los `86400`.
4. **NO poner `X-Frame-Options`/`Content-Security-Policy: frame-ancestors` en el host
   `mesh.*`.** La consola embebe MeshCentral en un `<iframe>` (Tomar control / WebVNC /
   Remote Background) desde `rmm.*` (otro origen) → esos headers **bloquean** el control
   remoto. En `rmm.*`/`api.*` sí puede dejarlos.
5. **No hace falta copiar certificados al NPM.** El servidor ya sirve un wildcard Let's
   Encrypt público-confiable; el NPM lo valida al re-encriptar. (Si algún día necesita los
   `.pem` sueltos —`cert.pem`/`chain.pem`— el rol ya los deja en `/etc/ssl/observer/`.)

### IP real del cliente en los logs (anti-spoofing) — `observer_trusted_proxy_ip`

Tras el proxy, el backend vería la IP del proxy como origen. Para que los logs, la
auditoría y el throttling registren la **IP real del cliente**, defina en el inventario la
IP LAN del proxy:

```yaml
# inventory/produccion.yml → all.vars
observer_trusted_proxy_ip: "10.20.0.254"     # IP LAN del NPM (o lista: ["10.20.0.254", ...])
```

Esto activa el módulo `real_ip` de nginx confiando **solo** en esa IP: reescribe
`$remote_addr` con la IP real del cliente (tomada de `X-Forwarded-For`) e **ignora un
`X-Forwarded-For` spoofeado** por clientes no confiables. Vacío (default) = sin proxy,
comportamiento intacto. Es a nivel `http`, aplica a los 3 vhosts. Reejecute el playbook
(o `--tags` del proxy) para regenerar `/etc/nginx/nginx.conf`.

### Cómo verificar que `real_ip` funciona (probado en producción)

Los clientes en la **LAN/VPN** resuelven los FQDN por DNS interno **directo al servidor** —
no pasan por el NPM—, así que para ejercitar el proxy hay que acceder **desde fuera de la
red** (p. ej. datos móviles del celular). Cargue la consola por la URL pública y revise
`/var/log/nginx/access.log` en el servidor: debe aparecer la **IP pública real del cliente**,
no la IP del NPM. Verificado end-to-end en producción:

- **HTTP** — `GET /`, `/v2/login/`, `/core/dashinfo/` quedaron registrados con la IP pública
  real del cliente externo (no la del proxy); el login completo funciona a través del doble proxy.
- **WebSocket** — `/ws/dashinfo/` registrado con la IP real y handshake `101 Switching
  Protocols` → el realtime del dashboard funciona E2E por el doble proxy. La línea del WS se
  escribe al **cerrar** la conexión (es de larga vida, `proxy_read_timeout 86400`), no al
  abrirla; mientras está abierta se ve viva con `ss -tn state established '( sport = :443 )'`
  (conexión desde la IP del NPM) y `ss -xn | grep daphne.sock`.

El acceso directo LAN/VPN queda intacto: `real_ip` solo reescribe conexiones que llegan
**desde** la IP del proxy declarada.

## Solución de problemas

- **`Se encontró 'CHANGEME' en ... vault`**: dejó placeholders sin reemplazar en algún
  `vault.yml`. Corríjalos y vuelva a cifrar.
- **PostgreSQL no arranca / `could not map anonymous shared memory: Cannot allocate memory`**:
  `pg_shared_buffers` (o un `pg_vm_nr_hugepages` fijado a mano) excede la RAM del host.
  Baje `pg_shared_buffers` en el **inventario** (nunca lo fije en group_vars) y reejecute.
- **HugePages no se reservan tras cambiar el tamaño**: reinicie el servidor (Paso 8b);
  el runtime (sysctl) puede no encontrar memoria contigua, el boot-time (grub) sí.
- **Falla la emisión del certificado (modo acme)**: verifique `vault_godaddy_key/secret`,
  que `ejemplo.cl` esté en GoDaddy y que el DNS haya propagado. Puede subir
  `observer_acme_dnssleep` si la propagación es lenta.
- **`sudo: a password is required`**: reejecute con `-K`.
- **Reejecutar solo el resumen de credenciales**:
  `ansible-playbook install.yml -i inventory/produccion.yml --tags access_summary`

---

## Notas sobre `group_vars` (importante si edita la configuración)

- Cada grupo tiene un directorio `group_vars/<grupo>/` con `vars.yml` (config no
  secreta) y `vault.yml` (secretos, gitignorado). **No** cree un archivo hermano
  `group_vars/<grupo>.yml`: si coexiste con el directorio, Ansible carga el directorio
  e **ignora el `.yml`** (la config quedaría muerta y regirían los defaults del rol).
- El **sizing de PostgreSQL dependiente de la RAM** (shared_buffers, effective_cache_size,
  max_connections, work_mem de mantenimiento, WAL) va en el **inventario** por ambiente,
  no en `group_vars/observer_db/vars.yml` (que solo trae parámetros independientes de la
  RAM). Así un host chico no hereda un sizing pensado para uno grande.
- Los **intervalos de check-in** (`group_vars/observer_api/vars.yml`) traen un perfil
  genérico de flota chica/media; para flotas muy grandes, súbalos overrideando en el
  inventario. Regla dura: `SYNCMESH >= 3600`.

## Modo multi-host (por hacer)

Cada componente en su propio host, para escalar horizontalmente. La estructura existe
(`inventory/production.yml` es una plantilla de referencia), pero **aún no está validada
de punta a punta**. Se documentará cuando se certifique. Por ahora use All-in-One.

## Arquitectura

Ver [`docs/architecture.md`](docs/architecture.md).

## Componentes

| Rol | Grupo | Servicios |
|-----|-------|-----------|
| `observer_common` | todos | usuario, ufw, dependencias |
| `observer_db` | observer_db | PostgreSQL 15 (PGDG) |
| `observer_redis` | observer_redis | Redis |
| `observer_mesh` | observer_mesh | MeshCentral |
| `observer_api` | observer_api | Django, Celery, NATS |
| `observer_proxy` | observer_proxy | nginx, SSL |

## Procedencia

El código de producto se consolida desde los forks de trabajo de BrainCorp
mediante commits squash sin historia derivada. El agente multiplataforma NO
vive en este repo (se distribuye como binarios de release del repo
`observer-agent`). Tabla de procedencia por componente, confianzas Reversa y
detalles en [`docs/PROVENANCE.md`](docs/PROVENANCE.md).
