import sys
import serial
import threading
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout,
    QHBoxLayout, QGridLayout, QFrame, QPushButton, QTextEdit
)
from PyQt5.QtGui import QPixmap, QFont, QPainter, QColor, QPen
from PyQt5.QtCore import Qt, QRectF, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtOpenGL import QGLWidget
from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
import numpy as np

FONT = 'Montserrat'


class CircularBattery(QWidget):
    def __init__(self, percentage):
        super().__init__()
        self.percentage = percentage
        self.setMinimumSize(170, 170)

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = QRectF(10, 10, 150, 150)
        painter.setPen(QPen(QColor("#444"), 10))
        painter.drawEllipse(rect)

        angle = int(360 * self.percentage / 100)
        painter.setPen(QPen(QColor("#66ff66"), 10))
        painter.drawArc(rect, 90 * 16, -angle * 16)

        painter.setPen(Qt.white)
        painter.setFont(QFont(FONT, 24, QFont.Bold))
        painter.drawText(rect, Qt.AlignCenter, f"{self.percentage}%")


class AltitudeIndicator(QWidget):
    def __init__(self, altitude):
        super().__init__()
        self.altitude = altitude
        self.setFixedSize(350, 500)
        self.scale = QPixmap("img/scale.png").scaled(350, 500)
        self.image = QPixmap("img/babycansat.png").scaled(100, 100, Qt.KeepAspectRatio,
                                                                                         Qt.SmoothTransformation)

    def setAltitude(self, altitude):
        self.altitude = altitude
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        max_altitude = 1000
        y_pos = max(0, 400 - int((self.altitude / max_altitude) * 400))
        painter.drawPixmap(0, 0, self.scale)
        painter.drawPixmap(144, y_pos, self.image)


