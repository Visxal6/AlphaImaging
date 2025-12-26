from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QObject, QThread, Signal, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import alpha_core as core
from alpha_app.widgets import LogBox, PathListPanel


@dataclass(frozen=True)
class JobProgress:
    done: int
    total: int
    path: str
    message: str


class Worker(QObject):
    progressed = Signal(object)
    finished = Signal(object, object)

    def __init__(self, fn: Callable[[], object]) -> None:
        super().__init__()
        self._fn = fn

    def run(self) -> None:
        try:
            out = self._fn()
            self.finished.emit(out, None)
        except Exception as e:
            self.finished.emit(None, e)


class JobController(QObject):
    progressed = Signal(object)
    finished = Signal(object, object)

    def __init__(self) -> None:
        super().__init__()
        self._thread: Optional[QThread] = None
        self._worker: Optional[Worker] = None

    def start(self, fn: Callable[[], object]) -> None:
        self.stop()
        t = QThread()
        w = Worker(fn)
        w.moveToThread(t)
        t.started.connect(w.run)
        w.progressed.connect(self.progressed)
        w.finished.connect(self.finished)
        w.finished.connect(t.quit)
        w.finished.connect(w.deleteLater)
        t.finished.connect(t.deleteLater)
        self._thread = t
        self._worker = w
        t.start()

    def stop(self) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread = None
            self._worker = None


