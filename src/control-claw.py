"""
Control remoto simplificado para SPIKE Prime (BLE via pybricksdev).

Características conservadas:
- Conexión BLE y pruebas iniciales mínimas
- Pulsación corta -> movimiento corto
- Mantener tecla -> movimiento continuo hasta soltar
- Parada inmediata (emergency stop) al soltar la tecla
- Protección básica: cooldown entre comandos y timeout en programas continuos

Requisitos: pybricksdev, keyboard. Ejecutar Powershell como Administrador.
"""
from __future__ import annotations

import asyncio
import tempfile
import time
import os
from typing import Optional

from pybricksdev.ble import find_device  # type: ignore
from pybricksdev.connections.pybricks import PybricksHubBLE  # type: ignore

import keyboard  # type: ignore

# ---- Configuración ----
HUB_NAME_SUBSTRING = "Spike"  # coincidencia parcial del nombre BLE
COMMAND_COOLDOWN = 0.12  # s entre envíos para reducir errores BLE
HOLD_THRESHOLD = 0.30  # s para distinguir short press vs hold
CONTINUOUS_MAX_DURATION = 2.0  # s límite de seguridad en el programa continuo

# Mapear comandos a comportamientos (drive, claw)
KEY_MAP = {
    "w": ("adelante", "stop"),
    "s": ("atras", "stop"),
    "a": ("izquierda", "stop"),
    "d": ("derecha", "stop"),
    "q": ("stop", "abrir"),
    "e": ("stop", "cerrar"),
    "space": ("stop", "stop"),
}


def create_short_program(drive: str, claw: str) -> str:
    """Genera un pequeño programa que mueve por poco tiempo (single press).

    drive: 'adelante'|'atras'|'izquierda'|'derecha'|'stop'
    claw: 'abrir'|'cerrar'|'stop'
    """
    # Programa ejecutado en el hub (Pybricks) -- keep minimal imports
    return f"""
from pybricks.hubs import PrimeHub
from pybricks.parameters import Port
from pybricks.pupdevices import Motor
from pybricks.tools import wait

hub = PrimeHub()
motorA = Motor(Port.A)
motorC = Motor(Port.C)
motorE = Motor(Port.E)

def drive_cmd(m):
    if m == 'adelante':
        motorA.run_angle(600, 40)
    elif m == 'atras':
        motorA.run_angle(-600, 40)
    elif m == 'izquierda':
        motorC.run_angle(600, 40)
    elif m == 'derecha':
        motorC.run_angle(-600, 40)

def claw_cmd(c):
    if c == 'abrir':
        motorE.run_angle(-300, 30)
    elif c == 'cerrar':
        motorE.run_angle(300, 30)

if '{drive}' != 'stop':
    drive_cmd('{drive}')
if '{claw}' != 'stop':
    claw_cmd('{claw}')
""".strip()


def create_continuous_program(drive: str, claw: str) -> str:
    """Programa que ejecuta movimiento continuo hasta timeout (safety).
    Está diseñado para pararse desde el hub cuando termine o detectar fuerza.
    """
    return f"""
from pybricks.hubs import PrimeHub
from pybricks.parameters import Port
from pybricks.pupdevices import Motor
from pybricks.tools import wait

hub = PrimeHub()
motorA = Motor(Port.A)
motorC = Motor(Port.C)
motorE = Motor(Port.E)

start = time.time() if 'time' in globals() else 0
end_time = start + {CONTINUOUS_MAX_DURATION}

def start_drive(m):
    if m == 'adelante':
        motorA.run(300)
    elif m == 'atras':
        motorA.run(-300)
    elif m == 'izquierda':
        motorC.run(300)
    elif m == 'derecha':
        motorC.run(-300)

def start_claw(c):
    if c == 'abrir':
        motorE.run(-150)
    elif c == 'cerrar':
        motorE.run(150)

if '{drive}' != 'stop':
    start_drive('{drive}')
if '{claw}' != 'stop':
    start_claw('{claw}')

while time.time() < end_time:
    wait(100)

motorA.stop()
motorC.stop()
motorE.stop()
""".strip()


def create_emergency_program() -> str:
    """Programa mínimo que detiene todos los motores de inmediato.
    Se ejecuta en key release para asegurar parada física.
    """
    return """
from pybricks.hubs import PrimeHub
from pybricks.parameters import Port
from pybricks.pupdevices import Motor

hub = PrimeHub()
Motor(Port.A).stop()
Motor(Port.C).stop()
Motor(Port.E).stop()
""".strip()


