# lego-spike-claw

Control remoto por teclado o mando para un robot construido con LEGO SPIKE Prime
y Pybricks. Este repositorio contiene varias versiones de herramientas de control
por Bluetooth (pybricksdev).

Requisitos
----------

- Python 3.9+ (óptimo 3.12)
- pybricksdev
- `keyboard` (para control por teclado; en Windows requiere ejecutar como Admin)
- `pygame` (para usar un joystick / gamepad)

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

<img src="assets/como_se_descarga.gif" alt="Descarga del sistema" width="100%">

> Al hacer click en el nombre SistemControlSpike.exe en el apartado de arriba se redigirá automaticamente al link y se podrá descargar automáticamente el ejecutable!

#### 2. Abrir el programa

<img src="assets/video_demo.gif" alt="Abrir el programa" width="100%">

#### 3. Conectar la interfaz con el robot

Para conectar la interfaz con el robot LEGO Spike, primero asegúrate de que el hub esté encendido y en modo Bluetooth. Luego, en la ventana principal del programa, haz clic en el botón **Conectar**. El sistema buscará automáticamente el hub disponible mediante Bluetooth y, una vez encontrado, establecerá la conexión. Cuando la conexión sea exitosa, el estado cambiará a "conectado" y podrás comenzar a controlar el robot desde la interfaz.

> Si tienes un mando compatible y deseas usarlo, puedes activar el control por mando haciendo clic en **Activar mando** después de conectar el robot.

#### 4. Operaciones básicas

Una vez conectado el robot, puedes realizar las siguientes operaciones desde la interfaz gráfica:

- **Mover el robot:** Usa los botones de dirección (rápido o lento) para avanzar, retroceder o girar el robot. También puedes utilizar un mando compatible para controlar el movimiento.
- **Controlar la garra:** Utiliza los botones de la sección "Garra" para abrir, cerrar, abrir lento o cerrar lento la garra del robot. El botón "Parar garra" detiene cualquier acción en curso de la garra.
- **Movimiento perpetuo:** En la sección "Movimiento perpetuo" puedes activar movimientos continuos del robot o la garra, y detenerlos cuando lo desees.

> Todas las acciones realizadas se mostrarán en el registro de la parte inferior de la ventana, donde podrás ver el estado de la conexión y los comandos enviados al robot.

> 💻 Spike: Garra controlable por Lego Spike, grupo SP-3