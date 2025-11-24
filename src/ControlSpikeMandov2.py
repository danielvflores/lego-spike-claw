# gui_control_lego.py
# Interfaz gráfica para controlar un hub LEGO (Pybricks) por Bluetooth.
# Controles en pantalla y soporte opcional de mando (pygame), sin depender del teclado global.

import asyncio
import threading
import tempfile
import os
from queue import Queue, Empty
from typing import Optional

import tkinter as tk
from tkinter import ttk

from pybricksdev.ble import find_device  # type: ignore
from pybricksdev.connections.pybricks import PybricksHubBLE  # type: ignore

# Soporte opcional de mando con pygame (reemplaza la librería inputs)
try:
    import pygame
    # Inicializar joystick (no forzamos display)
    pygame.init()
    pygame.joystick.init()
    GAMEPAD_AVAILABLE = pygame.joystick.get_count() > 0
except Exception:
    GAMEPAD_AVAILABLE = False

# -------------------- Lógica de comandos a enviar al hub --------------------

def create_program(drive_cmd: str, claw_cmd: str) -> str:
    drive_commands = {
        'adelante': "motorC.run(400)",
        'atras': "motorC.run(-400)",
        'izquierda': "motorA.run(-400)",
        'derecha': "motorA.run(400)",
        'adelante_lento': "motorC.run(80)",
        'atras_lento': "motorC.run(-80)",
        'izquierda_lento': "motorA.run(-80)",
        'derecha_lento': "motorA.run(80)",
        'stop': "motorA.stop()\nmotorC.stop()",
    }

    claw_commands = {
        'cerrar': "motorE.run_angle(200, 1200)",
        'abrir': "motorE.run_angle(200, -1200)",
        'cerrar_lento': "motorE.run_angle(100, 250)",
        'abrir_lento': "motorE.run_angle(100, -250)",
        'stop': "motorE.stop()",
    }

    drive_code = drive_commands.get(drive_cmd, "motorA.stop()\nmotorC.stop()")
    claw_code = claw_commands.get(claw_cmd, "motorE.stop()")

    program = f"""
from pybricks.hubs import PrimeHub
from pybricks.pupdevices import Motor
from pybricks.parameters import Port
from pybricks.tools import wait

hub = PrimeHub()

motorA = Motor(Port.A)
motorC = Motor(Port.C)
motorE = Motor(Port.E)

{drive_code}
{claw_code}
wait(300)
"""
    return program

def compute_drive_command(pressed: set) -> str:
    w = 'w' in pressed
    s = 's' in pressed
    a = 'a' in pressed
    d = 'd' in pressed
    i = 'i' in pressed
    j = 'j' in pressed
    k = 'k' in pressed
    l = 'l' in pressed

    if i or j or k or l:
        if i:
            return 'adelante_lento'
        if k:
            return 'atras_lento'
        if j:
            return 'izquierda_lento'
        if l:
            return 'derecha_lento'

    if w and not s:
        return 'adelante'
    if s and not w:
        return 'atras'
    if a and not d:
        return 'izquierda'
    if d and not a:
        return 'derecha'
    return 'stop'

async def execute_command(hub: PybricksHubBLE, drive_cmd: str, claw_cmd: str, log_cb=None):
    program = create_program(drive_cmd, claw_cmd)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as tf:
        tf.write(program)
        temp_path = tf.name
    try:
        await hub.run(temp_path, wait=True, print_output=False)
        if log_cb:
            log_cb(f"Ejecutado: drive={drive_cmd}, claw={claw_cmd}")
    except Exception as e:
        if log_cb:
            log_cb(f"Error ejecutando comandos: {e}")
    finally:
        try:
            os.unlink(temp_path)
        except Exception:
            pass

# -------------------- Worker BLE asíncrono en hilo dedicado --------------------

