# Changelog — Observer RMM

Notas de versión del producto Observer RMM. Es la **fuente de verdad**: el sitio
público `https://agents.observer.cl/changelog/` se genera a partir de este archivo
en cada push a `main` (workflow `publish-changelog.yml`). La consola enlaza aquí
desde el aviso de "versión disponible" (`MainLayout.vue`, ancla `#v{versión}`).

Formato de cada entrada: `## vX.Y.Z — YYYY-MM-DD` (el token `vX.Y.Z` se usa tal cual
como ancla HTML `id`, así que debe coincidir con `ORMM_VERSION`). Viñetas con `-`.

## v1.4.16 — 2026-08-26

- **Nuevo módulo Observer Erase: certificados de borrado y custodia de activos.** El producto ahora emite y conserva **certificados de borrado** —de destrucción remota o de destrucción física— y lleva el registro de ingreso de los equipos que entran a proceso de baja. Es la base para poder demostrar, con un documento verificable, que un equipo fue dado de baja como corresponde.
- **Certificados a prueba de manipulación.** Cada certificado se guarda en un repositorio de sólo-escritura, encadenado por hash: una vez emitido no se modifica ni se elimina, y si alguien alterara o borrara un registro intermedio, la cadena se rompe y queda en evidencia. La evidencia sobrevive al borrado del equipo.
- **Firma y verificación.** Cada certificado se firma criptográficamente y la consola verifica, al abrirlo, que el documento esté íntegro, que la firma sea válida y que la cadena no esté rota. La clave de firma vive fuera de la aplicación y el esquema queda listo para firma electrónica avanzada.
- **Reportería y descargas.** Una vista dedicada lista los certificados por cliente, con filtro por tipo y búsqueda, y permite descargar cada uno en **PDF** y **JSON**. En la ficha de cada equipo aparece además una pestaña propia con sus certificados de borrado, en cualquier plataforma.
- **Custodia de activos y destrucción física.** Un formulario formaliza el ingreso del equipo a baja (cadena de custodia) y, desde ahí, se emite el certificado de destrucción física. Un equipo no funcional o sin medio detectable se enruta directo a destrucción física.
- **Gobernanza del borrado con doble confirmación.** Las órdenes de borrado exigen la confirmación de **dos personas distintas** y abren una **ventana de arrepentimiento** cancelable, con cuenta regresiva. En esta versión el borrado destructivo del equipo sigue **deshabilitado** a la espera de la aprobación legal correspondiente: la consola gobierna y audita las órdenes, pero no se envía ninguna acción destructiva al equipo.
- **Permisos separados.** Se agregan tres permisos independientes —ordenar borrado (desactivado por omisión), ver certificados y gestionar ingresos de activos—, para que ver la evidencia no implique poder ordenar un borrado.
- **Sin cambios de agente en esta versión.** Todo lo anterior es del servidor y la consola; la flota sigue con el agente `v2.17.1` y no necesita actualizarse por este release.

## v1.4.15 — 2026-08-23

- **Un equipo que sale de su zona autorizada se mantiene despierto solo.** Cuando un equipo cruza fuera de su geocerca, el servidor le indica que no se suspenda ni hiberne, para que siga reportando ubicación y estado mientras esté fuera; al volver a la zona, se restaura el comportamiento normal de energía. La decisión de "está fuera" la toma el servidor a partir de la geocerca, no el equipo por su cuenta.
- **Línea base de "no dormir" configurable por equipo.** Un nuevo control permite fijar que ciertos equipos no se suspendan como estado de base —independiente de cualquier caso—, para que estén disponibles para medición y respuesta. Se activa desde la ficha del equipo y se revierte de forma limpia al desinstalar el agente.
- **Reconexión por redes WiFi abiertas.** Para no perder de vista un equipo que quedó sin conexión, el agente puede reconectarse por redes WiFi abiertas y resolver portales cautivos, y así volver a reportar. Está gobernado por un interruptor global (viene activado y se puede desactivar) y queda descrito en la política de uso aceptable.
- **La ficha del caso perdido ahora muestra el estado de cifrado del equipo.** Al abrir un caso de equipo perdido o robado, la ficha reporta si el disco está cifrado —reutilizando el mismo veredicto del panel de cifrado—, sin activar ni cambiar nada: es sólo información para decidir el curso del caso.
- Acompaña al **agente 2.17.1**, que ejecuta la no-suspensión por geocerca, la reconexión por WiFi y la no-suspensión reactiva del modo perdido en Windows, Linux y macOS. Contra un agente anterior, el servidor sigue calculando la geocerca y abriendo casos igual, pero las acciones nuevas en el equipo no se aplican hasta que actualice.

