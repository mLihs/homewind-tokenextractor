"""Homewind Token Extractor – minimal desktop app.

Sign in to Xiaomi Home (email/password or QR), see the fans Homewind supports as tiles,
copy a fan token or add the fan to a Homewind on the home network.
"""

from __future__ import annotations

import sys
import threading
from typing import List, Optional

import requests

from PySide6.QtCore import QByteArray, QObject, QSettings, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFontDatabase, QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

try:
    from . import __version__
    from .fans import ASSETS_DIR, NO_CONNECTION, PLACEHOLDER_IMAGE, SESSION_ENDED, Fan, collect_fans, load_catalog
    from .homewind_client import ADDED, UNREACHABLE, HomewindDevice, add, discover, probe
    from .xiaomi_cloud import InteractionCallbacks, PasswordXiaomiCloudConnector, QrCodeXiaomiCloudConnector
except ImportError:  # PyInstaller runs this file as a script
    from homewind_tokenextractor import __version__
    from homewind_tokenextractor.fans import (
        ASSETS_DIR,
        NO_CONNECTION,
        PLACEHOLDER_IMAGE,
        SESSION_ENDED,
        Fan,
        collect_fans,
        load_catalog,
    )
    from homewind_tokenextractor.homewind_client import ADDED, UNREACHABLE, HomewindDevice, add, discover, probe
    from homewind_tokenextractor.xiaomi_cloud import (
        InteractionCallbacks,
        PasswordXiaomiCloudConnector,
        QrCodeXiaomiCloudConnector,
    )

ISSUES_URL = "https://github.com/mLihs/Homewind/issues"

# Colors from the Homewind web UI (webui_src/app.css); type, spacing and radii on a 4 px grid.
INK = "#132237"        # primary text, primary button
INK_HOVER = "#22344D"
SECONDARY = "#516682"  # secondary text
MUTED = "#66768D"      # meta text, about 4.6:1 on the card
PINK = "#F00F66"       # brand accent: sign-in and add to Homewind
OFFLINE = "#8D9EB9"

STYLE = f"""
QWidget {{ font-family: Inter; font-size: 14px; color: {INK}; }}
QMainWindow, QWidget#page {{ background: #EEF2FA; }}
QLabel#title {{ font-family: Outfit; font-size: 28px; font-weight: 500; }}
QLabel#busyTitle {{ font-family: Outfit; font-size: 22px; font-weight: 500; }}
QLabel#subtitle {{ color: {SECONDARY}; font-size: 14px; }}
QLabel#muted {{ color: {MUTED}; font-size: 13px; }}
QLabel#error {{ color: #D70054; font-size: 13px; }}
QLabel#fanName {{ font-size: 15px; font-weight: 500; }}
QFrame#card {{ background: #FCFCFE; border: 1px solid rgba(19, 34, 55, 0.08); border-radius: 20px; }}
QLabel#imagePanel {{ background: #FFFFFF; border: 1px solid rgba(19, 34, 55, 0.06); border-radius: 8px; }}
QLineEdit {{ background: #FFFFFF; border: 1px solid #D1DAEB; border-radius: 8px; padding: 0 12px; min-height: 38px; }}
QLineEdit:focus {{ border-color: {SECONDARY}; }}
QPushButton {{ border-radius: 8px; padding: 0 16px; min-height: 38px; font-weight: 500;
              background: transparent; border: 1px solid #D1DAEB; color: {INK}; }}
QPushButton:hover {{ background: #F3F6FB; }}
QPushButton:focus {{ border-color: {SECONDARY}; }}
QPushButton:disabled {{ color: {OFFLINE}; border-color: #E4E9F3; background: transparent; }}
QPushButton#primary {{ background: {INK}; border-color: {INK}; color: #FFFFFF; }}
QPushButton#primary:hover {{ background: {INK_HOVER}; border-color: {INK_HOVER}; }}
QPushButton#primary:focus {{ border-color: #8D9EB9; }}
QPushButton#cta {{ background: {PINK}; border-color: {PINK}; color: #FFFFFF; }}
QPushButton#cta:hover {{ background: #D70054; border-color: #D70054; }}
QPushButton#cta:focus {{ border-color: {INK}; }}
QPushButton#cta:disabled {{ background: #F7A3C2; border-color: #F7A3C2; color: #FFFFFF; }}
QPushButton#link {{ border: none; background: transparent; color: {SECONDARY}; padding: 0 8px; min-height: 32px; }}
QPushButton#link:hover {{ color: {INK}; }}
QPushButton#iconBtn {{ padding: 0; min-width: 38px; max-width: 38px; min-height: 38px; max-height: 38px; }}
QPushButton#iconBtn:hover {{ background: #F3F6FB; }}
QFrame#segmentBar {{ background: #DDE4F0; border-radius: 10px; }}
QPushButton#segment {{ border: none; background: transparent; color: {SECONDARY}; border-radius: 6px; min-height: 32px; }}
QPushButton#segment:checked {{ background: #FCFCFE; color: {INK}; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
QToolTip {{ background: {INK}; color: #FFFFFF; border: none; padding: 4px 8px; }}
"""