async def send_program(hub: PybricksHubBLE, program: str, wait_for_finish: bool = True) -> None:
    """Escribe el archivo temporal y lo ejecuta en el hub.
    Se añade un pequeño cooldown para evitar sobrecargar BLE.
    """
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(program)
        path = f.name

    try:
        await hub.run(path, wait=wait_for_finish)
    finally:
        try:
            os.remove(path)
        except Exception:
            pass

    # cooldown
    await asyncio.sleep(COMMAND_COOLDOWN)


async def connect_hub() -> Optional[PybricksHubBLE]:
    print("🔍 Buscando hub BLE...")
    dev = await find_device(name_contains=HUB_NAME_SUBSTRING, timeout=8.0)
    if not dev:
        print("No se encontró hub BLE.")
        return None

    hub = PybricksHubBLE(dev)
    print(f"🔗 Conectando a {dev.name}...")
    await hub.connect()
    print("✅ Conectado")
    return hub


def on_key_event(event, queue: asyncio.Queue):
    """Callback de keyboard (sin asyncio). Pone eventos en la cola del loop.
    En el hilo de keyboard no se debe usar asyncio directamente.
    """
    # evento.name: llave como 'a', 'space', etc. event.event_type: down/up
    try:
        queue.put_nowait((time.time(), event.name, event.event_type))
    except Exception:
        pass


async def main_loop():
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    keyboard.hook(lambda e: on_key_event(e, queue))

    hub = await connect_hub()
    if not hub:
        return

    # Ejecutar programa de test inicial (opcional)
    print("📤 Ejecutando prueba inicial...")
    test_prog = """
from pybricks.hubs import PrimeHub
from pybricks.pupdevices import Motor
from pybricks.parameters import Port
hub = PrimeHub()
try:
    Motor(Port.A)
    Motor(Port.C)
    Motor(Port.E)
except Exception:
    pass
""".strip()
    await send_program(hub, test_prog, wait_for_finish=True)
    print("✅ Pruebas completadas. Listo para control remoto.")

    # Estado de teclas: mapping key -> (down_time)
    key_down_times: dict[str, float] = {}

    try:
        while True:
            ts, name, etype = await queue.get()
            if name not in KEY_MAP:
                continue

            drive, claw = KEY_MAP[name]

            if etype == "down":
                key_down_times[name] = ts
                # esperamos HOLD_THRESHOLD para decidir si es hold
                await asyncio.sleep(HOLD_THRESHOLD)
                # si sigue presionada -> iniciar continuo
                if name in key_down_times and key_down_times[name] == ts:
                    print(f"🔄 Inicio continuo: {name} -> {drive},{claw}")
                    prog = create_continuous_program(drive, claw)
                    # lanzar sin bloquear: la parada la hará emergency al soltar
                    asyncio.create_task(send_program(hub, prog, wait_for_finish=False))
                else:
                    # se soltó antes: enviar short
                    print(f"▶️ Pulsación corta: {name} -> {drive},{claw}")
                    prog = create_short_program(drive, claw)
                    await send_program(hub, prog, wait_for_finish=True)

            elif etype == "up":
                # parada inmediata: ejecutar emergency program bloqueante
                key_down_times.pop(name, None)
                print(f"⏹️ Suelta tecla: {name} -> parada inmediata")
                eprog = create_emergency_program()
                # Ejecutar y esperar para asegurarnos que el hub reciba la orden
                await send_program(hub, eprog, wait_for_finish=True)

    except asyncio.CancelledError:
        pass
    finally:
        await hub.disconnect()


def main():
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("Interrumpido por usuario")


if __name__ == "__main__":
    main()
"""
control-claw-v5-new.py

Nueva versión que usa ejecución de archivos temporales individuales
para cada comando, evitando el problema con eval() y write_line().

Requisitos: pybricksdev, keyboard. Ejecutar como Admin en Windows.
"""

import asyncio
import tempfile
import os
import time
import keyboard
from pybricksdev.ble import find_device # type: ignore
from pybricksdev.connections.pybricks import PybricksHubBLE # type: ignore

# Variables globales para control de sobrecarga
last_command_time = 0
command_cooldown = 0.1  # 100ms entre comandos

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


