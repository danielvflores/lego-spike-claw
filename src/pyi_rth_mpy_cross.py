# Runtime hook para PyInstaller
# Agrega los directorios de mpy-cross al PATH cuando está empaquetado

import sys
import os

if getattr(sys, 'frozen', False):
    # Estamos en un ejecutable empaquetado
    base_path = sys._MEIPASS
    
    # Agregar directorios de mpy-cross al PATH
    mpy_v5_path = os.path.join(base_path, 'mpy_cross_v5')
    mpy_v6_path = os.path.join(base_path, 'mpy_cross_v6')
    
    if os.path.exists(mpy_v5_path):
        os.environ['PATH'] = mpy_v5_path + os.pathsep + os.environ.get('PATH', '')
    
    if os.path.exists(mpy_v6_path):
        os.environ['PATH'] = mpy_v6_path + os.pathsep + os.environ.get('PATH', '')
