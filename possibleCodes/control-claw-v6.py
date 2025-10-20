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
    motorA.run(100)   # Velocidad reducida para pruebas
    wait(300)         # Tiempo reducido
    motorA.run(-100)  # Velocidad reducida para pruebas
    wait(300)         # Tiempo reducido
    motorA.stop()

if motorC:
    print("Testing motor C (vertical up/down)...")
    motorC.run(100)   # Velocidad reducida para pruebas
    wait(300)         # Tiempo reducido
    motorC.run(-100)  # Velocidad reducida para pruebas
    wait(300)         # Tiempo reducido
    motorC.stop()

if motorE:
    print("Testing motor E (claw open/close)...")
    motorE.run(-100)  # Velocidad reducida para pruebas
    wait(400)         # Tiempo ligeramente más largo para garra
    motorE.run(100)   # Velocidad reducida para pruebas
    wait(400)         # Tiempo ligeramente más largo para garra
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
    
    # Comandos de movimiento - MOVIMIENTO CORTO Y PRECISO
    drive_commands = {
        'adelante': """
if motorC:
    motorC.run(200)  # Velocidad reducida para más precisión
print("Motor C running forward at 200")""",
        'atras': """
if motorC:
    motorC.run(-200)  # Velocidad reducida para más precisión
print("Motor C running backward at -200")""",
        'izquierda': """
if motorA:
    motorA.run(-200)  # Velocidad reducida para más precisión
print("Motor A running left at -200")""",
        'derecha': """
if motorA:
    motorA.run(200)  # Velocidad reducida para más precisión
print("Motor A running right at 200")""",
        'izquierda_adelante': """
if motorA:
    motorA.run(-150)  # Velocidad reducida para diagonales
if motorC:
    motorC.run(200)
print("Motors A+C diagonal left-forward")""",
        'derecha_adelante': """
if motorA:
    motorA.run(150)  # Velocidad reducida para diagonales
if motorC:
    motorC.run(200)
print("Motors A+C diagonal right-forward")""",
        'izquierda_atras': """
if motorA:
    motorA.run(-150)  # Velocidad reducida para diagonales
if motorC:
    motorC.run(-200)
print("Motors A+C diagonal left-backward")""",
        'derecha_atras': """
if motorA:
    motorA.run(150)  # Velocidad reducida para diagonales
if motorC:
    motorC.run(-200)
print("Motors A+C diagonal right-backward")""",
        'stop': """
if motorA:
    motorA.stop()
if motorC:
    motorC.stop()
print("All drive motors stopped")"""
    }
    
    # Comandos de garra (Horario=cerrar, AntiHorario=abrir) - MOVIMIENTO CONTINUO
    claw_commands = {
        'cerrar': """
if motorE:
    motorE.run(200)
    # Mantener ejecutando mientras esté presionada
    for i in range(50):  # Movimiento continuo largo para garra
        wait(50)
    motorE.stop()
print("Motor E closing claw - continuous movement")""",
        'abrir': """
if motorE:
    motorE.run(-200)
    # Mantener ejecutando mientras esté presionada
    for i in range(50):  # Movimiento continuo largo para garra
        wait(50)
    motorE.stop()
print("Motor E opening claw - continuous movement")""",
        'stop': """
if motorE:
    motorE.stop()
print("Motor E stopped")"""
    }
    
    drive_code = drive_commands.get(drive_command, drive_commands['stop'])
    claw_code = claw_commands.get(claw_command, claw_commands['stop'])
    
    return f"""
from pybricks.hubs import PrimeHub
from pybricks.pupdevices import Motor
from pybricks.parameters import Port
from pybricks.tools import wait

hub = PrimeHub()

print("=== STARTING MOTOR EXECUTION ===")
print("Drive command: {drive_command}")
print("Claw command: {claw_command}")

try:
    motorA = Motor(Port.A)
    print("Motor A initialized successfully")
except Exception as e:
    print(f"Motor A initialization failed: {{e}}")
    motorA = None

try:
    motorC = Motor(Port.C)
    print("Motor C initialized successfully")
except Exception as e:
    print(f"Motor C initialization failed: {{e}}")
    motorC = None

try:
    motorE = Motor(Port.E)
    print("Motor E initialized successfully")
except Exception as e:
    print(f"Motor E initialization failed: {{e}}")
    motorE = None

# Execute drive command
{drive_code}

# Execute claw command  
{claw_code}

print("Commands executed: drive={drive_command}, claw={claw_command}")

# Bucle continuo para mantener el movimiento mientras se mantiene la tecla presionada
# SOLO para motores de movimiento (A y C) - movimiento corto
if "{drive_command}" != "stop":
    # Movimiento mínimo - solo 3 iteraciones para movimiento corto y preciso
    for i in range(3):  # 3 iteraciones = ~150ms de movimiento mínimo
        wait(50)  # 50ms cada iteración
        
# Para la garra (Motor E) - el movimiento continuo ya está integrado en claw_commands
# No necesita bucle adicional aquí
        
# Si es comando stop, asegurarse de que paren
if "{drive_command}" == "stop":
    if motorA:
        motorA.stop()
    if motorC:
        motorC.stop()
        
if "{claw_command}" == "stop":
    if motorE:
        motorE.stop()
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
            name = e.name.lower()  # Convertir a minúscula para consistencia
            
            # Mapear nombres alternativos de teclas
            key_mapping = {
                'spacebar': 'space',
                ' ': 'space',
                'up': 'w',
                'down': 's', 
                'left': 'a',
                'right': 'd'
            }
            
            # Aplicar mapeo si existe
            mapped_name = key_mapping.get(name, name)
            
            if e.event_type == 'down':
                if mapped_name not in pressed:
                    pressed.add(mapped_name)
                    print(f"⬇️ Tecla presionada: {name} → {mapped_name}")
                    loop.call_soon_threadsafe(queue.put_nowait, ('change', None))
            elif e.event_type == 'up':
                if mapped_name in pressed:
                    pressed.remove(mapped_name)
                    print(f"⬆️ Tecla liberada: {name} → {mapped_name}")
                    loop.call_soon_threadsafe(queue.put_nowait, ('change', None))

        keyboard.hook(hook)

        print('🎮 CONTROLES DISPONIBLES:')
        print('⬆️  W (o flecha ↑): Arriba (Motor C +)')
        print('⬇️  S (o flecha ↓): Abajo (Motor C -)')
        print('⬅️  A (o flecha ←): Izquierda (Motor A -)')
        print('➡️  D (o flecha →): Derecha (Motor A +)')
        print('🤏 Espacio: Cerrar garra (horario, Motor E +)')
        print('✋ G: Abrir garra (antihorario, Motor E -)')
        print('🛑 R: Parar garra')
        print('🚪 ESC: Salir')
        print('')
        print('🔍 MODO DEBUG: Se mostrará qué teclas detecta el programa')
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
                    
                    # Debug: mostrar comando de movimiento
                    if drive_cmd != 'stop':
                        print(f"🎮 Comando movimiento: {drive_cmd}")
                        print(f"    W={('w' in pressed)}, S={('s' in pressed)}, A={('a' in pressed)}, D={('d' in pressed)}")

                    # Manejo de garra - probar diferentes nombres para espacio
                    claw_cmd = "stop"  # Por defecto parar
                    if any(key in pressed for key in ['space', 'spacebar', ' ']) and 'g' not in pressed:
                        claw_cmd = "cerrar"
                        print("🤏 Detectado: CERRAR garra")
                    elif 'g' in pressed and not any(key in pressed for key in ['space', 'spacebar', ' ']):
                        claw_cmd = "abrir"
                        print("✋ Detectado: ABRIR garra")
                    
                    # Debug: mostrar qué teclas están presionadas
                    if pressed:
                        print(f"🔍 Teclas presionadas: {pressed}")

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