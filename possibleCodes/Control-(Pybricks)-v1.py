#Intentando nuevamente por pybricks para hacerlo funcional remotamente

from pybricks.hubs import PrimeHub
from pybricks.pupdevices import Motor, ColorSensor, UltrasonicSensor, ForceSensor
from pybricks.parameters import Button, Color, Direction, Port, Side, Stop
from pybricks.robotics import DriveBase
from pybricks.tools import wait, StopWatch

hub = PrimeHub()

motorA = Motor(Port.A)  # horizontal
motorC = Motor(Port.C)  # vertical
motorE = Motor(Port.E)  # garra

print("🤖 Listo para control por teclado (W/A/S/D, SPACE, G, R, ESC)")

kb = poll()
kb.register(stdin)

def stop_all_drive():
    motorA.stop()
    motorC.stop()

def stop_claw():
    motorE.stop()

while True:
    if not kb.poll(0):
        wait(50)
        continue

    key = stdin.read(1)
    if not key:
        continue

    # limpiar retorno de carro
    key = key.lower()
    print("Tecla:", repr(key))

    if key == '\x1b':  # ESC
        print("🚪 Salir")
        stop_all_drive()
        stop_claw()
        break

    # Movimiento
    if key == 'w':
        motorC.run(300)
        motorA.stop()
    elif key == 's':
        motorC.run(-300)
        motorA.stop()
    elif key == 'a':
        motorA.run(-300)
        motorC.stop()
    elif key == 'd':
        motorA.run(300)
        motorC.stop()
    else:
        stop_all_drive()

    # Garra
    if key == ' ':
        motorE.run(200)
    elif key == 'g':
        motorE.run(-200)
    elif key == 'r':
        motorE.stop()
    # else: no cambio garra

    wait(100)

print("✅ Programa terminado")
