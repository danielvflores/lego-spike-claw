"""
control-claw-v4.py

Versión v4: añade soporte para mando PS4 (DualShock) usando pygame.
Comportamiento:
 - Si detecta un joystick al inicio, entra en modo joystick.
 - Si no detecta ninguno, usa la misma lógica por teclado (keyboard hook) como fallback.

 - pip install pybricksdev pygame keyboard
 - En Windows ejecutar PowerShell como Administrador para que `keyboard` funcione.

Notas de mapeo (valores por defecto, pueden variar según plataforma/drivers):
 - Eje izquierdo: axis 0 = X (izq/der), axis 1 = Y (adelante/atrás)
 - Botón X (o boton 0) -> cerrar garra (hold)
 - Botón O/Circle (o boton 1) -> abrir garra (hold)
 - Botón R1/L1 pueden mapearse si lo prefieres; ajusta la constante BUTTON_CLAW_CLOSE/OPEN abajo.

 CON: python .\possibleCodes\control-claw-v4.py --mode joystick FUERZA USAR JOYSTICK
 CON: python .\possibleCodes\control-claw-v4.py --mode keyboard --speed 350 --claw-speed 220 FORZA USAR TECLADO
 PRO: Si tienes joystick, es más cómodo que el teclado.


"""

import asyncio
import tempfile
import os
import argparse
import time

try:
    import pygame # type: ignore
except Exception:
    pygame = None

try:
    import keyboard
except Exception:
    keyboard = None

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


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


async def run_with_joystick(hub, joystick, args):
    """Loop que lee el mando y envía comandos al hub."""
    print('Modo: joystick')
    # Configuración: mapping por defecto (ajustable)
    AXIS_LX = 0
    AXIS_LY = 1
    DEADZONE = 0.12
    MAX_SPEED = args.speed
    TURN_SCALE = args.turn_scale

    # Botones (pueden variar por plataforma/driver)
    BUTTON_CLAW_CLOSE = 0  # normalmente X
    BUTTON_CLAW_OPEN = 1   # normalmente O/Circle
    BUTTON_EXIT = 9        # ejemplo: Options/Start (ajusta si es necesario)

    last_drive = None
    last_claw = None

    while True:
            # Pump pygame events to update joystick state
            pygame.event.pump()

            lx = joystick.get_axis(AXIS_LX)
            ly = joystick.get_axis(AXIS_LY)

            # Normalizar: en muchos drivers, adelante es -1 en axis Y
            forward = -ly
            turn = lx

            # Aplicar deadzone
            if abs(forward) < DEADZONE:
                forward = 0.0
            if abs(turn) < DEADZONE:
                turn = 0.0

            # Combinar arcade drive
            left_speed = int(clamp((forward * MAX_SPEED) + (turn * MAX_SPEED * TURN_SCALE), -MAX_SPEED, MAX_SPEED))
            right_speed = int(clamp((forward * MAX_SPEED) - (turn * MAX_SPEED * TURN_SCALE), -MAX_SPEED, MAX_SPEED))

            # Construir código para motores A y C
            if left_speed == 0 and right_speed == 0:
                drive_code = "motorA.stop() if motorA else None; motorC.stop() if motorC else None"
                drive_label = 'stop'
            else:
                # Si ambos igual -> run same speed; si distintos -> differential
                drive_code = f"motorA.run({left_speed}) if motorA else None; motorC.run({right_speed}) if motorC else None"
                drive_label = f'L{left_speed}_R{right_speed}'

            # Enviar si cambió
            if drive_code != last_drive:
                try:
                    await hub.write_line(drive_code)
                    last_drive = drive_code
                    print('Drive ->', drive_label)
                except Exception as e:
                    print('Error enviando drive:', e)

            # Lectura de botones para garra (hold-to-run)
            close_pressed = joystick.get_button(BUTTON_CLAW_CLOSE)
            open_pressed = joystick.get_button(BUTTON_CLAW_OPEN)
            exit_pressed = joystick.get_button(BUTTON_EXIT)

            if exit_pressed:
                print('Botón exit presionado -> salir')
                try:
                    await hub.write_line('exit')
                except:
                    pass
                break

            if close_pressed and not open_pressed:
                claw_cmd = "motorE.run(-{} ) if motorE else None".format(args.claw_speed)
            elif open_pressed and not close_pressed:
                claw_cmd = "motorE.run({} ) if motorE else None".format(args.claw_speed)
            else:
                claw_cmd = "motorE.stop() if motorE else None"

            if claw_cmd != last_claw:
                try:
                    await hub.write_line(claw_cmd)
                    last_claw = claw_cmd
                    print('Claw ->', 'cerrar' if 'run(-' in claw_cmd else ('abrir' if 'run(' in claw_cmd and '-' not in claw_cmd else 'stop'))
                except Exception as e:
                    print('Error enviando claw:', e)


                await asyncio.sleep(1.0 / args.hz)

