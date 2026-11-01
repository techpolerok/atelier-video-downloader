#!/usr/bin/env bash
set -euo pipefail

APP_NAME="yt-downloader"
ARCH="x86_64"
BUILD_DIR="build_appimage"
APPDIR="${BUILD_DIR}/AppDir"

echo "=== [1/6] Preparando entorno virtual de compilación ==="
python3 -m venv "${BUILD_DIR}/venv"
source "${BUILD_DIR}/venv/bin/activate"
pip install --upgrade pip wheel
pip install -r requirements.txt pyinstaller

echo "=== [2/6] Compilando aplicación con PyInstaller ==="
# Usamos --onedir porque AppImage ya comprime el paquete y arranca al instante.
# --collect-all yt_dlp asegura que todos los extractores dinámicos se incluyan.
pyinstaller --noconfirm \
    --onedir \
    --windowed \
    --name "${APP_NAME}" \
    --collect-all yt_dlp \
    main.py

echo "=== [3/6] Creando estructura AppDir ==="
rm -rf "${APPDIR}"
mkdir -p "${APPDIR}/usr/bin"
mkdir -p "${APPDIR}/usr/share/applications"
mkdir -p "${APPDIR}/usr/share/icons/hicolor/scalable/apps"

# Copiar los archivos compilados por PyInstaller
cp -r "dist/${APP_NAME}/"* "${APPDIR}/usr/bin/"

echo "=== [4/6] Integrando FFmpeg y FFprobe estáticos ==="
# Descarga binarios estáticos para no depender del gestor de paquetes del sistema
FFMPEG_URL="https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz"
if [ ! -f "${BUILD_DIR}/ffmpeg.tar.xz" ]; then
    curl -L "${FFMPEG_URL}" -o "${BUILD_DIR}/ffmpeg.tar.xz"
fi
tar -xf "${BUILD_DIR}/ffmpeg.tar.xz" -C "${BUILD_DIR}"
cp "${BUILD_DIR}"/ffmpeg-master-latest-linux64-gpl/bin/ffmpeg "${APPDIR}/usr/bin/"
cp "${BUILD_DIR}"/ffmpeg-master-latest-linux64-gpl/bin/ffprobe "${APPDIR}/usr/bin/"
chmod +x "${APPDIR}/usr/bin/ffmpeg" "${APPDIR}/usr/bin/ffprobe"

echo "=== [5/6] Configurando lanzador AppRun, icono y .desktop ==="
cat << 'EOF' > "${APPDIR}/AppRun"
#!/usr/bin/env bash
SELF=$(readlink -f "$0")
HERE=${SELF%/*}

# Añadimos usr/bin al PATH para que la app detecte el ffmpeg interno automáticamente
export PATH="${HERE}/usr/bin:${PATH}"
export LD_LIBRARY_PATH="${HERE}/usr/bin/_internal:${LD_LIBRARY_PATH:-}"

# Evita conflictos de plugins Qt con el sistema anfitrión
export QT_PLUGIN_PATH="${HERE}/usr/bin/_internal/PySide6/Qt/plugins"

exec "${HERE}/usr/bin/yt-downloader" "$@"
EOF
chmod +x "${APPDIR}/AppRun"

# Generar el archivo .desktop para AppImage
cat << EOF > "${APPDIR}/${APP_NAME}.desktop"
[Desktop Entry]
Type=Application
Name=Atelier Video Downloader
Comment=Download video and audio streams powered by yt-dlp
Exec=${APP_NAME}
Icon=${APP_NAME}
Categories=Network;AudioVideo;Video;
Terminal=false
EOF
cp "${APPDIR}/${APP_NAME}.desktop" "${APPDIR}/usr/share/applications/"

# Crear icono SVG vectorial limpio
cat << 'EOF' > "${APPDIR}/${APP_NAME}.svg"
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">
  <rect x="4" y="4" width="56" height="56" rx="14" fill="#7C2D36"/>
  <path d="M32 16v22m0 0l-9-9m9 9l9-9" stroke="#F6F3EC" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
  <path d="M18 46h28" stroke="#F6F3EC" stroke-width="5" stroke-linecap="round"/>
</svg>
EOF
cp "${APPDIR}/${APP_NAME}.svg" "${APPDIR}/usr/share/icons/hicolor/scalable/apps/"

echo "=== [6/6] Generando archivo .AppImage final ==="
APPIMAGETOOL="${BUILD_DIR}/appimagetool-${ARCH}.AppImage"
if [ ! -f "${APPIMAGETOOL}" ]; then
    curl -L "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-${ARCH}.AppImage" -o "${APPIMAGETOOL}"
    chmod +x "${APPIMAGETOOL}"
fi

# --appimage-extract-and-run permite ejecutarlo incluso dentro de contenedores Docker sin FUSE
ARCH="${ARCH}" "${APPIMAGETOOL}" --appimage-extract-and-run "${APPDIR}" "Atelier_Video_Downloader-${ARCH}.AppImage"
chmod +x "Atelier_Video_Downloader-${ARCH}.AppImage"

echo "=========================================================="
echo "¡Listo! Ejecutable creado: Atelier_Video_Downloader-${ARCH}.AppImage"
echo "=========================================================="