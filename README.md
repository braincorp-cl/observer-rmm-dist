# observer-rmm-dist

Plataforma Observer RMM — despliegue distribuido con Ansible.

Reemplaza el script monolítico `install.sh` con 6 roles Ansible independientes que soportan:

- **all-in-one**: todos los componentes en un único host (dev/staging)
- **multi-host**: cada componente en su propio host (producción)

## Requisitos

- ansible-core >= 2.15
- Python 3.11+ en el nodo de control
- Ubuntu 22.04 LTS o 24.04 LTS en los hosts target

## Inicio rápido

```bash
pip install -r requirements.txt
ansible-galaxy collection install -r requirements.yml
cp group_vars/observer_api/vault.yml.example group_vars/observer_api/vault.yml
# Editar vault.yml con valores reales y cifrar:
ansible-vault encrypt group_vars/*/vault.yml
ansible-playbook install.yml -i inventory/all-in-one.yml --ask-vault-pass
```

Ver `docs/onboarding.md` para instrucciones completas.

## Arquitectura

Ver `docs/architecture.md`.

## Componentes

| Rol | Host | Servicios |
|-----|------|-----------|
| `observer_common` | todos | usuario, ufw, dependencias |
| `observer_db` | observer_db | PostgreSQL 18 |
| `observer_redis` | observer_redis | Redis |
| `observer_mesh` | observer_mesh | MeshCentral |
| `observer_api` | observer_api | Django, Celery, NATS |
| `observer_proxy` | observer_proxy | nginx, SSL |
