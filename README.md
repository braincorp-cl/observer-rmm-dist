# observer-rmm-dist

Plataforma Observer RMM — repo consolidado de BrainCorp: código de producto
(backend Django en `api/observerrmm/`, capa Go NATS, frontend Vue/Quasar en
`web/`) + despliegue con Ansible.

El despliegue reemplaza el script monolítico `install.sh` con 6 roles Ansible
independientes que soportan dos modos:

- **all-in-one**: todos los componentes en un único host. **Modo soportado y
  documentado hoy** (esta guía).
- **multi-host**: cada componente en su propio host. **Por hacer** — la topología
  está prevista en el playbook (`inventory/production.yml` es una plantilla), pero
  aún no está validada de punta a punta. No usar en producción todavía.

## Requisitos

- **Nodo de control** (la máquina desde donde ejecuta Ansible; puede ser su laptop):
  - ansible-core >= 2.15
  - Python 3.11+
  - Node.js 22.x + npm (el playbook compila el frontend SPA en el nodo de control)
  - `git`, acceso SSH al servidor
- **Servidor target**:
  - Ubuntu 22.04 LTS o 24.04 LTS, limpio (greenfield)
  - 2+ vCPU, 4+ GB RAM (8+ GB recomendado), 40+ GB disco
  - Acceso SSH con un usuario con `sudo`
  - Puertos 80 y 443 accesibles desde donde vivan los agentes/operadores
- **DNS**: un dominio bajo su control con registros apuntando al servidor (§5).

---

# Guía de instalación en producción — modo All-in-One

Instala **todos** los servicios (PostgreSQL 15, Redis, MeshCentral, API Django +
NATS + Celery, y nginx + TLS) en **un solo servidor**. Ansible se ejecuta desde su
nodo de control y se conecta por SSH al servidor.

> Convención de esta guía: el dominio de ejemplo es `ejemplo.cl`. Reemplácelo por su
> dominio real en todos los pasos.

## Paso 1 — Preparar el servidor target

1. Aprovisione una VM/servidor con **Ubuntu 22.04 LTS** (o 24.04) recién instalado.
2. Cree un usuario de despliegue con `sudo` (esta guía usa `observer`):
   ```bash
   sudo adduser observer
   sudo usermod -aG sudo observer
   ```
3. Habilite acceso SSH por clave para ese usuario (copie su clave pública):
   ```bash
   ssh-copy-id observer@<IP_DEL_SERVIDOR>
   ```
4. Verifique que puede entrar y usar sudo:
   ```bash
   ssh observer@<IP_DEL_SERVIDOR> "sudo -n true && echo OK || echo 'sudo pedirá password'"
   ```
   Si sudo pide password, más adelante ejecute el playbook con `-K`.

## Paso 2 — Preparar el nodo de control

```bash
# 1. Clonar el repo
git clone https://github.com/braincorp-cl/observer-rmm-dist.git
cd observer-rmm-dist

# 2. Instalar dependencias de Python y las colecciones de Ansible
pip install -r requirements.txt
ansible-galaxy collection install -r requirements.yml

# 3. Verificar que Node/npm están disponibles (el playbook compila el frontend aquí)
node --version   # referencia: v22.x
npm --version
```

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

    # Todos los servicios co-localizados → se hablan por loopback
    observer_db_host: localhost
    observer_redis_host: localhost
    observer_mesh_host: localhost
    observer_nats_host: 127.0.0.1

    # --- Dominios (REQUERIDOS) ---
    observer_domain: api.ejemplo.cl        # backend / API
    observer_app_domain: rmm.ejemplo.cl    # consola web (frontend SPA)
    observer_mesh_domain: mesh.ejemplo.cl  # MeshCentral (control remoto)
    observer_base_domain: ejemplo.cl       # dominio raíz (para el wildcard TLS)

    # --- TLS ---
    observer_cert_mode: acme               # 'acme' (wildcard vía DNS GoDaddy) o 'byo'
    observer_acme_email: ops@ejemplo.cl    # email de registro Let's Encrypt

    # --- URL ofuscada del panel /admin de Django (estable por instalación) ---
    # Genere una vez con:  openssl rand -hex 20
    observer_admin_url: "CAMBIE_ESTO_por_una_cadena_aleatoria_larga"

    # --- Tuning de PostgreSQL para una VM chica (~4 GB) ---
    # Si el servidor es grande y dedicado a la BD, suba estos valores.
    pg_vm_nr_hugepages: 0
    pg_huge_pages: "off"
    pg_shared_buffers: "256MB"
    pg_effective_cache_size: "1GB"
    pg_maintenance_work_mem: "64MB"
    pg_autovacuum_work_mem: "64MB"
    pg_min_wal_size: "128MB"
    pg_max_wal_size: "1GB"
    observer_db_max_connections: 100

  children:
    observer_db:
      hosts: { servidor: { ansible_host: <IP_DEL_SERVIDOR> } }
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
> el inventario `inventory/all-in-one.yml` que ya viene en el repo (usa conexión local).

## Paso 4 — Configurar DNS

Cree registros **A** apuntando a la IP pública del servidor:

| Registro          | Tipo | Valor            |
|-------------------|------|------------------|
| `api.ejemplo.cl`  | A    | `<IP_DEL_SERVIDOR>` |
| `rmm.ejemplo.cl`  | A    | `<IP_DEL_SERVIDOR>` |
| `mesh.ejemplo.cl` | A    | `<IP_DEL_SERVIDOR>` |

En modo TLS `acme` el certificado wildcard `*.ejemplo.cl` se emite por **DNS-01**
contra la API de GoDaddy, por lo que el dominio raíz `ejemplo.cl` debe estar
gestionado en GoDaddy. Espere a que el DNS propague antes del Paso 7.

## Paso 5 — Configurar TLS

- **`observer_cert_mode: acme`** (default, recomendado): acme.sh emite el wildcard
  `*.<observer_base_domain>` vía la API DNS de GoDaddy y configura la renovación
  automática por cron. Requiere las credenciales de GoDaddy en el vault del proxy
  (Paso 6). CA = Let's Encrypt.
- **`observer_cert_mode: byo`** (bring-your-own): usted aporta el certificado wildcard.
  Deje las credenciales de GoDaddy en `CHANGEME` y provea el cert/clave por su vía.

## Paso 6 — Configurar las credenciales (Ansible Vault)

Cada componente tiene una plantilla `vault.yml.example`. Cópielas a `vault.yml`,
reemplace los `CHANGEME` por valores reales y cifre todo con un único password de vault.

```bash
# 1. Copiar las plantillas
for c in observer_api observer_db observer_mesh observer_proxy observer_redis; do
  cp group_vars/$c/vault.yml.example group_vars/$c/vault.yml
done

# 2. Editar cada group_vars/<componente>/vault.yml y reemplazar los CHANGEME.
#    (ver la tabla de secretos más abajo)

# 3. Cifrar TODOS los vault con el mismo password (guárdelo bien: sin él no hay deploy)
ansible-vault encrypt group_vars/*/vault.yml
```

Secretos a definir:

| Archivo                              | Clave                            | Qué es |
|--------------------------------------|----------------------------------|--------|
| `observer_api/vault.yml`             | `vault_observer_admin_password`  | Password del usuario **`observeradmin`** (login web RMM) |
| `observer_api/vault.yml`             | `vault_django_secret_key`        | SECRET_KEY de Django (aleatoria, ≥50 chars) |
| `observer_db/vault.yml`              | `vault_observer_db_password`     | Password del rol PostgreSQL principal |
| `observer_db/vault.yml`              | `vault_observer_mesh_db_password`| Password del rol PostgreSQL de MeshCentral |
| `observer_mesh/vault.yml`            | `vault_observer_mesh_password`   | Password del usuario **`meshcentral_admin`** (admin de MeshCentral) |
| `observer_mesh/vault.yml`            | `vault_observer_mesh_db_password`| **Debe coincidir** con el de `observer_db` |
| `observer_redis/vault.yml`           | `vault_observer_redis_password`  | Password de Redis |
| `observer_proxy/vault.yml`           | `vault_godaddy_key` / `_secret`  | API de GoDaddy — **solo** en modo `acme` |

> ⚠️ Las claves `vault_observer_mesh_db_password` de `observer_db` y `observer_mesh`
> deben tener **exactamente el mismo valor**.

## Paso 7 — Ejecutar el playbook

```bash
ansible-playbook install.yml -i inventory/produccion.yml --ask-vault-pass
```

- Agregue `-K` si el usuario `observer` pide password para `sudo`.
- Ansible compila el frontend en el nodo de control y luego despliega los 6 roles en
  orden de dependencias. La primera corrida tarda varios minutos (compila Python desde
  fuente, instala PostgreSQL 15 PGDG, MeshCentral, etc.).
- El playbook es idempotente: puede volver a correrlo sin problema.

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

## Paso 9 — Verificación post-install

```bash
ansible-playbook healthcheck.yml -i inventory/produccion.yml --ask-vault-pass
```

Comprueba PostgreSQL, Redis, MeshCentral, el API y el proxy. Todo debe pasar.

## Paso 10 — Primer acceso

1. Abra `https://rmm.ejemplo.cl` e ingrese con `observeradmin` y su password.
2. Configure el **2FA (TOTP)** cuando se lo pida (obligatorio).
3. A `https://mesh.ejemplo.cl` puede entrar como `meshcentral_admin`, pero el control
   remoto desde la consola RMM (botón "Tomar control") funciona vía SSO sin login manual.

## Solución de problemas

- **`Se encontró 'CHANGEME' en ... vault`**: dejó placeholders sin reemplazar en algún
  `vault.yml`. Corríjalos y vuelva a cifrar.
- **Falla la emisión del certificado (modo acme)**: verifique `vault_godaddy_key/secret`,
  que `ejemplo.cl` esté en GoDaddy y que el DNS haya propagado. Puede subir
  `observer_acme_dnssleep` si la propagación es lenta.
- **`sudo: a password is required`**: reejecute con `-K`.
- **Reejecutar solo el resumen de credenciales**:
  `ansible-playbook install.yml -i inventory/produccion.yml --ask-vault-pass --tags access_summary`

---

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
