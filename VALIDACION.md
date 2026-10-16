# Validación · 5 de octubre de 2026

## Actualización PS5 + Switch 2 Zelda

**37 tests correctos** en Linux. La versión original ya fue instalada por el usuario y respondió en Telegram; la actualización aún debe instalarse en su Mac. No se ha utilizado un token real desde este entorno.

Se ha verificado el nombre oficial de la consola en [Nintendo España](https://www.nintendo.com/es-es/Hardware/Nintendo-Switch-2/Packs-de-Nintendo-Switch-2-/Nintendo-Switch-2-Packs-2785628.html): Nintendo Switch 2 (edición 40.º aniversario de The Legend of Zelda), con lanzamiento el 29/10/2026.

Lecturas directas de la búsqueda nueva durante la preparación:

- PcComponentes: ficha de la consola identificada; se etiqueta como reserva antes del lanzamiento.
- Idealo: ficha de la consola identificada; precio «desde», condiciones pendientes de la tienda final. Esto no resuelve el HTTP 403 observado en la conexión del usuario.
- MediaMarkt: página leída, pero sin una consola de esa edición entre las fichas recibidas; descartados el juego Ocarina of Time, el mando de aniversario, accesorios y otras Switch.
- Fnac: HTTP 403, sin posibilidad de validar la lectura desde aquí.
- Amazon: la consulta PS5 devuelve HTTP 503 en este entorno. La causa de las cero fichas en el Mac del usuario sigue pendiente del diagnóstico local. Se amplían títulos y precios compatibles, sin dar por resuelto el acceso.
- Chollometro: la nueva búsqueda usa el RSS público existente; la ausencia de anuncios coincidentes no se interpreta como un precio disponible.

Se añaden 11 pruebas a las 25 originales: consola frente a juego/accesorios, reservas, fixtures reales de Switch 2, títulos y precios Amazon, diagnósticos, RSS compartido filtrado por familia, comandos separados, estado amarillo con cero fichas, aviso al abrir reservas y migración idempotente que conserva ajustes. La selección de archivos del actualizador excluye credenciales, historial y logs.

El instalador/actualizador macOS no se ha ejecutado en macOS durante esta preparación. Se ha comprobado su sintaxis y probado la fusión de configuraciones; la actualización real y el envío Telegram quedan pendientes de su ejecución local.

## Validación original de PS5 (referencia)

## Fuentes consultadas en directo

| Fuente | Resultado observado | Qué queda por comprobar |
|---|---|---|
| Amazon | HTTP 503 en la búsqueda configurada | Acceso y compatibilidad del adaptador desde tu conexión. Solo fixture sintética. |
| Fnac | HTTP 403 en categoría y ficha consultadas | Acceso y compatibilidad del adaptador desde tu conexión. Solo fixture sintética. |
| MediaMarkt | Búsqueda accesible; 6 fichas Slim clasificadas | Estabilidad continuada; los datos recibidos no confirman stock. |
| PcComponentes | Categoría accesible; 4 fichas Slim clasificadas, con stock estructurado | Estabilidad continuada y cobertura de otras páginas. |
| Idealo | Búsqueda accesible; 27 fichas clasificadas, cubriendo las cuatro variantes | Precio final, envío y stock de la tienda a la que remite el comparador. |
| Chollometro | RSS `/rss/nuevos` y categorías `/categorias/ps5` y `/categorias/ps5-slim` accesibles | Vigencia real de cada oferta en la tienda. Una ficha activa clasificada con la referencia «E Chassis»; anuncios caducados excluidos. |

Las primeras consultas a algunas páginas recibieron bloqueos. Se corrigió la URL inicial de grupo de Chollometro utilizando las categorías y el RSS enlazados en su propia web. La tabla refleja las últimas comprobaciones, no garantiza disponibilidad futura. No se han sorteado controles de acceso.

## Pruebas automáticas

25 tests correctos con `python -m unittest discover -s tests -v`:

- Clasificación de los cuatro modelos; exclusión de Pro, accesorios, productos usados y títulos ambiguos.
- Formatos europeos de precio; rechazo de cuotas, texto ambiguo y valores inválidos.
- Fixtures reales reducidas de MediaMarkt, PcComponentes, Idealo y Chollometro.
- Fixtures sintéticas de los adaptadores de Amazon y Fnac y del RSS de Chollometro.
- Extracción del precio explícito del RSS sin confundirlo con el PVP anterior.
- Primera lectura, subidas/bajadas de un céntimo, ofertas que no son el mínimo, persistencia tras reinicio.
- Errores que no sustituyen precios, avisos de incidencia sin repetición continua, agotados, fichas desaparecidas y datos caducados.
- Chats autorizados, comandos dirigidos a otro bot, parámetros de Telegram y cola persistente con reintentos.

La creación de mensajes Telegram se prueba con un transporte simulado; **no se ha enviado un mensaje real**. La sintaxis Python y del instalador se ha comprobado; **launchd requiere la prueba de instalación en macOS**. No se ha realizado una prueba de funcionamiento prolongada.

## Comprobación pendiente en tu Mac

Después de instalar, ejecuta:

```bash
.venv/bin/python -m ps5bot.app --check
```

Después consulta `/estado` en el bot. Si Amazon o Fnac siguen fallando, esas fuentes no estarán monitorizando precios aunque el resto funcione. Sus adaptadores necesitarán una vía de acceso permitida y comprobar el HTML recibido. No des por operativo el conjunto de seis fuentes hasta resolverlo.

- **Carrefour · Switch 2 Zelda**: desactivada temporalmente. La URL configurada devuelve al cliente HTTP la categoría general de consolas en vez de la ficha específica; no se fuerza el parser para evitar falsos positivos.

## Validación local · 16 octubre 2026 · EAN

- 60 pruebas Python correctas: regresiones del monitor y Telegram, EAN-8/EAN-13 y ceros iniciales, checksum, persistencia, concurrencia, límite, altas repetidas, descubrimiento limitado al dominio, precio/moneda/estado, identidad por producto, fallos de ficha y alta incorporada por el planificador sin reiniciar.
- EAN 0711719021247: búsquedas reales PcComponentes y MediaMarkt, lectura posterior de cada ficha y GTIN confirmado; ambas devolvieron 649,00 EUR. No se añadió este producto al catálogo real del usuario.
- Amazon: 48 candidatos sin precio; Idealo: 403; Chollometro RSS: respuesta válida con 30 candidatos sin PS5 en esa muestra, búsqueda pública `/search` con 410. Las fuentes bloqueadas permanecen desactivadas. No se ha validado Creators API sin sus credenciales.
- ToneDashboard: 91 pruebas Python, pruebas HTTP autenticadas y de origen, agrupación y orden; JavaScript comprobado y renderizado probado con precios numéricos, enlaces y texto escapado.
- ToneDashboardApps: pruebas API, contratos y paridad incluidas altas EAN y errores; compilaciones macOS/iOS Simulator y Release firmadas para macOS/iOS físico; versión1.3(4) instalada en Mac e iPhone conectado.
- Servicios tracker y dashboard reiniciados; API real con autenticación devuelve ofertas ordenadas y formulario EAN; EAN inválido devuelve400. SQLite `integrity_check=ok`, respaldo previo e historial conservados. No se enviaron avisos Telegram de prueba.

No equivale a una prueba prolongada de todos los productos/tiendas. La cobertura EAN depende de que la fuente publique el identificador exacto; no se inventan coincidencias. La revisión remota CI se comprueba aparte de estas pruebas locales.

### Eliminación y Telegram · 16/10/2026

65 pruebas del tracker correctas y 91 del dashboard. Pruebas nuevas: primera oferta EAN para los dos chats configurados, bajadas/subidas y vuelta de stock, entrega por transporte Telegram simulado, eliminación idempotente, cancelación de cola exclusiva del EAN, conservación de otros avisos e historial, descarte de consultas anteriores a eliminar/recrear y migración de cola antigua. API protegida de eliminación y cliente nativo comprobados. No se enviaron mensajes reales de prueba.

Apps1.3.1(5) compiladas y firmadas para macOS/iOS; se aplican junto con el reinicio de tracker/dashboard. API real de eliminación validada con un EAN inválido (400), control web y migración `outbox.product_ean` comprobados; SQLite íntegro. Se conservan los dos destinatarios existentes.
