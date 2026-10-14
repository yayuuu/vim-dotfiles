"""Terminal wheel input belongs to the child application or actual scrollback."""
from pathlib import Path
import tempfile

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-terminal-wheel-') as directory:
    root = Path(directory)
    (root / 'reader.py').write_text(
        'import os, pathlib, time, tty\n'
        'tty.setraw(0)\n'
        'def emit(text): os.write(1, text.encode())\n'
        'emit("\\x1b[3J\\x1b[2J\\x1b[HReady")\n'
        'pathlib.Path("ready").touch()\n'
        'with open("input", "ab", buffering=0) as log:\n'
        '    while True:\n'
        '        data = os.read(0, 4096)\n'
        '        if data == b"enable":\n'
        '            emit("\\x1b[")\n'
        '            time.sleep(.04)\n'
        '            emit("?1000;1006h")\n'
        '            pathlib.Path("enabled").touch()\n'
        '        elif data == b"history":\n'
        '            emit("".join("\\r\\nHistory-%d" % i for i in range(120)))\n'
        '            pathlib.Path("history").touch()\n'
        '        elif data == b"disable":\n'
        '            emit("\\x1b[?1000;1006l")\n'
        '            pathlib.Path("disabled").touch()\n'
        '        elif data == b"alternate":\n'
        '            emit("\\x1b[?1049h\\x1b[?1002;1006hAlternate screen")\n'
        '            pathlib.Path("alternate").touch()\n'
        '        elif data == b"restore":\n'
        '            emit("\\x1b[?1002;1006l\\x1b[?1049l")\n'
        '            pathlib.Path("restored").touch()\n'
        '        else:\n'
        '            log.write(data)\n')
    editor = Editor(root, root / 'state')
    try:
        editor.lua('local t=require("config.terminals");t.show(t.active);'
                   'vim.fn.chansend(t.items[1].job,"/usr/bin/python3 -B reader.py\\n")')
        editor.wait((root / 'ready').exists, 'Raw child is ready')
        terminal = editor.lua('return require("config.terminals").win')
        job = editor.lua('return vim.b[require("config.terminals").active].terminal_job_id')
        position = editor.call('nvim_win_get_position', terminal)

        def bar():
            return editor.lua('local s=require("config.vscroll").sources[...];return s and s.bar', terminal)

        def wheel(direction):
            editor.call('nvim_input_mouse', 'wheel', direction, '', 0, position[0] + 2, position[1] + 5)
            editor.lua('vim.cmd("redraw!")')

        def command(text, marker):
            editor.call('nvim_chan_send', job, text)
            editor.wait((root / marker).exists, marker)
            editor.lua('vim.cmd("redraw!")')

        def received(direction):
            output = root / 'input'
            before = output.stat().st_size
            wheel(direction)
            editor.wait(lambda: output.stat().st_size > before, 'Application receives wheel ' + direction)
            data = output.read_bytes()[before:]
            expected = b'\x1b[<64;' if direction == 'up' else b'\x1b[<65;'
            assert data.startswith(expected), data
            assert editor.lua('return vim.fn.mode()') == 't'
            assert editor.lua('return vim.api.nvim_get_current_win()') == terminal

        editor.wait(lambda: not bar(), 'No terminal history scrollbar')
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 't', 'Terminal input')
        wheel('up')
        assert editor.lua('return vim.fn.mode()') == 't', 'No history must not leave terminal input'
        assert (root / 'input').read_bytes() == b'', 'Wheel without mouse reporting sends no shell keys'

        command('enable', 'enabled')
        received('up')
        received('down')
        command('history', 'history')
        editor.wait(bar, 'Terminal history scrollbar appears')
        received('up')
        received('down')
        # Our own scrollbar remains an explicit way to inspect history, even
        # while the application owns body mouse events.
        b = bar()
        bp = editor.call('nvim_win_get_position', b['win'])
        before = (root / 'input').read_bytes()
        editor.click(bp[0], bp[1])
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'n', 'Scrollbar explicitly opens history')
        assert (root / 'input').read_bytes() == before, 'Scrollbar click is not sent to the child'
        editor.click(position[0] + 2, position[1] + 5)
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 't', 'Click resumes application input')
        received('down')

        command('disable', 'disabled')
        wheel('up')
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'n', 'History wheel leaves terminal input')
        editor.wait(lambda: bar()['start'] < bar()['span'], 'History actually scrolls')
        # Use another cell: a rapid repeated body click intentionally selects
        # terminal text, which must retain its native selection mode.
        editor.click(position[0] + 3, position[1] + 6)
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 't', 'Click resumes terminal input')

        command('alternate', 'alternate')
        received('up')
        received('down')
        command('restore', 'restored')
        wheel('up')
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'n', 'Restored history wheel leaves terminal input')
        print('PASS: no-history wheel stays in Terminal; real PTY applications receive wheel bytes with/without history and on alternate screen; disabling mouse restores clamped scrollback.')
    finally:
        editor.close()
