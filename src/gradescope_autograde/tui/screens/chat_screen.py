from __future__ import annotations

from textual import on, work
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Static


class ChatScreen(Screen):
    AUTO_FOCUS = "#chat-input"

    def __init__(self, verbose: bool = False) -> None:
        super().__init__()
        self.verbose = verbose
        self._chat_history: list[str] = []

    BINDINGS = [
        ("escape", "go_back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield VerticalScroll(
            Label("AI Chat (OpenCode)", classes="screen-title"),
            Static(
                "Send messages to OpenCode CLI. Use 'verbose' toggle to see detailed output.",
                classes="info-message",
            ),
            Button("Toggle Verbose", id="toggle-verbose", variant="default"),
            Static("", id="verbose-status"),
            Static("Chat History:", classes="field-label"),
            Static("", id="chat-history"),
            Label("Message:", classes="field-label"),
            Input(placeholder="Type your message here...", id="chat-input"),
            Button("Send", id="send-chat", variant="primary"),
            id="main",
        )
        yield Footer()

    @on(Button.Pressed, "#toggle-verbose")
    def _toggle_verbose(self) -> None:
        self.verbose = not self.verbose
        btn = self.query_one("#toggle-verbose", Button)
        status = self.query_one("#verbose-status", Static)
        if self.verbose:
            btn.variant = "primary"
            btn.label = "Verbose*"
            status.update("[green]Verbose mode ON[/]")
        else:
            btn.variant = "default"
            btn.label = "Verbose"
            status.update("[dim]Verbose mode OFF[/]")

    @on(Button.Pressed, "#send-chat")
    def _on_send_button(self, event: Button.Pressed) -> None:
        self._send_message()

    @on(Input.Submitted, "#chat-input")
    def _on_input_submitted(self, event: Input.Submitted) -> None:
        self._send_message()

    @work(thread=True)
    def _send_message(self) -> None:
        input_widget = self.query_one("#chat-input", Input)
        message = input_widget.value.strip()
        if not message:
            return

        history = self.query_one("#chat-history", Static)
        self._chat_history.append(f"You: {message}")
        history.update("\n".join(self._chat_history[-20:]))

        input_widget.value = ""

        from gradescope_autograde.utils.opencode_utils import run_chat

        self._chat_history.append("AI: Thinking...")
        history.update("\n".join(self._chat_history[-20:]))

        response = run_chat(message, verbose=self.verbose)

        self._chat_history.pop()
        self._chat_history.append(f"AI: {response}")
        history.update("\n".join(self._chat_history[-20:]))

    @on(Button.Pressed, "#back")
    def _on_back(self) -> None:
        self.app.pop_screen()
