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
    print("Testing motor A...")
    motorA.run(100)
    wait(500)
    motorA.stop()

if motorC:
    print("Testing motor C...")
    motorC.run(100)
    wait(500)
    motorC.stop()

if motorE:
    print("Testing motor E...")
    motorE.run(100)
    wait(500)
    motorE.stop()

print("Tests completed. Ready for remote control.")
print("Hub keeping program active...")

# Simple loop to keep the program running
# Commands will arrive through write_line and execute directly
count = 0
while True:
    count += 1
    if count % 1000 == 0:
        print("Hub active - waiting for commands...")
    wait(10)
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
            
        except asyncio.TimeoutError:
            print(f'⏰ Timeout en intento {attempt + 1}')
            if attempt < max_retries - 1:
                print('🔄 Reintentando en 5 segundos...')
                await asyncio.sleep(5)
                continue
            else:
                print('❌ No se pudo conectar después de varios intentos')
                return
        except Exception as e:
            print(f'❌ Error en intento {attempt + 1}: {e}')
            if "Unreachable" in str(e) or "GATT" in str(e):
                print('💡 Sugerencias:')
                print('   🔹 Reinicia el hub SPIKE (mantén presionado 10 seg)')
                print('   🔹 Cierra otras apps SPIKE/LEGO')
                print('   🔹 Acerca el hub al PC')
                
            if attempt < max_retries - 1:
                print('🔄 Reintentando en 10 segundos...')
                await asyncio.sleep(10)
                continue
            else:
                print('❌ No se pudo conectar después de varios intentos')
                return

    try:
        # subir programa
        print('📤 Subiendo programa al hub...')
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as tf:
            tf.write(PROGRAM)
            temp_path = tf.name

        try:
            await hub.run(temp_path, wait=False, print_output=True)
            print('🚀 Programa ejecutándose en el hub')
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

        print('🎮 CONTROLES DISPONIBLES:')
        print('⬆️  W: Adelante')
        print('⬇️  S: Atrás') 
        print('⬅️  A: Izquierda')
        print('➡️  D: Derecha')
        print('🤏 Espacio: Cerrar garra')
        print('✋ G: Abrir garra')
        print('🛑 R: Parar garra')
        print('🚪 ESC: Salir')
        print('')
        print('📋 COMBINACIONES:')
        print('🔄 W+A: Adelante-Izquierda')
        print('🔄 W+D: Adelante-Derecha')
        print('🔄 S+A: Atrás-Izquierda')
        print('🔄 S+D: Atrás-Derecha')
        print('')
        print('⚠️  IMPORTANTE: Ejecuta como Administrador en Windows si no detecta teclas')
        print('')
        print('🚀 ¡Control activo! Presiona las teclas para mover el robot.')
        print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')

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
                            await hub.write_line("eval('exit()')")
                        except:
                            pass
                        break

                    # Determinar comando de movimiento
                    drive_cmd = compute_drive_command(pressed)

                    # Crear código directo para ejecutar con eval
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
                    else:  # stop
                        drive_code = "motorA.stop() if motorA else None; motorC.stop() if motorC else None"

                    # Enviar solo si cambió
                    if drive_cmd != last_drive:
                        try:
                            print(f'Enviando comando drive: {drive_cmd}')
                            # Usar eval para ejecutar el código directamente
                            await hub.write_line(f"eval('{drive_code}')")
                            last_drive = drive_cmd
                            print('Drive ->', drive_cmd)
                        except Exception as e:
                            print('Error enviando drive:', e)

                    # Manejo de garra: space = cerrar, g = abrir, r = stop garra
                    claw_cmd = None
                    if 'space' in pressed and 'g' not in pressed:
                        claw_cmd = "cerrar"
                        claw_code = "motorE.run(-200) if motorE else None"
                    elif 'g' in pressed and 'space' not in pressed:
                        claw_cmd = "abrir"
                        claw_code = "motorE.run(200) if motorE else None"
                    else:
                        # si no está presionada ni space ni g ni r -> stop garra
                        claw_cmd = "stop"
                        claw_code = "motorE.stop() if motorE else None"

                    if claw_cmd != last_claw:
                        try:
                            print(f'Enviando comando claw: {claw_cmd}')
                            await hub.write_line(f"eval('{claw_code}')")
                            last_claw = claw_cmd
                            print('Claw ->', claw_cmd)
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
