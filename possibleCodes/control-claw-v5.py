"""
control-claw-v5.py

Características principales:
- Modo `diagnose`: muestra ejes/botones del joystick en tiempo real y permite mapearlos
  (pulsar una tecla para asignar ese eje/botón a una acción y guarda en JSON).
- Modo `run`: usa el mapping (o valores por defecto) para controlar el hub por
  joystick o teclado (fallback) mediante pybricksdev.
- Guardado de configuración en `control-claw-config.json` dentro del repo.

Uso básico:
 python .\possibleCodes\control-claw-v5.py --mode diagnose
 python .\possibleCodes\control-claw-v5.py --mode run

Requisitos: pybricksdev, pygame (si deseas joystick), keyboard (si deseas teclado).
En Windows ejecuta PowerShell como Administrador para que `keyboard` funcione.
"""

import asyncio
import json
import os
import tempfile
import argparse
import time

try:
    import pygame
except Exception:
    pygame = None

try:
    import keyboard
except Exception:
    keyboard = None

from pybricksdev.ble import find_device
from pybricksdev.connections.pybricks import PybricksHubBLE

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'control-claw-config.json')

DEFAULT_CONFIG = {
    'speed': 300,
    'claw_speed': 200,
    'turn_scale': 0.8,
    'deadzone': 0.12,
    'hz': 20.0,
    # mapping: axis indices and button indices (None = not mapped)
    'mapping': {
        'axis_forward': 1,   # axis index for forward/back (typically 1)
        'axis_turn': 0,      # axis index for left/right (typically 0)
        'button_claw_close': 0,
        'button_claw_open': 1,
        'button_exit': 9
    }
}

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


def save_config(cfg, path=CONFIG_PATH):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2)


def load_config(path=CONFIG_PATH):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return DEFAULT_CONFIG.copy()


def diagnose_joystick(loop_seconds=0.1, duration=None):
    """Modo interactivo: imprime ejes y botones y permite al usuario presionar
    un botón o mover un eje para identificar su índice.
    Pulsar Ctrl-C sale del modo.
    """
    if pygame is None:
        print('pygame no está instalado. Instala: pip install pygame')
        return

    pygame.init()
    pygame.joystick.init()
    count = pygame.joystick.get_count()
    if count == 0:
        print('No se detectó ningún joystick.')
        return

    j = pygame.joystick.Joystick(0)
    j.init()
    print('Joystick:', j.get_name())
    print('Ejes:', j.get_numaxes(), 'Botones:', j.get_numbuttons())
    print('Movimientos: mueve un axis o pulsa un botón para ver su índice.')
    print('Presiona Ctrl-C para salir.')

    try:
        start = time.time()
        while True:
            pygame.event.pump()
            axes = [round(j.get_axis(i), 3) for i in range(j.get_numaxes())]
            buttons = [j.get_button(i) for i in range(j.get_numbuttons())]
            print('Axes:', axes)
            print('Btns:', buttons)

            # detectar cambios significativos en axes
            for i, v in enumerate(axes):
                if abs(v) > 0.2:
                    print(f'Axis {i} movimiento detectado: {v}')

            for i, b in enumerate(buttons):
                if b:
                    print(f'Botón {i} PRESIONADO')

            time.sleep(loop_seconds)
            if duration and (time.time() - start) > duration:
                break
    except KeyboardInterrupt:
        print('\nSaliendo de diagnose')


async def connect_hub_with_retries(retries=3, delay=2.0):
    for attempt in range(1, retries + 1):
        try:
            print('Buscando hub BLE (intentando)...')
            device = await asyncio.wait_for(find_device(), timeout=15.0)
            if device:
                hub = PybricksHubBLE(device)
                await hub.connect()
                print('Conectado al hub:', device.name)
                return hub
        except Exception as e:
            print(f'Intento {attempt} falló: {e}')
            if attempt < retries:
                await asyncio.sleep(delay * attempt)
    raise RuntimeError('No se pudo conectar al hub después de reintentos')


