# Batch Folder Redaction — Design Spec

**Date:** 2026-03-22
**Status:** Approved

---

## Overview

Add a batch folder redaction mode to the Tax PDF Redactor desktop app. The user selects an input folder, configures redaction rules (same options as today), and the app recursively finds all PDFs, redacts every match in every file automatically, and writes results to a mirrored output folder structure. A summary screen shows per-file status and per-category match counts.

---

## Goals

- Redact all PDFs inside a folder in one operation, preserving subfolder structure in the output
- Reuse existing redaction rules, engine, and options form — no duplicate logic
- Skip files already named `*redacted*` (they are previous outputs)
- Skip and report individual file failures without aborting the whole batch
- Show a per-file summary with expandable error details after completion

## Non-Goals

- Per-file match review step (automatic apply of all matches)
- Parallel file processing (sequential only in v1)
- Cancel mid-batch
- Resume a partial batch

---

## User Flow

1. User opens the app (or is already on the upload screen).
2. User fills in redaction options (names, TINs, auto-detect checkboxes) — unchanged from today.
3. User clicks the **Batch Folder** mode toggle in the file input area.
   - The drop zone is replaced by an input folder picker and an optional output folder field.
4. User picks an input folder (via "Browse..." or "Open Folder..." from the File menu).
5. User optionally overrides the output folder (default: `<input_folder>/redacted/`).
6. User clicks **Redact Folder**.
7. App scans for PDFs, shows `BatchProgressDialog` with per-file progress.
8. On completion, app navigates to `BatchResultPanel` showing a file-by-file summary table.
9. User clicks **Open Output Folder** or **Redact Another Folder**.

---

## Architecture

### New Components

| Component | Location | Responsibility |
|---|---|---|
| `FolderScanService` | `app/services/folder_scan_service.py` | Recursive PDF discovery, output-path computation |
| `BatchFolderWorker` | `app/ui/workers.py` | Sequential per-file analyze+apply in background thread |
| `BatchProgressDialog` | `app/ui/batch_progress_dialog.py` | Deterministic progress bar with current filename |
| `BatchResultPanel` | `app/ui/batch_result_panel.py` | Post-run summary screen with file table |

### Modified Components

| Component | Change |
|---|---|
| `app/core/models.py` | Add `BatchFileItem`, `BatchFileStatus`, `BatchFileResult` |
| `app/ui/upload_panel.py` | Add mode toggle (Single File / Batch Folder), folder picker rows, `batch_requested` signal |
| `app/ui/main_window.py` | Wire batch flow: `start_batch()`, `BatchResultPanel` in stack, "Open Folder..." menu item |

---

## Data Models

Added to `app/core/models.py`:

```python
@dataclass
class BatchFileItem:
    input_path: Path    # absolute path to the source PDF
    output_path: Path   # pre-computed mirrored path in the output folder


class BatchFileStatus(str, Enum):
    REDACTED = "redacted"       # at least one match applied
    NO_MATCHES = "no_matches"   # analyzed fine, zero matches found
    ERROR = "error"             # couldn't open, read, or write


@dataclass
class BatchFileResult:
    input_path: Path
    output_path: Path
    status: BatchFileStatus
    match_counts: dict[RedactionCategory, int] = field(default_factory=dict)
    error_message: str | None = None

    @property
    def total_matches(self) -> int:
        return sum(self.match_counts.values())
```

---

## FolderScanService

**File:** `app/services/folder_scan_service.py`

```python
class FolderScanService:
    def scan(self, input_folder: Path, output_folder: Path) -> list[BatchFileItem]: ...
```

**Logic:**
- Walk `input_folder` recursively using `Path.rglob("*.pdf")`
- Skip any file whose stem contains `"redacted"` (case-insensitive check: `"redacted" in path.stem.lower()`)
- For each kept file:
  - Compute relative path from `input_folder`
  - Build `output_path = output_folder / relative_path.parent / f"{stem}_redacted.pdf"`
- Return sorted list of `BatchFileItem` objects (sorted by `input_path`)

**Note:** Output subdirectories are not created here. `RedactionEngine.apply()` already calls `destination_path.parent.mkdir(parents=True, exist_ok=True)`.

