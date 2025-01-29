import os
import sys
import pyperclip

from openai import OpenAI
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QClipboard, QIcon
from functools import partial
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QCheckBox,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)


class ApiKeyApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OpenAI API Key and Settings")
        self.setGeometry(100, 100, 400, 250)
        self.is_initialized = False
        self.api_key = None
        self.notify_answers = True
        self.output_to_clipboard = True

        self.skip_clipboard_change = False
        # GUI-Elemente
        self.label = QLabel("Enter your OpenAI API Key:")
        self.input = QLineEdit()
        self.input.setEchoMode(QLineEdit.Password)
        self.save_button = QPushButton("Save and Minimize")
        self.last_anwer_label = QLabel("Last Answer:")
        self.openai_prompt_label = QLabel("OpenAI Prompt:")
        self.openai_prompt = QLineEdit()
        self.openai_prompt.setPlaceholderText("""
                                              You are assisting with a psychology exam at a German university.
                                              If a question is multiple-choice, provide only the correct answers (e.g., 'A + B' or '1 + 4') without any additional explanation.
                                              For non-multiple-choice questions, respond with concise and accurate text answers. Focus on clarity and brevity in all responses.
                                              """)
        self.openai_prompt.setReadOnly(False)


        self.last_answer = QLineEdit()
        self.last_answer.setReadOnly(True)

        self.notification_checkbox = QCheckBox("Show answers as notifications")
        self.notification_checkbox.setChecked(self.notify_answers)

        self.output_to_clipboard_checkbox = QCheckBox("Output answers to clipboard")
        self.output_to_clipboard_checkbox.setChecked(True)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.input)
        layout.addWidget(self.openai_prompt_label)
        layout.addWidget(self.openai_prompt)
        layout.addWidget(self.last_anwer_label)
        layout.addWidget(self.last_answer)
        layout.addWidget(self.notification_checkbox)
        layout.addWidget(self.output_to_clipboard_checkbox)
        layout.addWidget(self.save_button)
        self.setLayout(layout)

        # Event-Verknüpfungen
        self.save_button.clicked.connect(self.save_settings)

        # Tray-Support
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon("icon.png"))  # Icon für das Tray

        tray_menu = QMenu()
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.show)
        tray_menu.addAction(settings_action)

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.exit_application)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)

        # Prüfen, ob ein API-Schlüssel gespeichert ist
        self.check_saved_key()
        # Export the api key as export OPENAI_API_KEY="your_api_key_here"
        os.environ["OPENAI_API_KEY"] = self.api_key

        # Timer für Zwischenablage-Überwachung

        self.previous_text = ""
        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(partial(self.on_clipboard_changed, clipboard=self.clipboard))

    def check_saved_key(self):
        if os.path.exists("api_key.txt"):
            with open("api_key.txt", "r") as file:
                self.api_key = file.read().strip()
                if self.api_key:
                    self.label.setText("A saved API Key was found.")
                    self.input.setText(self.api_key)

    def save_settings(self):
        self.api_key = self.input.text()
        self.notify_answers = self.notification_checkbox.isChecked()
        self.output_to_clipboard = self.output_to_clipboard_checkbox.isChecked()

        if self.api_key:
            # API-Schlüssel speichern (lokal, für Demo-Zwecke)
            with open("api_key.txt", "w") as file:
                file.write(self.api_key)

            self.tray_icon.show()
            self.tray_icon.showMessage(
                "Success",
                "Settings saved and app minimized to tray.",
                QSystemTrayIcon.Information,
                3000,
            )

            self.hide()
            self.is_initialized = True
        else:
            self.label.setText("Please enter a valid API Key.")
            self.label.setStyleSheet("color: red;")

    def on_clipboard_changed(self, clipboard):
        print("Clipboard change event triggered.")
        if not self.is_initialized:
            print("App not initialized.")
            self.skip_clipboard_change = True

        if self.skip_clipboard_change:
            print("Skipping clipboard change event.")
            self.skip_clipboard_change = False
            return


        current_text = clipboard.text()
        if (
            current_text != self.previous_text
            and current_text.strip()
            and not current_text.startswith("Answer:")
        ):
            print("Clipboard content changed. Processing question.")
            self.previous_text = current_text
            answer = self.process_question(current_text)


            self.last_answer.setText(answer)

            if self.notify_answers:
                self.tray_icon.showMessage(
                  "Answer",  answer, QSystemTrayIcon.Information, 5000
                )

            if self.output_to_clipboard:
                print("Outputting answer to clipboard.")
                self.skip_clipboard_change = True

                pyperclip.copy(answer)
                # clipboard.setText(self.last_answer.copy())




    def process_question(self, text):
        if not os.environ.get("OPENAI_API_KEY"):
            self.tray_icon.showMessage(
                "Error",
                "No API Key set. Please restart the app and enter your key.",
                QSystemTrayIcon.Warning,
                3000,
            )
            return "No API Key set. Please restart the app and enter your key."

        try:
            # Anfrage an die OpenAI-API
            print("Processing question through OpenAI API")
            client = OpenAI()

            completion = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": self.openai_prompt.text(),
                    },
                    {
                        "role": "user",
                        "content": text,
                    },
                ],
            )

            response = completion.choices[0].message
            answer = response.content
            print("Success")
            return answer

        except Exception as e:
            self.tray_icon.showMessage(
                "Error", f"An error occurred: {str(e)}", QSystemTrayIcon.Warning, 5000
            )
            return "An error occurred during processing."

    def exit_application(self):
        self.tray_icon.hide()
        QApplication.instance().quit()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    main_window = ApiKeyApp()
    main_window.show()
    sys.exit(app.exec_())
