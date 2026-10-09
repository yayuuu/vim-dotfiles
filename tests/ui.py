"""Exercise the installed configuration through Neovim's real UI/RPC API."""
import json
import os
from pathlib import Path
import select
import subprocess
import tempfile
import time
import msgpack

NVIM = '/root/.local/bin/nvim'


class Editor:
    def __init__(self, cwd, state, args=()):
        self.process = subprocess.Popen(
            [NVIM, '--embed', '--headless', *args], cwd=cwd,
            env={**os.environ, 'XDG_STATE_HOME': str(state)},
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.unpacker = msgpack.Unpacker(raw=False)
        self.serial = 0
        self.grid = [[' '] * 160 for _ in range(48)]
        self.call('nvim_ui_attach', 160, 48, {'rgb': True, 'ext_linegrid': True})
        self.wait(lambda: self.lua('return require("config.layout").ready'), 'startup')

    def notify(self, message):
        if message[0] != 2 or message[1] != 'redraw':
            return
        for event in message[2]:
            if event[0] == 'grid_line':
                for grid, row, column, cells, *rest in event[1:]:
                    if grid != 1 or row >= len(self.grid):
                        continue
                    for cell in cells:
                        text, repeat = cell[0], cell[2] if len(cell) > 2 else 1
                        for _ in range(repeat):
                            if column < len(self.grid[row]):
                                self.grid[row][column] = text
                            column += 1

    def call(self, method, *arguments):
        self.serial += 1
        serial = self.serial
        self.process.stdin.write(msgpack.packb([0, serial, method, list(arguments)], use_bin_type=True))
        self.process.stdin.flush()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if not select.select([self.process.stdout], [], [], .1)[0]:
                continue
            data = os.read(self.process.stdout.fileno(), 1048576)
            if not data:
                raise RuntimeError(self.process.stderr.read().decode())
            self.unpacker.feed(data)
            for message in self.unpacker:
                self.notify(message)
                if message[0] == 1 and message[1] == serial:
                    if message[2]:
                        raise AssertionError((method, message[2]))
                    return message[3]
        self.process.kill()
        self.process.wait(timeout=5)
        raise TimeoutError((method, '\n'.join(''.join(line) for line in self.grid), self.process.stderr.read().decode()))

    def lua(self, code, *args):
        return self.call('nvim_exec_lua', code, list(args))

    def wait(self, predicate, description):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(.05)
        raise AssertionError(description)

    def click(self, row, column):
        self.call('nvim_input_mouse', 'left', 'press', '', 0, row, column)
        self.call('nvim_input_mouse', 'left', 'release', '', 0, row, column)
        time.sleep(.1)
        self.lua('vim.cmd("redraw!")')

    def files(self):
        return self.lua('local result={}; for _,b in ipairs(vim.api.nvim_list_bufs()) do '
                        'if vim.bo[b].buflisted and vim.bo[b].buftype=="" and vim.api.nvim_buf_get_name(b)~="" then '
                        'table.insert(result,vim.api.nvim_buf_get_name(b)) end end; return result')

    def close(self):
        try:
            self.call('nvim_command', 'qa!')
        except (RuntimeError, BrokenPipeError):
            pass
        self.process.wait(timeout=5)


