# control‑claw‑v6‑realtime.py

"""
Versión revisada para control en tiempo real:
- Ejecuta un programa permanente en el hub que acepta comandos vía input().
- Desde el PC se envían comandos ‘motorX run speed’ o ‘motorX stop’.
Requisitos: pybricksdev, keyboard. Ejecutar como Admin en Windows.
"""

import asyncio
import tempfile
import os
import keyboard
from pybricksdev.ble import find_device  # type: ignore
from pybricksdev.connections.pybricks import PybricksHubBLE  # type: ignore

# Programa que se ejecutará **una sola vez** en el hub y permanecerá escuchando comandos.
HUB_CONTROLLER_PROGRAM = """
from pybricks.hubs import PrimeHub
from pybricks.pupdevices import Motor
from pybricks.parameters import Port
from pybricks.tools import wait

hub = PrimeHub()

try:
    motorA = Motor(Port.A)
    print("Motor A ready")
except Exception as e:
    print("Motor A not available:", e)
    motorA = None

try:
    motorC = Motor(Port.C)
    print("Motor C ready")
except Exception as e:
    print("Motor C not available:", e)
    motorC = None

try:
    motorE = Motor(Port.E)
    print("Motor E ready")
except Exception as e:
    print("Motor E not available:", e)
    motorE = None

print("Hub controller loop started")

while True:
    try:
        line = input().strip()
    except Exception as e:
        print("Input error:", e)
        break

    if not line:
        continue

    if line == "exit":
        print("Exit command received")
        break

    parts = line.split()
    if len(parts) < 2:
        print("Invalid command:", line)
        continue

    target = parts[0]
    cmd = parts[1]

    if target == "motorA" and motorA:
        if cmd == "run" and len(parts) == 3:
            speed = int(parts[2])
            motorA.run(speed)
            print(f"motorA run {speed}")
        elif cmd == "stop":
            motorA.stop()
            print("motorA stop")
        else:
            print("motorA invalid:", parts)
    elif target == "motorC" and motorC:
        if cmd == "run" and len(parts) == 3:
            speed = int(parts[2])
            motorC.run(speed)
            print(f"motorC run {speed}")
        elif cmd == "stop":
            motorC.stop()
            print("motorC stop")
        else:
            print("motorC invalid:", parts)
    elif target == "motorE" and motorE:
        if cmd == "run" and len(parts) == 3:
            speed = int(parts[2])
            motorE.run(speed)
            print(f"motorE run {speed}")
        elif cmd == "stop":
            motorE.stop()
            print("motorE stop")
        else:
            print("motorE invalid:", parts)
    else:
        print("Unknown target or not available:", target)
"""

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

async def send_command(hub, drive_cmd, claw_cmd):
    """Envía comandos al hub para motores A, C, E."""
    # Mapear drive_cmd a líneas de comando:
    if drive_cmd == 'adelante':
        await hub.write_line("motorC run 300")
        await hub.write_line("motorA stop")
    elif drive_cmd == 'atras':
        await hub.write_line("motorC run -300")
        await hub.write_line("motorA stop")
    elif drive_cmd == 'izquierda':
        await hub.write_line("motorA run -300")
        await hub.write_line("motorC stop")
    elif drive_cmd == 'derecha':
        await hub.write_line("motorA run 300")
        await hub.write_line("motorC stop")
    elif drive_cmd == 'izquierda_adelante':
        await hub.write_line("motorA run -200")
        await hub.write_line("motorC run 300")
    elif drive_cmd == 'derecha_adelante':
        await hub.write_line("motorA run 200")
        await hub.write_line("motorC run 300")
    elif drive_cmd == 'izquierda_atras':
        await hub.write_line("motorA run -200")
        await hub.write_line("motorC run -300")
    elif drive_cmd == 'derecha_atras':
        await hub.write_line("motorA run 200")
        await hub.write_line("motorC run -300")
    else:  # stop
        await hub.write_line("motorA stop")
        await hub.write_line("motorC stop")

    # Mapear claw_cmd:
    if claw_cmd == 'cerrar':
        await hub.write_line("motorE run 200")
    elif claw_cmd == 'abrir':
        await hub.write_line("motorE run -200")
    else:  # stop
        await hub.write_line("motorE stop")

