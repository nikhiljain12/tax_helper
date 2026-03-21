#!/usr/bin/env bash
set -euo pipefail

APP_NAME="TaxPDFRedactor.app"
DIST_DIR="dist"
DMG_NAME="TaxPDFRedactor"
STAGING_DIR="${DIST_DIR}/dmg-staging"
APP_PATH="${DIST_DIR}/${APP_NAME}"
STAGED_APP_PATH="${STAGING_DIR}/${APP_NAME}"
DMG_PATH="${DIST_DIR}/${DMG_NAME}.dmg"
MACOS_CODESIGN_IDENTITY="${MACOS_CODESIGN_IDENTITY:-}"
MACOS_NOTARY_PROFILE="${MACOS_NOTARY_PROFILE:-}"

require_command() {
  local command_name="$1"

  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "Missing required command '${command_name}'." >&2
    exit 1
  fi
}

sign_app_bundle() {
  echo "Codesigning app bundle with identity: ${MACOS_CODESIGN_IDENTITY}"
  codesign \
    --force \
    --deep \
    --options runtime \
    --timestamp \
    --sign "${MACOS_CODESIGN_IDENTITY}" \
    "${APP_PATH}"
  codesign --verify --deep --strict --verbose=2 "${APP_PATH}"
}

sign_dmg() {
  echo "Codesigning DMG with identity: ${MACOS_CODESIGN_IDENTITY}"
  codesign \
    --force \
    --timestamp \
    --sign "${MACOS_CODESIGN_IDENTITY}" \
    "${DMG_PATH}"
  codesign --verify --verbose=2 "${DMG_PATH}"
}

notarize_dmg() {
  echo "Submitting DMG for notarization with keychain profile: ${MACOS_NOTARY_PROFILE}"
  xcrun notarytool submit "${DMG_PATH}" \
    --keychain-profile "${MACOS_NOTARY_PROFILE}" \
    --wait

  echo "Stapling notarization ticket to DMG"
  xcrun stapler staple "${DMG_PATH}"
}

rm -rf "${STAGING_DIR}"
mkdir -p "${STAGING_DIR}"

if [[ ! -d "${APP_PATH}" ]]; then
  echo "Expected macOS app bundle at ${APP_PATH}. Run 'pyinstaller desktop_app.spec' on macOS first." >&2
  exit 1
fi

if [[ -n "${MACOS_NOTARY_PROFILE}" && -z "${MACOS_CODESIGN_IDENTITY}" ]]; then
  echo "MACOS_NOTARY_PROFILE requires MACOS_CODESIGN_IDENTITY because Apple notarization only accepts signed artifacts." >&2
  exit 1
fi

if [[ -n "${MACOS_CODESIGN_IDENTITY}" ]]; then
  require_command codesign
  sign_app_bundle
fi

ditto "${APP_PATH}" "${STAGED_APP_PATH}"
ln -s /Applications "${STAGING_DIR}/Applications"

rm -f "${DMG_PATH}"

hdiutil create \
  -volname "Tax PDF Redactor" \
  -srcfolder "${STAGING_DIR}" \
  -ov \
  -format UDZO \
  "${DMG_PATH}"

if [[ -n "${MACOS_CODESIGN_IDENTITY}" ]]; then
  sign_dmg
fi

if [[ -n "${MACOS_NOTARY_PROFILE}" ]]; then
  require_command xcrun
  notarize_dmg
fi
