import sys
import os
import ctypes
import subprocess
import traceback
from pathlib import Path
import time

# ========== AGREGAR AL INICIO DEL SCRIPT ==========
def ensure_console():
    """Fuerza a que se muestre una consola en Windows"""
    if os.name == 'nt':
        # Verificar si ya hay consola
        if not ctypes.windll.kernel32.GetConsoleWindow():
            # Crear una nueva consola
            ctypes.windll.kernel32.AllocConsole()
            # Redirigir stdout/stderr a la consola
            sys.stdout = open('CONOUT$', 'w')
            sys.stderr = open('CONOUT$', 'w')
            sys.stdin = open('CONIN$', 'r')
            print("Launcher iniciado")

# Llamar la función al inicio
ensure_console()
# ===============================================

try:
    import tkinter as tk
    from tkinter import messagebox
except Exception:
    tk = None
    messagebox = None

BASE_DIR = Path(__file__).resolve().parent
VENV_DIR = BASE_DIR / "venv"
REQUIREMENTS = BASE_DIR / "requirements.txt"
APP_SCRIPT = BASE_DIR / "main.py"
LOG_FILE = BASE_DIR / "launcher.log"

def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")

def show_message(title, text, level='info'):
    log(f"{level.upper()}: {title} - {text}")
    if messagebox:
        try:
            root = tk.Tk()
            root.withdraw()
            if level == 'error':
                messagebox.showerror(title, text)
            else:
                messagebox.showinfo(title, text)
            root.destroy()
        except Exception:
            pass

def run(cmd, check=True, capture=False):
    log(f"RUN: {' '.join(cmd)}")
    if capture:
        # Quitamos check=check dentro de subprocess para manejar el error nosotros
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.stdout:
            log(f"STDOUT: {res.stdout.strip()}")
        if res.stderr:
            log(f"STDERR: {res.stderr.strip()}")
        
        # Si check es True y el comando falló, lanzamos la excepción manualmente
        if check and res.returncode != 0:
            raise subprocess.CalledProcessError(res.returncode, cmd)
        return res
    else:
        return subprocess.run(cmd, check=check)

def create_venv(python_exe):
    try:
        run([python_exe, "-m", "venv", str(VENV_DIR)])
        log("Entorno virtual creado")
        return True
    except Exception as e:
        log(f"Error creando venv: {e}")
        return False

def install_requirements(pip_exe):
    if REQUIREMENTS.exists():
        try:
            # Añadimos capture=True para que el log registre la salida de pip
            run([pip_exe, "install", "-r", str(REQUIREMENTS)], capture=True)
            log("Instalación desde requirements.txt completada")
            return True
        except Exception as e:
            log(f"Error instalando desde requirements: {e}")
            return False
    else:
        log("requirements.txt no encontrado, instalando dependencias por defecto")
        try:
            # Añadimos capture=True aquí también
            run([pip_exe, "install", "PyQt6", "pandas", "requests", "openpyxl"], capture=True)
            log("Instalación por defecto completada")
            return True
        except Exception as e:
            log(f"Error instalando dependencias por defecto: {e}")
            return False

def venv_paths():
    if os.name == 'nt':
        py = VENV_DIR / "Scripts" / "python.exe"
        pyw = VENV_DIR / "Scripts" / "pythonw.exe"
        pip = VENV_DIR / "Scripts" / "pip.exe"
    else:
        py = VENV_DIR / "bin" / "python"
        pyw = py
        pip = VENV_DIR / "bin" / "pip"
    return str(py), str(pyw), str(pip)

def main(no_run=False):
    try:
        log("--- Lanzador iniciado ---")
		
        # 1) Verificar que exista Python (el que ejecuta este script)
        python_exe = sys.executable
        log(f"Python que ejecuta el launcher: {python_exe}")
        print(f"Python que ejecuta el launcher: {python_exe}")

        # 2) Crear venv si no existe
        if not VENV_DIR.exists():
            log("No se encontró venv; creando...")
            ok = create_venv(python_exe)
            if not ok:
                show_message("Error", "No se pudo crear el entorno virtual. Revisa launcher.log", 'error')
                return
        else:
            log("venv ya existe, se usará el existente")

        # 3) Determinar rutas dentro de venv
        py, pyw, pip = venv_paths()
        log(f"Rutas venv: python={py}, pythonw={pyw}, pip={pip}")

        # 4) Instalar dependencias con pip del venv
        try:
            res = subprocess.run([pip, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode != 0:
                log(f"pip no accesible en venv: {res.stderr}")
                show_message("Error", "pip no accesible en el entorno virtual. Revisa launcher.log", 'error')
                return
        except Exception as e:
            log(f"Error comprobando pip: {e}")
            show_message("Error", "Error comprobando pip en el venv. Revisa launcher.log", 'error')
            return

        ok = install_requirements(pip)
        if not ok:
            show_message("Error", "No se pudieron instalar las dependencias. Revisa launcher.log", 'error')
            return

        # 5) Opcional: ejecutar la app con pythonw (silencioso)
        if no_run:
            show_message("Listo", "Entorno preparado correctamente.", 'info')
            return

        if not APP_SCRIPT.exists():
            show_message("Error", f"No se encontró {APP_SCRIPT.name}", 'error')
            return

        # Lanzar la app en proceso separado usando pythonw para no abrir consola
        try:
            log(f"Iniciando aplicación: {pyw} {APP_SCRIPT}")
            print(f"Iniciando aplicación: {pyw} {APP_SCRIPT}")

            # Archivo para capturar errores del script hijo
            error_log_hijo = open(BASE_DIR / "error_hijo.log", "w")

            popen_args = {
                "args": [pyw, str(APP_SCRIPT)],
                "cwd": str(BASE_DIR),
                "close_fds": True,
                "stderr": error_log_hijo, # <--- Capturamos el error aquí
                "stdout": error_log_hijo
            }

            if os.name == 'nt':
                # Quitamos temporalmente el DETACHED_PROCESS para debuggear
                # y usamos CREATE_NO_WINDOW si queremos que sea invisible pero rastreable
                popen_args["creationflags"] = 0x08000000 # CREATE_NO_WINDOW
                subprocess.Popen(**popen_args)
            else:
                subprocess.Popen(**popen_args)
                
            log("Aplicación lanzada (verificando error_hijo.log si no aparece)")
            print("Aplicación lanzada (verificando error_hijo.log si no aparece)")
        except Exception as e:
            log(f"Error lanzando la aplicación: {e}\n{traceback.format_exc()}")
            show_message("Error", "Error lanzando la aplicación. Revisa launcher.log", 'error')
            return

    except Exception as e:
        log(f"Error inesperado: {e}\n{traceback.format_exc()}")
        show_message("Error inesperado", "Revisa launcher.log para más detalles", 'error')
    finally:
        log("--- Fin del lanzador ---\n")

if __name__ == '__main__':
    args = sys.argv[1:]
    no_run = False
    if '--no-run' in args or '--setup-only' in args:
        no_run = True
    main(no_run=no_run)