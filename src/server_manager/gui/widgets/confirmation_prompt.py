from textual import on
from textual.containers import Grid
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class ConfirmationPrompt(ModalScreen):
    def __init__(self, container_name: str):
        self.container_name = container_name
        super().__init__()

    def compose(self):
        with Grid(id="confirmation_prompt_content"):
            yield Label(
                f"Are you sure you want to remove the container '{self.container_name}'?", id="confirmation_message"
            )
            yield Label("Please type the container name to confirm:", id="confirmation_submessage")
            yield Input("", id="container_name_input")
            yield Button("Yes", id="confirm_button", disabled=True)
            yield Button("No", id="cancel_button")

    def on_input_changed(self, event: Input.Changed) -> None:
        # Enable the confirm button only if the input matches the container name
        confirm_button = self.query_one("#confirm_button", Button)
        confirm_button.disabled = event.value != self.container_name

    @on(Button.Pressed, "#confirm_button")
    def confirm(self):
        input_value = self.query_one("#container_name_input", Input).value
        if input_value == self.container_name:
            self.loading = True
            self.dismiss(self.container_name)  # Confirm deletion
        else:
            self.query_one("#confirmation_submessage", Label).update("Container name does not match. Please try again.")

    @on(Button.Pressed, "#cancel_button")
    def cancel(self):
        self.dismiss(None)
