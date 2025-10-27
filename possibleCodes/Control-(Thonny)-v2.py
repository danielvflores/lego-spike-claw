"""
control_lego_pc.py

Control remoto del hub LEGO usando teclado y pybricksdev.

Requisitos:
- Python 3.8+
- pybricksdev (`pip install pybricksdev`)
- keyboard (`pip install keyboard`)
- Ejecutar Thonny como Administrador en Windows para detectar teclas
"""

import asyncio
import tempfile
import os
import keyboard
from pybricksdev.ble import find_device  # type: ignore
from pybricksdev.connections.pybricks import PybricksHubBLE  # type: ignore


# Programa simple que se envía al hub para mover motores según comandos
def create_program(drive_cmd, claw_cmd):
    drive_commands = {
        'adelante': "motorC.run(300)",
        'atras': "motorC.run(-300)",
        'izquierda': "motorA.run(-300)",
        'derecha': "motorA.run(300)",
        'stop': "motorA.stop()\nmotorC.stop()"
    }

    claw_commands = {
        'cerrar': "motorE.run(200)",
        'abrir': "motorE.run(-200)",
        'stop': "motorE.stop()"
    }

    drive_code = drive_commands.get(drive_cmd, "motorA.stop()\nmotorC.stop()")
    claw_code = claw_commands.get(claw_cmd, "motorE.stop()")

    program = f"""
from pybricks.hubs import PrimeHub
from pybricks.pupdevices import Motor
from pybricks.parameters import Port
from pybricks.tools import wait

hub = PrimeHub()

try:
    motorA = Motor(Port.A)
except:
    motorA = None

try:
    motorC = Motor(Port.C)
except:
    motorC = None

try:
    motorE = Motor(Port.E)
except:
    motorE = None

if motorA and motorC:
    {drive_code}

if motorE:
    {claw_code}

wait(500)
"""

    return program


def compute_drive_command(pressed):
    w = 'w' in pressed
    s = 's' in pressed
    a = 'a' in pressed
    d = 'd' in pressed

    if w and not s:
        if a and not d:
            return 'izquierda_adelante'
        if d and not a:
            return 'derecha_adelante'
        return 'adelante'
    if s and not w:
        if a and not d:
            return 'izquierda_atras'
        if d and not a:
            return 'derecha_atras'
        return 'atras'
    if a and not d:
        return 'izquierda'
    if d and not a:
        return 'derecha'
    return 'stop'


async def execute_command(hub, drive_cmd, claw_cmd):
    program = create_program(drive_cmd, claw_cmd)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as tf:
        tf.write(program)
        temp_path = tf.name
    try:
        await hub.run(temp_path, wait=True, print_output=False)
        print(f"Ejecutado: drive={drive_cmd}, claw={claw_cmd}")
    except Exception as e:
        print(f"Error ejecutando comandos: {e}")
    finally:
        try:
            os.unlink(temp_path)
        except:
            pass


async def main():
    print("Buscando hub Bluetooth...")
    device = await find_device()
    if not device:
        print("No se encontró hub.")
        return
    print(f"Conectando a {device.name}...")
    hub = PybricksHubBLE(device)
    await hub.connect()
    print("Conectado al hub. Usa W,A,S,D para mover, espacio para cerrar garra, G para abrir garra, R para parar garra, ESC para salir.")

    pressed = set()
    loop = asyncio.get_event_loop()
    queue = asyncio.Queue()

    def on_key_event(e):
        key = e.name.lower()
        # Map keys
        key_map = {
            'spacebar': 'space',
            'up': 'w',
            'down': 's',
            'left': 'a',
            'right': 'd'
        }
        key = key_map.get(key, key)

        if e.event_type == 'down':
            if key not in pressed:
                pressed.add(key)
                loop.call_soon_threadsafe(queue.put_nowait, 'change')
        elif e.event_type == 'up':
            if key in pressed:
                pressed.remove(key)
                loop.call_soon_threadsafe(queue.put_nowait, 'change')

    keyboard.hook(on_key_event)

    last_state = {'drive': None, 'claw': None}

    try:
        while True:
            await queue.get()

            if 'esc' in pressed:
                print("Salida detectada. Saliendo...")
                break

            drive_cmd = compute_drive_command(pressed)

            claw_cmd = 'stop'
            if 'space' in pressed and 'g' not in pressed:
                claw_cmd = 'cerrar'
            elif 'g' in pressed and 'space' not in pressed:
                claw_cmd = 'abrir'
            elif 'r' in pressed:
                claw_cmd = 'stop'

            current_state = {'drive': drive_cmd, 'claw': claw_cmd}

            if current_state != last_state:
                await execute_command(hub, drive_cmd, claw_cmd)
                last_state = current_state

    finally:
        keyboard.unhook_all()
        await hub.disconnect()
        print("Desconectado y terminado.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Interrumpido por usuario")
