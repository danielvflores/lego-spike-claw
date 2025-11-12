# gui_control_lego.py
# Interfaz gráfica para controlar un hub LEGO (Pybricks) por Bluetooth.
# Controles en pantalla y soporte opcional de mando (inputs), sin depender del teclado global.

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

# Soporte opcional de mando
try:
    from inputs import get_gamepad
    GAMEPAD_AVAILABLE = True
except Exception:
    GAMEPAD_AVAILABLE = False

# -------------------- Lógica de comandos a enviar al hub --------------------

def create_program(drive_cmd: str, claw_cmd: str) -> str:
    drive_commands = {
        'adelante': "motorC.run(300)",
        'atras': "motorC.run(-300)",
        'izquierda': "motorA.run(-300)",
        'derecha': "motorA.run(300)",
        'adelante_lento': "motorC.run(150)",
        'atras_lento': "motorC.run(-150)",
        'izquierda_lento': "motorA.run(-150)",
        'derecha_lento': "motorA.run(150)",
        'stop': "motorA.stop()\nmotorC.stop()",
    }

    claw_commands = {
        'cerrar': "motorE.run(300)",
        'abrir': "motorE.run(-300)",
        'cerrar_lento': "motorE.run(150)",
        'abrir_lento': "motorE.run(-150)",
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
            self.log("Buscando hub Bluetooth…")
            device = await find_device()
            if not device:
                self.log("No se encontró hub.")
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


# -------------------- Hilo para leer Gamepad (opcional) --------------------

class GamepadThread:
    def __init__(self, worker: BLEWorker, log_queue: Queue):
        self.worker = worker
        self.log = lambda m: log_queue.put(m)
        self.t = None
        self._stop = threading.Event()

    def start(self):
        if not GAMEPAD_AVAILABLE or (self.t and self.t.is_alive()):
            return
        self._stop.clear()
        self.t = threading.Thread(target=self._run, daemon=True)
        self.t.start()
        self.log("Control de mando activo (PS/Xbox).")

    def stop(self):
        self._stop.set()

    def _run(self):
        try:
            while not self._stop.is_set():
                events = get_gamepad()
                for e in events:
                    if e.code == "ABS_Y":
                        if e.state < 100:
                            self.worker.set_key('w', True)
                            self.worker.set_key('s', False)
                        elif e.state > 150:
                            self.worker.set_key('s', True)
                            self.worker.set_key('w', False)
                        else:
                            self.worker.set_key('w', False)
                            self.worker.set_key('s', False)
                    elif e.code == "ABS_X":
                        if e.state < 100:
                            self.worker.set_key('a', True)
                            self.worker.set_key('d', False)
                        elif e.state > 150:
                            self.worker.set_key('d', True)
                            self.worker.set_key('a', False)
                        else:
                            self.worker.set_key('a', False)
                            self.worker.set_key('d', False)
                    elif e.code == "ABS_RZ":
                        self.worker.set_key('m', e.state > 20)
                    elif e.code == "ABS_Z":
                        self.worker.set_key('n', e.state > 20)
                    elif e.code == "BTN_SOUTH":
                        self.worker.set_key('x', e.state == 1)
                    elif e.code == "BTN_WEST":
                        self.worker.set_key('z', e.state == 1)
        except Exception:
            self.log("Mando desconectado o no disponible.")


# -------------------- Interfaz gráfica (Tkinter) --------------------

class LegoGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Control LEGO – Pybricks")
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
        for k in ['x', 'z', 'm', 'n']:
            self.worker.set_key(k, False)
        # No interfiere con modo perpetuo; usa stop_perpetuo para detener continuo.

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