## v1.4.14 — 2026-08-20

- **Cascada automática de contramedidas al marcar un equipo perdido o robado.** Marcar un equipo ya no es sólo "empezar a mirar dónde está": según la configuración, encadena solo el bloqueo de pantalla, el encendido de la cámara, la no-hibernación del equipo y —si se pidió— la alarma. Antes esas acciones se disparaban a mano, una por una, desde otra pantalla.
- **Configuración en tres niveles con precedencia clara.** Cada contramedida se decide en el nivel **global** (Configuración), **por equipo** (la ficha del equipo) o **por caso** (el diálogo de marcar). La precedencia es *caso > equipo > global*, y cada control tiene tres estados —Heredar, Activar, Desactivar—; la ficha muestra qué valor se hereda hoy, así que "Heredar" nunca es una caja negra.
- **Bloqueo silencioso y diferido.** El bloqueo de pantalla espera una ventana configurable mientras se recolecta evidencia y recién entonces bloquea; recuperar el equipo dentro de esa ventana lo cancela. Un `0` bloquea de inmediato.
- **Override de cámara por caso.** Un equipo perdido puede forzar la captura de cámara aunque el interruptor global esté apagado. Vale sólo dentro del caso activo y queda auditado con el motivo del marcaje.
- **No-hibernación con revert limpio (Windows).** Mientras el equipo está perdido se evita que se suspenda o hiberne; al recuperar, el esquema de energía vuelve exactamente al que tenía antes. Ninguna contramedida queda pegada tras la recuperación.
- **Todo queda en la auditoría.** Cada cascada disparada se registra con la configuración resuelta —qué se encendió sobre la persona que tiene el equipo— junto al motivo del caso y a quién lo marcó.
- Acompaña al **agente 2.16.0**, que ejecuta las contramedidas en el equipo (bloqueo diferido, cámara y no-hibernación en Windows). Contra un agente anterior, el marcaje abre el caso y recolecta evidencia igual, pero las contramedidas nuevas no se aplican hasta que el equipo actualice. La cascada de bloqueo y no-hibernación es sólo Windows en esta versión.

## v1.4.13 — 2026-08-18

- **Nuevo panel de cifrado de disco para la flota Windows.** Una vista dedicada muestra, equipo por equipo, si el disco del sistema está cifrado con BitLocker. Se filtra por estado, por cliente y por sitio, así que ver "cuántos equipos de este cliente están sin cifrar" es una sola pantalla en lugar de una auditoría manual.
- **Cuatro estados que no se confunden.** El panel distingue *cifrado*, *sin cifrar*, *no compatible* y *sin dato*, cada uno con su color. Un equipo del que todavía no hay lectura **no** aparece como incumplidor: "sin dato" y "sin cifrar" son cosas distintas, y mezclarlas marcaría como riesgo a un equipo del que simplemente no se sabe nada aún.
- **Detalle por equipo, dentro de su ficha.** En la pestaña de activos, cada equipo Windows suma el estado de cifrado **por volumen** —método, porcentaje, protección y tipo de protectores—, la fecha de la última medición y el historial de cambios, para leer no sólo *cómo está* sino *desde cuándo*.
- **Botón para volver a medir.** Pide al equipo una lectura nueva del estado de cifrado; si está fuera de línea, la consola lo avisa y no manda el comando en vano. El dato se actualiza cuando el equipo vuelve a reportar.
- **Sin exponer material sensible.** El producto guarda y muestra el *estado* del cifrado —cantidad y tipo de protectores—, nunca claves ni contraseñas de recuperación.
- Acompaña al **agente 2.15.33**. Contra un agente anterior, el estado de cifrado aparece como "sin dato" hasta que el equipo actualice; el resto del producto se comporta igual que en la 1.4.12.