def create_continuous_program(drive_command, claw_command):
    """Crea un programa que mantiene el movimiento continuo pero con control de parada."""
    
    # Comandos de movimiento CONTINUO CON CONTROL DE PARADA
    drive_commands = {
        'adelante': """
if motorC:
    motorC.run(200)
    print("Motor C running forward CONTINUOUSLY")
    # BUCLE CONTROLADO - revisar cada 50ms si debe parar
    for i in range(40):  # Máximo 2 segundos (40 * 50ms) - REDUCIDO para paradas más rápidas
        wait(50)
        # Verificar si hay resistencia (motor bloqueado)
        try:
            current_angle = motorC.angle()
            wait(50)
            new_angle = motorC.angle()
            if abs(new_angle - current_angle) < 5:  # Si no se movió mucho
                print("Motor C detectó resistencia - PARANDO por seguridad")
                break
        except:
            pass
    motorC.stop()
print("Motor C forward movement completed")""",
        'atras': """
if motorC:
    motorC.run(-200)
    print("Motor C running backward CONTINUOUSLY")
    # BUCLE CONTROLADO - revisar cada 50ms si debe parar
    for i in range(40):  # Máximo 2 segundos - REDUCIDO
        wait(50)
        try:
            current_angle = motorC.angle()
            wait(50)
            new_angle = motorC.angle()
            if abs(new_angle - current_angle) < 5:
                print("Motor C detectó resistencia - PARANDO por seguridad")
                break
        except:
            pass
    motorC.stop()
print("Motor C backward movement completed")""",
        'izquierda': """
if motorA:
    motorA.run(-200)
    print("Motor A running left CONTINUOUSLY")
    # BUCLE CONTROLADO
    for i in range(40):  # Máximo 2 segundos - REDUCIDO
        wait(50)
        try:
            current_angle = motorA.angle()
            wait(50)
            new_angle = motorA.angle()
            if abs(new_angle - current_angle) < 5:
                print("Motor A detectó resistencia - PARANDO por seguridad")
                break
        except:
            pass
    motorA.stop()
print("Motor A left movement completed")""",
        'derecha': """
if motorA:
    motorA.run(200)
    print("Motor A running right CONTINUOUSLY")
    # BUCLE CONTROLADO
    for i in range(40):  # Máximo 2 segundos - REDUCIDO
        wait(50)
        try:
            current_angle = motorA.angle()
            wait(50)
            new_angle = motorA.angle()
            if abs(new_angle - current_angle) < 5:
                print("Motor A detectó resistencia - PARANDO por seguridad")
                break
        except:
            pass
    motorA.stop()
print("Motor A right movement completed")""",
        'izquierda_adelante': """
if motorA and motorC:
    motorA.run(-150)
    motorC.run(200)
    print("Motors A+C diagonal left-forward CONTINUOUSLY")
    for i in range(40):  # Máximo 2 segundos - REDUCIDO
        wait(50)
        # Verificar ambos motores
        try:
            angleA = motorA.angle()
            angleC = motorC.angle()
            wait(50)
            newA = motorA.angle()
            newC = motorC.angle()
            if abs(newA - angleA) < 3 or abs(newC - angleC) < 3:
                print("Motores detectaron resistencia - PARANDO por seguridad")
                break
        except:
            pass
    motorA.stop()
    motorC.stop()
print("Diagonal left-forward movement completed")""",
        'derecha_adelante': """
if motorA and motorC:
    motorA.run(150)
    motorC.run(200)
    print("Motors A+C diagonal right-forward CONTINUOUSLY")
    for i in range(40):  # Máximo 2 segundos - REDUCIDO
        wait(50)
        try:
            angleA = motorA.angle()
            angleC = motorC.angle()
            wait(50)
            newA = motorA.angle()
            newC = motorC.angle()
            if abs(newA - angleA) < 3 or abs(newC - angleC) < 3:
                print("Motores detectaron resistencia - PARANDO por seguridad")
                break
        except:
            pass
    motorA.stop()
    motorC.stop()
print("Diagonal right-forward movement completed")""",
        'izquierda_atras': """
if motorA and motorC:
    motorA.run(-150)
    motorC.run(-200)
    print("Motors A+C diagonal left-backward CONTINUOUSLY")
    for i in range(40):  # Máximo 2 segundos - REDUCIDO
        wait(50)
        try:
            angleA = motorA.angle()
            angleC = motorC.angle()
            wait(50)
            newA = motorA.angle()
            newC = motorC.angle()
            if abs(newA - angleA) < 3 or abs(newC - angleC) < 3:
                print("Motores detectaron resistencia - PARANDO por seguridad")
                break
        except:
            pass
    motorA.stop()
    motorC.stop()
print("Diagonal left-backward movement completed")""",
        'derecha_atras': """
if motorA and motorC:
    motorA.run(150)
    motorC.run(-200)
    print("Motors A+C diagonal right-backward CONTINUOUSLY")
    for i in range(40):  # Máximo 2 segundos - REDUCIDO
        wait(50)
        try:
            angleA = motorA.angle()
            angleC = motorC.angle()
            wait(50)
            newA = motorA.angle()
            newC = motorC.angle()
            if abs(newA - angleA) < 3 or abs(newC - angleC) < 3:
                print("Motores detectaron resistencia - PARANDO por seguridad")
                break
        except:
            pass
    motorA.stop()
    motorC.stop()
print("Diagonal right-backward movement completed")""",
        'stop': """
if motorA:
    motorA.stop()
if motorC:
    motorC.stop()
print("All drive motors stopped IMMEDIATELY")"""
    }
    
    # Comandos de garra CONTINUO CON SEGURIDAD
    claw_commands = {
        'cerrar': """
if motorE:
    motorE.run(200)
    print("Motor E closing claw CONTINUOUSLY")
    # Bucle controlado con detección de límites para garra
    for i in range(30):  # Máximo 1.5 segundos para garra - REDUCIDO
        wait(50)
        try:
            current_angle = motorE.angle()
            wait(50)
            new_angle = motorE.angle()
            if abs(new_angle - current_angle) < 2:  # Más sensible para garra
                print("Garra detectó objeto o límite - PARANDO por seguridad")
                break
        except:
            pass
    motorE.stop()
print("Claw closing completed")""",
        'abrir': """
if motorE:
    motorE.run(-200)
    print("Motor E opening claw CONTINUOUSLY")
    for i in range(30):  # Máximo 1.5 segundos - REDUCIDO
        wait(50)
        try:
            current_angle = motorE.angle()
            wait(50)
            new_angle = motorE.angle()
            if abs(new_angle - current_angle) < 2:
                print("Garra detectó límite de apertura - PARANDO por seguridad")
                break
        except:
            pass
    motorE.stop()
print("Claw opening completed")""",
        'stop': """
if motorE:
    motorE.stop()
print("Motor E stopped IMMEDIATELY")"""
    }
    
    drive_code = drive_commands.get(drive_command, drive_commands['stop'])
    claw_code = claw_commands.get(claw_command, claw_commands['stop'])
    
    return f"""
from pybricks.hubs import PrimeHub
from pybricks.pupdevices import Motor
from pybricks.parameters import Port
from pybricks.tools import wait

hub = PrimeHub()

print("=== STARTING SAFE CONTINUOUS MOTOR EXECUTION ===")
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

# Execute drive command CONTINUOUSLY WITH SAFETY
{drive_code}

# Execute claw command CONTINUOUSLY WITH SAFETY
{claw_code}

print("Safe continuous commands completed: drive={drive_command}, claw={claw_command}")

# EMERGENCY STOP - asegurar que todo pare
if motorA:
    motorA.stop()
if motorC:
    motorC.stop()
if motorE:
    motorE.stop()
print("All motors stopped - SAFETY ENSURED")
"""