**Example:**
```
input_folder/sub_a/file1.pdf  →  output_folder/sub_a/file1_redacted.pdf
input_folder/file0.pdf        →  output_folder/file0_redacted.pdf
input_folder/sub_a/file2_redacted.pdf  →  skipped
```

---

## BatchFolderWorker

**File:** `app/ui/workers.py` (added alongside existing workers)

```python
class BatchProgressSignals(QObject):
    file_started = Signal(int, int, str)  # (current_index, total, relative_filename)
    file_done = Signal(object)            # BatchFileResult
    all_done = Signal(object)             # list[BatchFileResult]
    failed = Signal(str)                  # fatal pre-loop error


class BatchFolderWorker(QRunnable):
    def __init__(
        self,
        engine: RedactionEngine,
        items: list[BatchFileItem],
        request_template: RedactionRequest,
        input_folder: Path,               # used to compute relative display paths
    ) -> None: ...
```

**Processing loop** (background thread):
1. Emit `failed` and return early if `items` is empty.
2. For each `BatchFileItem` at index `i`:
   a. Compute `display_name = str(item.input_path.relative_to(input_folder))` for display (e.g. `sub_b/file4.pdf`)
   b. Emit `file_started(i + 1, total, display_name)`
   b. Build per-file request: `dataclasses.replace(request_template, input_path=item.input_path)`
   c. Call `engine.analyze(request)` — catch any exception → `BatchFileResult(status=ERROR, error_message=...)`
   d. If `analysis.matches` is empty → `BatchFileResult(status=NO_MATCHES)`
   e. Otherwise: collect all match IDs, call `engine.apply(...)`, compute `match_counts` via `Counter(m.category for m in analysis.matches)`, build `BatchFileResult(status=REDACTED, match_counts=...)`
   f. On any exception in apply → `BatchFileResult(status=ERROR, error_message=...)`
   g. Emit `file_done(result)`
3. Emit `all_done(results)`

---

## BatchProgressDialog

**File:** `app/ui/batch_progress_dialog.py`

Layout:
```
┌──────────────────────────────────────┐
│  Redacting folder...                 │
│                                      │
│  [████████████░░░░░░░] 8 of 17       │
│  Currently: sub_b/file4.pdf          │
└──────────────────────────────────────┘
```

- `QProgressBar` with `min=0`, `max=total_files`
- Label showing current filename (relative to input folder)
- Connects to `BatchFolderWorker.signals.file_started` to update bar and label
- No cancel button in v1

---

## BatchResultPanel

**File:** `app/ui/batch_result_panel.py`

Layout:
```
┌─────────────────────────────────────────────────────────────┐
│  Batch Complete                                             │
│  17 files · 14 redacted · 2 no matches · 1 error           │
├──────────────────┬──────────┬──────────────┬───────────────┤
│  File            │ Status   │ Matches      │ Error         │
├──────────────────┼──────────┼──────────────┼───────────────┤
│  sub_a/file1.pdf │ Redacted │ TIN:3        │               │
│  sub_a/file3.pdf │ Redacted │ TIN:1 Name:2 │               │
│  sub_b/file4.pdf │ No match │              │               │
│  sub_b/file5.pdf │ Error    │              │ ▶ Password... │
└──────────────────┴──────────┴──────────────┴───────────────┘
│  [Open Output Folder]              [Redact Another Folder] │
└─────────────────────────────────────────────────────────────┘
```

**Key behaviors:**
- File paths displayed relative to input folder
- Match counts shown as `TIN:3 Name:1` inline; full output path shown in tooltip for `REDACTED` rows only — `NO_MATCHES` rows have no output file and the tooltip should show nothing or "No output written"
- Error rows: clicking `▶` expands the full error message inline
- `NO_MATCHES` rows show `—` and no match detail; **no output file is created** for these rows (the worker returns after `analyze()` without calling `apply()`)
- Summary counts in header (redacted / no matches / errors)
- "Open Output Folder" → opens output folder root in Finder/Explorer
- "Redact Another Folder" → calls `MainWindow.reset_flow()`

---

## UploadPanel Changes

