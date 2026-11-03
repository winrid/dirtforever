"""Exercise the Advanced tab scroll helper from dirtforever.py in a fresh
process. Run by tests/test_gui_scroll.py; prints one JSON object.

Tk is kept out of the pytest process on purpose: tearing a Tk interpreter
down inside a long test run has crashed the interpreter during a later
garbage collection.

Exit codes: 0 ran, 3 no display or no tkinter available.
"""
import ast
import json
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI_SOURCE = (ROOT / "dirtforever.py").read_text(encoding="utf-8")


def nested_function_source(module_src: str, outer: str, inner: str) -> str:
    tree = ast.parse(module_src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == outer:
            for child in ast.walk(node):
                if isinstance(child, ast.FunctionDef) and child.name == inner:
                    return textwrap.dedent(ast.get_source_segment(module_src, child))
    raise LookupError(f"{outer}.{inner} not found in dirtforever.py")


def main() -> int:
    try:
        import tkinter as tk
        from tkinter import ttk
    except ImportError as exc:
        print(json.dumps({"skip": f"no tkinter: {exc}"}))
        return 3

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(json.dumps({"skip": str(exc)}))
        return 3
    root.withdraw()

    src = nested_function_source(GUI_SOURCE, "run_gui", "_scrollable_body")
    namespace = {"tk": tk, "ttk": ttk, "BG": "#101010"}
    exec(compile(src, "dirtforever.py::_scrollable_body", "exec"), namespace)
    scrollable_body = namespace["_scrollable_body"]

    result = {}

    # 1. Content taller than the window is reachable by scrolling.
    outer = tk.Frame(root, width=440, height=560)
    outer.pack_propagate(False)
    outer.pack()
    body = scrollable_body(outer)
    for i in range(12):
        tk.Label(body, text=f"card {i}", height=4).pack(fill="x", padx=20, pady=5)
    root.update_idletasks()
    canvas = next(w for w in outer.winfo_children() if isinstance(w, tk.Canvas))
    bar = next(w for w in outer.winfo_children() if isinstance(w, ttk.Scrollbar))
    region = [int(float(v)) for v in str(canvas.cget("scrollregion")).split()]
    result["bar_manager"] = bar.winfo_manager()
    result["body_reqheight"] = body.winfo_reqheight()
    result["region_height"] = region[3] - region[1] if len(region) == 4 else None
    result["view_top"] = list(canvas.yview())
    canvas.yview_moveto(1.0)
    result["view_bottom"] = list(canvas.yview())
    outer.destroy()

    # 2. Wheel events (Windows delta and X11 buttons) move the view.
    outer = tk.Frame(root, width=440, height=200)
    outer.pack_propagate(False)
    outer.pack()
    body = scrollable_body(outer)
    for i in range(30):
        tk.Label(body, text=f"row {i}").pack(fill="x")
    root.update_idletasks()
    canvas = next(w for w in outer.winfo_children() if isinstance(w, tk.Canvas))
    canvas.event_generate("<Enter>")
    root.update()
    positions = {"start": canvas.yview()[0]}
    for name, event, kwargs in (
        ("delta_down", "<MouseWheel>", {"delta": -120}),
        ("delta_up", "<MouseWheel>", {"delta": 120}),
        ("button5", "<Button-5>", {}),
        ("button4", "<Button-4>", {}),
    ):
        canvas.event_generate(event, **kwargs)
        root.update()
        positions[name] = canvas.yview()[0]
    canvas.event_generate("<Leave>")
    root.update()
    result["wheel_positions"] = positions
    result["tk_version"] = float(tk.TkVersion)

    root.destroy()
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
