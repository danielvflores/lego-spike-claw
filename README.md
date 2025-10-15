# lego-spike-claw

Control remoto por teclado o mando para un robot construido con LEGO SPIKE Prime
y Pybricks. Este repositorio contiene varias versiones de herramientas de control
por Bluetooth (pybricksdev).

Contenido relevante
- `src/control-claw.py` — versión principal que usa `pybricksdev` y `keyboard`.
- `possibleCodes/control-claw-v2.py` — control básico por teclado (hooks).
- `possibleCodes/control-claw-v3.py` — control por estado (teclas mantenidas, diagonales).
- `possibleCodes/control-claw-v4.py` — añade soporte para mando (pygame) + fallback.
- `possibleCodes/control-claw-v5.py` — diagnóstico interactivo de joystick, mapeo configurable y modo `run` que usa la configuración guardada.

Requisitos
----------
- Python 3.9+ (óptimo 3.12)
- pybricksdev
- `keyboard` (para control por teclado; en Windows requiere ejecutar como Admin)
- `pygame` (para usar un joystick / gamepad)

Posibles Versiones
----------------------------------

- `src/control-claw.py` (principal referencia)
	- Qué hace: ejemplo de flujo mínimo con `pybricksdev`: busca el hub por BLE,
		sube un programa pequeño al hub que define los motores y deja abierto un
		REPL/entrada para recibir comandos por línea.
	- Entradas: pensado para recibir comandos desde el PC (ej. con `hub.write_line`).
	- Uso típico: sirve como plantilla para los scripts en `possibleCodes` — garantiza
		que los motores A, C y E estén inicializados en el contexto del hub.

- `possibleCodes/control-claw-v2.py`
	- Qué hace: adaptación directa del control por teclado (W/A/S/D, espacio, G, R,
		ESC) usando listeners de teclado (hooks). Cuando se presiona una tecla se
		envía inmediatamente la línea de Python correspondiente al hub (por ejemplo
		`motorA.run(300)`). Al soltar, se envía el `stop` correspondiente.
	- Entradas: teclado global (requiere `keyboard`, en Windows suele requerir Admin).
	- Comportamiento: evento-driven, cada pulsación genera una acción instantánea.
		Es simple y de baja latencia para teclas individuales; menos ideal para
		mezclar múltiples teclas de forma natural (aunque posible con lógica adicional).

- `possibleCodes/control-claw-v3.py`
	- Qué hace: mejora el comportamiento de v2 para soportar teclas mantenidas y
		mezcla de direcciones (diagonales). Mantiene un conjunto `pressed` con
		las teclas actualmente presionadas y, periódicamente o al cambio, calcula
		la acción compuesta (ej. adelante + izquierda → velocidad diferencial).
	- Entradas: teclado global (igual que v2).
	- Comportamiento: ideal para control tipo 'mantén la tecla para avanzar' —
		cuando sueltas la tecla principal se envía `stop`. Evita enviar comandos
		redundantes cuando el estado no cambia.

- `possibleCodes/control-claw-v4.py`
	- Qué hace: añade soporte para gamepad/joystick usando `pygame`. Si `pygame`
		no está disponible o no se detecta un mando, hace fallback al control por
		teclado. Traduce ejes analógicos a velocidades y botones a acciones de garra.
	- Entradas: joystick (preferido) o teclado (fallback).
	- Comportamiento: permite control analógico (velocidades proporcionales al
		eje) y mapeo simple por índices; los ejes suelen necesitar calibración por
		plataforma, por eso v5 añade utilidades de diagnóstico y mapeo.

- `possibleCodes/control-claw-v5.py`
	- Qué hace: versión más completa. Añade tres modos:
		- `diagnose`: imprime en tiempo real valores de ejes y botones para que veas
			los índices que corresponden a cada entrada del mando.
		- `interactive-map`: te guía para asignar ejes y botones (por ejemplo, eje
			de avance/retroceso, eje de giro, botón abrir/cerrar garra) y guarda una
			configuración JSON en `possibleCodes/control-claw-config.json`.
		- `run`: usa la configuración guardada (o valores por defecto) para mapear
			el joystick/teclado a comandos que se envían al hub; incluye reintentos de
			conexión y parámetros ajustables (velocidad, deadzone, turn_scale, hz).
	- Entradas: joystick (mapeo configurable) y teclado (fallback).
	- Comportamiento: recomendado para uso real porque te permite diagnosticar
		el mando en tu sistema, crear un mapeo persistente y ejecutar con parámetros
		afinados. También evita enviar comandos idénticos repetidamente y maneja
		reconexiones al hub.

Notas prácticas
---------------
- Si sólo quieres probar rápido desde el PC con teclado, empieza por `v3`.
- Si tienes un gamepad, ejecuta primero `v5 --mode diagnose` para ver índices y
	luego `v5 --mode interactive-map` para crear la configuración antes de `run`.
- Recuerda que los índices de ejes/botones cambian entre sistemas y drivers;
	por eso el mapeo interactivo hace la diferencia.

> 💻 Spike: Garra controlable por Lego Spike, grupo SP-3