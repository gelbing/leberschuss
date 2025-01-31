import os
import sys
from functools import partial

import pyperclip
from openai import OpenAI
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QTextOption
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QCheckBox,
    QDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QStyle,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class LastAnswerWindow(QWidget):
    """
    A simple, separate window that shows only the last answer.
    """

    def __init__(self, parent=None):
        logger.debug("Creating LastAnswerWindow")
        # Pass None to create a top-level window instead of a child widget
        super().__init__(None)
        self.setWindowTitle("272")

        self.answer_view = QPlainTextEdit(self)
        self.answer_view.setReadOnly(True)

        # Enable line wrap in the last answer text
        self.answer_view.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.answer_view.setWordWrapMode(QTextOption.WordWrap)

        layout = QVBoxLayout()
        layout.addWidget(self.answer_view)
        self.setLayout(layout)

        # Optional: Set a minimum size
        self.setMinimumSize(400, 300)
        logger.debug("LastAnswerWindow created")

    def set_answer_text(self, text: str):
        logger.debug(f"Setting answer text: {text}")
        self.answer_view.setPlainText(text)
        logger.debug("Answer text set")


class ApiKeyApp(QWidget):
    def __init__(self):
        logger.debug("Creating ApiKeyApp")
        super().__init__()

        self.setWindowTitle("OpenAI API Key and Settings")
        self.setGeometry(100, 100, 600, 500)  # Slightly larger default window

        # State
        self.is_initialized = False
        self.api_key = None
        self.notify_answers = True
        self.output_to_clipboard = False
        self.skip_clipboard_change = False
        self.previous_text = ""

        # GUI Elements
        self.label = QLabel("Enter your OpenAI API Key:")
        self.input = QLineEdit()
        self.input.setEchoMode(QLineEdit.Password)

        self.save_button = QPushButton("Save and Minimize")

        # Prompt label + multi-line text
        self.openai_prompt_label = QLabel("OpenAI Prompt:")
        self.openai_prompt = QPlainTextEdit()
        # Make sure it is editable
        self.openai_prompt.setReadOnly(False)
        # Instead of placeholder, set an initial text:
        self.openai_prompt.setPlainText(
            "You are assisting with a psychology exam at a German university.\n"
            "The questions will all be multiple choice and where copied from tables on the exam paper.\n"
            "You should not provide any additional information.\n"
            "You should not repeat the options.\n"
            "Only return for each option whether it is correct or incorrect.\n"
            "you should return your answer as one string. e.g. 'RICHTIG FALSCH FALSCH FALSCH'\n should answer a multiple choice question with 4 options.\n"
            "Please use emojis instead of the words 'RICHTIG' and 'FALSCH'.\n"
        )
        # Decide if you want line wrapping for the prompt as well:
        self.openai_prompt.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.openai_prompt.setWordWrapMode(QTextOption.WordWrap)

        # Last Answer label + multi-line text
        self.last_anwer_label = QLabel("Last Answer:")
        self.last_answer = QPlainTextEdit()
        self.last_answer.setReadOnly(True)
        # Enable line wrap so it shows the entire text
        self.last_answer.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.last_answer.setWordWrapMode(QTextOption.WordWrap)

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

        # Events
        self.save_button.clicked.connect(self.save_settings)

        # System Tray
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        # self.tray_icon.setIcon(QIcon("leberschuss/icon.png"))  # Replace with your own icon

        tray_menu = QMenu()
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.show)
        tray_menu.addAction(settings_action)

        last_answer_action = QAction("Last Answer Window", self)
        last_answer_action.triggered.connect(self.show_last_answer_only)
        tray_menu.addAction(last_answer_action)

        notify_action = QAction("Notify", self)
        notify_action.triggered.connect(self.parse_and_run_clipboard_query)
        tray_menu.addAction(notify_action)

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.exit_application)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        # Check saved key
        self.check_saved_key()
        os.environ["OPENAI_API_KEY"] = self.api_key if self.api_key else ""

        # Clipboard monitoring
        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(self.parse_and_run_clipboard_query)

        # Separate window for showing only the last answer
        self.last_answer_window = LastAnswerWindow()
        logger.debug("ApiKeyApp created")

    def show_notification(self):
        logger.debug("Showing notification")
        self.tray_icon.showMessage(
            "",
            self.last_answer.toPlainText(),
            QSystemTrayIcon.Information,
            3000,
        )
        logger.debug("Notification shown")

    def check_saved_key(self):
        logger.debug("Checking saved key")
        if os.path.exists("api_key.txt"):
            logger.debug("Saved key found")
            with open("api_key.txt", "r") as file:
                self.api_key = file.read().strip()
                if self.api_key:
                    self.label.setText("A saved API Key was found.")
                    self.input.setText(self.api_key)
        else:
            logger.debug("No saved key found")
        logger.debug("Saved key check complete")

    def _manual_run(self):
        self.parse_and_run_clipboard_query()

    def save_settings(self):
        logger.debug("Saving settings")
        self.api_key = self.input.text().strip()
        self.notify_answers = self.notification_checkbox.isChecked()
        self.output_to_clipboard = self.output_to_clipboard_checkbox.isChecked()

        if self.api_key:
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
        logger.debug("Settings saved")

    def copy_answer_to_clipboard(self):
        logger.debug("Copying answer to clipboard")
        self.skip_clipboard_change = True
        pyperclip.copy(self.last_answer.toPlainText())
        logger.debug("Answer copied to clipboard")

    def parse_and_run_clipboard_query(self):
        logger.debug("Running OpenAI query")

        if not self.is_initialized:
            logger.debug("App not initialized")
            return

        if self.skip_clipboard_change:
            logger.debug("Skipping clipboard change")
            self.skip_clipboard_change = False
            return

        current_text = pyperclip.paste()
        logger.debug(f"Clipboard text: {current_text}")
        # Only process if it changed and is not empty and doesn’t start with "Answer:"
        if current_text.strip():
            if current_text == self.previous_text:
                logger.debug("Text unchanged. Processing anyway.")

            self.previous_text = current_text
            answer = self._process_openapi_query(current_text)
            self.last_answer.setPlainText(answer)
            self.last_answer_window.set_answer_text(answer)

            if self.notify_answers:
                self.show_notification()

            if self.output_to_clipboard:
                self.copy_answer_to_clipboard()

            logger.debug("OpenAI query complete")
        else:
            logger.debug("No text to process in clipboard")


    def _process_openapi_query(self, text):
        if not os.environ.get("OPENAI_API_KEY"):
            self.tray_icon.showMessage(
                "Error",
                "No API Key set. Please restart the app and enter your key.",
                QSystemTrayIcon.Warning,
                3000,
            )
            return "No API Key set. Please restart the app and enter your key."

        try:
            # Send query to OpenAI
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
            logger.debug(f"OpenAI response: {answer}")

            return answer

        except Exception as e:
            error_msg = f"An error occurred: {str(e)}"
            self.tray_icon.showMessage(
                "Error", error_msg, QSystemTrayIcon.Warning, 5000
            )
            return "An error occurred during processing."
        looger.debug("OpenAI query processed")

    def show_last_answer_only(self):
        """
        Hides the main window and shows a separate window
        that displays only the last answer.
        """
        logger.debug("Showing last answer window")
        # Update text in the last answer window
        self.last_answer_window.set_answer_text(self.last_answer.toPlainText())

        # Hide main window. You can show it again from the tray "Settings" action.
        self.hide()
        self.last_answer_window.show()
        logger.debug("Last answer window shown")

    def exit_application(self):
        logger.debug("Exiting application")
        self.tray_icon.hide()
        QApplication.instance().quit()


def main():
    app = QApplication(sys.argv)
    main_window = ApiKeyApp()
    main_window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