class BLEWorker:
    def __init__(self, log_queue: Queue):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._thread_main, daemon=True)
        self.queue = None  # se crea dentro del loop
        self.hub = None
        self.pressed = set()
        self.lock = threading.Lock()
        self.last_state = {'drive': None, 'claw': None}
        self.perpetual = {'drive': None, 'claw': None}
        self.running = threading.Event()
        self.log_queue = log_queue

    def log(self, msg: str):
        self.log_queue.put(msg)

    def _thread_main(self):
        asyncio.set_event_loop(self.loop)
        self.queue = asyncio.Queue()
        self.loop.create_task(self._runner())
        try:
            self.loop.run_forever()
        finally:
            pending = asyncio.all_tasks(self.loop)
            for t in pending:
                t.cancel()

    async def _runner(self):
        try:
            self.log("Buscando hub mediante Bluetooth…")
            device = await find_device()
            if not device:
                self.log("No se ha encontrado hub.")
                return
            name = getattr(device, 'name', str(device))
            self.log(f"Conectando a {name}…")
            self.hub = PybricksHubBLE(device)
            await self.hub.connect()
            self.log("Conectado. Listo para recibir órdenes.")
            self.running.set()

            asyncio.create_task(self._ticker())

            while True:
                token = await self.queue.get()
                with self.lock:
                    drive_cmd = compute_drive_command(self.pressed)
                    claw_cmd = 'stop'
                    if 'x' in self.pressed and 'z' not in self.pressed:
                        claw_cmd = 'cerrar'
                    elif 'z' in self.pressed and 'x' not in self.pressed:
                        claw_cmd = 'abrir'
                    elif 'm' in self.pressed and 'n' not in self.pressed:
                        claw_cmd = 'cerrar_lento'
                    elif 'n' in self.pressed and 'm' not in self.pressed:
                        claw_cmd = 'abrir_lento'

                    # Sobrescritura por modo perpetuo
                    if self.perpetual['drive'] is not None:
                        drive_cmd = self.perpetual['drive']
                    if self.perpetual['claw'] is not None:
                        claw_cmd = self.perpetual['claw']

                    current_state = {'drive': drive_cmd, 'claw': claw_cmd}

                force = (token == 'tick') and (self.perpetual['drive'] is not None or self.perpetual['claw'] is not None)
                if force or current_state != self.last_state:
                    await execute_command(self.hub, drive_cmd, claw_cmd, self.log)
                    self.last_state = current_state
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.log(f"Error en worker: {e}")
        finally:
            try:
                if self.hub:
                    await self.hub.disconnect()
                    self.log("Hub desconectado.")
            except Exception as e:
                self.log(f"Error al desconectar: {e}")
            self.running.clear()

    def start(self):
        if self.thread.is_alive():
            return
        self.thread.start()

    def stop(self):
        if self.loop.is_running():
            for task in asyncio.all_tasks(self.loop):
                task.cancel()
            self.loop.call_soon_threadsafe(self.loop.stop)

    async def _ticker(self):
        try:
            while True:
                await asyncio.sleep(0.25)
                if self.queue is not None:
                    await self.queue.put('tick')
        except asyncio.CancelledError:
            pass

    # Interfaz desde el hilo de la GUI
    def set_perpetual_drive(self, cmd: Optional[str]):
        with self.lock:
            self.perpetual['drive'] = cmd
        if self.loop.is_running() and self.queue is not None:
            self.loop.call_soon_threadsafe(self.queue.put_nowait, 'change')

    def set_perpetual_claw(self, cmd: Optional[str]):
        with self.lock:
            self.perpetual['claw'] = cmd
        if self.loop.is_running() and self.queue is not None:
            self.loop.call_soon_threadsafe(self.queue.put_nowait, 'change')

    def clear_perpetual(self):
        with self.lock:
            self.perpetual = {'drive': None, 'claw': None}
        if self.loop.is_running() and self.queue is not None:
            self.loop.call_soon_threadsafe(self.queue.put_nowait, 'change')

    def set_key(self, key: str, down: bool):
        with self.lock:
            if down:
                self.pressed.add(key)
            else:
                self.pressed.discard(key)
        if self.loop.is_running() and self.queue is not None:
            self.loop.call_soon_threadsafe(self.queue.put_nowait, 'change')