## v1.4.12 — 2026-08-16

- **El modo perdido ya captura la pantalla en Linux con Wayland (GNOME y KDE).** En los escritorios modernos, un caso no lograba sacar la captura de pantalla aunque el equipo lo permitía: la imagen se tomaba pero se daba por perdida. Con el **agente 2.15.28** eso queda resuelto, y en KDE se acabó además la falsa «pantalla en negro» que se leía como avería. La foto de cámara ya funcionaba antes; ahora la pantalla también.
- **«Tomar control» vuelve a funcionar en los Linux virtualizados.** El control remoto del escritorio fallaba en equipos Linux sobre VMware por un permiso que el servicio del Mesh no necesitaba y que el hipervisor rechazaba. Se le retira ese permiso en toda la flota Linux y el control remoto se restablece.
- **macOS: la línea de tiempo dice por qué no hay foto de cámara.** Cuando la cámara del Mac no entrega imagen, el caso ahora muestra el motivo en vez de dejar un hueco, igual que ya hacía con la pantalla.
- **Nuevo motivo en la cronología del caso: «pantalla bloqueada».** Si el equipo tenía la sesión bloqueada al intentar la captura, el caso lo registra como tal —un dato del caso— en lugar de reportarlo como un fallo.
- **Nuevo script en la biblioteca para endurecer el servicio de control remoto** en la flota Linux, con su verificación posterior.
- **Mayor fidelidad en el estado de cifrado de disco que reportan los equipos**, al corregir unos valores de respaldo que habían quedado rezagados.
- Acompaña al **agente 2.15.28**. Contra un agente anterior, el producto se comporta igual que en la 1.4.11.

## v1.4.11 — 2026-08-14

- **Un caso de modo perdido se puede exportar a PDF.** Desde la pantalla del caso sale un informe que se lee **sin la consola al lado**: portada con el equipo, el motivo, quién lo marcó y la política de retención vigente; el recorrido y la cronología completa; y las imágenes **dentro del documento**, no como enlaces que a quien lo reciba le pedirían iniciar sesión. Es el formato que sirve para una denuncia, un sumario interno o un seguro.
- **La cronología del informe imprime los dos relojes:** la hora del equipo y la del servidor. Entre las dos puede haber horas de diferencia si el equipo estuvo sin red, y en un documento que puede terminar ante un tercero esa diferencia es justo lo que alguien va a preguntar.
- **Quien opera el caso puede exportarlo aunque no tenga permiso para ver los rostros.** Exportar exige el permiso de gestionar el modo perdido; el de ver la evidencia decide **otra cosa**: si el PDF lleva o no las imágenes. Cuando no las lleva, **el documento lo declara en la portada** — un informe incompleto que no lo dice es un informe engañoso. Cada exportación queda en la auditoría.
- **Las acciones de respuesta, a mano en la pantalla de equipos perdidos.** Cada fila suma un menú con bloquear el equipo, mandarle un mensaje, hacer sonar la alarma, detenerla y exportar el caso. Son las mismas acciones que ya existían en el listado general: quien está operando un caso deja de tener que ir a buscar el equipo a otra pantalla.
- **El instalador de macOS avisa de los permisos que van a pedirse.** Le dice a quien instala que no cierre la sesión todavía y que hay dos solicitudes que hay que aceptar, porque después **no se pueden conceder a distancia**.
- **Nueva página pública de uso aceptable y privacidad** en la documentación, con las reglas de uso del modo perdido y de la evidencia que genera.
- Acompaña al **agente 2.15.20**, que en macOS pide por su cuenta los permisos que el sistema le quita en cada actualización, y en Linux con **Wayland** vuelve a poder capturar la pantalla. Contra un agente anterior, el producto funciona igual que en la 1.4.10.

## v1.4.10 — 2026-08-13

