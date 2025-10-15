"""
control-claw-v3.py

Versión mejorada que mantiene un conjunto de teclas presionadas.
Mientras una tecla de movimiento esté presionada, el robot se mueve.
Al soltarlas todas, se envía 'stop'. La garra (motorE) funciona
de forma similar: mientras se mantenga Space/G se mantiene el run;
al soltarse se hace stop.

Requisitos: mismos que v2 (pybricksdev, keyboard). Ejecutar como Admin en Windows.
"""

import asyncio
import tempfile
import os
import keyboard
from pybricksdev.ble import find_device
from pybricksdev.connections.pybricks import PybricksHubBLE

PROGRAM = """
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

print('Hub listo para comandos remotos')

while True:
    wait(100)
"""


def compute_drive_command(pressed):
    """Dada la colección de teclas presionadas, determina el comando de movimiento.

    pressed: set de nombres de teclas (lowercase)
    retorna: 'adelante','atras','izquierda','derecha','stop' o código compuesto
    """
    # Prioridad simple: si W y S están ambos presionados -> stop
    w = 'w' in pressed
    s = 's' in pressed
    a = 'a' in pressed
    d = 'd' in pressed

    if w and not s:
        # Adelante con mezcla lateral
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
    # si ni W ni S -> chequear giro en sitio
    if a and not d:
        return 'izquierda'
    if d and not a:
        return 'derecha'

    return 'stop'


async def main():
    print('Buscando hub BLE...')
    try:
        device = await asyncio.wait_for(find_device(), timeout=30.0)
    except asyncio.TimeoutError:
        print('No se encontró hub (timeout).')
        return

    print('Encontrado:', device.name)
    hub = PybricksHubBLE(device)

    try:
        await hub.connect()
        print('Conectado al hub')

        # subir programa
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tf:
            tf.write(PROGRAM)
            temp_path = tf.name

        try:
            await hub.run(temp_path, wait=False, print_output=True)
            print('Programa ejecutándose en el hub')
        finally:
            try:
                os.unlink(temp_path)
            except:
                pass

        pressed = set()  # teclas actualmente presionadas

        loop = asyncio.get_event_loop()
        queue = asyncio.Queue()

        def hook(e):
            name = e.name
            if e.event_type == 'down':
                # ignorar repeticiones de teclado
                if name not in pressed:
                    pressed.add(name)
                    loop.call_soon_threadsafe(queue.put_nowait, ('change', None))
            elif e.event_type == 'up':
                if name in pressed:
                    pressed.remove(name)
                    loop.call_soon_threadsafe(queue.put_nowait, ('change', None))

        keyboard.hook(hook)

        print('Controles: W/A/S/D movimiento, Espacio cerrar garra, G abrir garra, R parar garra, ESC salir')
        print('Ejecuta como Administrador en Windows si no detecta teclas')

        last_drive = None
        last_claw = None

        try:
            while True:
                # Esperar hasta que haya un cambio de teclas
                msg = await queue.get()
                if msg[0] == 'change':
                    # manejar salida
                    if 'esc' in pressed:
                        print('ESC detectado -> salir')
                        try:
                            await hub.write_line('exit')
                        except:
                            pass
                        break

                    # Determinar comando de movimiento
                    drive_cmd = compute_drive_command(pressed)

                    # Mapear a código en hub
                    if drive_cmd == 'adelante':
                        drive_code = "motorA.run(300) if motorA else None; motorC.run(300) if motorC else None"
                    elif drive_cmd == 'atras':
                        drive_code = "motorA.run(-300) if motorA else None; motorC.run(-300) if motorC else None"
                    elif drive_cmd == 'izquierda':
                        drive_code = "motorA.run(-300) if motorA else None; motorC.run(300) if motorC else None"
                    elif drive_cmd == 'derecha':
                        drive_code = "motorA.run(300) if motorA else None; motorC.run(-300) if motorC else None"
                    elif drive_cmd == 'izquierda_adelante':
                        drive_code = "motorA.run(150) if motorA else None; motorC.run(300) if motorC else None"
                    elif drive_cmd == 'derecha_adelante':
                        drive_code = "motorA.run(300) if motorA else None; motorC.run(150) if motorC else None"
                    elif drive_cmd == 'izquierda_atras':
                        drive_code = "motorA.run(-150) if motorA else None; motorC.run(-300) if motorC else None"
                    elif drive_cmd == 'derecha_atras':
                        drive_code = "motorA.run(-300) if motorA else None; motorC.run(-150) if motorC else None"
                    else:
                        drive_code = "motorA.stop() if motorA else None; motorC.stop() if motorC else None"

                    # Enviar solo si cambió
                    if drive_code != last_drive:
                        try:
                            await hub.write_line(drive_code)
                            last_drive = drive_code
                            print('Drive ->', drive_cmd)
                        except Exception as e:
                            print('Error enviando drive:', e)

                    # Manejo de garra: space = cerrar, g = abrir, r = stop garra
                    claw_cmd = None
                    if 'space' in pressed and 'g' not in pressed:
                        claw_cmd = "motorE.run(-200) if motorE else None"
                    elif 'g' in pressed and 'space' not in pressed:
                        claw_cmd = "motorE.run(200) if motorE else None"
                    elif 'r' in pressed:
                        claw_cmd = "motorE.stop() if motorE else None"
                    else:
                        # si no está presionada ni space ni g ni r -> stop garra
                        claw_cmd = "motorE.stop() if motorE else None"

                    if claw_cmd != last_claw:
                        try:
                            await hub.write_line(claw_cmd)
                            last_claw = claw_cmd
                            print('Claw ->', 'cerrar' if claw_cmd.startswith('motorE.run(-') else ('abrir' if claw_cmd.startswith('motorE.run(2') else 'stop'))
                        except Exception as e:
                            print('Error enviando claw:', e)

        finally:
            keyboard.unhook_all()

    except Exception as e:
        print('Error:', e)
    finally:
        try:
            await hub.disconnect()
        except:
            pass


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\nInterrumpido por usuario')
