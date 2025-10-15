import asyncio
import keyboard
from pybricksdev.ble import find_device
from pybricksdev.connections.pybricks import PybricksHubBLE

# Programa que se ejecutará dentro del hub
PROGRAM = """
from pybricks.hubs import PrimeHub
from pybricks.pupdevices import Motor
from pybricks.parameters import Port, Stop
from pybricks.tools import wait

hub = PrimeHub()

try:
    motorA = Motor(Port.A)  # Left motor
    print("Motor A conectado")
except:
    print("Error: Motor A no encontrado en puerto A")
    motorA = None

try:
    motorC = Motor(Port.C)  # Right motor
    print("Motor C conectado")
except:
    print("Error: Motor C no encontrado en puerto C")
    motorC = None

try:
    motorE = Motor(Port.E)  # Gripper
    print("Motor E conectado")
except:
    print("Error: Motor E no encontrado en puerto E")
    motorE = None

velocidad = 300
velocidad_garra = 200

print("Hub program started and motors initialized.")
print("Waiting for direct motor commands...")

# Test inicial de motores
if motorA:
    print("Testing motor A...")
    motorA.run(100)
    wait(500)
    motorA.stop()
    print("Motor A test complete")

if motorC:
    print("Testing motor C...")
    motorC.run(100)
    wait(500)
    motorC.stop()
    print("Motor C test complete")

if motorE:
    print("Testing motor E...")
    motorE.run(100)
    wait(500)
    motorE.stop()
    print("Motor E test complete")

print("All tests complete. Ready for control.")

# Loop simple para mantener el programa activo
count = 0
while True:
    count += 1
    if count % 1000 == 0:
        print(f"Hub active - count: {count}")
    wait(10)
"""

async def main():
    print("🔍 Buscando el hub por Bluetooth...")
    
    try:
        # Buscar dispositivo Pybricks con timeout de 30 segundos
        device = await asyncio.wait_for(find_device(), timeout=30.0)
    except asyncio.TimeoutError:
        print("❌ No se encontró ningún hub Pybricks")
        print("💡 Asegúrate de que:")
        print("   🔹 El hub SPIKE Prime esté encendido")
        print("   🔹 Tenga firmware Pybricks instalado")
        print("   🔹 Esté en modo de emparejamiento Bluetooth")
        print("   🔹 No esté conectado a otro dispositivo")
        print("   🔹 El Bluetooth de tu PC esté habilitado")
        return
    except Exception as e:
        print(f"❌ Error buscando dispositivo: {e}")
        return
    
    if not device:
        print("❌ No se encontró ningún hub Pybricks")
        return
    
    print(f"📱 Dispositivo encontrado: {device.name}")
    
    # Crear conexión al hub con el dispositivo
    hub = PybricksHubBLE(device)
    
    try:
        # Conectar al hub (sin parámetros)
        print("🔗 Conectando al hub...")
        await hub.connect()
        print("✅ Conectado al hub.")

        # Subir y ejecutar el programa
        print("📤 Subiendo programa al hub...")
        
        # Crear archivo temporal con el programa
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_file:
            temp_file.write(PROGRAM)
            temp_path = temp_file.name
        
        try:
            await hub.run(temp_path, wait=False, print_output=True)
            print("🚀 Programa ejecutándose en el hub.")
        finally:
            # Limpiar archivo temporal
            try:
                os.unlink(temp_path)
            except:
                pass

        print("\n🎮 CONTROLES:")
        print("⬆️  W: Adelante")
        print("⬇️  S: Atrás")
        print("⬅️  A: Izquierda")
        print("➡️  D: Derecha")
        print("🤏 Espacio: Cerrar garra")
        print("✋ G: Abrir garra")
        print("🛑 R: Parar garra")
        print("🚪 ESC: Salir")
        print("\n🕹️  ¡Empezando control!")
        print("🔍 Iniciando detección de teclas...")

        # Variables para controlar el estado
        last_command = ""
        loop_count = 0
        
        # Control del robot
        while True:
            try:
                current_command = ""
                loop_count += 1
                
                # Log cada 100 iteraciones (aprox 5 segundos) para confirmar que funciona
                if loop_count % 100 == 0:
                    print(f"🔄 Bucle activo - iteración {loop_count}")
                
                # Log detallado de detección de teclas
                if keyboard.is_pressed("w"):
                    current_command = "adelante"
                    print("🔍 Tecla W detectada - Adelante")
                elif keyboard.is_pressed("s"):
                    current_command = "atras"
                    print("🔍 Tecla S detectada - Atrás")
                elif keyboard.is_pressed("a"):
                    current_command = "izquierda"
                    print("🔍 Tecla A detectada - Izquierda")
                elif keyboard.is_pressed("d"):
                    current_command = "derecha"
                    print("🔍 Tecla D detectada - Derecha")
                elif keyboard.is_pressed("space"):
                    current_command = "garra_cerrar"
                    print("🔍 Tecla ESPACIO detectada - Cerrar garra")
                elif keyboard.is_pressed("g"):
                    current_command = "garra_abrir"
                    print("🔍 Tecla G detectada - Abrir garra")
                elif keyboard.is_pressed("r"):
                    current_command = "garra_stop"
                    print("🔍 Tecla R detectada - Parar garra")
                else:
                    # Solo parar motores de movimiento, no la garra
                    if last_command not in ["garra_cerrar", "garra_abrir", "garra_stop"]:
                        current_command = "stop"
                    else:
                        current_command = last_command  # Mantener comando de garra

                # Solo enviar comando si ha cambiado
                if current_command != last_command:
                    print(f"📤 Enviando comando: '{current_command}'")
                    try:
                        # Enviar código Python directamente al hub
                        if current_command == "adelante":
                            code = "motorA.run(300) if motorA else None; motorC.run(300) if motorC else None"
                        elif current_command == "atras":
                            code = "motorA.run(-300) if motorA else None; motorC.run(-300) if motorC else None"
                        elif current_command == "izquierda":
                            code = "motorA.run(-300) if motorA else None; motorC.run(300) if motorC else None"
                        elif current_command == "derecha":
                            code = "motorA.run(300) if motorA else None; motorC.run(-300) if motorC else None"
                        elif current_command == "garra_cerrar":
                            code = "motorE.run(-200) if motorE else None"
                        elif current_command == "garra_abrir":
                            code = "motorE.run(200) if motorE else None"
                        elif current_command == "stop":
                            code = "motorA.stop() if motorA else None; motorC.stop() if motorC else None"
                        elif current_command == "garra_stop":
                            code = "motorE.stop() if motorE else None"
                        else:
                            code = "pass"
                        
                        await hub.write_line(code)
                        print(f"✅ Código enviado: {code}")
                    except Exception as write_error:
                        print(f"❌ Error enviando comando: {write_error}")
                    last_command = current_command

                if keyboard.is_pressed("esc"):
                    print("👋 Saliendo...")
                    await hub.write_line("exit")
                    break

                await asyncio.sleep(0.05)
                
            except Exception as e:
                print(f"❌ Error durante el control: {e}")
                break
                
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        print("💡 Verifica que el hub esté encendido y cerca del PC")
        
    finally:
        try:
            await hub.disconnect()
            print("🔌 Desconectado del hub.")
        except:
            pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Programa interrumpido por el usuario.")
    except Exception as e:
        print(f"❌ Error general: {e}")
        import traceback
        traceback.print_exc()