# lucide icons (ISC license), stroke 1.5
_ICON_COPY = (
    '<rect x="8" y="8" width="14" height="14" rx="2"/>'
    '<path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>'
)
COPY_LABEL = "\u2002Copy token"  # en space = 8 px gap after the icon
_ICON_CHECK = '<path d="M20 6 9 17l-5-5"/>'
_ICON_RELOAD = (
    '<path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>'
    '<path d="M3 3v5h5"/>'
    '<path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/>'
    '<path d="M16 16h5v5"/>'
)
_ICON_SIGN_OUT = (
    '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>'
    '<path d="m16 17 5-5-5-5"/>'
    '<path d="M21 12H9"/>'
)


def icon(paths: str, color: str, size: int = 16) -> QIcon:
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" '
        f'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">{paths}</svg>'
    ).encode()
    renderer = QSvgRenderer(QByteArray(svg))
    pix = QPixmap(size * 3, size * 3)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    renderer.render(painter)
    painter.end()
    pix.setDevicePixelRatio(3)
    return QIcon(pix)



# ----------------------------------------------------------------------------
# Background work
# ----------------------------------------------------------------------------
class _Future:
    def __init__(self) -> None:
        self._event = threading.Event()
        self._value: Optional[str] = None

    def set(self, value: Optional[str]) -> None:
        self._value = value
        self._event.set()

    def wait(self) -> Optional[str]:
        self._event.wait()
        return self._value


class Worker(QObject):
    """Runs login + fan lookup on a daemon thread so closing the window never hangs on QR polling."""

    status = Signal(str)
    qr = Signal(bytes)
    captcha = Signal(bytes, object)
    twofactor = Signal(str, object)
    done = Signal(list)
    failed = Signal(str)

    def __init__(self, mode: str, email: str = "", password: str = "") -> None:
        super().__init__()
        self._mode, self._email, self._password = mode, email, password
        self.cancelled = False
        self.connector = None

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True).start()

    def _ask(self, signal, *args) -> Optional[str]:
        future = _Future()
        signal.emit(*args, future)
        return future.wait()

    def _run(self) -> None:
        callbacks = InteractionCallbacks(
            log=lambda _m: None,
            request_captcha=lambda img, _url: self._ask(self.captcha, img),
            request_twofactor=lambda prompt: self._ask(self.twofactor, prompt),
            display_qr=lambda img, _login, _url: None if self.cancelled else self.qr.emit(img),
        )
        try:
            if self._mode == "qr":
                connector = QrCodeXiaomiCloudConnector(callbacks)
            else:
                connector = PasswordXiaomiCloudConnector(callbacks, self._email, self._password)
            if not connector.login():
                raise PermissionError(
                    "QR code expired or not confirmed. Try again."
                    if self._mode == "qr"
                    else "Sign-in failed. Check email and password."
                )
            if self.cancelled:
                return
            self.connector = connector
            self.status.emit("Looking for your fans …")
            fans = collect_fans(
                connector,
                load_catalog(),
                log=lambda message: None if self.cancelled else self.status.emit(message),
            )
            if not self.cancelled:
                self.done.emit(fans)
        except PermissionError as exc:
            if not self.cancelled:
                self.failed.emit(str(exc))
        except ConnectionError:
            if not self.cancelled:
                self.failed.emit(NO_CONNECTION)
        except requests.exceptions.Timeout:
            if not self.cancelled:
                self.failed.emit("Xiaomi did not answer. Try again.")
        except Exception as exc:  # noqa: BLE001
            if not self.cancelled:
                self.failed.emit(f"Something went wrong: {exc}")


