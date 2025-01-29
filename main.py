import os
import sys
import pyperclip
from openai import OpenAI
from functools import partial

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QClipboard, QIcon
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
    QPlainTextEdit,
    QDialog,
    QHBoxLayout,
)


# Window to show only the last answer
class LastAnswerWindow(QWidget):
    def __init__(self, answer_text="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Last Answer")

        layout = QVBoxLayout()
        self.answer_view = QPlainTextEdit(self)
        self.answer_view.setReadOnly(True)
        self.answer_view.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.answer_view.setPlainText(answer_text)

        layout.addWidget(self.answer_view)
        self.setLayout(layout)

        # Optional: set a minimum size
        self.setMinimumSize(300, 200)


class ApiKeyApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OpenAI API Key and Settings")
        self.setGeometry(100, 100, 600, 400)  # Widen the default window a bit

        self.is_initialized = False
        self.api_key = None
        self.notify_answers = True
        self.output_to_clipboard = True
        self.skip_clipboard_change = False

        # GUI Elements
        self.label = QLabel("Enter your OpenAI API Key:")
        self.input = QLineEdit()
        self.input.setEchoMode(QLineEdit.Password)

        self.save_button = QPushButton("Save and Minimize")

        # Prompt label and multi-line text field (QPlainTextEdit)
        self.openai_prompt_label = QLabel("OpenAI Prompt:")
        self.openai_prompt = QPlainTextEdit()
        self.openai_prompt.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.openai_prompt.setPlaceholderText(
            "You are assisting with a psychology exam at a German university.\n"
            "If a question is multiple-choice, provide only the correct answers (e.g., 'A + B' or '1 + 4') "
            "without any additional explanation.\n"
            "For non-multiple-choice questions, respond with concise and accurate text answers. "
            "Focus on clarity and brevity in all responses."
        )

        # Last Answer label and multi-line text field (QPlainTextEdit)
        self.last_anwer_label = QLabel("Last Answer:")
        self.last_answer = QPlainTextEdit()
        self.last_answer.setReadOnly(True)
        self.last_answer.setLineWrapMode(QPlainTextEdit.NoWrap)

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

        # Event Connections
        self.save_button.clicked.connect(self.save_settings)

        # Tray Support
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon("icon.png"))  # your tray icon

        tray_menu = QMenu()
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.show)
        tray_menu.addAction(settings_action)

        # NEW: Show last answer only (no settings/prompt)
        last_answer_action = QAction("Show Last Answer Only", self)
        last_answer_action.triggered.connect(self.show_last_answer_only)
        tray_menu.addAction(last_answer_action)

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.exit_application)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)

        # Check if an API key is saved
        self.check_saved_key()
        # Export the api key as an environment variable
        os.environ["OPENAI_API_KEY"] = self.api_key if self.api_key else ""

        # Timer for clipboard monitoring
        self.previous_text = ""
        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(
            partial(self.on_clipboard_changed, clipboard=self.clipboard)
        )

        self.last_answer_window = None  # Reference to the last-answer-only window

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
            # Save the API key (locally for demo purposes)
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
        if not self.is_initialized:
            self.skip_clipboard_change = True

        if self.skip_clipboard_change:
            self.skip_clipboard_change = False
            return

        current_text = clipboard.text()
        if (
            current_text != self.previous_text
            and current_text.strip()
            and not current_text.startswith("Answer:")
        ):
            self.previous_text = current_text
            answer = self.process_question(current_text)
            self.last_answer.setPlainText(answer)

            if self.notify_answers:
                self.tray_icon.showMessage(
                    "Answer", answer, QSystemTrayIcon.Information, 5000
                )

            if self.output_to_clipboard:
                self.skip_clipboard_change = True
                pyperclip.copy(answer)

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
            # Send query to OpenAI API
            client = OpenAI()

            completion = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": self.openai_prompt.toPlainText(),
                    },
                    {
                        "role": "user",
                        "content": text,
                    },
                ],
            )

            response = completion.choices[0].message
            answer = response.content
            return answer

        except Exception as e:
            error_msg = f"An error occurred: {str(e)}"
            self.tray_icon.showMessage(
                "Error", error_msg, QSystemTrayIcon.Warning, 5000
            )
            return "An error occurred during processing."

    def show_last_answer_only(self):
        """Creates or updates a separate window displaying only the last answer."""
        if not self.last_answer_window:
            self.last_answer_window = LastAnswerWindow(parent=self)
        # Update the text in case the last answer changed
        self.last_answer_window.answer_view.setPlainText(self.last_answer.toPlainText())
        self.last_answer_window.show()

    def exit_application(self):
        self.tray_icon.hide()
        QApplication.instance().quit()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = ApiKeyApp()
    main_window.show()
    sys.exit(app.exec_())
