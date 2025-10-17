"""
control-claw-v5-new.py

Nueva versión que usa ejecución de archivos temporales individuales
para cada comando, evitando el problema con eval() y write_line().

Requisitos: pybricksdev, keyboard. Ejecutar como Admin en Windows.
"""

import asyncio
import tempfile
import os
import keyboard
from pybricksdev.ble import find_device # type: ignore
from pybricksdev.connections.pybricks import PybricksHubBLE # type: ignore

# Programa de prueba inicial que se ejecuta una sola vez
INITIAL_TEST_PROGRAM = """
from pybricks.hubs import PrimeHub
from pybricks.pupdevices import Motor
from pybricks.parameters import Port
from pybricks.tools import wait

hub = PrimeHub()

try:
    motorA = Motor(Port.A)
    print("Motor A connected on port A")
except:
    print("Motor A not found on port A")
    motorA = None

try:
    motorC = Motor(Port.C)
    print("Motor C connected on port C")
except:
    print("Motor C not found on port C")
    motorC = None

try:
    motorE = Motor(Port.E)
    print("Motor E connected on port E")
except:
    print("Motor E not found on port E")
    motorE = None

print('Hub ready for remote commands')
print('Motors initialized')

# Initial motor tests
if motorA:
    print("Testing motor A (horizontal X-axis)...")
    motorA.run(150)   # Mover derecha
    wait(500)
    motorA.run(-150)  # Mover izquierda
    wait(500)
    motorA.stop()

if motorC:
    print("Testing motor C (vertical up/down)...")
    motorC.run(150)   # Mover arriba
    wait(500)
    motorC.run(-150)  # Mover abajo
    wait(500)
    motorC.stop()

if motorE:
    print("Testing motor E (claw open/close)...")
    motorE.run(150)   # Abrir garra
    wait(500)
    motorE.run(-150)  # Cerrar garra
    wait(500)
    motorE.stop()

print("Tests completed. Ready for remote control.")
"""


def compute_drive_command(pressed):
    """Dada la colección de teclas presionadas, determina el comando de movimiento."""
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


def create_complete_program(drive_command, claw_command):
    """Crea un programa completo que ejecuta tanto movimiento como garra."""
    
    # Comandos de movimiento
    drive_commands = {
        'adelante': "motorC.run(300) if motorC else None",  # Motor C: arriba
        'atras': "motorC.run(-300) if motorC else None",    # Motor C: abajo
        'izquierda': "motorA.run(-300) if motorA else None", # Motor A: izquierda en X
        'derecha': "motorA.run(300) if motorA else None",   # Motor A: derecha en X
        'izquierda_adelante': "motorA.run(-200) if motorA else None; motorC.run(300) if motorC else None",  # Diagonal
        'derecha_adelante': "motorA.run(200) if motorA else None; motorC.run(300) if motorC else None",     # Diagonal
        'izquierda_atras': "motorA.run(-200) if motorA else None; motorC.run(-300) if motorC else None",    # Diagonal
        'derecha_atras': "motorA.run(200) if motorA else None; motorC.run(-300) if motorC else None",       # Diagonal
        'stop': "motorA.stop() if motorA else None; motorC.stop() if motorC else None"
    }
    
    # Comandos de garra
    claw_commands = {
        'cerrar': "motorE.run(-200) if motorE else None",
        'abrir': "motorE.run(200) if motorE else None",
        'stop': "motorE.stop() if motorE else None"
    }
    
    drive_code = drive_commands.get(drive_command, drive_commands['stop'])
    claw_code = claw_commands.get(claw_command, claw_commands['stop'])
    
    return f"""
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

# Execute drive command
{drive_code}

# Execute claw command  
{claw_code}

print("Commands executed: drive={drive_command}, claw={claw_command}")

# Small wait to ensure commands are processed
wait(50)
"""


