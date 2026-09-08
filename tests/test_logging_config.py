from research_automation.logging_config import configure_console_encoding


class ReconfigurableStream:
    def __init__(self):
        self.configuration = None

    def reconfigure(self, **kwargs):
        self.configuration = kwargs


def test_console_is_reconfigured_for_multilingual_headlines() -> None:
    stream = ReconfigurableStream()
    configure_console_encoding([stream])
    assert stream.configuration == {"encoding": "utf-8", "errors": "replace"}
