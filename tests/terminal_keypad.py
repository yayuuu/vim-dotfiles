"""Keypad navigation reaches a real PTY as navigation, while digits stay digits."""
from pathlib import Path
import shlex
import tempfile

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-terminal-keypad-') as directory:
    root = Path(directory)
    output, ready = root / 'bytes', root / 'ready'
    reader = root / 'reader.py'
    reader.write_text('import os, pathlib, sys, tty\n'
                      'tty.setraw(0)\n'
                      f'pathlib.Path({str(ready)!r}).touch()\n'
                      f'with open({str(output)!r}, "ab", buffering=0) as stream:\n'
                      '    while True:\n'
                      '        stream.write(os.read(0, 1024))\n')
    editor = Editor(root, root / 'state')
    try:
        editor.lua('local t=require("config.terminals");t.show(t.active);'
                   'vim.fn.chansend(t.items[1].job, ...)',
                   '/usr/bin/python3 -B ' + shlex.quote(str(reader)) + '\n')
        editor.wait(ready.exists, 'Raw PTY reader is ready')
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 't', 'Terminal input active')

        def receive(keys, size=1):
            before = output.stat().st_size if output.exists() else 0
            editor.call('nvim_input', keys)
            editor.wait(lambda: output.exists() and output.stat().st_size >= before + size, 'PTY receives ' + keys)
            return output.read_bytes()[before:]

        for key in ('Home', 'End', 'Up', 'Down', 'Left', 'Right', 'PageUp', 'PageDown', 'Del', 'Insert'):
            expected = receive('<' + key + '>')
            actual = receive('<k' + key + '>', len(expected))
            assert actual == expected, (key, actual, expected)
        assert receive('17', 2) == b'17', 'Number row keeps its digits'
        assert receive('<k1><k7>', 2) == b'17', 'Numeric keypad digits keep their digits'
        assert editor.lua('return vim.fn.mode()') == 't'
        print('PASS: keypad Home/End, arrows, PageUp/PageDown, Delete/Insert match ordinary navigation in the child PTY; numeric input is preserved.')
    finally:
        editor.close()
