# -*- coding: utf-8 -*-
import queue
import datetime


class UILogHandler:
    def __init__(self, data_text_widget, sys_text_widget):
        self.data_widget = data_text_widget
        self.sys_widget = sys_text_widget
        self.queue = queue.Queue()

    def log_data(self, msg):
        self.queue.put(("data", str(msg)))

    def log_sys(self, msg):
        self.queue.put(("sys", str(msg)))

    def flush_to_widgets(self):
        processed = 0
        while True:
            try:
                typ, msg = self.queue.get_nowait()
            except queue.Empty:
                break
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            if typ == "data":
                try:
                    self.data_widget.configure(state='normal')
                    self.data_widget.insert('end', f"[{ts}] {msg}\n")
                    self.data_widget.see('end')
                    self.data_widget.configure(state='disabled')
                except Exception:
                    pass
            else:
                try:
                    self.sys_widget.configure(state='normal')
                    self.sys_widget.insert('end', f"[{ts}] {msg}\n")
                    self.sys_widget.see('end')
                    self.sys_widget.configure(state='disabled')
                except Exception:
                    pass
            processed += 1
        return processed
