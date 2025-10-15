"""
control-claw-v2.py

Conecta a un hub Pybricks (SPIKE Prime) usando pybricksdev, sube
un programa liviano al hub que inicializa los motores y mantiene
el proceso vivo, y luego permite control por teclado desde el PC.

Requisitos en el PC:
 - Python 3.9+
 - pybricksdev (pip install pybricksdev)
 - keyboard (pip install keyboard) -> En Windows requiere ejecutar el script como Administrador

Controles:
 W/S/A/D -> movimiento (mientras la tecla esté presionada)
 Espacio  -> cerrar garra (mientras)
 G       -> abrir garra (mientras)
 R       -> parar garra (acción instantánea)
 ESC     -> salir

Nota: keyboard necesita privilegios en Windows; si no detecta teclas,
ejecuta PowerShell como Administrador y vuelve a ejecutar el script.
"""

import asyncio
import tempfile
import os
import threading
import keyboard
from pybricksdev.ble import find_device
from pybricksdev.connections.pybricks import PybricksHubBLE

# Programa que se ejecutará dentro del hub: inicializa motores y mantiene
# el bucle principal activo. Debe dejar el hub listo para recibir líneas
# vía la conexión remota (write_line desde pybricksdev).
PROGRAM = """
from pybricks.hubs import PrimeHub
from pybricks.pupdevices import Motor
from pybricks.parameters import Port
from pybricks.tools import wait

hub = PrimeHub()

try:
    motorA = Motor(Port.A)
    print('Motor A conectado')
except:
    motorA = None

try:
    motorC = Motor(Port.C)
    print('Motor C conectado')
except:
    motorC = None

try:
    motorE = Motor(Port.E)
    print('Motor E conectado')
except:
    motorE = None

print('Programa del hub listo. Esperando comandos remotos...')

count = 0
while True:
    count += 1
    if count % 1000 == 0:
        print('Hub activo -', count)
    wait(10)
"""


def key_to_command(key, event_type):
    """Mapea tecla + evento a comando lógico."""
    # event_type: 'down' | 'up'
    movement_keys = {"w", "a", "s", "d"}
    if key == 'esc' and event_type == 'down':
        return 'exit'

    if key in movement_keys:
        if event_type == 'down':
            if key == 'w':
                return 'adelante'
            if key == 's':
                return 'atras'
            if key == 'a':
                return 'izquierda'
            if key == 'd':
                return 'derecha'
        else:
            # al soltar cualquier tecla de movimiento -> stop
            return 'stop'

    # Garra
    if key == 'space':
        if event_type == 'down':
            return 'garra_cerrar'
        else:
            return 'garra_stop'

    if key == 'g':
        if event_type == 'down':
            return 'garra_abrir'
        else:
            return 'garra_stop'

    if key == 'r' and event_type == 'down':
        return 'garra_stop'

    return None


async def main():
    print('Buscando el hub por Bluetooth (timeout 30s)...')
    try:
        device = await asyncio.wait_for(find_device(), timeout=30.0)
    except asyncio.TimeoutError:
        print('No se encontró ningún hub Pybricks. Asegúrate de que el hub esté encendido y en modo BLE.')
        return
    except Exception as e:
        print('Error buscando dispositivo:', e)
        return

    print(f'Dispositivo encontrado: {device.name}')

    hub = PybricksHubBLE(device)

    try:
        print('Conectando al hub...')
        await hub.connect()
        print('Conectado.')

        # Subir y ejecutar programa en el hub
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tf:
            tf.write(PROGRAM)
            temp_path = tf.name

        try:
            print('Subiendo y ejecutando programa en el hub...')
            await hub.run(temp_path, wait=False, print_output=True)
            print('Programa en ejecución en el hub.')
        finally:
            try:
                os.unlink(temp_path)
            except:
                pass

        # Cola asyncio para recibir comandos desde callbacks de keyboard
        loop = asyncio.get_event_loop()
        cmd_queue = asyncio.Queue()

        # Estado para evitar envíos repetidos
        last_command = None

        def on_press(e):
            key = e.name
            cmd = key_to_command(key, 'down')
            if cmd:
                # Envío thread-safe al loop de asyncio
                loop.call_soon_threadsafe(cmd_queue.put_nowait, cmd)

        def on_release(e):
            key = e.name
            cmd = key_to_command(key, 'up')
            if cmd:
                loop.call_soon_threadsafe(cmd_queue.put_nowait, cmd)

        print('\nControles: W A S D (mover), Espacio (cerrar garra), G (abrir garra), R (parar garra), ESC (salir)')
        print('IMPORTANTE: En Windows ejecuta este script como Administrador para que la librería `keyboard` detecte las teclas.')

        # Registrar hooks (se ejecutan en hilos internos)
        keyboard.on_press(on_press)
        keyboard.on_release(on_release)

        try:
            while True:
                try:
                    cmd = await cmd_queue.get()
                except asyncio.CancelledError:
                    break

                if cmd == last_command:
                    # evitar reenvíos redundantes
                    continue

                print('Enviando comando:', cmd)

                # Traducir a código Python que se ejecuta en el hub
                if cmd == 'adelante':
                    code = "motorA.run(300) if motorA else None; motorC.run(300) if motorC else None"
                elif cmd == 'atras':
                    code = "motorA.run(-300) if motorA else None; motorC.run(-300) if motorC else None"
                elif cmd == 'izquierda':
                    code = "motorA.run(-300) if motorA else None; motorC.run(300) if motorC else None"
                elif cmd == 'derecha':
                    code = "motorA.run(300) if motorA else None; motorC.run(-300) if motorC else None"
                elif cmd == 'garra_cerrar':
                    code = "motorE.run(-200) if motorE else None"
                elif cmd == 'garra_abrir':
                    code = "motorE.run(200) if motorE else None"
                elif cmd == 'garra_stop':
                    code = "motorE.stop() if motorE else None"
                elif cmd == 'stop':
                    code = "motorA.stop() if motorA else None; motorC.stop() if motorC else None"
                elif cmd == 'exit':
                    print('Saliendo y pidiendo al hub que termine...')
                    try:
                        await hub.write_line('exit')
                    except Exception:
                        pass
                    break
                else:
                    code = 'pass'

                try:
                    await hub.write_line(code)
                    last_command = cmd
                except Exception as e:
                    print('Error enviando comando al hub:', e)
                    # intentar continuar; si falla repetidamente el usuario verá los errores

        finally:
            # limpiamos hooks
            keyboard.unhook_all()

    except Exception as e:
        print('Error de conexión o ejecución:', e)
    finally:
        try:
            await hub.disconnect()
            print('Desconectado del hub.')
        except Exception:
            pass


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\nInterrumpido por el usuario.')
