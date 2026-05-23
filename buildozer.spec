[app]
# Nombre de tu app
title = NeonFlow
package.name = neonflow
package.domain = org.test
source.include_exts = py,png,jpg,kv,atlas,sqlite,db
version = 0.1

# Requisitos básicos de tu app
requirements = python3,kivy,kivymd,pillow,sqlite3

# Orientación y pantalla
orientation = portrait
fullscreen = 0

# Configuración de Android
android.archs = arm64-v8a
android.accept_sdk_license = True
icon.filename = icono.png

[buildozer]
# Nivel de detalle (2 es ideal para ver errores si algo falla)
log_level = 2
warn_on_root = 1

# Carpeta de salida
bin_dir = ./bin