# -------------------- Hilo para leer Gamepad (pygame) --------------------

class GamepadThread:
    """
    Mapeo PS4:
    - L2 (trigger axis) => cerrar garra (set key x True via axis detection)
    - R2 (trigger axis) => abrir garra
    - L1 (button index 4) => cerrar garra lento (mapeado a 'm' o 'n')
    - R1 (button index 5) => abrir garra lento
    - D-PAD (hat 0) => movimiento lento (i/j/k/l)
    - Right stick (axes 2/3) => movimiento perpetuo (set_perpetual_drive)
    - START/OPTIONS (button 9 or 8 depending) => stop garra (set_perpetual_claw('stop'))
    - Square (button 0 on some mappings, but commonly button 0 is X/A; we try typical mapping and also check others)
      We use:
        - btn_square -> cerrar continuo (set_perpetual_claw('cerrar'))
        - btn_circle -> abrir continuo (set_perpetual_claw('abrir'))
        - btn_triangle -> detener continuidad (clear_perpetual)
    """
    def __init__(self, worker: BLEWorker, log_queue: Queue):
        self.worker = worker
        self.log = lambda m: log_queue.put(m)
        self.t = None
        self._stop = threading.Event()
        self.joystick = None

    def start(self):
        if not GAMEPAD_AVAILABLE or (self.t and self.t.is_alive()):
            if not GAMEPAD_AVAILABLE:
                self.log("No hay mando disponible (pygame).")
            return
        # Inicializar primer joystick si no está inicializado
        try:
            if pygame.joystick.get_count() == 0:
                self.log("No se detectó ningún mando al intentar activar.")
                return
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()
        except Exception as e:
            self.log(f"Error inicializando joystick: {e}")
            return

        self._stop.clear()
        self.t = threading.Thread(target=self._run, daemon=True)
        self.t.start()
        self.log("Control de mando activo (pygame).")

    def stop(self):
        self._stop.set()

    def _run(self):
        try:
            # Loop de lectura del mando
            while not self._stop.is_set():
                # Procesar eventos internos de pygame
                try:
                    pygame.event.pump()
                except Exception:
                    # Si hay error con pygame, terminamos el hilo
                    self.log("Error en pygame.event.pump(), deteniendo lectura de mando.")
                    break

                # Re-detectar joystick si es necesario
                if self.joystick is None or not getattr(self.joystick, 'get_init', lambda: True)():
                    try:
                        if pygame.joystick.get_count() > 0:
                            self.joystick = pygame.joystick.Joystick(0)
                            self.joystick.init()
                            self.log(f"Mando (re)conectado: {self.joystick.get_name()}")
                        else:
                            pygame.time.wait(200)
                            continue
                    except Exception:
                        pygame.time.wait(200)
                        continue

                # --- LECTURA DE HAT (D-PAD) para movimiento lento (i/j/k/l) ---
                try:
                    hatx, haty = self.joystick.get_hat(0)
                except Exception:
                    hatx = haty = 0

                # Mapear hat -> i/j/k/l (lento)
                self.worker.set_key('i', haty == 1)    # up -> adelante lento
                self.worker.set_key('k', haty == -1)   # down -> atrás lento
                self.worker.set_key('j', hatx == -1)   # left -> izquierda lento
                self.worker.set_key('l', hatx == 1)    # right -> derecha lento

                # --- LEFT STICK para WASD rápido (por compatibilidad con teclado/GUI) ---
                try:
                    lx = self.joystick.get_axis(0)
                    ly = self.joystick.get_axis(1)
                except Exception:
                    lx = ly = 0.0

                dead = 0.25
                self.worker.set_key('w', ly < -dead)
                self.worker.set_key('s', ly > dead)
                self.worker.set_key('a', lx < -dead)
                self.worker.set_key('d', lx > dead)

                # --- RIGHT STICK para MOVIMIENTO PERPETUO (override) ---
                # según tu confirmación: no se desactiva automáticamente al volver al centro (respuesta 1 = No)
                # Así que sólo se cambia el modo perpetuo cuando el stick supera deadzone.
                try:
                    rx = self.joystick.get_axis(2)
                    ry = self.joystick.get_axis(3)
                except Exception:
                    rx = ry = 0.0

                # Determinar dirección perpetua si el stick derecho está inclinado
                perp_cmd = None
                if ry < -0.5:
                    perp_cmd = 'adelante'
                elif ry > 0.5:
                    perp_cmd = 'atras'
                elif rx < -0.5:
                    perp_cmd = 'izquierda'
                elif rx > 0.5:
                    perp_cmd = 'derecha'

                # Si se detecta inclinación, activamos modo perpetuo correspondiente.
                # Si no se detecta inclinación, NO lo desactivamos (respuesta 1 = No).
                if perp_cmd is not None:
                    # Al activar perpetuo, queremos que esto sobrescriba otras entradas (respuesta 3 = Si)
                    self.worker.set_perpetual_drive(perp_cmd)
                    # opcional: log
                    self.log(f"Perpetuo drive activado: {perp_cmd}")

                # --- GATILLOS (L2/R2 asíncronos: axis) y L1/R1 (botones) ---
                # Intentamos leer triggers por axis (común en muchos mapeos).
                # L2 -> cerrar garra, R2 -> abrir garra
                try:
                    # Muchos sticks reportan triggers en axis 4/5 o 2/5; intentamos varios
                    lt = None
                    rt = None
                    # comprobar algunos índices plausibles (4,5 y también 2,5)
                    for idx in (4, 2):
                        try:
                            val = self.joystick.get_axis(idx)
                        except Exception:
                            val = None
                        if val is not None:
                            # guardamos primera lectura válida
                            if lt is None:
                                lt = val
                    for idx in (5, 5):
                        try:
                            val = self.joystick.get_axis(idx)
                        except Exception:
                            val = None
                        if val is not None:
                            if rt is None:
                                rt = val
                    # normalizar None -> 0
                    if lt is None: lt = 0.0
                    if rt is None: rt = 0.0
                except Exception:
                    lt = rt = 0.0

                # Umbral para triggers (analógico)
                # PS4 a veces da -1..1, a veces 0..1; comprobamos por magnitud
                trig_thresh = 0.4
                # L2 -> cerrar (map to 'x' pressed)
                if lt and (lt > trig_thresh or lt < -trig_thresh):
                    # activamos cerrar garra (equivalente a presionar botón 'x')
                    self.worker.set_key('x', True)
                else:
                    # no forzamos liberación si usuario mantiene otro input; respetamos pressed state
                    # pero para mantener comportamiento estable, solo desactivamos si axis no activo
                    self.worker.set_key('x', False)

                # R2 -> abrir (map to 'z' pressed)
                if rt and (rt > trig_thresh or rt < -trig_thresh):
                    self.worker.set_key('z', True)
                else:
                    self.worker.set_key('z', False)

                # L1 / R1 normalmente son botones (índices comunes 4 y 5, pero puede variar).
                try:
                    btn_l1 = self.joystick.get_button(4)
                except Exception:
                    btn_l1 = 0
                try:
                    btn_r1 = self.joystick.get_button(5)
                except Exception:
                    btn_r1 = 0

                # L1 cerrar lento -> m (cerrar_lento)
                if btn_l1 == 1:
                    self.worker.set_key('m', True)
                    # ensure other slow open key off
                    self.worker.set_key('n', False)
                else:
                    self.worker.set_key('m', False)

                # R1 abrir lento -> n
                if btn_r1 == 1:
                    self.worker.set_key('n', True)
                    self.worker.set_key('m', False)
                else:
                    self.worker.set_key('n', False)

                # --- BOTONES FACE y START/OPTIONS ---
                # mapeos comunes de botones (puede variar por sistema; se intenta usar el mapeo típico)
                try:
                    btn_0 = self.joystick.get_button(0)  # X / Cross (a menudo)
                    btn_1 = self.joystick.get_button(1)  # Circle (a menudo)
                    btn_2 = self.joystick.get_button(2)  # Square (a menudo)
                    btn_3 = self.joystick.get_button(3)  # Triangle (a menudo)
                except Exception:
                    btn_0 = btn_1 = btn_2 = btn_3 = 0

                # Interpretación solicitada:
                # Square (btn_2) => cerrar continuo
                # Circle (btn_1) => abrir continuo
                # Triangle (btn_3) => detener continuidad (clear_perpetual for claw)
                # Start/Options -> stop garra inmediato (we try button index 9 or 8)
                try:
                    btn_start = self.joystick.get_button(9)
                except Exception:
                    try:
                        btn_start = self.joystick.get_button(8)
                    except Exception:
                        btn_start = 0

                # Cuadrado -> cerrar continuo
                if btn_2 == 1:
                    self.worker.set_perpetual_claw('cerrar')
                    self.log("Perpetuo garra: cerrar")
                # Círculo -> abrir continuo
                if btn_1 == 1:
                    self.worker.set_perpetual_claw('abrir')
                    self.log("Perpetuo garra: abrir")
                # Triángulo -> detener continuidad (garra)
                if btn_3 == 1:
                    # detener únicamente la parte de garra perpetua
                    # implementamos conservadoramente: si hay un perpetual de garra, lo limpiamos.
                    with self.worker.lock:
                        self.worker.perpetual['claw'] = None
                    if self.worker.loop.is_running() and self.worker.queue is not None:
                        self.worker.loop.call_soon_threadsafe(self.worker.queue.put_nowait, 'change')
                    self.log("Perpetuo garra detenido (triangle)")

                # START/OPTIONS -> stop garra inmediato (no limpiar pressed per tu respuesta)
                if btn_start == 1:
                    # set perpetual claw to 'stop' so runner will send stop command (without clearing pressed)
                    self.worker.set_perpetual_claw('stop')
                    self.log("Stop garra inmediato (START)")

                # Small wait to avoid busy loop
                pygame.time.wait(30)

        except Exception as e:
            self.log(f"Mando desconectado o no disponible: {e}")
        finally:
            self.log("Lectura de mando finalizada.")