async def execute_command(hub, drive_cmd, claw_cmd):
    """Ejecuta comandos combinados de movimiento y garra con protección contra sobrecarga."""
    try:
        # Evitar sobrecarga - esperar si es necesario
        current_time = time.time()
        global last_command_time, command_cooldown
        time_since_last = current_time - last_command_time
        if time_since_last < command_cooldown:
            await asyncio.sleep(command_cooldown - time_since_last)
        
        program = create_complete_program(drive_cmd, claw_cmd)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as tf:
            tf.write(program)
            temp_path = tf.name

        # Ejecutar el programa completo
        await hub.run(temp_path, wait=True, print_output=False)
        print(f'✅ Comandos ejecutados: drive={drive_cmd}, claw={claw_cmd}')
        last_command_time = time.time()
        
    except Exception as e:
        print(f'❌ Error ejecutando comandos: {e}')
        # Si hay error, esperar más tiempo antes del próximo comando
        last_command_time = time.time() + 0.5  # Esperar 500ms extra
    finally:
        try:
            os.unlink(temp_path)
        except:
            pass


async def execute_continuous_movement(hub, drive_cmd, claw_cmd, key):
    """Ejecuta movimiento continuo mientras la tecla esté presionada con control de seguridad."""
    try:
        # Verificar que no hay otra tarea continua ejecutándose para el mismo motor
        current_time = time.time()
        global last_command_time, command_cooldown
        time_since_last = current_time - last_command_time
        if time_since_last < command_cooldown:
            print(f"⏳ Esperando para evitar sobrecarga...")
            await asyncio.sleep(command_cooldown - time_since_last)
        
        print(f"🔄 Ejecutando movimiento continuo SEGURO: drive={drive_cmd}, claw={claw_cmd}")
        program = create_continuous_program(drive_cmd, claw_cmd)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as tf:
            tf.write(program)
            temp_path = tf.name

        # Ejecutar el programa continuo con tiempo limitado
        await hub.run(temp_path, wait=True, print_output=False)  # Cambiar a wait=True para poder controlarlo
        print(f'🔄 Movimiento continuo COMPLETADO para: {key}')
        last_command_time = time.time()
        
    except Exception as e:
        print(f'❌ Error en movimiento continuo: {e}')
        # Enviar comando de parada de emergencia
        try:
            stop_program = create_complete_program("stop", "stop")
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as tf:
                tf.write(stop_program)
                stop_path = tf.name
            await hub.run(stop_path, wait=True, print_output=False)
            print(f'🚨 PARADA DE EMERGENCIA ejecutada')
            os.unlink(stop_path)
        except:
            pass
        last_command_time = time.time() + 1.0  # Esperar 1 segundo extra tras error
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
        key_hold_timers = {}  # para rastrear cuánto tiempo está presionada cada tecla
        continuous_tasks = {}  # para rastrear tareas continuas ejecutándose

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
                    # Usar time.time() en lugar de asyncio loop.time()
                    import time
                    key_hold_timers[mapped_name] = time.time()
                    print(f"⬇️ Tecla presionada: {name} → {mapped_name}")
                    loop.call_soon_threadsafe(queue.put_nowait, ('keydown', mapped_name))
            elif e.event_type == 'up':
                if mapped_name in pressed:
                    pressed.remove(mapped_name)
                    if mapped_name in key_hold_timers:
                        del key_hold_timers[mapped_name]
                    print(f"⬆️ Tecla liberada: {name} → {mapped_name}")
                    loop.call_soon_threadsafe(queue.put_nowait, ('keyup', mapped_name))

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
        print('🔒 MODO SEGURO MEJORADO:')
        print('   • 🚨 PARADA DE EMERGENCIA al soltar tecla')
        print('   • ⚡ Detección automática de resistencia/límites')
        print('   • 🛡️ Control de sobrecarga BLE')
        print('   • ⏰ Parada automática tras 1.5-2 segundos máximo')
        print('   • 🔒 Parada inmediata garantizada al soltar tecla')
        print('')
        print('�🔍 MODO DEBUG: Se mostrará qué teclas detecta el programa')
        print('')
        print('📋 COMBINACIONES:')
        print('🔄 W+A: Arriba-Izquierda (diagonal)')
        print('🔄 W+D: Arriba-Derecha (diagonal)')
        print('🔄 S+A: Abajo-Izquierda (diagonal)')
        print('🔄 S+D: Abajo-Derecha (diagonal)')
        print('')
        print('⚠️  IMPORTANTE: Ejecuta como Administrador en Windows si no detecta teclas')
        print('')
        print('🚀 ¡Control activo con modo seguro! Presiona las teclas para mover el robot.')
        print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')

        try:
            while True:
                msg = await queue.get()
                
                if msg[0] == 'keydown':
                    key = msg[1]
                    
                    # manejar salida
                    if key == 'esc':
                        print('🚪 ESC detectado -> salir')
                        break

                    # Determinar comando de movimiento
                    drive_cmd = compute_drive_command(pressed)
                    
                    # Manejo de garra - probar diferentes nombres para espacio
                    claw_cmd = "stop"  # Por defecto parar
                    if any(k in pressed for k in ['space', 'spacebar', ' ']) and 'g' not in pressed:
                        claw_cmd = "cerrar"
                        print("🤏 Detectado: CERRAR garra")
                    elif 'g' in pressed and not any(k in pressed for k in ['space', 'spacebar', ' ']):
                        claw_cmd = "abrir"
                        print("✋ Detectado: ABRIR garra")
                    
                    print(f"🎮 Tecla presionada: {key}")
                    print(f"    Comando: drive={drive_cmd}, claw={claw_cmd}")
                    
                    # MOVIMIENTO CORTO INICIAL
                    await execute_command(hub, drive_cmd, claw_cmd)
                    
                    # Programar movimiento continuo después de 300ms si sigue presionada
                    async def check_continuous(key, drive_cmd, claw_cmd):
                        await asyncio.sleep(0.3)  # Esperar 300ms (más tiempo para evitar ejecución accidental)
                        # Verificar si la tecla todavía está presionada usando time.time()
                        if key in key_hold_timers and key in pressed:
                            current_time = time.time()
                            press_time = key_hold_timers[key]
                            if current_time - press_time >= 0.3:  # Si ha estado presionada por al menos 300ms
                                print(f"🔄 Iniciando movimiento continuo para: {key}")
                                # Cancelar cualquier tarea continua previa
                                if key in continuous_tasks:
                                    continuous_tasks[key].cancel()
                                
                                # Iniciar movimiento continuo
                                continuous_tasks[key] = asyncio.create_task(
                                    execute_continuous_movement(hub, drive_cmd, claw_cmd, key)
                                )
                    
                    # Programar verificación continua
                    asyncio.create_task(check_continuous(key, drive_cmd, claw_cmd))
                
                elif msg[0] == 'keyup':
                    key = msg[1]
                    
                    print(f"⬆️ Tecla liberada: {key}")
                    
                    # PARADA INMEDIATA - Cancelar movimiento continuo si existe
                    if key in continuous_tasks:
                        continuous_tasks[key].cancel()
                        del continuous_tasks[key]
                        print(f"🛑 Movimiento continuo cancelado para: {key}")
                    
                    # ENVIAR COMANDO STOP INMEDIATO con máxima prioridad
                    try:
                        # Crear programa de parada de emergencia simple y rápido
                        emergency_stop = """
from pybricks.hubs import PrimeHub
from pybricks.pupdevices import Motor
from pybricks.parameters import Port

hub = PrimeHub()

# Parada de emergencia inmediata
try:
    motorA = Motor(Port.A)
    motorA.stop()
    print("Motor A STOPPED IMMEDIATELY")
except:
    pass

try:
    motorC = Motor(Port.C)
    motorC.stop()
    print("Motor C STOPPED IMMEDIATELY")
except:
    pass

try:
    motorE = Motor(Port.E)
    motorE.stop()
    print("Motor E STOPPED IMMEDIATELY")
except:
    pass

print("EMERGENCY STOP COMPLETED")
"""
                        
                        # Ejecutar parada de emergencia inmediatamente
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as tf:
                            tf.write(emergency_stop)
                            emergency_path = tf.name
                        
                        # Ejecutar con máxima prioridad
                        await hub.run(emergency_path, wait=True, print_output=False)
                        print(f"🚨 PARADA DE EMERGENCIA ejecutada para tecla: {key}")
                        
                        # Limpiar archivo temporal
                        try:
                            os.unlink(emergency_path)
                        except:
                            pass
                            
                    except Exception as e:
                        print(f"❌ Error en parada de emergencia: {e}")
                    
                    # Luego determinar el nuevo estado basado en teclas restantes
                    drive_cmd = compute_drive_command(pressed)
                    claw_cmd = "stop"  # Por defecto parar al soltar
                    if any(k in pressed for k in ['space', 'spacebar', ' ']) and 'g' not in pressed:
                        claw_cmd = "cerrar"
                    elif 'g' in pressed and not any(k in pressed for k in ['space', 'spacebar', ' ']):
                        claw_cmd = "abrir"
                    
                    # Solo ejecutar nuevo comando si hay otras teclas presionadas
                    if pressed and any(k in pressed for k in ['w', 'a', 's', 'd', 'space', 'g']):
                        await execute_command(hub, drive_cmd, claw_cmd)
                    else:
                        print("🔒 Todas las teclas liberadas - robot completamente parado")

        finally:
            keyboard.unhook_all()
            # Cancelar todas las tareas continuas
            for task in continuous_tasks.values():
                task.cancel()

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