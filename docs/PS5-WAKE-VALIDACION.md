# Orbit y encendido desde reposo · 1.1.1

## Cambios

La solicitud explícita «Ver código» y el registro «Recordar dispositivo» validan origen y contraseña antes de consultar la consola. Si Remote Play confirma reposo, se envía una única señal autenticada. Solo se lee el código tras confirmar que la PS5 está encendida y Orbit acepta conexiones. Estados desconocidos, fallo de red, ausencia de credencial y Orbit detenido devuelven mensajes de error; nunca cargan el jailbreak. La clave queda fuera del repositorio y no se entrega a los clientes.

Web, macOS e iOS consumen el mismo flujo del servidor. Las apps instaladas reciben el cambio al recargar; no necesitan reinstalación para esta funcionalidad. Los targets mantienen versión pública común 1.1.1.

## Pruebas realizadas el 19/10/2026

- 159 pruebas de servidor y 74 del tracker: correctas.
- Validaciones JavaScript de las funcionalidades existentes: correctas.
- Navegador Chrome con perfil temporal: 390, 768, 1440 y 2560 px, sin desbordamiento ni errores JS; diálogo Orbit, respuesta de despertar y limpieza del código/contraseña probados a 390 y 1440 px.
- Pruebas Swift de autenticación, HTTPS, aislamiento y conservación de preferencias: correctas.
- Compilaciones macOS e iOS sin firma: correctas. No se han instalado estos binarios de prueba.
- Prueba real del módulo: PS5 standby → señal única → ready → conexión Orbit correcta.

## Validación final del servicio

El proceso Python de launchd devolvía error de red 65 pese al permiso mostrado para Python. Se incorporó un asistente puntual TonePS5Wake con identidad propia de LaunchServices y permiso Red local autorizado por el propietario. No instala servicios permanentes. La comunicación del resultado usa un FIFO privado y la credencial nunca aparece en argumentos ni respuesta HTTP.

Tras conceder el permiso: asistente responde en 0,2 s y termina; solicitud protegida real POST /api/orbit/pair-code devuelve HTTP 200, código vigente válido y console_woken=false con consola ya encendida. No se imprimió ni guardó el código. La sección Cómo funciona de Orbit Zero quedó desplegada para el lector autorizado existente.

El despertar físico se validó con la implementación compartida: standby → señal única → ready → Orbit disponible. No se forzó un segundo reposo durante la validación del servicio. Las apps instaladas consumen el mismo endpoint HTTPS; se compilaron ambos targets como comprobación, sin reinstalar binarios ni alterar llaveros.