async def run_control(config, args):
    # conectar
    try:
        hub = await connect_hub_with_retries(retries=3)
    except Exception as e:
        print('Error al conectar:', e)
        return

    # subir programa
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tf:
        tf.write(PROGRAM)
        temp_path = tf.name

    try:
        await hub.run(temp_path, wait=False, print_output=True)
    finally:
        try:
            os.unlink(temp_path)
        except:
            pass

    mapping = config.get('mapping', {})
    speed = config.get('speed', 300)
    claw_speed = config.get('claw_speed', 200)
    deadzone = config.get('deadzone', 0.12)
    turn_scale = config.get('turn_scale', 0.8)
    hz = config.get('hz', 20.0)

    # Decide modo: joystick si pygame está disponible y hay joystick
    use_joystick = False
    joystick = None
    if pygame is not None:
        pygame.init()
        pygame.joystick.init()
        if pygame.joystick.get_count() > 0:
            joystick = pygame.joystick.Joystick(0)
            joystick.init()
            use_joystick = True

    print('Modo joystick' if use_joystick else 'Modo teclado (polling)')

    last_drive = None
    last_claw = None

    try:
        while True:
            if use_joystick:
                pygame.event.pump()
                ax_f = -joystick.get_axis(mapping.get('axis_forward', 1))
                ax_t = joystick.get_axis(mapping.get('axis_turn', 0))
                if abs(ax_f) < deadzone:
                    ax_f = 0.0
                if abs(ax_t) < deadzone:
                    ax_t = 0.0

                left_speed = int(clamp((ax_f * speed) + (ax_t * speed * turn_scale), -speed, speed))
                right_speed = int(clamp((ax_f * speed) - (ax_t * speed * turn_scale), -speed, speed))

                if left_speed == 0 and right_speed == 0:
                    drive_code = "motorA.stop() if motorA else None; motorC.stop() if motorC else None"
                else:
                    drive_code = f"motorA.run({left_speed}) if motorA else None; motorC.run({right_speed}) if motorC else None"

                btn_close = joystick.get_button(mapping.get('button_claw_close', 0))
                btn_open = joystick.get_button(mapping.get('button_claw_open', 1))
                btn_exit = joystick.get_button(mapping.get('button_exit', 9))

                if btn_close and not btn_open:
                    claw_code = f"motorE.run(-{claw_speed}) if motorE else None"
                elif btn_open and not btn_close:
                    claw_code = f"motorE.run({claw_speed}) if motorE else None"
                else:
                    claw_code = "motorE.stop() if motorE else None"

                if btn_exit:
                    print('Exit button pressed -> quitting')
                    try:
                        await hub.write_line('exit')
                    except:
                        pass
                    break

            else:
                # keyboard polling
                w = keyboard.is_pressed('w') if keyboard else False
                s = keyboard.is_pressed('s') if keyboard else False
                a = keyboard.is_pressed('a') if keyboard else False
                d = keyboard.is_pressed('d') if keyboard else False
                esc = keyboard.is_pressed('esc') if keyboard else False

                if esc:
                    print('ESC pressed -> quitting')
                    try:
                        await hub.write_line('exit')
                    except:
                        pass
                    break

                forward = 0.0
                turn = 0.0
                if w and not s:
                    forward = 1.0
                elif s and not w:
                    forward = -1.0
                if a and not d:
                    turn = -1.0
                elif d and not a:
                    turn = 1.0

                left_speed = int(clamp((forward * speed) + (turn * speed * turn_scale), -speed, speed))
                right_speed = int(clamp((forward * speed) - (turn * speed * turn_scale), -speed, speed))

                if left_speed == 0 and right_speed == 0:
                    drive_code = "motorA.stop() if motorA else None; motorC.stop() if motorC else None"
                else:
                    drive_code = f"motorA.run({left_speed}) if motorA else None; motorC.run({right_speed}) if motorC else None"

                close = keyboard.is_pressed('space') if keyboard else False
                openb = keyboard.is_pressed('g') if keyboard else False
                r = keyboard.is_pressed('r') if keyboard else False

                if close and not openb:
                    claw_code = f"motorE.run(-{claw_speed}) if motorE else None"
                elif openb and not close:
                    claw_code = f"motorE.run({claw_speed}) if motorE else None"
                elif r:
                    claw_code = "motorE.stop() if motorE else None"
                else:
                    claw_code = "motorE.stop() if motorE else None"

            # enviar comandos si cambian
            if drive_code != last_drive:
                try:
                    await hub.write_line(drive_code)
                    last_drive = drive_code
                except Exception as e:
                    print('Error sending drive:', e)

            if claw_code != last_claw:
                try:
                    await hub.write_line(claw_code)
                    last_claw = claw_code
                except Exception as e:
                    print('Error sending claw:', e)

            await asyncio.sleep(1.0 / hz)

    finally:
        try:
            await hub.disconnect()
        except:
            pass


def interactive_mapping():
    """Modo donde se asigna cada acción a un botón/axis. El usuario presiona
    el control que quiere asignar y el programa detecta y lo guarda.
    """
    if pygame is None:
        print('pygame no instalado; instala pygame para usar mapping interactivo')
        return

    pygame.init()
    pygame.joystick.init()
    if pygame.joystick.get_count() == 0:
        print('No joystick detectado')
        return

    j = pygame.joystick.Joystick(0)
    j.init()
    print('Joystick:', j.get_name())
    print('Presiona la acción que quieras mapear cuando te lo indique.')

    cfg = load_config()
    mapping = cfg.setdefault('mapping', {})

    actions = [
        ('axis_forward', 'Mueve el stick adelante/atrás (axis)'),
        ('axis_turn', 'Mueve el stick izquierda/derecha (axis)'),
        ('button_claw_close', 'Pulsa el botón para CERRAR garra'),
        ('button_claw_open', 'Pulsa el botón para ABRIR garra'),
        ('button_exit', 'Pulsa el botón para EXIT (salir)')
    ]

    try:
        for key, prompt in actions:
            print('\n' + prompt)
            detected = None
            while detected is None:
                pygame.event.pump()
                # revisar ejes
                for i in range(j.get_numaxes()):
                    v = j.get_axis(i)
                    if abs(v) > 0.5:
                        print(f'  Detectado axis {i} valor {v}')
                        detected = ('axis', i)
                        break
                # revisar botones
                for i in range(j.get_numbuttons()):
                    b = j.get_button(i)
                    if b:
                        print(f'  Detectado button {i}')
                        detected = ('button', i)
                        break
                time.sleep(0.05)

            if detected[0] == 'axis':
                mapping[key] = detected[1]
            else:
                mapping[key] = detected[1]
            print(f'Asignado {key} -> {mapping[key]}')

        cfg['mapping'] = mapping
        save_config(cfg)
        print('\nMapping guardado en', CONFIG_PATH)
    except KeyboardInterrupt:
        print('\nInterrumpido por usuario; no se guardaron cambios')


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['diagnose', 'interactive-map', 'run'], default='diagnose')
    parser.add_argument('--config', default=CONFIG_PATH)
    args = parser.parse_args()

    if args.mode == 'diagnose':
        diagnose_joystick()
        return

    if args.mode == 'interactive-map':
        interactive_mapping()
        return

    # run mode
    cfg = load_config(args.config) if args.config else load_config()
    try:
        asyncio.run(run_control(cfg, args))
    except KeyboardInterrupt:
        print('\nInterrumpido por usuario')


if __name__ == '__main__':
    main()