class CubeWidget(QGLWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(300, 300)
        self.rotation_matrix = np.identity(4)  # Identity matrix (no rotation)

    def initializeGL(self):
        glClearColor(2.0/255, 15.0/255, 28.0/255, 1.0)  # Black background
        glEnable(GL_DEPTH_TEST)  # Enable depth testing for 3D rendering

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()

        # Position the camera
        gluLookAt(0.0, 0.0, 5.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0)

        # Apply the rotation matrix for cube orientation
        glMultMatrixf(self.rotation_matrix.T)  # Multiply the rotation matrix

        # Render a cube
        glBegin(GL_QUADS)

        # Front face
        glColor3f(1.0, 0.0, 0.0)
        glVertex3f(-1.0, -1.0,  1.0)
        glVertex3f( 1.0, -1.0,  1.0)
        glVertex3f( 1.0,  1.0,  1.0)
        glVertex3f(-1.0,  1.0,  1.0)

        # Back face
        glColor3f(0.0, 1.0, 0.0)
        glVertex3f(-1.0, -1.0, -1.0)
        glVertex3f(-1.0,  1.0, -1.0)
        glVertex3f( 1.0,  1.0, -1.0)
        glVertex3f( 1.0, -1.0, -1.0)

        # Other faces (top, bottom, left, right) omitted for brevity...

        glEnd()

    def setOrientation(self, orientation_matrix):
        """Sets the rotation matrix from IMU data."""
        self.rotation_matrix = orientation_matrix
        self.update()


class CanSatUI(QWidget):

    update_packet_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.cube_widget = None
        self.latest_latitude = None
        self.latest_longitude = None
        self.map_view = None
        self.latest_pressure = None
        self.latest_humidity = None
        self.latest_temperature = None
        self.telemetry_container = None
        self.altitude_indicator = None
        self.console_box = None  # Placeholder; will bind later
        self.battery_indicator = None
        self.altitude_text = None
        self.serial_port = None
        self.latest_line = None
        self.latest_battery = None
        self.latest_altitude = None
        self.read_serial_thread = threading.Thread(target=self.read_serial_data, daemon=True)
        self.start_serial("COM5", 9600)  # Update COM port name for your system
        self.initUI()
        self.update_packet_signal.connect(self.update_from_packet)

    # def showEvent(self, event):
    #     self.showFullScreen()
    def initUI(self):
        self.setWindowTitle('CanSat Telemetry UI')
        self.setStyleSheet("background-color: #0e1a2b; color: white;")
        self.setWindowFlags(Qt.FramelessWindowHint)  # 🔧 Remove system title bar
        self.setGeometry(110, 110, 1200, 700)
        self.showFullScreen()

        main_layout = QVBoxLayout()  # 🔧 Change to QVBox to insert top bar

        # --- 🔧 Custom Title Bar with Buttons ---
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(10, 10, 10, 10)

        title_label = QLabel("LIVE")
        title_label.setFont(QFont(FONT, 24))

        top_bar.addWidget(title_label)
        top_bar.addStretch()

        # Minimize button
        btn_min = QPushButton("_")
        btn_min.setFixedSize(35, 35)
        btn_min.setStyleSheet("background-color: #1f2e3e; border: none; color: white;")
        btn_min.clicked.connect(self.showMinimized)
        top_bar.addWidget(btn_min)

        # Close button
        btn_close = QPushButton("X")
        btn_close.setFixedSize(35, 35)
        btn_close.setStyleSheet("background-color: #b22222; border: none; color: white;")
        btn_close.clicked.connect(self.close)
        top_bar.addWidget(btn_close)

        main_layout.addLayout(top_bar)

        # Content Layout
        content_layout = QGridLayout()

        # Title
        title = QLabel("CDOSR CanSat Tracking Software")
        title.setFont(QFont(FONT, 32, QFont.Bold))
        content_layout.addWidget(title, 0, 0, 1, 5)

        # Line
        line_container = QHBoxLayout()
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("color: #35506b; background-color: #35506b; height: 1px;")
        line.setFixedWidth(800)
        line_container.addStretch()
        line_container.addWidget(line)
        line_container.addStretch()
        line_widget = QWidget()
        line_widget.setLayout(line_container)
        content_layout.addWidget(line_widget, 1, 0, 1, 5)

        # Telemetry Section (Smaller)
        # telemetry_box = self.createInfoBox("TELEMETRY", [
        #     ("Pressure", "1013 hPa"),
        #     ("Temperature", "18.5 °C"),
        #     ("Humidity", "52 %")
        # ])

        telemetry_box = QFrame()
        self.telemetry_container = QGridLayout()
        self.telemetry_container.addWidget(self.createSensorBox("Temperature", 20, " °C"), 0, 0, 1, 1)
        self.telemetry_container.addWidget(self.createSensorBox("Pressure", 1000, " hPa"), 0, 1, 1, 1)
        self.telemetry_container.addWidget(self.createSensorBox("Humidity", 52, "%"), 0, 2, 1, 1)
        telemetry_box.setStyleSheet("background-color: #1b2a40; border-radius: 15px; padding: 10px;")
        telemetry_box.setLayout(self.telemetry_container)

        content_layout.addWidget(telemetry_box, 2, 0, 3, 5)

        # Altitude Indicator Section
        self.altitude_indicator = AltitudeIndicator(214)
        self.altitude_text = QLabel("Altitude\n214 m")
        self.altitude_text.setFont(QFont(FONT, 18))
        self.altitude_text.setAlignment(Qt.AlignCenter)
        altitude_layout = QVBoxLayout()
        altitude_layout.addWidget(self.altitude_indicator)
        altitude_layout.addStretch()
        altitude_layout.addWidget(self.altitude_text)
        altitude_frame = QFrame()
        altitude_frame.setLayout(altitude_layout)
        altitude_frame.setStyleSheet("background-color: #1b2a40; border-radius: 15px; padding: 10px;")
        content_layout.addWidget(altitude_frame, 0, 5, 6, 5)

        # Map Section using QWebEngineView with OpenStreetMap
        self.map_view = QWebEngineView()
        self.map_view.setHtml('''
            <!DOCTYPE html>
            <html>
            <head>
              <meta charset="utf-8" />
              <title>Leaflet Map</title>
              <meta name="viewport" content="width=device-width, initial-scale=1.0">
              <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css" />
              <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
              <style>
                #map { width: 100%; height: 100%; }
                html, body { margin: 0; height: 100%; }
              </style>
            </head>
            <body>
              <div id="map"></div>
              <script>
                  var map = L.map('map').setView([45.75, 21.23], 13);
                  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                    attribution: '&copy; OpenStreetMap contributors'
                  }).addTo(map);
                  var marker = L.marker([45.75, 21.23]).addTo(map)
                    .bindPopup('CanSat location')
                    .openPopup();
                
                  function updateMarker(lat, lon) {
                    marker.setLatLng([lat, lon]).update();
                    map.setView([lat, lon]);
                  }
                </script>
            </body>
            </html>
        ''')
        map_container = QFrame()
        map_container.setStyleSheet("background-color: #1b2a40; border-radius: 15px; padding: 5px;")
        map_layout = QVBoxLayout()
        map_layout.addWidget(self.map_view)
        map_container.setLayout(map_layout)
        content_layout.addWidget(map_container, 0, 10, 6, 6)

        # Circular Battery Indicator
        battery_frame = QFrame()
        battery_layout = QVBoxLayout()
        battery_label = QLabel("BATTERY")
        battery_label.setFont(QFont(FONT, 18, QFont.Bold))
        battery_label.setAlignment(Qt.AlignCenter)
        self.battery_indicator = CircularBattery(57)
        battery_container = QHBoxLayout()
        battery_container.addStretch()
        battery_container.addWidget(self.battery_indicator)
        battery_container.addStretch()
        battery_layout.addWidget(battery_label)
        battery_layout.addLayout(battery_container)
        battery_frame.setLayout(battery_layout)
        battery_frame.setStyleSheet("background-color: #1b2a40; border-radius: 15px; padding: 10px;")
        content_layout.addWidget(battery_frame, 6, 5, 3, 3)

        # Orientation Cube (Placeholder)
        orientation_label = QLabel("ORIENTATION")
        orientation_label.setAlignment(Qt.AlignCenter)
        cube_label = QLabel("[3D CUBE PLACEHOLDER]")
        cube_label.setAlignment(Qt.AlignCenter)
        cube_label.setStyleSheet("background-color: #1f2e3e; border-radius: 10px; padding: 20px;")
        orientation_layout = QVBoxLayout()
        orientation_layout.addWidget(orientation_label)
        orientation_layout.addWidget(cube_label)
        orientation_frame = QFrame()
        orientation_frame.setLayout(orientation_layout)
        orientation_frame.setStyleSheet("background-color: #1b2a40; border-radius: 15px; padding: 10px;")
        content_layout.addWidget(orientation_frame, 5, 0, 4, 5)

        # Console Box for Raw Packet Data
        self.console_box = QTextEdit()
        self.console_box.setReadOnly(True)
        self.console_box.setStyleSheet("background-color: #020f1c; color: white; border-radius: 15px; padding: 10px;")
        self.console_box.setText("[Raw packet data will appear here]")
        content_layout.addWidget(self.console_box, 6, 8, 3, 8)

        content_frame = QFrame()
        content_frame.setLayout(content_layout)
        content_frame.setStyleSheet("background-color: #112135; border-radius: 15px; padding: 10px;")

        main_layout.addWidget(content_frame)

        self.setLayout(main_layout)

    def start_serial(self, port, baudrate):
        try:
            self.serial_port = serial.Serial(port, baudrate, timeout=1)
            self.read_serial_thread.start()
        except serial.SerialException as e:
            print(f"Could not open serial port: {e}")

    def read_serial_data(self):
        while True:
            if self.serial_port and self.serial_port.in_waiting:
                try:
                    line = self.serial_port.readline().decode().strip()
                    self.update_packet_signal.emit(line)
                except Exception as e:
                    print(f"Serial read error: {e}")

    def update_gui(self):
        if self.console_box:
            self.console_box.append(self.latest_line)

        if self.battery_indicator:
            self.battery_indicator.percentage = int(self.latest_battery)
            self.battery_indicator.update()

        if self.altitude_indicator:
            self.altitude_indicator.setAltitude(self.latest_altitude)

        if self.altitude_text:
            self.altitude_text.setText(f"Altitude\n{int(self.latest_altitude)} m")

        if self.latest_temperature:
            self.telemetry_container.addWidget(self.createSensorBox("Temperature", self.latest_temperature, " °C"), 0, 0, 1, 1)

        if self.latest_pressure:
            self.telemetry_container.addWidget(self.createSensorBox("Pressure", self.latest_pressure, " hPa"), 0, 1, 1, 1)

        if self.latest_humidity:
            self.telemetry_container.addWidget(self.createSensorBox("Humidity", self.latest_humidity, "%"), 0, 2, 1, 1)

        if self.latest_latitude and self.latest_longitude:
            self.map_view.page().runJavaScript(f"updateMarker({self.latest_latitude}, {self.latest_longitude});")

    @pyqtSlot(str)
    def update_from_packet(self, line):
        try:
            # print(line)
            data = line.split(",")

            # Extract required values
            battery = float(data[0])
            altitude = float(data[1])
            pressure = float(data[2])
            temperature = float(data[3])
            humidity = float(data[4])
            latitude = float(data[5])
            longitude = float(data[6])
            accelerometer_x = float(data[7])
            accelerometer_y = float(data[8])
            accelerometer_z = float(data[9])
            gyroscope_x = float(data[10])
            gyroscope_y = float(data[11])
            gyroscope_z = float(data[12])
            magnetometer_x = float(data[13])
            magnetometer_y = float(data[14])
            magnetometer_z = float(data[15])

            rotation_matrix = self.compute_rotation_matrix(accelerometer_x, accelerometer_y, accelerometer_z, gyroscope_x, gyroscope_y, gyroscope_z, magnetometer_x, magnetometer_y, magnetometer_z)

            # self.cube_widget.setOrienation(rotation_matrix)
            self.latest_line = line
            self.latest_battery = battery
            self.latest_altitude = altitude
            self.latest_temperature = temperature
            self.latest_humidity = humidity
            self.latest_pressure = pressure
            self.latest_latitude = latitude
            self.latest_longitude = longitude
            QTimer.singleShot(0, self.update_gui)  # Safely update from thread

        except Exception as e:
            print(f"Parse/update error: {e}")

    def compute_rotation_matrix(self, ax, ay, az, gx, gy, gz, mx, my, mz):
        # Placeholder for the actual rotation matrix computation
        # Typically, this would involve sensor fusion algorithms like Madgwick or Mahony filters
        # For now, we return a simple identity matrix
        return np.identity(4)

    def createInfoBox(self, title, items):
        frame = QFrame()
        layout = QVBoxLayout()
        header = QLabel(title)
        header.setFont(QFont(FONT, 14, QFont.Bold))
        layout.addWidget(header)
        for label, value in items:
            row = QLabel(f"{label}: {value}")
            row.setFont(QFont(FONT, 12))
            layout.addWidget(row)
        frame.setLayout(layout)
        frame.setStyleSheet("background-color: #1b2a40; border-radius: 15px; padding: 10px;")
        return frame

    def createSensorBox(self, title, value, unit):
        frame = QFrame()
        layout = QVBoxLayout()
        header = QLabel(title)
        header.setFont(QFont(FONT, 18))
        layout.addWidget(header)
        row = QLabel(str(value)+unit)
        row.setFont(QFont(FONT, 24, QFont.Bold))
        layout.addWidget(row)
        frame.setLayout(layout)
        frame.setStyleSheet("background-color: #20324C; border-radius: 15px; padding: 10px;")
        return frame


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ui = CanSatUI()
    ui.show()
    sys.exit(app.exec_())
