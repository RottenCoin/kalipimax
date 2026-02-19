#!/usr/bin/env python3
"""
KaliPiMax Y/N Prompt
Simple yes/no confirmation widget for 128x128 LCD.

Usage:
    prompt = YNPrompt("Use tools on\nthis network?")
    prompt.move(-1)  # left = Y
    prompt.move(1)   # right = N
    answer = prompt.confirm()  # True=Y, False=N
    prompt.render(canvas, y_start)
"""

from ui.renderer import Canvas
from config import DISPLAY_WIDTH


class YNPrompt:
    """Yes/No confirmation prompt."""

    def __init__(self, question: str, default_yes: bool = False):
        self.question = question
        self.selected_yes = default_yes

    def move(self, dx: int):
        """Move selection. Any movement toggles."""
        if dx != 0:
            self.selected_yes = not self.selected_yes

    def confirm(self) -> bool:
        """Return current selection. True = Yes, False = No."""
        return self.selected_yes

    def render(self, canvas: Canvas, y_start: int) -> int:
        """
        Draw the prompt on the canvas.

        Returns Y position after the prompt.
        """
        y = y_start

        # Question text (supports newlines)
        for line in self.question.splitlines():
            canvas.text(2, y, line, colour='text', font='small')
            y += 12

        y += 6

        # Y/N buttons
        btn_w = 40
        gap = 20
        total = btn_w * 2 + gap
        x_start = (DISPLAY_WIDTH - total) // 2

        x_y = x_start
        x_n = x_start + btn_w + gap

        # Yes button
        if self.selected_yes:
            canvas.rect(x_y - 2, y - 2, x_y + btn_w, y + 14, fill='bg_selected')
        colour_y = 'ok' if self.selected_yes else 'text_dim'
        canvas.text(x_y + 10, y, "YES", colour=colour_y, font='medium')

        # No button
        if not self.selected_yes:
            canvas.rect(x_n - 2, y - 2, x_n + btn_w, y + 14, fill='bg_selected')
        colour_n = 'error' if not self.selected_yes else 'text_dim'
        canvas.text(x_n + 12, y, "NO", colour=colour_n, font='medium')

        return y + 18