async def run_with_keyboard(hub, args):
    """Fallback: comportamiento por teclado similar a v3 pero en polling.

    Este modo usa keyboard.is_pressed en vez de hooks para simplificar en
    entornos donde hook no funciona.
    """
    if keyboard is None:
        raise RuntimeError('Librería keyboard no disponible; instala "keyboard" para usar modo teclado')

    print('Modo: keyboard (polling)')
    MAX_SPEED = args.speed
    TURN_SCALE = args.turn_scale
    hz = args.hz

    last_drive = None
    last_claw = None

    while True:
            # movimiento
            w = keyboard.is_pressed('w')
            s = keyboard.is_pressed('s')
            a = keyboard.is_pressed('a')
            d = keyboard.is_pressed('d')
            esc = keyboard.is_pressed('esc')

            if esc:
                print('ESC -> salir')
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

            left_speed = int(clamp((forward * MAX_SPEED) + (turn * MAX_SPEED * TURN_SCALE), -MAX_SPEED, MAX_SPEED))
            right_speed = int(clamp((forward * MAX_SPEED) - (turn * MAX_SPEED * TURN_SCALE), -MAX_SPEED, MAX_SPEED))

            if left_speed == 0 and right_speed == 0:
                drive_code = "motorA.stop() if motorA else None; motorC.stop() if motorC else None"
            else:
                drive_code = f"motorA.run({left_speed}) if motorA else None; motorC.run({right_speed}) if motorC else None"

            if drive_code != last_drive:
                try:
                    await hub.write_line(drive_code)
                    last_drive = drive_code
                    print('Drive ->', left_speed, right_speed)
                except Exception as e:
                    print('Error enviando drive:', e)

            # garra
            close = keyboard.is_pressed('space')
            openb = keyboard.is_pressed('g')
            r = keyboard.is_pressed('r')

            if close and not openb:
                claw_cmd = f"motorE.run(-{args.claw_speed}) if motorE else None"
            elif openb and not close:
                claw_cmd = f"motorE.run({args.claw_speed}) if motorE else None"
            elif r:
                claw_cmd = "motorE.stop() if motorE else None"
            else:
                claw_cmd = "motorE.stop() if motorE else None"

            if claw_cmd != last_claw:
                try:
                    await hub.write_line(claw_cmd)
                    last_claw = claw_cmd
                    print('Claw ->', 'cerrar' if 'run(-' in claw_cmd else ('abrir' if 'run(' in claw_cmd and '-' not in claw_cmd else 'stop'))
                except Exception as e:
                    print('Error enviando claw:', e)

            await asyncio.sleep(1.0 / hz)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['auto', 'joystick', 'keyboard'], default='auto')
    parser.add_argument('--speed', type=int, default=300, help='Velocidad máxima de desplazamiento')
    parser.add_argument('--claw-speed', dest='claw_speed', type=int, default=200, help='Velocidad garra')
    parser.add_argument('--turn-scale', type=float, default=0.8, help='Escala de giro aplicada al eje X')
    parser.add_argument('--hz', type=float, default=20.0, help='Frecuencia de polling (Hz)')
    args = parser.parse_args()

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

        mode = args.mode
        joystick = None

        if mode in ('auto', 'joystick'):
            if pygame is None:
                print('pygame no disponible; no se puede usar joystick')
            else:
                pygame.init()
                pygame.joystick.init()
                count = pygame.joystick.get_count()
                if count > 0:
                    joystick = pygame.joystick.Joystick(0)
                    joystick.init()
                    print('Joystick detectado:', joystick.get_name())
                    mode = 'joystick'
                else:
                    print('No se detectó joystick; usando modo teclado')

        if mode == 'joystick' and joystick is not None:
            await run_with_joystick(hub, joystick, args)
        else:
            # keyboard fallback en polling
            if keyboard is None:
                raise RuntimeError('keyboard no disponible y no hay joystick. Instala pygame o keyboard.')
            await run_with_keyboard(hub, args)

    except Exception as e:
        print('Error:', e)
    finally:
        try:
            await hub.disconnect()
            print('Desconectado')
        except:
            pass


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\nInterrumpido por usuario')
