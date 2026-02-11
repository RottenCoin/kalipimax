#!/usr/bin/env python3
"""
KaliPiMax On-Screen Keyboard
Joystick-navigated character input for 128x128 LCD.

Usage:
    kb = OnScreenKeyboard()
    kb.move(dx, dy)   # joystick navigation
    result = kb.select()  # joystick press — returns char, 'DEL', 'DONE', or None
    kb.toggle_shift()     # K1
    kb.render(canvas, y)  # draw at position y
    kb.text               # current input string
"""

from ui.renderer import Canvas, Fonts
from config import DISPLAY_WIDTH, COLOURS


# Character grids — 4 rows of 10 characters each
_LOWER = [
    list('abcdefghij'),
    list('klmnopqrst'),
    list('uvwxyz0123'),
    list('456789.-_@'),
]

_UPPER = [
    list('ABCDEFGHIJ'),
    list('KLMNOPQRST'),
    list('UVWXYZ!#$%'),
    list('&*()+=?/:;'),
]

# Action row labels
_ACTIONS = ['DEL', 'SPC', 'DONE']

# Grid dimensions
_COLS = 10
_CHAR_ROWS = 4
_ACTION_ROW = _CHAR_ROWS  # row index 4
_TOTAL_ROWS = _CHAR_ROWS + 1

# Cell sizing (pixels)
_CELL_W = 12
_CELL_H = 11
_GRID_X = 4


class OnScreenKeyboard:
    """On-screen keyboard navigated by joystick."""

    def __init__(self, max_length: int = 63):
        self.text = ""
        self.max_length = max_length
        self._shifted = False
        self._row = 0
        self._col = 0

    def move(self, dx: int, dy: int):
        """
        Move cursor. dx = left/right (-1/+1), dy = up/down (-1/+1).
        Only one axis per call.
        """
        if dy != 0:
            self._move_vertical(dy)
        if dx != 0:
            self._move_horizontal(dx)

    def _move_vertical(self, dy: int):
        new_row = self._row + dy

        if new_row < 0:
            new_row = 0
        elif new_row >= _TOTAL_ROWS:
            new_row = _TOTAL_ROWS - 1

        # Transitioning between char grid and action row
        if self._row < _ACTION_ROW and new_row == _ACTION_ROW:
            # Map 10 columns → 3 actions
            if self._col <= 2:
                self._col = 0      # DEL
            elif self._col <= 6:
                self._col = 1      # SPC
            else:
                self._col = 2      # DONE
        elif self._row == _ACTION_ROW and new_row < _ACTION_ROW:
            # Map 3 actions → 10 columns
            self._col = [1, 5, 8][self._col]

        self._row = new_row

    def _move_horizontal(self, dx: int):
        if self._row == _ACTION_ROW:
            max_col = len(_ACTIONS) - 1
        else:
            max_col = _COLS - 1

        self._col = max(0, min(max_col, self._col + dx))

    def select(self) -> str:
        """
        Press the currently highlighted key.

        Returns:
            Single character that was typed, or
            'DEL' if backspace, or
            'DONE' if user confirmed input, or
            None if nothing happened.
        """
        if self._row == _ACTION_ROW:
            action = _ACTIONS[self._col]
            if action == 'DEL':
                if self.text:
                    self.text = self.text[:-1]
                return 'DEL'
            elif action == 'SPC':
                if len(self.text) < self.max_length:
                    self.text += ' '
                return ' '
            elif action == 'DONE':
                return 'DONE'
        else:
            grid = _UPPER if self._shifted else _LOWER
            ch = grid[self._row][self._col]
            if len(self.text) < self.max_length:
                self.text += ch
            return ch

        return None

    def toggle_shift(self):
        """Toggle between lower and upper/symbol layers."""
        self._shifted = not self._shifted

    @property
    def shifted(self) -> bool:
        return self._shifted

    def render(self, canvas: Canvas, y_start: int) -> int:
        """
        Draw the keyboard grid on the canvas.

        Args:
            canvas: Canvas to draw on.
            y_start: Y pixel to start drawing the grid.

        Returns:
            Y position after the grid.
        """
        grid = _UPPER if self._shifted else _LOWER

        # Draw character rows
        for row_idx in range(_CHAR_ROWS):
            y = y_start + row_idx * _CELL_H
            for col_idx in range(_COLS):
                x = _GRID_X + col_idx * _CELL_W
                is_sel = (row_idx == self._row and col_idx == self._col)

                if is_sel:
                    canvas.rect(x - 1, y - 1, x + _CELL_W - 2, y + _CELL_H - 2,
                                fill='bg_selected')

                ch = grid[row_idx][col_idx]
                colour = 'highlight' if is_sel else 'text_dim'
                canvas.text(x + 2, y, ch, colour=colour, font='tiny')

        # Draw action row
        action_y = y_start + _CHAR_ROWS * _CELL_H
        action_specs = [
            (0, 36, 'DEL'),     # x=4..40
            (40, 44, 'SPC'),    # x=44..88
            (84, 40, 'DONE'),   # x=88..124
        ]

        for i, (x_off, width, label) in enumerate(action_specs):
            x = _GRID_X + x_off
            is_sel = (self._row == _ACTION_ROW and self._col == i)

            if is_sel:
                canvas.rect(x - 1, action_y - 1, x + width - 2, action_y + _CELL_H - 2,
                            fill='bg_selected')

            colour = 'highlight' if is_sel else 'info'
            # Centre the label roughly
            tx = x + (width - len(label) * 5) // 2
            canvas.text(tx, action_y, label, colour=colour, font='tiny')

        return action_y + _CELL_H

    def render_input_line(self, canvas: Canvas, y: int, label: str = "PW:"):
        """Draw the current text input with cursor."""
        canvas.text(2, y, label, colour='text_dim', font='small')
        # Show text with blinking cursor placeholder
        display = self.text[-16:] + "_"
        canvas.text(22, y, display, colour='text', font='small')
