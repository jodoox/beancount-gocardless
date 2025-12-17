from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Label


raise Exception


class MinimalApp(App):
    TITLE = "Minimal Test App"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("If you see this, MinimalApp from tui.py is running!")
        yield Footer()


app = MinimalApp()