- **El modo perdido ahora saca una foto de la cámara del equipo.** Junto a la captura de pantalla, cada ciclo de un caso puede sumar una foto de quién tiene el equipo delante, y la línea de tiempo la muestra como una segunda miniatura. Disponible en **Windows y Linux**; en macOS queda a la espera del permiso del sistema, que no se puede conceder a distancia.
- **Nace apagada de fábrica.** Fotografiar la cara de una persona es más sensible que ubicar un activo, así que actualizar el producto no la enciende: hay un interruptor global en Configuración que hay que activar a propósito. Con él apagado, ningún equipo de la flota toma fotos.
- **El LED de la cámara se enciende, y el producto no lo oculta.** En la mayoría de los equipos el LED está cableado al sensor y ninguna aplicación puede apagarlo. La foto nunca es invisible; prometer lo contrario sería, además de indebido, algo que el hardware no permite cumplir.
- **Una foto en negro no se guarda como si fuera evidencia.** La tapa puesta o el cuarto a oscuras dan una imagen negra, y el agente la descarta con su motivo en vez de subirla —igual que ya hace con la pantalla—. En Windows funciona sin ninguna herramienta extra; en Linux usa `fswebcam` o `ffmpeg` si están instalados, y si no, el caso lo dice.
- **La foto hereda el cifrado y el plazo de borrado** de la evidencia del caso, sin nada que configurar aparte: se guarda cifrada en el servidor y se borra sola con los mismos plazos que la captura de pantalla.
- Corregido: el interruptor de la foto de cámara **se aplica al instante**, también al apagarlo. Antes, apagarlo durante un caso abierto no detenía las fotos hasta el siguiente reinicio del agente.
- Acompaña al **agente 2.15.17**, que es quien toma la foto. Contra un servidor anterior, el agente sigue funcionando igual que la 2.15.16.

## v1.4.9 — 2026-08-12

- **La evidencia del modo perdido ahora se borra sola.** Las capturas y los puntos de un caso se eliminan a los **90 días**, y también unos días después de marcar el equipo como recuperado —lo que ocurra primero—. Deja de ser una tarea que alguien tenga que acordarse de hacer: el servidor la corre por su cuenta, y **borra el archivo del disco además del registro**, que es la parte que no se ve desde la consola y la que de verdad importa.
- **Dos plazos configurables, en Configuración global.** El de los 90 días admite entre 1 y 365 y **no se puede desactivar**: apagarlo dejaría un depósito de capturas de pantalla de personas creciendo sin fecha de término. El segundo es cuántos días sobrevive la evidencia después de cerrar el caso, con **7 por omisión** — la denuncia suele presentarse *después* de recuperar el equipo, y una evidencia que se evapora en la hora siguiente no serviría para presentarla. Ponerlo en 0 borra apenas se cierra el caso.
- **La evidencia se guarda cifrada en el servidor.** Cada instalación genera su propia llave al instalarse; quien lea el disco del servidor no ve las imágenes. Desde la consola no cambia nada: la miniatura y la descarga funcionan igual. Lo capturado **antes** de esta versión se sigue leyendo sin problemas.
- **La línea de tiempo del caso dice las dos cosas a la vista:** en cuántos días se borrará esa evidencia y si está cifrada. Un servidor que no la esté cifrando lo declara ahí, en vez de que se descubra el día que alguien mire el disco.
- Corregido: los archivos de evidencia de un equipo **eliminado** de la consola quedaban en el disco del servidor para siempre. Ahora se recogen con el mismo plazo que el resto.
- **No cambia la versión del agente**: la retención y el cifrado son enteramente del servidor. La flota sigue en la **2.15.16**.

## v1.4.8 — 2026-08-12

