import sys
import requests
import yfinance as yf
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QMenu, QFrame, QGraphicsDropShadowEffect)
from PyQt6.QtCore import QTimer, Qt, QPoint, QThread, pyqtSignal
from PyQt6.QtGui import QColor
import os

# CONFIGURACIÓN DE RUTAS
BASE_DIR = r"C:\portfolio_pro\pages"
LOG_FILE = os.path.join(BASE_DIR, "terminal_log.txt")

def log_error(msg):
    with open(LOG_FILE, "a") as f:
        f.write(f"{datetime.now()}: {msg}\n")

class DataWorker(QThread):
    data_updated = pyqtSignal(dict)

    def run(self):
        try:
            # 1. Crypto - Binance (Agregamos timeout de 10 seg para evitar tildes)
            symbols = '["BTCUSDT","LINKUSDT"]'
            r = requests.get(f'https://api.binance.com/api/v3/ticker/24hr?symbols={symbols}', timeout=10)
            crypto_req = r.json()
            
            # 2. Nasdaq - Doble Verificación
            nq_price, nq_change = 0.0, 0.0
            # Intentamos con NQ=F (Futuros) que es más estable para 2026
            nq = yf.Ticker("NQ=F")
            nq_data = nq.history(period="2d")

            if not nq_data.empty and len(nq_data) >= 1:
                nq_price = nq_data['Close'].iloc[-1]
                prev_val = nq_data['Close'].iloc[-2] if len(nq_data) > 1 else nq_data['Open'].iloc[-1]
                nq_change = ((nq_price - prev_val) / prev_val) * 100

            results = {
                "BTC": {"p": float(crypto_req[0]['lastPrice']), "c": float(crypto_req[0]['priceChangePercent']), "news": "Soporte clave"},
                "LINK": {"p": float(crypto_req[1]['lastPrice']), "c": float(crypto_req[1]['priceChangePercent']), "news": "Acumulación LINK"},
                "NASDAQ": {"p": nq_price, "c": nq_change, "news": "Foco operativo"}
            }
            self.data_updated.emit(results)
        except Exception as e:
            # Si falla, no hace nada pero deja que el próximo ciclo lo intente
            pass

class AssetWidget(QFrame):
    def __init__(self, name, color="#FFFFFF"):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(0)

        self.name_lbl = QLabel(name)
        self.name_lbl.setStyleSheet("color: #A0A5B5; font-weight: bold; font-size: 8pt; text-transform: uppercase;")
        self.price_lbl = QLabel("--")
        self.price_lbl.setStyleSheet(f"color: {color}; font-size: 15pt; font-weight: bold; font-family: 'Courier New';")
        
        self.sub_layout = QHBoxLayout()
        self.trend_lbl = QLabel("--")
        self.trend_lbl.setStyleSheet("font-size: 8pt; font-weight: bold;")
        self.news_lbl = QLabel("| Esperando datos...")
        self.news_lbl.setStyleSheet("color: #6B7280; font-size: 7pt; font-style: italic; margin-left: 5px;")
        
        self.sub_layout.addWidget(self.trend_lbl)
        self.sub_layout.addWidget(self.news_lbl)
        self.sub_layout.addStretch()

        self.layout.addWidget(self.name_lbl)
        self.layout.addWidget(self.price_lbl)
        self.layout.addLayout(self.sub_layout)

    def update_data(self, data):
        if data['p'] <= 0: return 
        price_str = f"${data['p']:,.2f}" if data['p'] > 10 else f"${data['p']:.4f}"
        self.price_lbl.setText(price_str)
        color = "#4CAF50" if data['c'] >= 0 else "#F44336"
        self.trend_lbl.setText(f"{'+' if data['c'] >= 0 else ''}{data['c']:.2f}%")
        self.trend_lbl.setStyleSheet(f"color: {color}; font-size: 8pt; font-weight: bold;")
        self.news_lbl.setText(f"| {data['news']}")

class MarketTerminal(QWidget):
    def __init__(self):
        super().__init__()
        self.oldPos = QPoint()
        self.initUI()

    def initUI(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(100, 100, 720, 110)

        self.container = QFrame(self)
        self.container.setGeometry(10, 10, 700, 80)
        self.container.setObjectName("MainContainer")
        self.container.setStyleSheet("#MainContainer { background-color: #1E2023; border-radius: 10px; border: 1px solid #3A3D45; }")

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 220))
        shadow.setOffset(0, 5)
        self.container.setGraphicsEffect(shadow)

        layout = QHBoxLayout(self.container)
        layout.setContentsMargins(15, 5, 15, 5)
        layout.setSpacing(15)

        self.assets = {
            "BTC": AssetWidget("₿ Bitcoin", "#f7931a"),
            "LINK": AssetWidget("🔗 Chainlink", "#2A5ADA"),
            "NASDAQ": AssetWidget("📊 Nasdaq 100", "#FFFFFF")
        }

        keys = list(self.assets.keys())
        for i, key in enumerate(keys):
            layout.addWidget(self.assets[key])
            if i < len(keys) - 1:
                line = QFrame(); line.setFixedWidth(1); line.setStyleSheet("background-color: #3A3D45; margin: 10px 0px;")
                layout.addWidget(line)

        self.worker = DataWorker()
        self.worker.data_updated.connect(self.refresh_ui)
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.safe_update)
        self.timer.start(10000) # Actualización cada 10 segundos para mayor fluidez
        self.safe_update()

    def safe_update(self):
        # PROTECCIÓN: Solo arranca si el anterior terminó. Si no, lo ignora.
        if not self.worker.isRunning():
            self.worker.start()

    def refresh_ui(self, results):
        for key, data in results.items():
            self.assets[key].update_data(data)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton: self.oldPos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            delta = QPoint(event.globalPosition().toPoint() - self.oldPos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = event.globalPosition().toPoint()

    def contextMenuEvent(self, event):
        menu = QMenu(self); exit_act = menu.addAction("❌ Cerrar"); 
        if menu.exec(self.mapToGlobal(event.pos())) == exit_act: sys.exit()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    terminal = MarketTerminal()
    terminal.show()
    sys.exit(app.exec())