async def main():
    print('🔍 Buscando hub BLE...')
    max_retries = 3
    hub = None

    for attempt in range(max_retries):
        try:
            print(f'📡 Intento {attempt + 1}/{max_retries} de conexión...')
            device = await asyncio.wait_for(find_device(), timeout=30.0)
            if not device:
                print('❌ No se encontró hub (timeout).')
                if attempt < max_retries - 1:
                    await asyncio.sleep(5)
                    continue
                else:
                    return

            print(f'📱 Dispositivo encontrado: {device.name}')
            hub = PybricksHubBLE(device)
            print('🔗 Intentando conectar al hub...')
            await hub.connect()
            print('✅ Conectado al hub exitosamente')
            break
        except Exception as e:
            print(f'❌ Error en intento {attempt + 1}: {e}')
            if attempt < max_retries - 1:
                await asyncio.sleep(10)
                continue
            else:
                return

    if not hub:
        return

    try:
        # Ejecutar el programa permanente en el hub
        print('📤 Cargando programa controlador en el hub...')
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as tf:
            tf.write(HUB_CONTROLLER_PROGRAM)
            temp_path = tf.name

        try:
            await hub.run(temp_path, wait=False, print_output=True)
            print('✅ Programa controlador iniciado')
        finally:
            try:
                os.unlink(temp_path)
            except:
                pass

        pressed = set()
        loop = asyncio.get_event_loop()
        queue = asyncio.Queue()

        def hook(e):
            name = e.name.lower()
            key_mapping = {
                'spacebar': 'space',
                ' ': 'space',
                'up': 'w',
                'down': 's',
                'left': 'a',
                'right': 'd'
            }
            mapped_name = key_mapping.get(name, name)

            if e.event_type == 'down':
                if mapped_name not in pressed:
                    pressed.add(mapped_name)
                    loop.call_soon_threadsafe(queue.put_nowait, ('change', None))
            elif e.event_type == 'up':
                if mapped_name in pressed:
                    pressed.remove(mapped_name)
                    loop.call_soon_threadsafe(queue.put_nowait, ('change', None))

        keyboard.hook(hook)

        print('🎮 CONTROLES DISPONIBLES:')
        print('⬆️  W (o flecha ↑): Arriba (Motor C +)')
        print('⬇️  S (o flecha ↓): Abajo (Motor C -)')
        print('⬅️  A (o flecha ←): Izquierda (Motor A -)')
        print('➡️  D (o flecha →): Derecha (Motor A +)')
        print('🤏 Espacio: Cerrar garra (Motor E +)')
        print('✋ G: Abrir garra (Motor E -)')
        print('🛑 R: Parar garra (Motor E stop)')
        print('🚪 ESC: Salir')
        print('🚀 ¡Control activo! Mantén presionadas las teclas para mover el robot.')

        last_state = {'drive': None, 'claw': None}

        try:
            while True:
                msg = await queue.get()
                if msg[0] == 'change':
                    if 'esc' in pressed:
                        print('🚪 ESC detectado → salir')
                        break

                    drive_cmd = compute_drive_command(pressed)

                    claw_cmd = 'stop'
                    if any(k in pressed for k in ['space', 'spacebar', ' ']) and 'g' not in pressed:
                        claw_cmd = 'cerrar'
                    elif 'g' in pressed:
                        claw_cmd = 'abrir'

                    current_state = {'drive': drive_cmd, 'claw': claw_cmd}
                    if current_state != last_state:
                        print(f'🎯 Nuevo estado → drive={drive_cmd}, claw={claw_cmd}')
                        await send_command(hub, drive_cmd, claw_cmd)
                        last_state = current_state

        finally:
            keyboard.unhook_all()

    except Exception as e:
        print('❌ Error:', e)
    finally:
        try:
            await hub.disconnect()
            print('🔌 Desconectado del hub')
        except:
            pass

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\n🛑 Interrumpido por usuario')