- **El modo perdido ahora ve la pantalla.** Mientras un equipo está marcado, cada ciclo junta su ubicación y una **captura de su pantalla**, y el caso las muestra juntas en una **línea de tiempo**: el recorrido en el mapa y, al lado, qué se estaba haciendo con el equipo en cada momento. La captura es silenciosa —no suena, no avisa, no deja ventanas a la vista— y sale de la sesión de la persona que tiene el equipo, que es la única forma de que la imagen no salga negra.
- **Ninguna captura en negro entra al caso.** El equipo mira la imagen antes de mandarla y, si está vacía, manda el motivo en su lugar: la pantalla estaba apagada, nadie había iniciado sesión, el permiso del sistema no está concedido. Un caso lleno de imágenes negras parece tener evidencia y no la tiene.
- **Ver la evidencia exige su propio permiso.** Seguir el recorrido de un equipo y mirar lo que su pantalla estaba mostrando son dos cosas distintas, y se conceden por separado. La evidencia se descarga desde la consola con la sesión del operador, nunca por un enlace que funcione para cualquiera que lo tenga.
- **La evidencia no se acumula en el equipo perdido:** la imagen se borra apenas se sube.
- La versión de agente que se ofrece a la flota pasa a la **2.15.16**, que es la que captura. Los equipos se actualizan solos al hacer check-in.
- ⚠️ **Pendiente y dicho a tiempo:** la evidencia todavía **no se borra sola a los 90 días** ni se guarda cifrada. Las dos cosas llegan en la etapa siguiente; hasta entonces, cerrar un caso viejo implica pedir el borrado de su evidencia.

## v1.4.7 — 2026-08-12

- ⚠️ **Corregido, y cambia la evidencia de un caso:** un equipo marcado como perdido que no lograba medir su posición **heredaba las coordenadas declaradas de su sitio**, así que el recorrido del caso lo mostraba sentado en la oficina mientras alguien se lo llevaba. Esa herencia existe para equipos estacionarios y ahí es correcta; en un equipo perdido es un dato falso, y un caso que puede terminar en una denuncia no puede llevar evidencia fabricada. Ahora, con el equipo marcado, se guarda la posición realmente medida —con su margen de error a la vista— o no se guarda ninguna.
- Corregido: el aviso de gobernanza del módulo **Equipos perdidos** quedaba ilegible con la interfaz en modo oscuro, y su texto citaba una referencia interna del proyecto. Se corrigió el contraste y se reescribió en el idioma del producto.
- La versión de agente que se ofrece a la flota pasa a la **2.15.15**, que corrige la demora en activar la ubicación intensiva al marcar un equipo encendido. Los equipos se actualizan solos al hacer check-in.

## v1.4.6 — 2026-08-11

- **Modo perdido/robado, primera etapa.** Un equipo se puede marcar como perdido desde la consola, con un **motivo obligatorio**, y sólo se apaga marcándolo como recuperado. Mientras está marcado, el equipo **reporta su ubicación con mucha más frecuencia** (de una vez cada media hora a una vez por minuto, configurable entre 1 y 60). Todavía **no** captura pantalla ni fotos: eso llega en la próxima etapa.
- El marcaje **funciona con el equipo apagado o sin red**: se aplica en cuanto vuelve a conectarse, sin depender de que el aviso lo haya alcanzado. Y **sobrevive a que lo reinicien** o a que le corten la energía, que es lo que suele pasar con un equipo robado.
- Módulo **"Equipos perdidos"** en la consola, con la lista de equipos marcados, desde cuándo, quién los marcó y con qué motivo.
- **Dos permisos nuevos y separados a propósito**: uno para operar el modo perdido y otro para ver la evidencia. Quien coordina la recuperación de un equipo no necesita ver lo que la cámara o la pantalla capturen.
- Marcar y recuperar **quedan en la auditoría** con el usuario, el motivo y la hora, incluso cuando el equipo no contesta. La entrada deja escrito de forma explícita que el marcaje **pasa por encima del interruptor global de geolocalización**.
- Cuatro **plantillas de scripts** nuevas para Linux y macOS.
- ⚠️ **Corregido:** con la geolocalización global apagada —que es como viene una instalación nueva— el equipo marcado como perdido reportaba su ubicación y **el servidor la descartaba**. El recorrido quedaba vacío justo en el caso para el que existe la función. Se detectó midiendo contra un equipo real, no en las pruebas.
- ⚠️ **Corregido:** el historial de ubicaciones de un equipo seguía siendo visible aunque la geolocalización global estuviera apagada. La posición actual sí se ocultaba; el recorrido completo, no.
- Corregido: al encender el equipo, el modo perdido tardaba **hasta media hora** en activarse pese a que el dato ya estaba disponible desde el primer segundo. Ahora se aplica en el arranque.
- Corregido: tras reiniciar el equipo, la ubicación volvía a reportarse a la frecuencia normal **hasta media hora**, en vez de retomar de inmediato la del caso.

