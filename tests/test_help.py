from vpsbot.bot.handlers.start import help_text


def test_help_examples_are_single_line_copy_blocks():
    text = help_text()
    examples = [
        "/r remind me tomorrow at 5pm",
        "/r remind me tomorrow at 5pm /pm",
        "/r take meds at 8am, 3pm, 8pm",
        "/r do this 3pm, tomorrow 5pm, next wednesday 8pm, 11pm",
        "/r every day at 9am",
        "/r every monday at 8pm",
        "/r every day at 9am for 3 times",
        "/r every 2 days at 8pm for 2 weeks",
        "/list",
        "/cancel",
    ]
    assert "```" not in text
    for example in examples:
        assert f"`{example}`" in text
