"""
control_lego_pc.py

Control remoto del hub LEGO usando teclado y pybricksdev.
También soporta mando (PS4 / PS5 / Xbox) usando la librería "inputs".

Requisitos:
- Python 3.8+
- pybricksdev (`pip install pybricksdev`)
- keyboard (`pip install keyboard`)
- inputs (`pip install inputs`)
- Ejecutar Thonny como Administrador en Windows para detectar teclas
"""

import asyncio
import tempfile
import os
import keyboard
import threading  # 🔸 NUEVO
from pybricksdev.ble import find_device  # type: ignore
from pybricksdev.connections.pybricks import PybricksHubBLE  # type: ignore

# 🔸 NUEVO
try:
    from inputs import get_gamepad
    GAMEPAD_AVAILABLE = True
except ImportError:
    GAMEPAD_AVAILABLE = False


# Programa que se envía al hub
def create_program(drive_cmd, claw_cmd):
    drive_commands = {
        'adelante': "motorC.run(300)",
        'atras': "motorC.run(-300)",
        'izquierda': "motorA.run(-300)",
        'derecha': "motorA.run(300)",
        'adelante_lento': "motorC.run(150)",
        'atras_lento': "motorC.run(-150)",
        'izquierda_lento': "motorA.run(-150)",
        'derecha_lento': "motorA.run(150)",
        'stop': "motorA.stop()\nmotorC.stop()"
    }

    claw_commands = {
        'cerrar': "motorE.run_target(200, 500)",
        'abrir': "motorE.run_target(200, -500)",
        'cerrar_lento': "motorE.run_target(100, 250)",
        'abrir_lento': "motorE.run_target(100, -250)",
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

motorA = Motor(Port.A)
motorC = Motor(Port.C)
motorE = Motor(Port.E)

{drive_code}
{claw_code}
wait(300)
"""
    return program


def compute_drive_command(pressed):
    w = 'w' in pressed
    s = 's' in pressed
    a = 'a' in pressed
    d = 'd' in pressed
    i = 'i' in pressed
    j = 'j' in pressed
    k = 'k' in pressed
    l = 'l' in pressed

    if i or j or k or l:  # 🔸 Movimiento lento
        if i:
            return 'adelante_lento'
        if k:
            return 'atras_lento'
        if j:
            return 'izquierda_lento'
        if l:
            return 'derecha_lento'

    if w and not s:
        return 'adelante'
    if s and not w:
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


# 🔸 NUEVO: lectura del mando
def start_gamepad_listener(pressed, loop, queue):
    if not GAMEPAD_AVAILABLE:
        return

    def gamepad_thread():
        print("Control de mando activo (PS4/Xbox).")
        while True:
            try:
                events = get_gamepad()
                for e in events:
                    # Ejes del joystick izquierdo
                    if e.code == "ABS_Y":
                        if e.state < 100:
                            pressed.add('w')
                        elif e.state > 150:
                            pressed.add('s')
                        else:
                            pressed.discard('w')
                            pressed.discard('s')

                    elif e.code == "ABS_X":
                        if e.state < 100:
                            pressed.add('a')
                        elif e.state > 150:
                            pressed.add('d')
                        else:
                            pressed.discard('a')
                            pressed.discard('d')

                    # Gatillos para control de garra lenta
                    elif e.code == "ABS_RZ" and e.state > 20:
                        pressed.add('m')  # cerrar lento
                    else:
                        pressed.discard('m')

                    if e.code == "ABS_Z" and e.state > 20:
                        pressed.add('n')  # abrir lento
                    else:
                        pressed.discard('n')

                    # Botones
                    if e.code == "BTN_SOUTH" and e.state == 1:
                        pressed.add('x')  # cerrar garra normal
                    elif e.code == "BTN_SOUTH" and e.state == 0:
                        pressed.discard('x')

                    if e.code == "BTN_WEST" and e.state == 1:
                        pressed.add('z')  # abrir garra normal
                    elif e.code == "BTN_WEST" and e.state == 0:
                        pressed.discard('z')

                    loop.call_soon_threadsafe(queue.put_nowait, 'change')
            except Exception:
                break

    t = threading.Thread(target=gamepad_thread, daemon=True)
    t.start()


async def main():
    print("Buscando hub Bluetooth...")
    device = await find_device()
    if not device:
        print("No se encontró hub.")
        return

    print(f"Conectando a {getattr(device, 'name', str(device))}...")
    hub = PybricksHubBLE(device)
    await hub.connect()
    print("✅ Conectado al hub. Usa W,A,S,D para moverte, Z/X para garra, IJKL y N/M para movimientos lentos. Mando compatible si está conectado.")

    pressed = set()
    loop = asyncio.get_event_loop()
    queue = asyncio.Queue()

    def on_key_event(e):
        key = e.name.lower()
        key_map = {'spacebar': 'space', 'up': 'w', 'down': 's', 'left': 'a', 'right': 'd'}
        key = key_map.get(key, key)

        if e.event_type == 'down':
            pressed.add(key)
            loop.call_soon_threadsafe(queue.put_nowait, 'change')
        elif e.event_type == 'up':
            pressed.discard(key)
            loop.call_soon_threadsafe(queue.put_nowait, 'change')

    keyboard.hook(on_key_event)
    if GAMEPAD_AVAILABLE:
        start_gamepad_listener(pressed, loop, queue)

    last_state = {'drive': None, 'claw': None}

    try:
        while True:
            await queue.get()
            if 'esc' in pressed:
                print("Salida detectada. Saliendo...")
                break

            drive_cmd = compute_drive_command(pressed)

            claw_cmd = 'stop'
            if 'x' in pressed and 'z' not in pressed:
                claw_cmd = 'cerrar'
            elif 'z' in pressed and 'x' not in pressed:
                claw_cmd = 'abrir'
            elif 'm' in pressed and 'n' not in pressed:
                claw_cmd = 'cerrar_lento'
            elif 'n' in pressed and 'm' not in pressed:
                claw_cmd = 'abrir_lento'

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