## v1.4.5 — 2026-08-10

- El **modo mantenimiento** deja de ser invisible: un aviso permanente en el encabezado dice cuántos equipos están marcados y desde hace cuánto, con un botón que los lista en un clic. El aviso no se puede cerrar mientras haya equipos marcados.
- Cada equipo en mantenimiento muestra **desde cuándo y quién lo activó**, tanto en la lista como en su ficha. Los que ya estaban marcados desde antes de esta versión aparecen como "desconocido": el producto no inventa una fecha que no tiene.
- Activar o desactivar el modo mantenimiento **por cliente o por sitio queda registrado en la auditoría**, con el usuario, el alcance y los equipos afectados. Antes no dejaba ningún rastro.
- **Aviso por correo** cuando un equipo lleva demasiados días en mantenimiento. El umbral se configura en Configuración global (3 días por omisión) y se puede apagar. Se envía un solo aviso por equipo y por ventana.
- ⚠️ **Corregido, y cambia lo que verá en el tablero:** un solo equipo en mantenimiento hacía que su sitio y su cliente completos se mostraran sanos, incluidos los equipos que sí estaban fallando. Al actualizar, los sitios que hoy se ven verdes por este motivo pasarán a mostrar su estado real. No es una regresión: esos equipos ya estaban fallando y estaban tapados.
- Los **secretos de la configuración global** (contraseña SMTP, tokens de Twilio y de MeshCentral, clave del asistente de IA) dejan de ser legibles desde la consola: una vez guardados sólo se reemplazan o se borran. Los datos de conexión con MeshCentral pasan a sólo lectura, porque editarlos ahí nunca persistía y podía dejar el control remoto roto.
- La consola **marca los equipos con el agente de 32 bits instalado sobre un Windows de 64 bits**. Ese equipo se ve sano pero nunca completa una actualización y reporta el inventario de software incompleto; hasta ahora no había forma de distinguirlo.
- Los **instaladores de Linux y macOS verifican la arquitectura** del equipo antes de instalar y se niegan si no corresponde. El agente equivocado no fallaba de forma ruidosa: quedaba corriendo y pidiendo la arquitectura equivocada para siempre.
- **Censo diario de nodos huérfanos** de MeshCentral: registros que quedaron de un enrolamiento fallido y que no aparecen en ninguna pantalla. El censo sólo informa, no borra.
- Dos **plantillas de scripts** nuevas para censar y limpiar los archivos que queda en Windows tras migrar un agente de 32 bits, que el desinstalador no alcanza.
- Corregido: los **correos de alerta** se reportaban como enviados aunque el servidor SMTP los rechazara. El botón "Probar" era la única ruta que no sufría el problema, así que el transporte podía verse verde mientras las alertas reales no salían.
- Corregido: el instalador de Windows **no corría en Windows 7**, la única plataforma para la que existe el agente de 32 bits.
- Corregido: al escribir un secreto en la configuración, el tabulador **duplicaba el primer carácter**.
- Corregido: tres textos de la consola quedaban en inglés con la interfaz en español.
- Corregido: el **borrador de script generado con IA** llegaba con el razonamiento interno del modelo mezclado en el código.
- Corregido: la plantilla de servicios reportaba **FALLA a servicios que sí habían arrancado**.
- Corregido: cuando la hora de una desinstalación manual llegaba ilegible, el producto lo dejaba pasar en silencio; ahora queda registrado.

## v1.4.4 — 2026-08-04

- La versión de agente que el producto ofrece a la flota pasa a ser la **2.15.1**, que corrige los acentos y la ñ en los scripts ejecutados sobre Windows en español. Los equipos se actualizan solos al hacer check-in.

## v1.4.3 — 2026-08-04

