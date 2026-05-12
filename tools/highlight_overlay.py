import json
import sys
import tkinter as tk


def main() -> None:
    boxes = json.loads(sys.argv[1]) if len(sys.argv) > 1 else []
    duration = int(sys.argv[2]) if len(sys.argv) > 2 else 2200
    root = tk.Tk()
    root.attributes("-fullscreen", True)
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.28)
    root.overrideredirect(True)
    root.configure(bg="black")
    canvas = tk.Canvas(root, bg="black", highlightthickness=0)
    canvas.pack(fill="both", expand=True)
    for b in boxes:
        canvas.create_rectangle(b["left"], b["top"], b["right"], b["bottom"], outline="cyan", width=4)
        canvas.create_text(b["left"], max(10, b["top"] - 12), text=b.get("text", ""), fill="white", anchor="w", font=("Segoe UI", 13, "bold"))
    root.after(duration, root.destroy)
    root.mainloop()


if __name__ == "__main__":
    main()
