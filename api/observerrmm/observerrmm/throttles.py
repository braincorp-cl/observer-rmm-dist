from rest_framework.throttling import AnonRateThrottle


class CheckCredsMinThrottle(AnonRateThrottle):
    scope = "check_creds_min"


class CheckCredsDayThrottle(AnonRateThrottle):
    scope = "check_creds_day"


class LoginMinThrottle(AnonRateThrottle):
    scope = "login_min"


class LoginDayThrottle(AnonRateThrottle):
    scope = "login_day"


# Portal público de verificación de certificados (053 ola 4). AnonRateThrottle
# cuenta por IP del anónimo, que es exactamente el sujeto acá: el endpoint no
# tiene usuarios. 🔑 El límite NO es la defensa principal contra la enumeración
# de identificadores: lo son los 40 bits de `new_certificate_id()` y el contrato
# mínimo de la respuesta, que vuelve inútil un acierto.
class VerifyMinThrottle(AnonRateThrottle):
    scope = "verify_min"


class VerifyDayThrottle(AnonRateThrottle):
    scope = "verify_day"