- Biblioteca de 44 **plantillas de scripts** propias del producto para Windows, Linux y macOS, listas para ejecutar o clonar, sin depender de repositorios externos.
- Las plantillas se distinguen con su propio isotipo en el Administrador de scripts, y sus argumentos y variables de entorno se pueden revisar y ajustar para una prueba puntual sin tener que clonarlas.
- **Asistente IA** con pestaña propia en Configuración global: funciona con cualquier proveedor de API estilo OpenAI, con URL base, modelo, límite de tokens y temperatura configurables.
- Redacción de un **borrador de script con IA** desde el Administrador de scripts, describiendo en lenguaje natural lo que se necesita.
- Alerta por correo y baja del equipo en la consola cuando alguien **desinstala el agente a mano**, con una ventana de gracia de 10 minutos que se puede cancelar si la desinstalación era parte de una reinstalación.
- La alarma antirrobo suena al volumen máximo del equipo y no se detiene bajando el volumen.
- Geolocalización y su forzado activados por omisión en instalaciones nuevas.
- Documentación pública en `docs.observer.cl`, indexable y con la tabla de funciones soportadas por plataforma.
- Corregido: el cuadro para pedirle el borrador a la IA mostraba una sola línea, así que no se alcanzaba a leer lo que uno mismo estaba escribiendo. Ahora es un campo amplio, con ejemplos y contador.
- Corregido: la espera por la respuesta del proveedor de IA pasa de 60 a 120 segundos, y la consola muestra los segundos transcurridos en vez de una rueda muda. Antes se descartaban modelos que responden bien pero lento.
- Corregido: el desinstalador del agente en Linux se quedaba esperando una confirmación en pantalla que nadie iba a dar.
- Corregido: el respaldo programado reportaba éxito sin haber escrito el archivo.
- Corregido: la hora de las alertas se informa en la zona horaria del producto.
- Corregido: la desinstalación en macOS ya no queda colgada cuando MeshCentral no responde.

## v1.4.2 — 2026-07-26

- Respuesta rápida en el equipo: **bloqueo remoto de pantalla**, **mensaje en pantalla** y **alarma sonora**, disponibles equipo por equipo o como acción masiva.
- Las tres acciones tienen permiso propio por rol (se otorgan por separado) y quedan registradas en el log de auditoría, tanto si se ejecutan como si fallan.
- Geolocalización de activos: mapa con la ubicación de cada equipo y trayectoria histórica de posiciones.
- Ubicación por redes WiFi cercanas, con precisión típica de unos 20 metros, en vez de solo por dirección IP. En macOS se usa la ubicación nativa del sistema operativo.
- Coordenadas declarables por sitio, que se usan como respaldo cuando el equipo no puede resolver su posición.
- Geocerca opcional por equipo, con alerta por correo y aviso en la consola cuando un activo sale del perímetro de su sitio.
- Control remoto compatible con doble proxy inverso.

## v1.4.1 — 2026-07-22

- Reportería: 19 plantillas curadas, 4 de ellas con gráficos, y el módulo completo internacionalizado en español e inglés.
- El instalador del agente en Linux ya no se detiene en equipos sin entorno de escritorio.
- Favicon de Observer en la consola.
- Documentación: guía "Generar reportes" y capturas de la consola en `docs.observer.cl`.

## v1.4.0 — 2026-07-13

- Correos de alerta por SMTP con TLS implícito en el puerto 465 (`SMTP_SSL`), además de STARTTLS en 587/25.
- Distribución de los agentes desde un CDN propio en `agents.observer.cl` (descarga directa, sin depender de terceros).
- Consola internacionalizada en español e inglés, con idioma por defecto configurable en la instalación.
- Tema visual "Observation Deck" (navy profundo + cian de señal).
- Conexión cifrada del servicio `nats-api` hacia PostgreSQL.
- Todos los enlaces de documentación y ayuda apuntan a `docs.observer.cl`.
- Endurecimiento del registro de auditoría (límite de tamaño configurable) y del rate-limit de inicio de sesión.
- Comandos de mantenimiento del backend (inventario WMI y limpieza de nodos huérfanos de MeshCentral).
