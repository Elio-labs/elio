from textual.screen import ModalScreen
from textual.widgets import OptionList, Label
from textual.widgets.option_list import Option
from textual.app import ComposeResult
from textual.containers import Vertical

from elio.providers.registry import MODEL_REGISTRY


class ModelSelectorScreen(ModalScreen[str]):
    """
    A modal overlay that lists all model aliases.
    Pressing Enter on one returns the alias string to the caller.
    """

    CSS = """
    ModelSelectorScreen {
        align: center middle;
    }
    #selector-box {
        width: 60;
        height: auto;
        max-height: 20;
        background: $surface;
        border: solid $accent;
        padding: 1;
    }
    #selector-title {
        text-align: center;
        padding-bottom: 1;
        color: $text-muted;
    }
    """

    def compose(self) -> ComposeResult:
        options = [
            Option(f"{alias:10}  {entry.description}", id=alias)
            for alias, entry in MODEL_REGISTRY.items()
        ]
        with Vertical(id="selector-box"):
            yield Label("Select a model  (Enter to confirm, Esc to cancel)", id="selector-title")
            yield OptionList(*options, id="model-list")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        self.dismiss(event.option.id)

    def on_key(self, event):
        if event.key == "escape":
            self.dismiss(None)