class BaseTab(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.controller = JobController()
        self.cancel_event = threading.Event()

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

        self.btn_run = QPushButton("Run")
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setEnabled(False)

        self.logbox = LogBox()

        self.controller.finished.connect(self._on_finished)

    def set_running(self, running: bool) -> None:
        self.btn_run.setEnabled(not running)
        self.btn_cancel.setEnabled(running)

    def reset_progress(self) -> None:
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

    def progress_cb(self, done: int, total: int, path: Path, message: str) -> None:
        if total <= 0:
            return
        pct = int((done * 100) / total)
        self.progress.setValue(max(0, min(100, pct)))
        self.logbox.log(f"{done}/{total} {message}: {path}")

    def _on_finished(self, result: object, error: object) -> None:
        self.set_running(False)
        if self.cancel_event.is_set():
            self.logbox.log("Canceled")
            return
        if error is not None:
            self.logbox.log(f"Error: {error}")
            return
        self.logbox.log("Done")


class SplitTab(BaseTab):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.inputs = PathListPanel("Inputs")
        self.out_dir = QLineEdit()
        self.btn_out_dir = QPushButton("Choose")

        self.rgb_suffix = QLineEdit("_rgb")
        self.alpha_suffix = QLineEdit("_alpha")

        self.on_missing = QComboBox()
        self.on_missing.addItems(["opaque", "error"])

        self.overwrite = QCheckBox("Overwrite")

        out_row = QHBoxLayout()
        out_row.addWidget(self.out_dir)
        out_row.addWidget(self.btn_out_dir)

        opts = QGroupBox("Options")
        form = QFormLayout(opts)
        form.addRow("Output folder", out_row)
        form.addRow("RGB suffix", self.rgb_suffix)
        form.addRow("Alpha suffix", self.alpha_suffix)
        form.addRow("On missing alpha", self.on_missing)
        form.addRow("", self.overwrite)

        buttons = QHBoxLayout()
        buttons.addWidget(self.btn_run)
        buttons.addWidget(self.btn_cancel)
        buttons.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(self.inputs)
        layout.addWidget(opts)
        layout.addWidget(self.progress)
        layout.addLayout(buttons)
        layout.addWidget(self.logbox)

        self.inputs.btn_add_files.clicked.connect(self._add_files)
        self.inputs.btn_add_folder.clicked.connect(self._add_folder)
        self.inputs.btn_remove.clicked.connect(self.inputs.list.remove_selected)
        self.inputs.btn_clear.clicked.connect(self.inputs.list.clear_all)
        self.btn_out_dir.clicked.connect(self._choose_out_dir)
        self.btn_run.clicked.connect(self._run)
        self.btn_cancel.clicked.connect(self._cancel)

    def _add_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Select images")
        self.inputs.list.add_paths([Path(f) for f in files])

    def _add_folder(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Select folder")
        if d:
            self.inputs.list.add_paths([Path(d)])

    def _choose_out_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Select output folder")
        if d:
            self.out_dir.setText(d)

    def _cancel(self) -> None:
        self.cancel_event.set()

    def _run(self) -> None:
        in_paths = self.inputs.list.get_paths()
        if not in_paths:
            QMessageBox.warning(self, "Missing input", "Add at least one input file or folder.")
            return
        out_dir = Path(self.out_dir.text().strip()) if self.out_dir.text().strip() else None
        if out_dir is None:
            QMessageBox.warning(self, "Missing output", "Choose an output folder.")
            return

        self.cancel_event.clear()
        self.reset_progress()
        self.set_running(True)

        def fn() -> object:
            return core.split_alpha_files(
                in_paths,
                out_dir,
                rgb_suffix=self.rgb_suffix.text(),
                alpha_suffix=self.alpha_suffix.text(),
                overwrite=self.overwrite.isChecked(),
                on_missing_alpha=self.on_missing.currentText(),
                progress_cb=lambda d, t, p, m: self.progress_cb(d, t, p, m),
                cancel_flag=self.cancel_event,
            )

        self.controller.start(fn)


class CombineTab(BaseTab):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.rgb = PathListPanel("RGB inputs")
        self.alpha = PathListPanel("Alpha inputs")

        self.out_dir = QLineEdit()
        self.btn_out_dir = QPushButton("Choose")

        self.rule_mode = QComboBox()
        self.rule_mode.addItems(["suffix", "folder", "exact"])
        self.alpha_suffix = QLineEdit("_alpha")
        self.rgb_suffix = QLineEdit("")
        self.rgb_dir_name = QLineEdit("rgb")
        self.alpha_dir_name = QLineEdit("alpha")
        self.case_sensitive = QCheckBox("Case sensitive")

        self.out_suffix = QLineEdit("_rgba")
        self.invert = QCheckBox("Invert mask")
        self.resize_mode = QComboBox()
        self.resize_mode.addItems(["error", "resize"])
        self.resample = QComboBox()
        self.resample.addItems(["nearest", "bilinear"])
        self.overwrite = QCheckBox("Overwrite")

        out_row = QHBoxLayout()
        out_row.addWidget(self.out_dir)
        out_row.addWidget(self.btn_out_dir)

        pairing = QGroupBox("Pairing")
        pairing_form = QFormLayout(pairing)
        pairing_form.addRow("Mode", self.rule_mode)
        pairing_form.addRow("Alpha suffix", self.alpha_suffix)
        pairing_form.addRow("RGB suffix", self.rgb_suffix)
        pairing_form.addRow("RGB folder name", self.rgb_dir_name)
        pairing_form.addRow("Alpha folder name", self.alpha_dir_name)
        pairing_form.addRow("", self.case_sensitive)

        opts = QGroupBox("Options")
        form = QFormLayout(opts)
        form.addRow("Output folder", out_row)
        form.addRow("Output suffix", self.out_suffix)
        form.addRow("", self.invert)
        form.addRow("Resize mode", self.resize_mode)
        form.addRow("Resample", self.resample)
        form.addRow("", self.overwrite)

        buttons = QHBoxLayout()
        buttons.addWidget(self.btn_run)
        buttons.addWidget(self.btn_cancel)
        buttons.addStretch(1)

        top = QGridLayout()
        top.addWidget(self.rgb, 0, 0)
        top.addWidget(self.alpha, 0, 1)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(pairing)
        layout.addWidget(opts)
        layout.addWidget(self.progress)
        layout.addLayout(buttons)
        layout.addWidget(self.logbox)

        self.rgb.btn_add_files.clicked.connect(lambda: self._add_files(self.rgb))
        self.rgb.btn_add_folder.clicked.connect(lambda: self._add_folder(self.rgb))
        self.rgb.btn_remove.clicked.connect(self.rgb.list.remove_selected)
        self.rgb.btn_clear.clicked.connect(self.rgb.list.clear_all)

        self.alpha.btn_add_files.clicked.connect(lambda: self._add_files(self.alpha))
        self.alpha.btn_add_folder.clicked.connect(lambda: self._add_folder(self.alpha))
        self.alpha.btn_remove.clicked.connect(self.alpha.list.remove_selected)
        self.alpha.btn_clear.clicked.connect(self.alpha.list.clear_all)

        self.btn_out_dir.clicked.connect(self._choose_out_dir)
        self.btn_run.clicked.connect(self._run)
        self.btn_cancel.clicked.connect(self._cancel)

    def _add_files(self, panel: PathListPanel) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Select images")
        panel.list.add_paths([Path(f) for f in files])

    def _add_folder(self, panel: PathListPanel) -> None:
        d = QFileDialog.getExistingDirectory(self, "Select folder")
        if d:
            panel.list.add_paths([Path(d)])

    def _choose_out_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Select output folder")
        if d:
            self.out_dir.setText(d)

    def _cancel(self) -> None:
        self.cancel_event.set()

    def _rule(self) -> core.PairingRule:
        return core.PairingRule(
            mode=self.rule_mode.currentText(),
            alpha_suffix=self.alpha_suffix.text(),
            rgb_suffix=self.rgb_suffix.text(),
            rgb_dir_name=self.rgb_dir_name.text(),
            alpha_dir_name=self.alpha_dir_name.text(),
            case_sensitive=self.case_sensitive.isChecked(),
        )

    def _run(self) -> None:
        rgb_paths = core.list_images(self.rgb.list.get_paths())
        alpha_paths = core.list_images(self.alpha.list.get_paths())
        if not rgb_paths or not alpha_paths:
            QMessageBox.warning(self, "Missing input", "Add RGB and Alpha inputs.")
            return
        out_dir = Path(self.out_dir.text().strip()) if self.out_dir.text().strip() else None
        if out_dir is None:
            QMessageBox.warning(self, "Missing output", "Choose an output folder.")
            return

        rule = self._rule()
        pairs, un_rgb, un_a = core.build_pairs(rgb_paths, alpha_paths, rule)
        self.logbox.log(f"Pairs: {len(pairs)}")
        if un_rgb:
            self.logbox.log(f"Unpaired RGB: {len(un_rgb)}")
        if un_a:
            self.logbox.log(f"Unpaired Alpha: {len(un_a)}")
        if not pairs:
            QMessageBox.warning(self, "No pairs", "No matching RGB/Alpha pairs found with current pairing settings.")
            return

        self.cancel_event.clear()
        self.reset_progress()
        self.set_running(True)

        def fn() -> object:
            return core.combine_alpha_files(
                pairs,
                out_dir,
                out_suffix=self.out_suffix.text(),
                invert=self.invert.isChecked(),
                resize_mode=self.resize_mode.currentText(),
                resample=self.resample.currentText(),
                overwrite=self.overwrite.isChecked(),
                progress_cb=lambda d, t, p, m: self.progress_cb(d, t, p, m),
                cancel_flag=self.cancel_event,
            )

        self.controller.start(fn)


class ValidateTab(BaseTab):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.inputs = PathListPanel("Inputs")
        self.fail_no_alpha = QCheckBox("Fail if no alpha")

        self.warn_pct_255 = QSpinBox()
        self.warn_pct_255.setRange(0, 100)
        self.warn_pct_255.setValue(99)

        self.warn_pct_zero = QSpinBox()
        self.warn_pct_zero.setRange(0, 100)
        self.warn_pct_zero.setValue(99)

        self.warn_std_lt = QSpinBox()
        self.warn_std_lt.setRange(0, 1000)
        self.warn_std_lt.setValue(1)

        self.warn_range_le = QSpinBox()
        self.warn_range_le.setRange(0, 255)
        self.warn_range_le.setValue(2)

        self.report_path = QLineEdit()
        self.btn_report = QPushButton("Save report as")

        report_row = QHBoxLayout()
        report_row.addWidget(self.report_path)
        report_row.addWidget(self.btn_report)

        opts = QGroupBox("Rules")
        form = QFormLayout(opts)
        form.addRow("", self.fail_no_alpha)
        form.addRow("Warn if %==255 >=", self.warn_pct_255)
        form.addRow("Warn if %==0 >=", self.warn_pct_zero)
        form.addRow("Warn if std <", self.warn_std_lt)
        form.addRow("Warn if range <=", self.warn_range_le)
        form.addRow("Report file", report_row)

        buttons = QHBoxLayout()
        buttons.addWidget(self.btn_run)
        buttons.addWidget(self.btn_cancel)
        buttons.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(self.inputs)
        layout.addWidget(opts)
        layout.addWidget(self.progress)
        layout.addLayout(buttons)
        layout.addWidget(self.logbox)

        self.inputs.btn_add_files.clicked.connect(self._add_files)
        self.inputs.btn_add_folder.clicked.connect(self._add_folder)
        self.inputs.btn_remove.clicked.connect(self.inputs.list.remove_selected)
        self.inputs.btn_clear.clicked.connect(self.inputs.list.clear_all)
        self.btn_report.clicked.connect(self._choose_report)
        self.btn_run.clicked.connect(self._run)
        self.btn_cancel.clicked.connect(self._cancel)

    def _add_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Select images")
        self.inputs.list.add_paths([Path(f) for f in files])

    def _add_folder(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Select folder")
        if d:
            self.inputs.list.add_paths([Path(d)])

    def _choose_report(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save report", filter="JSON (*.json);;CSV (*.csv)")
        if path:
            self.report_path.setText(path)

    def _cancel(self) -> None:
        self.cancel_event.set()

    def _rules(self) -> core.ValidationRules:
        return core.ValidationRules(
            warn_pct_255=float(self.warn_pct_255.value()),
            warn_pct_zero=float(self.warn_pct_zero.value()),
            warn_std_lt=float(self.warn_std_lt.value()),
            warn_range_le=int(self.warn_range_le.value()),
            fail_no_alpha=self.fail_no_alpha.isChecked(),
        )

    def _run(self) -> None:
        paths = core.list_images(self.inputs.list.get_paths())
        if not paths:
            QMessageBox.warning(self, "Missing input", "Add at least one input file or folder.")
            return

        report = self.report_path.text().strip()
        rules = self._rules()

        self.cancel_event.clear()
        self.reset_progress()
        self.set_running(True)

        def fn() -> object:
            results = core.validate_alpha_files(
                paths,
                rules=rules,
                progress_cb=lambda d, t, p, m: self.progress_cb(d, t, p, m),
                cancel_flag=self.cancel_event,
            )
            if report:
                rp = Path(report)
                if rp.suffix.lower() == ".csv":
                    core.results_to_csv(results, rp)
                else:
                    core.results_to_json(results, rp)
            warn = sum(1 for r in results if r.status == "WARN")
            fail = sum(1 for r in results if r.status == "FAIL")
            self.logbox.log(f"Results: {len(results)} PASS={len(results)-warn-fail} WARN={warn} FAIL={fail}")
            return results

        self.controller.start(fn)


class GenerateTab(BaseTab):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.inputs = PathListPanel("Inputs")
        self.out_dir = QLineEdit()
        self.btn_out_dir = QPushButton("Choose")

        self.kind = QComboBox()
        self.kind.addItems(["luminance", "threshold", "colorkey"])

        self.threshold = QSpinBox()
        self.threshold.setRange(0, 255)
        self.threshold.setValue(128)

        self.key_r = QSpinBox()
        self.key_g = QSpinBox()
        self.key_b = QSpinBox()
        for s in (self.key_r, self.key_g, self.key_b):
            s.setRange(0, 255)
            s.setValue(0)

        self.tolerance = QSpinBox()
        self.tolerance.setRange(0, 255)
        self.tolerance.setValue(20)

        self.out_suffix = QLineEdit("_alpha")
        self.invert = QCheckBox("Invert")
        self.overwrite = QCheckBox("Overwrite")

        out_row = QHBoxLayout()
        out_row.addWidget(self.out_dir)
        out_row.addWidget(self.btn_out_dir)

        key_row = QHBoxLayout()
        key_row.addWidget(QLabel("R"))
        key_row.addWidget(self.key_r)
        key_row.addWidget(QLabel("G"))
        key_row.addWidget(self.key_g)
        key_row.addWidget(QLabel("B"))
        key_row.addWidget(self.key_b)
        key_row.addStretch(1)

        opts = QGroupBox("Options")
        form = QFormLayout(opts)
        form.addRow("Output folder", out_row)
        form.addRow("Kind", self.kind)
        form.addRow("Threshold", self.threshold)
        form.addRow("Key color", key_row)
        form.addRow("Tolerance", self.tolerance)
        form.addRow("Output suffix", self.out_suffix)
        form.addRow("", self.invert)
        form.addRow("", self.overwrite)

        buttons = QHBoxLayout()
        buttons.addWidget(self.btn_run)
        buttons.addWidget(self.btn_cancel)
        buttons.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(self.inputs)
        layout.addWidget(opts)
        layout.addWidget(self.progress)
        layout.addLayout(buttons)
        layout.addWidget(self.logbox)

        self.inputs.btn_add_files.clicked.connect(self._add_files)
        self.inputs.btn_add_folder.clicked.connect(self._add_folder)
        self.inputs.btn_remove.clicked.connect(self.inputs.list.remove_selected)
        self.inputs.btn_clear.clicked.connect(self.inputs.list.clear_all)
        self.btn_out_dir.clicked.connect(self._choose_out_dir)
        self.btn_run.clicked.connect(self._run)
        self.btn_cancel.clicked.connect(self._cancel)

        self.kind.currentTextChanged.connect(self._sync_fields)
        self._sync_fields()

    def _sync_fields(self) -> None:
        k = self.kind.currentText()
        is_thr = k == "threshold"
        is_key = k == "colorkey"
        self.threshold.setEnabled(is_thr)
        self.key_r.setEnabled(is_key)
        self.key_g.setEnabled(is_key)
        self.key_b.setEnabled(is_key)
        self.tolerance.setEnabled(is_key)

    def _add_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Select images")
        self.inputs.list.add_paths([Path(f) for f in files])

    def _add_folder(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Select folder")
        if d:
            self.inputs.list.add_paths([Path(d)])

    def _choose_out_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Select output folder")
        if d:
            self.out_dir.setText(d)

    def _cancel(self) -> None:
        self.cancel_event.set()

    def _opts(self) -> core.GenerateOptions:
        return core.GenerateOptions(
            kind=self.kind.currentText(),
            threshold=int(self.threshold.value()),
            key_color=(int(self.key_r.value()), int(self.key_g.value()), int(self.key_b.value())),
            tolerance=int(self.tolerance.value()),
            invert=self.invert.isChecked(),
        )

    def _run(self) -> None:
        in_paths = self.inputs.list.get_paths()
        if not in_paths:
            QMessageBox.warning(self, "Missing input", "Add at least one input file or folder.")
            return
        out_dir = Path(self.out_dir.text().strip()) if self.out_dir.text().strip() else None
        if out_dir is None:
            QMessageBox.warning(self, "Missing output", "Choose an output folder.")
            return

        opts = self._opts()
        self.cancel_event.clear()
        self.reset_progress()
        self.set_running(True)

        def fn() -> object:
            return core.generate_alpha_files(
                in_paths,
                out_dir,
                opts,
                out_suffix=self.out_suffix.text(),
                overwrite=self.overwrite.isChecked(),
                progress_cb=lambda d, t, p, m: self.progress_cb(d, t, p, m),
                cancel_flag=self.cancel_event,
            )

        self.controller.start(fn)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Alpha Imaging Tool")

        tabs = QTabWidget()
        tabs.addTab(SplitTab(), "Split")
        tabs.addTab(CombineTab(), "Combine")
        tabs.addTab(ValidateTab(), "Validate")
        tabs.addTab(GenerateTab(), "Generate")

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.addWidget(tabs)
        root.setLayout(layout)
        self.setCentralWidget(root)
        self.resize(1100, 800)