async def execute_command(hub, drive_cmd, claw_cmd):
    """Ejecuta comandos combinados de movimiento y garra."""
    try:
        program = create_complete_program(drive_cmd, claw_cmd)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as tf:
            tf.write(program)
            temp_path = tf.name

        # Ejecutar el programa completo
        await hub.run(temp_path, wait=True, print_output=False)
        print(f'✅ Comandos ejecutados: drive={drive_cmd}, claw={claw_cmd}')
        
    except Exception as e:
        print(f'❌ Error ejecutando comandos: {e}')
    finally:
        try:
            os.unlink(temp_path)
        except:
            pass


async def main():
    print('🔍 Buscando hub BLE...')
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f'📡 Intento {attempt + 1}/{max_retries} de conexión...')
            device = await asyncio.wait_for(find_device(), timeout=30.0)
            
            if not device:
                print('❌ No se encontró hub (timeout).')
                if attempt < max_retries - 1:
                    print('🔄 Reintentando en 5 segundos...')
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
                print('🔄 Reintentando en 10 segundos...')
                await asyncio.sleep(10)
                continue
            else:
                print('❌ No se pudo conectar después de varios intentos')
                return

    try:
        # Ejecutar programa de prueba inicial
        print('📤 Ejecutando pruebas iniciales...')
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as tf:
            tf.write(INITIAL_TEST_PROGRAM)
            temp_path = tf.name

        try:
            await hub.run(temp_path, wait=True, print_output=True)
            print('✅ Pruebas completadas')
        finally:
            try:
                os.unlink(temp_path)
            except:
                pass

        # NO ejecutar un programa base permanente - solo las pruebas

        pressed = set()  # teclas actualmente presionadas

        loop = asyncio.get_event_loop()
        queue = asyncio.Queue()

        def hook(e):
            name = e.name
            if e.event_type == 'down':
                if name not in pressed:
                    pressed.add(name)
                    loop.call_soon_threadsafe(queue.put_nowait, ('change', None))
            elif e.event_type == 'up':
                if name in pressed:
                    pressed.remove(name)
                    loop.call_soon_threadsafe(queue.put_nowait, ('change', None))

        keyboard.hook(hook)

        print('🎮 CONTROLES DISPONIBLES:')
        print('⬆️  W: Arriba (Motor C +)')
        print('⬇️  S: Abajo (Motor C -)')
        print('⬅️  A: Izquierda (Motor A -)')
        print('➡️  D: Derecha (Motor A +)')
        print('🤏 Espacio: Cerrar garra (Motor E -)')
        print('✋ G: Abrir garra (Motor E +)')
        print('🛑 R: Parar garra')
        print('🚪 ESC: Salir')
        print('')
        print('📋 COMBINACIONES:')
        print('🔄 W+A: Arriba-Izquierda (diagonal)')
        print('🔄 W+D: Arriba-Derecha (diagonal)')
        print('🔄 S+A: Abajo-Izquierda (diagonal)')
        print('🔄 S+D: Abajo-Derecha (diagonal)')
        print('')
        print('⚠️  IMPORTANTE: Ejecuta como Administrador en Windows si no detecta teclas')
        print('')
        print('🚀 ¡Control activo! Presiona las teclas para mover el robot.')
        print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')

        last_drive = None
        last_claw = None
        last_state = {}  # Para rastrear el estado completo

        try:
            while True:
                msg = await queue.get()
                if msg[0] == 'change':
                    # manejar salida
                    if 'esc' in pressed:
                        print('🚪 ESC detectado -> salir')
                        break

                    # Determinar comando de movimiento
                    drive_cmd = compute_drive_command(pressed)

                    # Manejo de garra
                    claw_cmd = None
                    if 'space' in pressed and 'g' not in pressed:
                        claw_cmd = "cerrar"
                    elif 'g' in pressed and 'space' not in pressed:
                        claw_cmd = "abrir"
                    else:
                        claw_cmd = "stop"

                    # Solo ejecutar si cambió el estado completo
                    current_state = {'drive': drive_cmd, 'claw': claw_cmd}
                    if current_state != last_state:
                        print(f'🎯 Ejecutando: drive={drive_cmd}, claw={claw_cmd}')
                        await execute_command(hub, drive_cmd, claw_cmd)
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



## --- IGNORE ---
## S , SPACE  