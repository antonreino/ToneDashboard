# Instrucciones del proyecto

## Versiones

- La versión pública es común a web, macOS e iOS y se obtiene de `VERSION`; mantener sincronizados los valores MARKETING_VERSION de ambos targets y apple/project.yml.
- La siguiente versión publicada después de 1.1.0 es 1.1.1. Secuencia: 1.1.1, 1.1.2, …, 1.1.9, 1.2.0, 1.2.1, etc. El último componente va de 0 a 9; al superar 9 vuelve a 0 e incrementa el componente central. No reiniciar el componente central ni incrementar la versión principal sin autorización expresa del propietario.
- La interfaz, la documentación del producto y las comunicaciones al usuario muestran solo la versión pública, sin sufijos como «(10)» ni números de compilación añadidos.
- Conservar CURRENT_PROJECT_VERSION/CFBundleVersion como contador interno de Apple y aumentarlo cuando sea necesario para instalar/publicar una compilación nueva. No mostrarlo como parte de la versión pública.
- No incrementar la versión pública por cada commit interno: hacerlo al preparar una nueva versión publicada. La documentación de esta política no requiere recompilar ni reinstalar las apps actuales.

## Interfaz y automatizaciones

- La interfaz funcional es única en `web/`. Los contenedores Apple deben conservar paleta y fondos comunes, identificadores, llavero y almacenes WebKit al actualizar.
- Al crear una automatización asociada al proyecto, registrar una descripción segura y requisitos en `audits/scheduled-tasks/<id>/metadata.json` del directorio Scripts e incluir en su flujo el registro de resultados `{at,status,message}` según `docs/TAREAS-PROGRAMADAS.md`. El catálogo la descubre automáticamente; nunca publicar prompts o secretos para completar descripciones.
- Distinguir tarea programada, último resultado documentado y estado de servicio. Ausencia de registros no significa error ni éxito. Los informes incompletos y cambios aplazados se identifican como parciales.