# -------------------- Interfaz gráfica (Tkinter) --------------------

class LegoGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Control de Garra LEGO – Pybricks")
        self.root.geometry("680x520")
        self.root.minsize(840, 480)

        self.log_queue = Queue()
        self.worker = BLEWorker(self.log_queue)
        self.gamepad = GamepadThread(self.worker, self.log_queue)

        self._build_ui()
        self._poll_logs()

    # UI
    def _build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except Exception:
            pass
        
        pastel_morado = "#C8A2C8"
        boton_morado = "#E6D1E6"

        self.root.configure(bg=pastel_morado)
        style.configure('TFrame', background=pastel_morado)
        style.configure('TLabelframe', background=pastel_morado)
        style.configure('TLabelframe.Label', background=pastel_morado)
        style.configure('TLabel', background=pastel_morado)
        style.configure('TButton', background=boton_morado, foreground='black')

        top = ttk.Frame(self.root, padding=10)
        top.pack(fill='x')

        self.btn_connect = ttk.Button(top, text="Conectar", command=self.on_connect)
        self.btn_connect.pack(side='left')

        self.btn_disconnect = ttk.Button(top, text="Desconectar", command=self.on_disconnect, state='disabled')
        self.btn_disconnect.pack(side='left', padx=(8, 0))

        self.btn_stop_all = ttk.Button(top, text="Parar todo", command=self.stop_all, state='disabled')
        self.btn_stop_all.pack(side='left', padx=(8, 0))

        if GAMEPAD_AVAILABLE:
            self.btn_gamepad = ttk.Button(top, text="Activar mando", command=self.on_toggle_gamepad, state='disabled')
            self.btn_gamepad.pack(side='left', padx=(20, 0))
        else:
            self.btn_gamepad = None

        self.status = ttk.Label(top, text="Estado: sin conexión")
        self.status.pack(side='right')

        body = ttk.Frame(self.root, padding=10)
        body.pack(fill='both', expand=True)

        # Panel de movimiento
        move = ttk.Labelframe(body, text="Movimiento")
        move.pack(side='left', fill='both', expand=True, padx=(0, 10))

        grid = ttk.Frame(move)
        grid.pack(pady=10)

        # Botones direccionales rápidos (WASD)
        self._mk_hold_button(grid, text='↑\nRápido', key_on='w', row=0, col=1)
        self._mk_hold_button(grid, text='←\nRápido', key_on='a', row=1, col=0)
        self._mk_hold_button(grid, text='Stop', key_on=None, row=1, col=1, command=self.stop_move)
        self._mk_hold_button(grid, text='→\nRápido', key_on='d', row=1, col=2)
        self._mk_hold_button(grid, text='↓\nRápido', key_on='s', row=2, col=1)

        # Botones lentos (IJKL)
        slow = ttk.Frame(move)
        slow.pack(pady=10)
        ttk.Label(slow, text="Precisión (lento)").pack()
        slowg = ttk.Frame(slow)
        slowg.pack()
        self._mk_hold_button(slowg, text='↑\nLento', key_on='i', row=0, col=1)
        self._mk_hold_button(slowg, text='←\nLento', key_on='j', row=1, col=0)
        self._mk_hold_button(slowg, text='→\nLento', key_on='l', row=1, col=2)
        self._mk_hold_button(slowg, text='↓\nLento', key_on='k', row=2, col=1)

        # Panel de garra
        claw = ttk.Labelframe(body, text="Garra")
        claw.pack(side='left', fill='both', expand=True)

        clawg = ttk.Frame(claw)
        clawg.pack(pady=10)
        self._mk_hold_button(clawg, text='Cerrar', key_on='x', row=0, col=0)
        self._mk_hold_button(clawg, text='Abrir', key_on='z', row=0, col=1)
        self._mk_hold_button(clawg, text='Cerrar lento', key_on='m', row=1, col=0)
        self._mk_hold_button(clawg, text='Abrir lento', key_on='n', row=1, col=1)
        ttk.Button(clawg, text='Parar garra', command=self.stop_claw).grid(row=2, column=0, columnspan=2, sticky='nsew', pady=(8, 0))

        # Panel de movimiento perpetuo
        perpetuo = ttk.Labelframe(body, text="Movimiento perpetuo")
        perpetuo.pack(side='left', fill='both', expand=True, padx=(10, 0))

        pg = ttk.Frame(perpetuo)
        pg.pack(pady=10)
        ttk.Label(pg, text='Conducir').grid(row=0, column=0, columnspan=2, pady=(0,4))
        ttk.Button(pg, text='Avanzar continuo', command=lambda: self.worker.set_perpetual_drive('adelante')).grid(row=1, column=0, sticky='nsew', padx=4, pady=4)
        ttk.Button(pg, text='Atrás continuo', command=lambda: self.worker.set_perpetual_drive('atras')).grid(row=1, column=1, sticky='nsew', padx=4, pady=4)
        ttk.Button(pg, text='Giro izq. continuo', command=lambda: self.worker.set_perpetual_drive('izquierda')).grid(row=2, column=0, sticky='nsew', padx=4, pady=4)
        ttk.Button(pg, text='Giro der. continuo', command=lambda: self.worker.set_perpetual_drive('derecha')).grid(row=2, column=1, sticky='nsew', padx=4, pady=4)

        ttk.Label(pg, text='Garra').grid(row=3, column=0, columnspan=2, pady=(8,4))
        ttk.Button(pg, text='Cerrar continuo', command=lambda: self.worker.set_perpetual_claw('cerrar')).grid(row=4, column=0, sticky='nsew', padx=4, pady=4)
        ttk.Button(pg, text='Abrir continuo', command=lambda: self.worker.set_perpetual_claw('abrir')).grid(row=4, column=1, sticky='nsew', padx=4, pady=4)
        ttk.Button(pg, text='Detener perpetuo', command=self.stop_perpetuo).grid(row=5, column=0, columnspan=2, sticky='nsew', padx=4, pady=(8,0))

        # Log
        logf = ttk.Labelframe(self.root, text="Registro")
        logf.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        self.log_text = tk.Text(logf, height=8, wrap='word')
        self.log_text.pack(fill='both', expand=True)
        self.log_text.configure(state='disabled')

    def _mk_hold_button(self, parent, text, key_on, row, col, command=None):
        btn = ttk.Button(parent, text=text)
        btn.grid(row=row, column=col, padx=6, pady=6, sticky='nsew')
        parent.grid_columnconfigure(col, weight=1)
        parent.grid_rowconfigure(row, weight=1)
        if command is None:
            def press(_e=None, key=key_on):
                if key:
                    self.worker.set_key(key, True)
            def release(_e=None, key=key_on):
                if key:
                    self.worker.set_key(key, False)
            btn.bind('<ButtonPress-1>', press)
            btn.bind('<ButtonRelease-1>', release)
        else:
            btn.configure(command=command)
        return btn

    # Acciones de UI
    def stop_all(self):
        self.stop_move()
        self.stop_claw()
    def on_connect(self):
        self.status.configure(text="Estado: conectando…")
        self._log("Conectando…")
        self.worker.start()
        def check_ready():
            if self.worker.running.is_set():
                self.status.configure(text="Estado: conectado")
                self.btn_connect.configure(state='disabled')
                self.btn_disconnect.configure(state='normal')
                self.btn_stop_all.configure(state='normal')
                if self.btn_gamepad is not None:
                    self.btn_gamepad.configure(state='normal')
            else:
                self.root.after(200, check_ready)
        check_ready()

    def on_disconnect(self):
        self.status.configure(text="Estado: desconectando…")
        try:
            self.worker.stop()
        finally:
            self.btn_connect.configure(state='normal')
            self.btn_disconnect.configure(state='disabled')
            self.btn_stop_all.configure(state='disabled')
            if self.btn_gamepad is not None:
                self.btn_gamepad.configure(state='disabled', text='Activar mando')
            self.status.configure(text="Estado: sin conexión")
            self._log("Desconectado.")

    def on_toggle_gamepad(self):
        if not GAMEPAD_AVAILABLE:
            return
        if self.btn_gamepad['text'].startswith('Activar'):
            self.gamepad.start()
            self.btn_gamepad.configure(text='Desactivar mando')
        else:
            self.gamepad.stop()
            self.btn_gamepad.configure(text='Activar mando')

    def stop_move(self):
        for k in ['w', 'a', 's', 'd', 'i', 'j', 'k', 'l']:
            self.worker.set_key(k, False)
        # No interfiere con modo perpetuo; usa stop_perpetuo para detener continuo.

    def stop_claw(self):
        # En GUI, parar garra limpia los keys de garra (porque es una acción manual)
        for k in ['x', 'z', 'm', 'n']:
            self.worker.set_key(k, False)
        # También pedimos un stop inmediato (sin alterar otros perpetuos)
        self.worker.set_perpetual_claw('stop')
        self._log('Garra parada')

    def stop_perpetuo(self):
        self.worker.clear_perpetual()
        self._log('Perpetuo detenido')

    # Log helpers
    def _log(self, msg: str):
        self.log_queue.put(msg)

    def _poll_logs(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log_text.configure(state='normal')
                self.log_text.insert('end', msg + "\n")
                self.log_text.see('end')
                self.log_text.configure(state='disabled')
        except Empty:
            pass
        self.root.after(150, self._poll_logs)

def main():
    root = tk.Tk()
    app = LegoGUI(root)
    root.mainloop()

if __name__ == '__main__':
    main()
