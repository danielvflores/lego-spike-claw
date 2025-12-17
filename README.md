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

## Posibles Versiones

El directorio `possibleCodes/` contiene múltiples versiones de control con diferentes funcionalidades:

### Versiones principales:
- **control-claw-v2.py**: Control básico por teclado con listeners (W/A/S/D, ESC).
- **control-claw-v3.py**: Control mejorado con soporte para teclas mantenidas y movimientos diagonales.
- **control-claw-v4.py**: Añade soporte para gamepad/joystick con fallback a teclado.
- **control-claw-v5.py**: Versión completa con tres modos:
  - `diagnose`: Diagnóstico de ejes y botones del mando
  - `interactive-map`: Mapeo interactivo de controles (guarda configuración en JSON)
  - `run`: Ejecución con configuración guardada
- **control-claw-v6.py**: Última versión con mejoras en tiempo real

### Versiones Pybricks y Thonny:
- **Control-(Pybricks)-v1.py y v4.py**: Implementaciones usando Pybricks
- **Control-(Thonny)-v1 a v4.py**: Versiones para entorno Thonny IDE

### Recomendaciones:
- Para pruebas rápidas con teclado: usa `v3`
- Para gamepad: ejecuta `v5 --mode diagnose` → `v5 --mode interactive-map` → `v5 --mode run`
- Los índices de ejes/botones varían según el sistema, por eso el mapeo interactivo es importante

---

## Manual de Usuario

### Introducción
Dentro de la Minería 4.0 hay un descontento en general por las malas prácticas de seguridad, al ser una minería tradicional, se trabaja de forma obsoleta. La Minería 4.0 está, por esto mismo, en una transición para dejar lo obsoleto hacia algo más tecnológico; la Industria 4.0 mediante diversos cambios, tales como implementar Internet de las cosas (IoT), inteligencia artificial, big data, maquetas y herramientas robóticas todo esto con el fin de alivianar la carga y ser seguro.

### Objetivos
Otorgar soporte técnico a Mineros, para que ellos no tengan que realizar acciones perjudiciales para su salud, dándoles una alternativa para poder realizar su trabajo de manera eficiente y ética, sin arriesgar su integridad tanto física como mental.

### Requerimientos
**Equipo necesario:**
- Equipo Lego Spike Prime
- Un dispositivo (PC/Notebook) con las siguientes características (mínimo):
  - 4GB RAM
  - Intel Celeron
  - Gráficos integrados
  - Bluetooth ó apartado USB
  - Sistema operativo: Windows 10/11 (para mayor compatibilidad)
  - Resolución gráfica mínima: 680x520
  - Conexión Bluetooth

### Instrucciones del Sistema
El presente Manual de Usuario está diseñado para poder guiar a los usuarios del sistema, y dentro del Manual está organizado de acuerdo a una secuencias de pasos para instalar y poder inicializar el sistema:

1. Descargar el sistema
2. Abrir el programa
3. Conectar la interfaz con el robot
4. Operaciones básicas

#### 1. Descargar el sistema
Para poder descargar todos los archivos necesarios para ingresar al sistema, se deberá ingresar al repositorio oficial del proyecto: https://github.com/danielvflores/lego-spike-claw, ingresar al apartado [Releases](https://github.com/danielvflores/lego-spike-claw/releases/tag/brazorobot) y descargar el ejecutable llamado: [SistemaControlSpike.exe](https://github.com/danielvflores/lego-spike-claw/releases/download/brazorobot/SistemaControlSpike.exe)
> Al hacer click en el nombre SistemControlSpike.exe en el apartado de arriba se redigirá automaticamente al link y se podrá descargar automáticamente el ejecutable!

#### 2. Abrir el programa
*[Sección en desarrollo]*

#### 3. Conectar la interfaz con el robot
*[Sección en desarrollo]*

#### 4. Operaciones básicas
*[Sección en desarrollo]*

> 💻 Spike: Garra controlable por Lego Spike, grupo SP-3