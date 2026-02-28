#!/usr/bin/env bash
set -euo pipefail

APP_NAME="TaxPDFRedactor.app"
DIST_DIR="dist"
DMG_NAME="TaxPDFRedactor"
STAGING_DIR="${DIST_DIR}/dmg-staging"

rm -rf "${STAGING_DIR}"
mkdir -p "${STAGING_DIR}"
cp -R "${DIST_DIR}/${APP_NAME}" "${STAGING_DIR}/${APP_NAME}"

hdiutil create \
  -volname "Tax PDF Redactor" \
  -srcfolder "${STAGING_DIR}" \
  -ov \
  -format UDZO \
  "${DIST_DIR}/${DMG_NAME}.dmg"
