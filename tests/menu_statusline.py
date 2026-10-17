"""Record every UI frame to catch blank/menu status bars and mode-color flashes."""
from pathlib import Path
import tempfile
import time

from ui import Editor


class RecordedEditor(Editor):
    recording = False

    def snapshot(self):
        return (''.join(self.grid[-1]),
                [self.highlights.get(identifier, {}) for identifier in self.attributes[-1]])

    def notify(self, message):
        if message[0] != 2 or message[1] != 'redraw':
            return super().notify(message)
        for event in message[2]:
            if event[0] == 'grid_resize':
                for grid, width, height in event[1:]:
                    if grid == 1:
                        self.grid = [[' '] * width for _ in range(height)]
                        self.attributes = [[0] * width for _ in range(height)]
            if event[0] == 'grid_clear' and [1] in event[1:]:
                self.grid = [[' '] * len(row) for row in self.grid]
                self.attributes = [[0] * len(row) for row in self.attributes]
            super().notify([2, 'redraw', [event]])
            if self.recording and event[0] == 'flush':
                self.frames.append(self.snapshot())


with tempfile.TemporaryDirectory(prefix='nvim-menu-statusline-') as directory:
    root = Path(directory)
    path = root / 'example.lua'
    content = [f'local value_{index} = {index}' for index in range(80)]
    path.write_text('\n'.join(content) + '\n')
    editor = RecordedEditor(root, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...);'
                   'vim.api.nvim_win_set_cursor(0,{21,7});vim.cmd("startinsert")', str(path))
        document = editor.lua('return vim.api.nvim_get_current_buf()')
        editor.call('nvim_buf_set_lines', document, 30, 31, False, ['local unsaved = true'])

        def pump(duration=.15):
            deadline = time.monotonic() + duration
            while time.monotonic() < deadline:
                editor.lua('return true')
                time.sleep(.01)

        def click(row, column):
            # No forced redraw: inspect the frames a real mouse gesture produces.
            editor.call('nvim_input_mouse', 'left', 'press', '', 0, row, column)
            editor.call('nvim_input_mouse', 'left', 'release', '', 0, row, column)

        def heading(name):
            click(0, ''.join(editor.grid[0]).index(' ' + name + ' ') + 2)

        def stable(action, description, duration=.15, require_frames=True):
            expected = editor.snapshot()
            editor.frames = []
            editor.recording = True
            action()
            pump(duration)
            editor.recording = False
            assert editor.frames or not require_frames, description + ': no frames observed'
            assert editor.snapshot() == expected, description + ': final status bar changed'
            for frame in editor.frames:
                assert frame == expected, (description, expected[0], frame[0],
                                           'colors changed' if frame[1] != expected[1] else '')

        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'i', 'Editor starts in Insert')
        pump(.4)
        assert 'example.lua' in editor.snapshot()[0] and '21:8' in editor.snapshot()[0]
        for width in (160, 100, 240):
            editor.call('nvim_ui_try_resize', width, 48)
            pump(.2)
            for name in ('File', 'Edit', 'Search', 'View', 'Project', 'Git', 'Debug', 'Terminal', 'Help'):
                stable(lambda: heading(name), f'Open/switch {name} at width {width}')
                assert editor.lua('return require("config.ide").menu_name') == name
            # Include a periodic Lualine refresh, not only the first menu frame.
            stable(lambda: editor.lua('require("lualine").refresh({force=true,scope="window"})'),
                   'Refresh while menu has focus', 1.1, require_frames=False)
            stable(lambda: heading('Help'), 'Repeated heading dismisses menu')
            editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'i', 'Dismissal resumes editor input')
            for key in ('<Esc>', 'q'):
                stable(lambda: heading('File'), 'Open before ' + key)
                stable(lambda: editor.call('nvim_input', key), key + ' dismisses menu')
                assert editor.lua('return require("config.ide").menu_name') is None

        # A genuine mode/cursor change must still update the normal status bar.
        editor.call('nvim_input', '<Esc>')
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'n', 'Explicit Normal mode')
        pump(.2)
        assert 'NORMAL' in editor.snapshot()[0]
        stable(lambda: heading('Edit'), 'Opening from Normal preserves its badge')
        editor.call('nvim_input', '<Esc>')
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'i', 'Return to editable document')
        editor.lua('vim.api.nvim_win_set_cursor(0,{35,4})')
        pump(.2)
        assert 'INSERT' in editor.snapshot()[0] and '35:5' in editor.snapshot()[0]
        assert editor.call('nvim_buf_get_lines', document, 30, 31, False) == ['local unsaved = true']
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
        print('PASS: every menu UI frame retains status text, file location and colors through '
              'opening, switching, periodic refresh, resizing, heading/Esc/q dismissal; normal updates and unsaved text survive.')
    finally:
        editor.close()
