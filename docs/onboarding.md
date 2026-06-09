# Onboarding — Observer RMM Distributed

## 1. Prerrequisitos

- **Nodo de control** (donde se ejecuta Ansible): Python 3.11+, acceso SSH a los hosts target
- **Hosts target**: Ubuntu 22.04 LTS (primario) o Ubuntu 24.04 LTS. Debian NO soportado.
- **DNS o /etc/hosts**: los hosts deben resolverse entre sí por nombre o IP
- **Acceso SSH con clave pública** instalada en todos los hosts target con usuario `observer`

```bash
pip install -r requirements.txt
ansible-galaxy collection install -r requirements.yml
```

---

## 2. Configurar credenciales (vault)

```bash
# 1. Crear archivo de password del vault (NO commitear)
echo "mi-password-segura" > ~/.vault_pass
chmod 600 ~/.vault_pass

# 2. Editar los vault.yml con credenciales reales
# Descomentar y rellenar las variables en cada archivo:
# - group_vars/observer_db/vault.yml
# - group_vars/observer_redis/vault.yml
# - group_vars/observer_mesh/vault.yml
# - group_vars/observer_api/vault.yml
# - group_vars/observer_proxy/vault.yml

# 3. Cifrar todos los vault.yml
ansible-vault encrypt group_vars/*/vault.yml --vault-password-file ~/.vault_pass

# Guardar la password del vault en Vaultwarden (MINSAL)
```

---

## 3. Primer deploy — all-in-one (dev/staging, ~30 min)

Despliega todos los componentes en un único host local.

```bash
# Editar observer_domain en group_vars/all.yml
# Ejemplo: observer_domain: "rmm.lab.braincorp.cl"

ansible-playbook install.yml \
  -i inventory/all-in-one.yml \
  --vault-password-file ~/.vault_pass

# Verificar
ansible-playbook healthcheck.yml \
  -i inventory/all-in-one.yml \
  --vault-password-file ~/.vault_pass
```

---

## 4. Primer deploy — multi-host (producción, ~60 min)

```bash
# 1. Editar inventory/production.yml con las IPs reales de los 4 hosts

# 2. Editar group_vars/all.yml:
#    observer_domain: "rmm.braincorp.cl"

# 3. Verificar conectividad SSH a todos los hosts
ansible all -i inventory/production.yml -m ping --vault-password-file ~/.vault_pass

# 4. Desplegar
ansible-playbook install.yml \
  -i inventory/production.yml \
  --vault-password-file ~/.vault_pass

# 5. Verificar
ansible-playbook healthcheck.yml \
  -i inventory/production.yml \
  --vault-password-file ~/.vault_pass
```

---

## 5. Troubleshooting

| Síntoma | Causa probable | Solución |
|---------|---------------|---------|
| `UNREACHABLE! => {"msg": "Failed to connect to the host"}` | SSH no configurado | `ssh-copy-id observer@<ip>` |
| `FAILED! => {"msg": "Decryption failed"}` | Vault password incorrecta | Verificar `~/.vault_pass` |
| `Error: pg_hba.conf: no pg_hba.conf entry for host` | IP no incluida en `observer_db_allowed_hosts` | Agregar IP del API en `group_vars/observer_db.yml` |
| `uwsgi: error loading plugin` | Python venv no creado | Revisar log de T014 en `/opt/observer/logs/` |
| `[Errno 111] Connection refused` en API | rmm.service no arrancó | `systemctl status rmm` en el host observer_api |
| `CHANGEME found in vault` | Vault sin configurar | Editar y cifrar todos los `vault.yml` antes de desplegar |