The file input area gains a mode toggle rendered as two mutually exclusive buttons (using `QButtonGroup`):

```
[ Single File ]  [ Batch Folder ]
```

**Single File mode** (default): existing drop zone and "Choose PDF" button are visible. Primary action: "Find Matches".

**Batch Folder mode**: drop zone hidden, replaced by:
```
Input folder:   [/path/to/folder        ] [Browse...]
Output folder:  [redacted/ (default)    ] [Browse...]
```
Primary action: "Redact Folder".

New signal emitted when "Redact Folder" is clicked:
```python
batch_requested = Signal(Path, Path)  # (input_folder, output_folder)
```

Validation before emitting:
- Input folder must exist and be a directory
- At least one redaction option must be configured (same check as today)

The options form (names, addresses, TINs, auto-detect) is **unchanged and always visible** in both modes.

---

## MainWindow Changes

1. Add `BatchResultPanel` instance to the `QStackedWidget`.
2. Add `"Open Folder..."` action to the `File` menu (below `"Open..."`, above separator), wired to `choose_folder()`.
3. Connect `upload_panel.batch_requested` → `start_batch(input_folder, output_folder)`.

**`start_batch()` logic:**
```python
def start_batch(self, input_folder: Path, output_folder: Path) -> None:
    options = self.upload_panel.collect_options()
    try:
        request_template = self.workflow.build_request(
            input_path=input_folder,  # placeholder; replaced per file in worker
            ...options...
        )
    except ValueError as exc:
        self._show_error(str(exc))
        return

    items = self.folder_scan_service.scan(input_folder, output_folder)
    if not items:
        self._show_error("No PDF files found in the selected folder.")
        return

    dialog = BatchProgressDialog(total=len(items), input_folder=input_folder, parent=self)
    worker = BatchFolderWorker(engine=self.engine, items=items, request_template=request_template)
    worker.signals.file_started.connect(dialog.update_progress)
    worker.signals.file_done.connect(...)   # optional: hook for future per-file streaming
    worker.signals.all_done.connect(lambda results: self._handle_batch_complete(results, output_folder, dialog))
    worker.signals.failed.connect(lambda msg: (dialog.close(), self._show_error(msg)))
    dialog.show()
    self.thread_pool.start(worker)

def _handle_batch_complete(self, results, output_folder, dialog):
    dialog.close()
    self.batch_result_panel.load_results(results, output_folder)
    self.stack.setCurrentWidget(self.batch_result_panel)
```

---

## Edge Cases

| Scenario | Behavior |
|---|---|
| Input folder has zero PDFs (after filtering) | Show error before launching worker |
| All PDFs in folder are named `*redacted*` | Treated as zero PDFs — show error |
| PDF is password-protected | `BatchFileResult(status=ERROR)` — skip and continue |
| PDF has no text layer (scanned) | `BatchFileResult(status=NO_MATCHES)` with warning in error_message |
| Output folder is inside input folder | Allowed; scanner skips the output folder's own PDFs since they will be named `*_redacted.pdf` |
| Output folder already has a file at the target path | `RedactionEngine.apply()` overwrites it (existing behavior) |
| Network/permissions error writing output | `BatchFileResult(status=ERROR)` — skip and continue |

---

## Testing

### Unit Tests

- `FolderScanService.scan()`: correct filtering of `*redacted*` files, correct output path mirroring, empty folder, all-filtered folder
- `BatchFileResult.total_matches`: correct sum across categories
- `BatchFolderWorker`: mock engine, verify `NO_MATCHES` path, `REDACTED` path, `ERROR` path, correct `match_counts`

### Integration Tests

- Scan a temp folder with mixed PDFs (some redacted-named, some in subfolders) and verify correct `BatchFileItem` list
- Run full batch on a temp folder, verify output structure mirrors input structure

### Manual QA

- Batch a folder with 3+ PDFs across 2 subfolders — verify output folder mirrors structure
- Include a password-protected PDF — verify it appears as ERROR in summary, others complete
- Include a `*_redacted.pdf` file — verify it is skipped
- Leave output folder field blank — verify default `redacted/` folder is used
- Click "Open Output Folder" from summary — verify Finder/Explorer opens correct folder
