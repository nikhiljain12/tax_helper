#!/usr/bin/env bash
set -euo pipefail

APP_NAME="TaxPDFRedactor.app"
DIST_DIR="dist"
DMG_NAME="TaxPDFRedactor"
STAGING_DIR="${DIST_DIR}/dmg-staging"
APP_PATH="${DIST_DIR}/${APP_NAME}"
DMG_PATH="${DIST_DIR}/${DMG_NAME}.dmg"

rm -rf "${STAGING_DIR}"
mkdir -p "${STAGING_DIR}"

if [[ ! -d "${APP_PATH}" ]]; then
  echo "Expected macOS app bundle at ${APP_PATH}. Run 'pyinstaller desktop_app.spec' on macOS first." >&2
  exit 1
fi

cp -R "${APP_PATH}" "${STAGING_DIR}/${APP_NAME}"
ln -s /Applications "${STAGING_DIR}/Applications"

rm -f "${DMG_PATH}"

hdiutil create \
  -volname "Tax PDF Redactor" \
  -srcfolder "${STAGING_DIR}" \
  -ov \
  -format UDZO \
  "${DMG_PATH}"