# ----------------------------------------------------------------------------
# Dialogs
# ----------------------------------------------------------------------------
class CodeDialog(QDialog):
    def __init__(self, title: str, text: str, placeholder: str, image: Optional[bytes], parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        label = QLabel(text)
        label.setWordWrap(True)
        layout.addWidget(label)
        if image:
            pix = QPixmap()
            pix.loadFromData(image)
            img = QLabel()
            img.setAlignment(Qt.AlignCenter)
            img.setPixmap(pix)
            layout.addWidget(img)
        self.input = QLineEdit()
        self.input.setPlaceholderText(placeholder)
        layout.addWidget(self.input)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


# ----------------------------------------------------------------------------
# Fan tile
# ----------------------------------------------------------------------------
class FanCard(QFrame):
    WIDTH = 240
    COLUMNS = 3
    GAP = 16

    def __init__(self, fan: Fan, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.fan = fan
        self.setObjectName("card")
        self.setFixedWidth(self.WIDTH)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(0)

        # Fan picture on its own panel: card radius 20 - padding 12 = 8
        image = QLabel()
        image.setObjectName("imagePanel")
        image.setFixedHeight(176)
        pix = QPixmap(str(fan.image))
        if fan.image == PLACEHOLDER_IMAGE:
            image.setAlignment(Qt.AlignCenter)
            side = 112
        else:
            # Product shots on white: fill the panel height so stands run into the bottom edge
            image.setAlignment(Qt.AlignHCenter | Qt.AlignBottom)
            side = 174
        if not pix.isNull():
            dpr = self.devicePixelRatioF() or 1.0
            scaled = pix.scaled(QSize(int(side * dpr), int(side * dpr)), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            scaled.setDevicePixelRatio(dpr)
            image.setPixmap(scaled)
        layout.addWidget(image)

        text = QVBoxLayout()
        text.setContentsMargins(8, 16, 8, 16)
        text.setSpacing(4)
        name = QLabel(fan.name)
        name.setObjectName("fanName")
        name.setWordWrap(True)
        model = QLabel(fan.model_name)
        model.setObjectName("muted")
        model.setWordWrap(True)
        text.addWidget(name)
        text.addWidget(model)

        layout.addLayout(text)
        layout.addStretch(1)

        buttons = QVBoxLayout()
        buttons.setSpacing(8)
        self.copy_btn = QPushButton(COPY_LABEL)
        self.copy_btn.setObjectName("primary")
        self.copy_btn.setIcon(icon(_ICON_COPY, "#FFFFFF"))
        self.copy_btn.setIconSize(QSize(16, 16))
        self.copy_btn.setCursor(Qt.PointingHandCursor)
        self.copy_btn.clicked.connect(self._copy)
        buttons.addWidget(self.copy_btn)

        self.add_btn = QPushButton("Add to Homewind")
        self.add_btn.setObjectName("cta")
        self.add_btn.setCursor(Qt.PointingHandCursor)
        buttons.addWidget(self.add_btn)
        self.add_error = QLabel("")
        self.add_error.setObjectName("error")
        self.add_error.setWordWrap(True)
        self.add_error.hide()
        buttons.addWidget(self.add_error)
        layout.addLayout(buttons)

    def _copy(self) -> None:
        QGuiApplication.clipboard().setText(self.fan.token)
        self.copy_btn.setText("\u2002Copied")
        self.copy_btn.setIcon(icon(_ICON_CHECK, "#FFFFFF"))
        # The card as context: the timer is dropped if Sign out or a reload deletes the card first.
        QTimer.singleShot(1500, self, self._reset_copy)

    def _reset_copy(self) -> None:
        self.copy_btn.setText(COPY_LABEL)
        self.copy_btn.setIcon(icon(_ICON_COPY, "#FFFFFF"))

    def show_adding(self, keep_error: bool = False) -> None:
        self.add_btn.setText("Adding …")
        self.add_btn.setEnabled(False)
        if not keep_error:
            self.add_error.hide()

    def show_added(self) -> None:
        self.add_btn.setText(ADDED)
        self.add_btn.setEnabled(True)
        self.add_error.hide()

    def show_add_error(self, text: str) -> None:
        self.add_btn.setText("Add to Homewind")
        self.add_btn.setEnabled(True)
        self.add_error.setText(text)
        self.add_error.show()

    def reset_add(self) -> None:
        self.add_btn.setText("Add to Homewind")
        self.add_btn.setEnabled(True)
        self.add_error.hide()


class FindHomewindDialog(QDialog):
    """Shown when no Homewind answered. Search again, or type an IP or hostname."""

    def __init__(self, detail: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Homewind not found")
        self.setMinimumWidth(420)
        self.action = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        text = QLabel(
            "No Homewind answered on this network. Set up Homewind's Wi-Fi first, "
            "then search again or enter its IP address or hostname."
        )
        text.setWordWrap(True)
        layout.addWidget(text)
        if detail:
            err = QLabel(detail)
            err.setObjectName("error")
            err.setWordWrap(True)
            layout.addWidget(err)
        self.input = QLineEdit()
        self.input.setPlaceholderText("IP address or hostname")
        self.input.returnPressed.connect(self._use)
        layout.addWidget(self.input)
        row = QHBoxLayout()
        search = QPushButton("Search again")
        search.clicked.connect(self._search)
        use = QPushButton("Use this address")
        use.setObjectName("primary")
        use.clicked.connect(self._use)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("link")
        cancel.clicked.connect(self.reject)
        row.addWidget(search)
        row.addWidget(use)
        row.addWidget(cancel)
        layout.addLayout(row)

    def _search(self) -> None:
        self.action = "search"
        self.accept()

    def _use(self) -> None:
        if not self.input.text().strip():
            self.input.setFocus()
            return
        self.action = "use"
        self.accept()


class ChooseHomewindDialog(QDialog):
    def __init__(self, devices: List[HomewindDevice], parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Choose a Homewind")
        self.setMinimumWidth(420)
        self._devices = devices
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        text = QLabel("More than one Homewind is on this network.")
        text.setWordWrap(True)
        layout.addWidget(text)
        self.list = QListWidget()
        for device in devices:
            QListWidgetItem(device.label, self.list)
        self.list.setCurrentRow(0)
        self.list.itemDoubleClicked.connect(self.accept)
        layout.addWidget(self.list)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def chosen(self) -> Optional[HomewindDevice]:
        row = self.list.currentRow()
        if row < 0:
            return None
        return self._devices[row]


class _Bg(QObject):
    """Runs one blocking Homewind call off the UI thread."""

    done = Signal(object)
    failed = Signal(str)
    status = Signal(str)

    def __init__(self, work) -> None:
        super().__init__()
        self._work = work

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        try:
            # A tuple so a missed Homewind (None) still crosses the thread boundary.
            self.done.emit((self._work(),))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


def _homewind_settings() -> QSettings:
    return QSettings("Homewind", "Token Extractor")


def load_saved_homewind() -> Optional[tuple]:
    settings = _homewind_settings()
    host = settings.value("homewind/host", "")
    if not isinstance(host, str) or not host:
        return None
    hostname = settings.value("homewind/hostname", "") or ""
    address = settings.value("homewind/address", "") or ""
    return host, str(hostname), str(address)


def save_homewind(device: HomewindDevice) -> None:
    settings = _homewind_settings()
    settings.setValue("homewind/host", device.host)
    settings.setValue("homewind/hostname", device.hostname)
    settings.setValue("homewind/address", device.address)


def forget_homewind() -> None:
    settings = _homewind_settings()
    settings.remove("homewind/host")
    settings.remove("homewind/hostname")
    settings.remove("homewind/address")


# ----------------------------------------------------------------------------
# Main window
# ----------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Homewind Token Extractor")
        self.resize(860, 640)
        self.setMinimumSize(560, 560)
        self._worker: Optional[Worker] = None
        self._retired: List[Worker] = []  # cancelled workers stay referenced until their thread ends
        self._cards: List[FanCard] = []
        self._add_card: Optional[FanCard] = None
        self._bg: Optional[_Bg] = None
        self._add_phase = ""
        self._connector = None
        self._reload: Optional[_Bg] = None
        self._held: List[QObject] = []  # cancelled background jobs stay referenced until their thread ends

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.login_page = self._build_login()
        self.busy_page = self._build_busy()
        self.fans_page = self._build_fans()
        for page in (self.login_page, self.busy_page, self.fans_page):
            page.setObjectName("page")
            self.stack.addWidget(page)

    # -- login ---------------------------------------------------------------
    def _build_login(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setAlignment(Qt.AlignCenter)
        box = QWidget()
        box.setFixedWidth(380)
        layout = QVBoxLayout(box)
        layout.setSpacing(12)

        title = QLabel("Homewind Token Extractor")
        title.setObjectName("title")
        layout.addWidget(title)
        sub = QLabel("Sign in with your Xiaomi Home account to read the tokens of your fans.")
        sub.setObjectName("subtitle")
        sub.setWordWrap(True)
        layout.addWidget(sub)
        layout.addSpacing(8)

        bar = QFrame()
        bar.setObjectName("segmentBar")
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(4, 4, 4, 4)
        self.seg_group = QButtonGroup(self)
        for index, text in enumerate(("Email", "QR code")):
            btn = QPushButton(text)
            btn.setObjectName("segment")
            btn.setCheckable(True)
            btn.setChecked(index == 0)
            self.seg_group.addButton(btn, index)
            bar_layout.addWidget(btn)
        layout.addWidget(bar)

        self.login_stack = QStackedWidget()
        # email
        email_page = QWidget()
        el = QVBoxLayout(email_page)
        el.setContentsMargins(0, 8, 0, 0)
        el.setSpacing(12)
        self.email = QLineEdit()
        self.email.setPlaceholderText("Email, phone or Xiaomi ID")
        self.password = QLineEdit()
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QLineEdit.Password)
        self.email.returnPressed.connect(self.password.setFocus)
        self.password.returnPressed.connect(self._sign_in_password)
        self.sign_in_btn = QPushButton("Sign in")
        self.sign_in_btn.setObjectName("cta")
        self.sign_in_btn.clicked.connect(self._sign_in_password)
        el.addWidget(self.email)
        el.addWidget(self.password)
        el.addWidget(self.sign_in_btn)
        # qr
        qr_page = QWidget()
        ql = QVBoxLayout(qr_page)
        ql.setContentsMargins(0, 8, 0, 0)
        ql.setSpacing(12)
        qr_hint = QLabel("Open Xiaomi Home on your phone, tap the scan icon and scan the code.")
        qr_hint.setObjectName("muted")
        qr_hint.setWordWrap(True)
        self.qr_btn = QPushButton("Show QR code")
        self.qr_btn.setObjectName("cta")
        self.qr_btn.clicked.connect(self._sign_in_qr)
        ql.addWidget(qr_hint)
        ql.addWidget(self.qr_btn)
        self.login_stack.addWidget(email_page)
        self.login_stack.addWidget(qr_page)
        self.seg_group.idClicked.connect(self._on_segment)
        self.login_stack.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        layout.addWidget(self.login_stack)

        self.login_error = QLabel("")
        self.login_error.setObjectName("error")
        self.login_error.setWordWrap(True)
        self.login_error.hide()
        layout.addWidget(self.login_error)

        privacy = QLabel("Your sign-in goes straight to Xiaomi. The password is not stored.")
        privacy.setObjectName("muted")
        privacy.setWordWrap(True)
        layout.addWidget(privacy)
        outer.addWidget(box)
        return page

    def _set_error(self, text: str) -> None:
        self.login_error.setText(text)
        self.login_error.setVisible(bool(text))

    def _on_segment(self, index: int) -> None:
        self.login_stack.setCurrentIndex(index)
        self._set_error("")

    # -- busy / qr -----------------------------------------------------------
    def _build_busy(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(16)
        self.busy_label = QLabel("Signing in …")
        self.busy_label.setObjectName("busyTitle")
        self.busy_label.setAlignment(Qt.AlignCenter)
        self.qr_image = QLabel()
        self.qr_image.setAlignment(Qt.AlignCenter)
        self.busy_hint = QLabel("")
        self.busy_hint.setObjectName("muted")
        self.busy_hint.setAlignment(Qt.AlignCenter)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("link")
        cancel.clicked.connect(self._cancel)
        layout.addWidget(self.busy_label)
        layout.addWidget(self.qr_image)
        layout.addWidget(self.busy_hint)
        layout.addWidget(cancel, alignment=Qt.AlignCenter)
        return page

    # -- fans ----------------------------------------------------------------
    def _build_fans(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 32, 32, 24)
        layout.setSpacing(16)
        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(4)
        title = QLabel("Your fans")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignHCenter)
        self.fans_sub = QLabel("")
        self.fans_sub.setObjectName("subtitle")
        self.fans_sub.setAlignment(Qt.AlignHCenter)
        self.fans_sub.setWordWrap(True)
        titles.addWidget(title)
        titles.addWidget(self.fans_sub)
        self.fans_error = QLabel("")
        self.fans_error.setObjectName("error")
        self.fans_error.setAlignment(Qt.AlignHCenter)
        self.fans_error.setWordWrap(True)
        self.fans_error.hide()
        titles.addWidget(self.fans_error)
        self.reload_btn = QPushButton()
        self.reload_btn.setObjectName("iconBtn")
        self.reload_btn.setIcon(icon(_ICON_RELOAD, SECONDARY))
        self.reload_btn.setIconSize(QSize(18, 18))
        self.reload_btn.setCursor(Qt.PointingHandCursor)
        self.reload_btn.setToolTip("Reload fans")
        self.reload_btn.setAccessibleName("Reload fans")
        self.reload_btn.clicked.connect(self._reload_fans)
        sign_out = QPushButton()
        sign_out.setObjectName("iconBtn")
        sign_out.setIcon(icon(_ICON_SIGN_OUT, SECONDARY))
        sign_out.setIconSize(QSize(18, 18))
        sign_out.setCursor(Qt.PointingHandCursor)
        sign_out.setToolTip("Sign out")
        sign_out.setAccessibleName("Sign out")
        sign_out.clicked.connect(self._sign_out)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addWidget(self.reload_btn)
        actions.addWidget(sign_out)
        # Same width on the left keeps the headline centered in the window, not beside the buttons.
        balance = QWidget()
        balance.setFixedWidth(38 + 8 + 38)
        head.addWidget(balance)
        head.addLayout(titles, 1)
        head.addLayout(actions)
        layout.addLayout(head)
        layout.addSpacing(8)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.grid_host = QWidget()
        self.grid_host.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        self.rows = QVBoxLayout(self.grid_host)
        self.rows.setContentsMargins(0, 0, 0, 0)
        self.rows.setSpacing(FanCard.GAP)
        self.rows.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.scroll.setWidget(self.grid_host)
        self._layout_sig: Optional[tuple] = None
        layout.addWidget(self.scroll, 1)

        self.empty = QLabel(
            "No fan that Homewind supports was found in this account.<br>"
            f"Your fan is missing? <a href='{ISSUES_URL}'>Open an issue</a> with the model name."
        )
        self.empty.setObjectName("muted")
        self.empty.setOpenExternalLinks(True)
        self.empty.setWordWrap(True)
        self.empty.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.empty, 1)
        return page

    def show_fans(self, fans: List[Fan]) -> None:
        self._drop_cards()
        for fan in fans:
            card = FanCard(fan)
            card.add_btn.clicked.connect(lambda _checked=False, c=card: self._add_fan(c))
            self._cards.append(card)
        self.empty.setVisible(not fans)
        self.scroll.setVisible(bool(fans))
        if fans:
            n = len(fans)
            self.fans_sub.setText(
                f"{n} fan{'s' if n != 1 else ''} Homewind can control. "
                "Add a fan to a Homewind on your home network, or copy the token."
            )
        else:
            self.fans_sub.setText("")
        self._layout_cards()
        self.fans_error.hide()
        self.reload_btn.setEnabled(self._add_card is None)
        self.stack.setCurrentWidget(self.fans_page)

    def _drop_cards(self) -> None:
        for card in self._cards:
            card.setParent(None)
            card.deleteLater()
        self._cards = []
        # New cards can reuse the ids of freed ones, so the old signature must not match them.
        self._layout_sig = None

    def _column_count(self) -> int:
        available = self.scroll.viewport().width()
        if available <= 0:
            available = max(self.width() - 64, FanCard.WIDTH)
        cols = min(FanCard.COLUMNS, len(self._cards))
        while cols > 1 and cols * FanCard.WIDTH + (cols - 1) * FanCard.GAP > available:
            cols -= 1
        return max(1, cols)

    def _clear_fan_rows(self) -> None:
        for card in self._cards:
            card.setParent(self.grid_host)
        while self.rows.count():
            item = self.rows.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _layout_cards(self) -> None:
        if not self._cards:
            self._clear_fan_rows()
            self._layout_sig = None
            self.grid_host.setMinimumHeight(0)
            return
        cols = self._column_count()
        signature = (cols, tuple(id(card) for card in self._cards))
        if signature == self._layout_sig:
            return
        self._clear_fan_rows()
        for start in range(0, len(self._cards), cols):
            row = QWidget()
            boxes = QHBoxLayout(row)
            boxes.setContentsMargins(0, 0, 0, 0)
            boxes.setSpacing(FanCard.GAP)
            boxes.addStretch(1)
            for card in self._cards[start:start + cols]:
                boxes.addWidget(card, 0, Qt.AlignTop)
                # Reparenting hides a card; hidden cards count as 0 px in the height below.
                card.show()
            boxes.addStretch(1)
            self.rows.addWidget(row)
            row.show()
        self.rows.addStretch(1)
        self.rows.activate()
        self._layout_sig = signature
        self.grid_host.setMinimumHeight(self.rows.totalSizeHint().height())
        self.grid_host.updateGeometry()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._layout_cards()

    # -- add to homewind -----------------------------------------------------
    def _add_fan(self, card: FanCard) -> None:
        if self._add_card is not None:
            return
        self._add_card = card
        card.show_adding()
        self._set_add_enabled(False)
        saved = load_saved_homewind()
        if saved:
            host, hostname, address = saved
            self._run("saved", lambda: probe(host, hostname=hostname, address=address))
        else:
            self._discover()

    def _discover(self) -> None:
        self._run("discover", discover)

    def _run(self, phase: str, work) -> None:
        self._add_phase = phase
        bg = _Bg(work)
        bg.done.connect(self._on_bg_done)
        bg.failed.connect(self._on_bg_failed)
        self._bg = bg  # keep the QObject alive until the thread emits
        bg.start()

    def _on_bg_done(self, payload: object) -> None:
        # A search started earlier can finish after Sign out or a new click. Ignore it.
        if self.sender() is not self._bg or not self._card_alive():
            return
        result = payload[0]
        phase = self._add_phase
        if phase == "saved":
            if isinstance(result, HomewindDevice):
                self._send(result)
            else:
                self._discover()
        elif phase == "discover":
            devices = list(result or [])
            if not devices:
                self._ask_for_homewind("")
            elif len(devices) == 1:
                self._send(devices[0])
            else:
                dialog = ChooseHomewindDialog(devices, self)
                if dialog.exec() == QDialog.Accepted and dialog.chosen():
                    self._send(dialog.chosen())
                else:
                    self._stop_add()
        elif phase == "manual":
            if isinstance(result, HomewindDevice):
                self._send(result)
            else:
                self._ask_for_homewind(UNREACHABLE)
        elif phase == "add":
            self._add_card.show_added()
            self._add_card = None
            self._set_add_enabled(True)

    def _on_bg_failed(self, message: str) -> None:
        if self.sender() is not self._bg or not self._card_alive():
            return
        phase = self._add_phase
        if phase == "add" and message == UNREACHABLE:
            forget_homewind()
            self._add_card.show_add_error(message)
            self._add_card.show_adding(keep_error=True)
            self._discover()
            return
        if phase in ("discover", "saved"):
            self._ask_for_homewind(message if phase == "discover" else "")
            return
        if phase == "manual":
            self._ask_for_homewind(message or UNREACHABLE)
            return
        self._add_card.show_add_error(message)
        self._add_card = None
        self._set_add_enabled(True)

    def _send(self, device: HomewindDevice) -> None:
        save_homewind(device)
        token = self._add_card.fan.token
        self._run("add", lambda: add(device, token))

    def _ask_for_homewind(self, detail: str) -> None:
        if not self._card_alive():
            return
        dialog = FindHomewindDialog(detail, self)
        if dialog.exec() != QDialog.Accepted:
            self._stop_add()
            return
        if dialog.action == "search":
            self._add_card.show_adding()
            self._discover()
            return
        host = dialog.input.text().strip()
        self._add_card.show_adding()
        self._run("manual", lambda: probe(host))

    def _stop_add(self) -> None:
        if self._add_card is not None:
            self._add_card.reset_add()
        self._add_card = None
        self._set_add_enabled(True)

    def _card_alive(self) -> bool:
        return self._add_card is not None and self._add_card in self._cards

    def _set_add_enabled(self, enabled: bool) -> None:
        self.reload_btn.setEnabled(enabled and self._reload is None)
        for card in self._cards:
            if card is self._add_card and not enabled:
                continue
            card.add_btn.setEnabled(enabled)

    # -- flow ----------------------------------------------------------------
    def _sign_in_password(self) -> None:
        email, password = self.email.text().strip(), self.password.text()
        if not email or not password:
            self._set_error("Enter email and password")
            return
        self._start(Worker("password", email, password), "Signing in …", "")

    def _sign_in_qr(self) -> None:
        self._start(Worker("qr"), "Loading QR code …", "")

    def _start(self, worker: Worker, label: str, hint: str) -> None:
        self._set_error("")
        self.qr_image.clear()
        self.qr_image.hide()
        self.busy_label.setText(label)
        self.busy_hint.setText(hint)
        self.stack.setCurrentWidget(self.busy_page)
        worker.status.connect(self._on_status)
        worker.qr.connect(self._on_qr)
        worker.captcha.connect(self._on_captcha)
        worker.twofactor.connect(self._on_twofactor)
        worker.done.connect(self._on_fans_ready)
        worker.failed.connect(self._on_failed)
        self._worker = worker
        worker.start()

    def _current(self) -> bool:
        """True when the signal comes from the sign-in or reload that the window still waits for."""
        sender = self.sender()
        return sender is not None and sender in (self._worker, self._reload)

    def _on_status(self, text: str) -> None:
        if not self._current():
            return
        self.qr_image.hide()
        self.busy_label.setText(text)
        self.busy_hint.setText("")

    def _on_qr(self, image: bytes) -> None:
        if not self._current():
            return
        pix = QPixmap()
        pix.loadFromData(image)
        self.qr_image.setPixmap(pix.scaled(QSize(260, 260), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.qr_image.show()
        self.busy_label.setText("Scan with Xiaomi Home")
        self.busy_hint.setText("Then confirm the sign-in on your phone.")

    def _on_captcha(self, image: bytes, future: _Future) -> None:
        if not self._current():
            future.set(None)
            return
        dlg = CodeDialog("Security check", "Enter the characters shown (case-sensitive).", "Characters", image, self)
        future.set(dlg.input.text().strip() if dlg.exec() == QDialog.Accepted else None)

    def _on_twofactor(self, _prompt: str, future: _Future) -> None:
        if not self._current():
            future.set(None)
            return
        dlg = CodeDialog("Check your email", "Xiaomi sent a code to your email address.", "Code", None, self)
        future.set(dlg.input.text().strip() if dlg.exec() == QDialog.Accepted else None)

    def _on_fans_ready(self, fans: list) -> None:
        worker = self.sender()
        if worker is None or worker is not self._worker:
            return
        if worker.connector is not None:
            self._connector = worker.connector
        self.show_fans(fans)

    def _reload_fans(self) -> None:
        if self._connector is None or self._reload is not None or self._add_card is not None:
            return
        connector = self._connector
        self.reload_btn.setEnabled(False)
        self.qr_image.clear()
        self.qr_image.hide()
        self.busy_label.setText("Looking for your fans …")
        self.busy_hint.setText("")
        self.stack.setCurrentWidget(self.busy_page)
        bg = _Bg(lambda: collect_fans(connector, load_catalog(), log=bg.status.emit))
        bg.status.connect(self._on_status)
        bg.done.connect(self._on_reload_done)
        bg.failed.connect(self._on_reload_failed)
        self._reload = bg
        bg.start()

    def _on_reload_done(self, payload: object) -> None:
        if self.sender() is not self._reload:
            return
        self._reload = None
        self.show_fans(list(payload[0] or []))

    def _on_reload_failed(self, message: str) -> None:
        if self.sender() is not self._reload:
            return
        self._reload = None
        if message == SESSION_ENDED:
            self._sign_out()
            self._set_error(message)
            return
        self.reload_btn.setEnabled(self._add_card is None)
        self.fans_error.setText(message)
        self.fans_error.show()
        self.stack.setCurrentWidget(self.fans_page)

    def _on_failed(self, message: str) -> None:
        if self.sender() is not self._worker:
            return
        self._set_error(message)
        self.stack.setCurrentWidget(self.login_page)

    def _cancel(self) -> None:
        if self._reload is not None:
            self._held.append(self._reload)
            self._reload = None
            self.reload_btn.setEnabled(True)
            self.stack.setCurrentWidget(self.fans_page)
            return
        self._retire_worker()
        self.stack.setCurrentWidget(self.login_page)

    def _retire_worker(self) -> None:
        if self._worker:
            self._worker.cancelled = True
            self._retired.append(self._worker)
            self._worker = None

    def _sign_out(self) -> None:
        self._retire_worker()
        if self._reload is not None:
            self._held.append(self._reload)
            self._reload = None
        self._connector = None
        self._add_card = None
        self.password.clear()
        self._drop_cards()
        self._layout_cards()
        self.stack.setCurrentWidget(self.login_page)


def load_fonts() -> None:
    for path in sorted((ASSETS_DIR / "fonts").glob("*.ttf")):
        QFontDatabase.addApplicationFont(str(path))


def run() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Homewind Token Extractor")
    app.setApplicationVersion(__version__)
    # The window icon is also the Dock icon on macOS, so it needs the padded, rounded Mac shape.
    icon = ASSETS_DIR / ("icon.png" if sys.platform == "darwin" else "icon.ico")
    if icon.is_file():
        app.setWindowIcon(QIcon(str(icon)))
    load_fonts()
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run()
