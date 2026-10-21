# Tone Usage · panel flotante de macOS

Utilidad nativa complementaria; no cambia el Dashboard ni añade un LaunchAgent. Panel crema movible, inicialmente arriba a la derecha del monitor principal (el primero de NSScreen.screens, con la barra de menú), visible sobre otras ventanas y con un menú en la barra de macOS para reposicionarlo, actualizar o salir.

- Codex: dos tarjetas, **Diario** primero (con la duración real de la ventana, actualmente 5 horas; no se inventa un límite de 24 horas) y **Semanal** después. Porcentajes **restantes**, renovación y última lectura. No se estima un número de mensajes. Los datos no disponibles se muestran como desconocidos, nunca como 100 %.
- ChatGPT (mensajes de chat ordinarios): sin contador automático verificable para la cuenta probada. Se indica expresamente y se ofrece abrir ChatGPT. No confundir esta ausencia con cuota agotada ni usar los porcentajes de Codex para representarla.
- Consulta cada tres segundos mediante `account/rateLimits/read` del app-server oficial, con una sola conexión stdio persistente. Acepta también notificaciones `account/rateLimits/updated`. La actualización remota depende del proveedor; no se promete que el servicio calcule nuevos porcentajes cada tres segundos.
- Reinicios disponibles: cantidad autorizada por la cuenta y botón voluntario con confirmación del alcance del bono. Nunca se consumen al consultar ni al probar. `account/rateLimitResetCredit/consume` solo se envía tras confirmación; después se vuelven a consultar los límites, sin suponer que han cambiado.
- Se guarda antes de enviar una operación pendiente con clave de idempotencia y crédito seleccionado en `~/Library/Application Support/ToneUsageWidget/reset-request.json` (directorio privado y fichero 0600). Ante desconexión o cierre se conserva. «Comprobar reinicio pendiente» reutiliza la misma clave y, si aún no se aplicó, reintenta la misma operación. No hay reenvíos automáticos ni nuevos reinicios hasta confirmar su resultado. El registro se elimina solo tras una respuesta reconocida.
- Sin conversaciones, inferencia, lectura manual de tokens, cookies ni nuevas credenciales. Usa la sesión existente a través de Codex. No hay servidor HTTP ni puerto abierto. No consume créditos de inferencia para leer cuotas.
- Una sola solicitud pendiente; timeout de respuesta de 15 segundos y reintentos progresivos hasta 60 segundos ante fallos. Se conserva la última lectura con aviso de desconexión. Al salir se cierra el proceso auxiliar. No arranca al iniciar sesión salvo que el usuario lo añada por su cuenta.

Fuente: https://learn.chatgpt.com/docs/app-server (rate limits, account/rateLimits/read).

## Construir

`bash apple/UsageWidget/build.sh /private/tmp/ToneUsageWidget.app`

Instalación del usuario: `~/Applications/ToneUsageWidget.app`. Compilación nativa Release, firma ad hoc con hardened runtime; no incluye Debug dylibs ni desactiva library validation. Requiere el Codex instalado con ChatGPT en su ruta actual. No incluye dependencias externas.

## Verificación

Compilar UsageModel.swift + ModelTests.swift y ejecutar. Compilar UsageModel.swift + UsageWidget.swift con `-D WIDGET_PROBE` para dos consultas reales sin abrir el panel ni crear conversaciones. Las pruebas de reinicio usan modelos y respuestas simuladas: no consumen ningún bono real. La prueba de lectura debe tener dos lecturas válidas separadas aproximadamente tres segundos y no registrar identificadores de cuenta ni tokens.


## Escritorio y salvapantallas

El panel no se oculta al desactivarse su aplicación (`hidesOnDeactivate=false`). Se conserva el salvapantallas, el fondo y la configuración de seguridad existentes. Se comprueba el motor de salvapantallas y, como alternativa, únicamente propietario/capa de ventanas visibles; no se capturan imágenes ni contenidos.

Al detectar el salvapantallas se eleva la ventana por encima de su capa, sin sustituir el fondo. En ese modo no hay controles interactivos: se ocultan acciones y se ignora el ratón. Al salir vuelve a la capa flotante normal. Ante cambio de sesión se oculta. Esto no implementa un widget de login ni garantiza visibilidad en la pantalla de autenticación protegida de macOS.

La instalación del 21/10 se comprobó visible en el monitor principal de 3440×1440, esquina superior derecha (ventana 324×560). La comprobación visual sobre el salvapantallas real se solicita al propietario; no se considera superada solo por haber compilado.
