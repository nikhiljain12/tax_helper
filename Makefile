PYTHON := .venv/bin/python
PYINSTALLER := .venv/bin/pyinstaller
ICON_SCRIPT := packaging/scripts/generate_icon.py
ICON_PATH := build/macos/TaxPDFRedactor.icns
PYINSTALLER_CACHE := $(CURDIR)/.pyinstaller-cache
APP_PATH := dist/TaxPDFRedactor.app
DMG_PATH := dist/TaxPDFRedactor.dmg

.PHONY: mac-build mac-clean

mac-build:
	@if [ "$$(uname -s)" != "Darwin" ]; then \
		echo "mac-build only supports macOS."; \
		exit 1; \
	fi
	@if [ ! -x "$(PYTHON)" ]; then \
		echo "Missing $(PYTHON). Create the virtualenv and install dependencies first."; \
		exit 1; \
	fi
	@if [ ! -x "$(PYINSTALLER)" ]; then \
		echo "Missing $(PYINSTALLER). Install build dependencies with 'pip install -e \".[build]\"'."; \
		exit 1; \
	fi
	@if ! command -v hdiutil >/dev/null 2>&1; then \
		echo "Missing 'hdiutil'. macOS DMG creation is unavailable."; \
		exit 1; \
	fi
	$(PYTHON) $(ICON_SCRIPT) $(ICON_PATH)
	PYINSTALLER_CONFIG_DIR="$(PYINSTALLER_CACHE)" $(PYINSTALLER) -y desktop_app.spec
	bash packaging/macos/build_dmg.sh
	@echo "Built app bundle: $(APP_PATH)"
	@echo "Built disk image: $(DMG_PATH)"

mac-clean:
	rm -rf build/desktop_app \
		build/macos \
		dist/TaxPDFRedactor \
		dist/TaxPDFRedactor.app \
		dist/TaxPDFRedactor.dmg \
		dist/dmg-staging \
		.pyinstaller-cache
