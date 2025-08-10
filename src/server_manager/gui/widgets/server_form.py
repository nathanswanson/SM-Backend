from __future__ import annotations

import logging

from textual import on
from textual.containers import Grid, Horizontal
from textual.logging import TextualHandler
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static
from textual_autocomplete import AutoComplete

from server_manager.common.template import Template, TemplateManager

logging.basicConfig(
    level="NOTSET",
    handlers=[TextualHandler()],
)


class ServerForm(ModalScreen):
    def __init__(self, templates: dict[str, Template]):
        self.template: Template | None = None
        self.templates: dict[str, Template] = templates
        self.container_fields: dict[str, str] = {}
        self.dynamic_box = Static(
            "Enter Server to see available options", id="server_dynamic_box"
        )
        super().__init__(id="ServerForm")

    @on(Button.Pressed, "#create_server_button")
    def create_server(self):
        if self.template is None:
            return
        self.log("Creating server...")
        env: dict[str, str] = {}
        # space seperated dictionary of server fields
        for field in self.query(".server_dynamic_box_entry_input"):
            if isinstance(field, Input):
                if field.name is None:
                    logging.warning("Field name is None, skipping...")
                    continue
                if field.value:
                    env[field.name] = field.value
        self.dismiss({"server_name": "", "image_name": self.template.image, "env": env})

    @on(Button.Pressed, "#cancel_button")
    def cancel(self):
        self.app.pop_screen()

    @on(Button.Pressed, "#apply_server_name")
    def apply_template(self):
        self.template = TemplateManager().get_template(
            self.query_one("#server_name_input", Input).value
        )
        if self.template is None:
            return
        self.log(f"Server name applied: {self.template}")
        for template_name, template in self.templates.items():
            if template_name == self.template.name:
                template_env = TemplateManager().get_template_env(template)
                if template_env:
                    self.container_fields = template_env
                self.refresh(recompose=True)

    def compose(self):
        text_input = Input(
            self.template.name if self.template else "", id="server_name_input"
        )
        with Grid(id="serverdialog"):
            yield Label("Image Name:", id="server_name_label")
            yield text_input
            yield Button("✔️", id="apply_server_name")
            with Static(
                id="server_dynamic_box"
                if len(self.container_fields) == 0
                else "server_dynamic_box_expanded",
                expand=True,
            ):
                if len(self.container_fields) == 0:
                    yield Label(
                        "Enter Server to see available options", classes="dynamic_box"
                    )
                else:
                    for config_entry in self.container_fields:
                        yield Horizontal(
                            Label(
                                config_entry, classes="server_dynamic_box_entry_label"
                            ),
                            Input(
                                name=config_entry,
                                classes="server_dynamic_box_entry_input",
                                id=f"server_dynamic_box_entry_{config_entry}",
                            ),
                            classes="server_dynamic_box_entry",
                        )
            yield Button("Create", id="create_server_button")
            yield Button("Cancel", id="cancel_button")
        yield AutoComplete(
            target=text_input,
            candidates=list(self.templates.keys()),
        )
