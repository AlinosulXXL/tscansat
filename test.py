from PyQt5.QtWidgets import QApplication, QWidget, QGridLayout, QLabel

app = QApplication([])

# Main window
window = QWidget()
grid_layout = QGridLayout()

# Widgets
label1 = QLabel("Widget 1")
label2 = QLabel("Widget 2")
label3 = QLabel("Widget 3")

# Set fixed size for label1
label1.setFixedSize(100, 50)

# Set minimum and maximum size for label2
label2.setMinimumSize(150, 100)
label2.setMaximumSize(200, 150)

# Set a large size for label3
label3.setFixedSize(300, 150)

# Add widgets to grid
grid_layout.addWidget(label1, 0, 0)  # Widget 1
grid_layout.addWidget(label2, 0, 1)  # Widget 2
grid_layout.addWidget(label3, 1, 0, 1, 2)  # Widget 3 spans across two columns

# Set column stretch factors (you can adjust the widths of columns)
grid_layout.setColumnStretch(0, 1)  # Column 0 will stretch slightly less
grid_layout.setColumnStretch(1, 2)  # Column 1 will stretch more

# Set row stretch factor
grid_layout.setRowStretch(0, 1)
grid_layout.setRowStretch(1, 3)  # Row 1 will take more space

window.setLayout(grid_layout)
window.show()

app.exec_()
