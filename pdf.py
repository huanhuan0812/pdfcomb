import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
from pathlib import Path

# 尝试导入 tkinterdnd2，若不存在则提示
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False
    TkinterDnD = None
    DND_FILES = None

# 尝试导入 pypdf
try:
    from pypdf import PdfWriter, PdfReader
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False
    PdfWriter = None
    PdfReader = None


class PDFMergerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF 合并工具 (pypdf + 拖拽)")
        self.root.geometry("720x580")
        self.root.minsize(620, 480)

        self.pdf_files = []  # 存储 (显示名, 完整路径)

        self._check_dependencies()
        self._build_ui()

    def _check_dependencies(self):
        """检查 pypdf 与 tkinterdnd2 是否可用"""
        self.pypdf_ok = PYPDF_AVAILABLE
        self.dnd_ok = DND_AVAILABLE

    def _build_ui(self):
        # ===== 顶部：依赖状态 =====
        status_frame = ttk.Frame(self.root, padding=(10, 8))
        status_frame.pack(fill="x")

        # pypdf 状态
        if self.pypdf_ok:
            ttk.Label(
                status_frame,
                text="✔ pypdf 已安装",
                foreground="green",
            ).pack(side="left", padx=(0, 15))
        else:
            ttk.Label(
                status_frame,
                text="✘ 未找到 pypdf，请执行: pip install pypdf",
                foreground="red",
            ).pack(side="left", padx=(0, 15))

        # 拖拽支持状态
        if self.dnd_ok:
            ttk.Label(
                status_frame,
                text="✔ 支持拖拽",
                foreground="green",
            ).pack(side="left")
        else:
            ttk.Label(
                status_frame,
                text="✘ 拖拽不可用（请安装 tkinterdnd2）",
                foreground="orange",
            ).pack(side="left")

        # ===== 中部：文件列表 =====
        list_frame = ttk.LabelFrame(
            self.root,
            text="待合并的 PDF 文件（从上到下依次合并，可拖拽 PDF 或文件夹到此处）",
            padding=8,
        )
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        inner = ttk.Frame(list_frame)
        inner.pack(fill="both", expand=True)

        scrollbar = ttk.Scrollbar(inner, orient="vertical")
        scrollbar.pack(side="right", fill="y")

        self.listbox = tk.Listbox(
            inner,
            selectmode="extended",
            yscrollcommand=scrollbar.set,
            activestyle="dotbox",
        )
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.listbox.yview)

        # 双击从列表移除
        self.listbox.bind("<Double-Button-1>", lambda e: self.remove_selected())

        # ===== 拖拽注册 =====
        if self.dnd_ok:
            try:
                self.listbox.drop_target_register(DND_FILES)
                self.listbox.dnd_bind("<<Drop>>", self._on_drop)
            except Exception:
                pass

        # ===== 按钮行 =====
        btn_frame = ttk.Frame(self.root, padding=(10, 0))
        btn_frame.pack(fill="x", pady=4)

        ttk.Button(btn_frame, text="添加 PDF 文件…", command=self.add_files).pack(side="left", padx=3)
        ttk.Button(btn_frame, text="添加文件夹…", command=self.add_folder).pack(side="left", padx=3)
        ttk.Separator(btn_frame, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Button(btn_frame, text="上移", command=self.move_up).pack(side="left", padx=3)
        ttk.Button(btn_frame, text="下移", command=self.move_down).pack(side="left", padx=3)
        ttk.Button(btn_frame, text="移除选中", command=self.remove_selected).pack(side="left", padx=3)
        ttk.Button(btn_frame, text="清空", command=self.clear_list).pack(side="left", padx=3)

        # ===== 底部：输出设置 =====
        out_frame = ttk.LabelFrame(self.root, text="输出设置", padding=8)
        out_frame.pack(fill="x", padx=10, pady=5)

        row = ttk.Frame(out_frame)
        row.pack(fill="x")
        ttk.Label(row, text="输出文件：").pack(side="left")
        self.out_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.out_var).pack(side="left", fill="x", expand=True, padx=5)
        ttk.Button(row, text="浏览…", command=self.choose_output).pack(side="left")

        row2 = ttk.Frame(out_frame)
        row2.pack(fill="x", pady=(6, 0))
        self.overwrite_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row2, text="如果输出文件已存在则覆盖", variable=self.overwrite_var).pack(side="left")

        # ===== 合并按钮 =====
        action_frame = ttk.Frame(self.root, padding=(10, 6))
        action_frame.pack(fill="x")
        self.merge_btn = ttk.Button(action_frame, text="开始合并", command=self.do_merge)
        self.merge_btn.pack(side="right")

        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(action_frame, textvariable=self.status_var).pack(side="left")

    # ---------- 拖拽处理 ----------
    def _on_drop(self, event):
        """处理拖拽释放的文件/文件夹"""
        if not self.dnd_ok:
            return
        # event.data 可能是由空格分隔的多个路径，也可能带有花括号包裹
        raw = event.data
        # 使用 tkinter 的 splitlist 可以安全解析带空格的路径
        try:
            paths = self.root.tk.splitlist(raw)
        except Exception:
            paths = raw.split()

        pdf_paths = []
        for p in paths:
            p = p.strip()
            if not p:
                continue
            # 去除可能的花括号
            if p.startswith("{") and p.endswith("}"):
                p = p[1:-1]
            if os.path.isdir(p):
                # 如果是文件夹，收集其中的 PDF 文件
                try:
                    for f in sorted(os.listdir(p)):
                        if f.lower().endswith(".pdf"):
                            pdf_paths.append(os.path.join(p, f))
                except Exception:
                    pass
            elif os.path.isfile(p) and p.lower().endswith(".pdf"):
                pdf_paths.append(p)

        if pdf_paths:
            self._add_paths(pdf_paths)
        else:
            self.status_var.set("拖拽的内容中没有找到 PDF 文件")

    # ---------- 列表操作 ----------
    def _refresh_listbox(self):
        self.listbox.delete(0, tk.END)
        for name, _ in self.pdf_files:
            self.listbox.insert(tk.END, name)

    def _add_paths(self, paths):
        added = 0
        for p in paths:
            p = os.path.abspath(p)
            if not p.lower().endswith(".pdf"):
                continue
            if any(os.path.normcase(pp) == os.path.normcase(p) for _, pp in self.pdf_files):
                continue
            self.pdf_files.append((p, p))
            added += 1
        self._refresh_listbox()
        if added:
            self.status_var.set(f"已添加 {added} 个文件，共 {len(self.pdf_files)} 个")

    def add_files(self):
        files = filedialog.askopenfilenames(
            title="选择 PDF 文件",
            filetypes=[("PDF 文件", "*.pdf"), ("所有文件", "*.*")],
        )
        if files:
            self._add_paths(files)

    def add_folder(self):
        folder = filedialog.askdirectory(title="选择包含 PDF 的文件夹")
        if not folder:
            return
        pdfs = sorted(
            [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(".pdf")]
        )
        if not pdfs:
            messagebox.showinfo("提示", "该文件夹中没有 PDF 文件。")
            return
        self._add_paths(pdfs)

    def remove_selected(self):
        sel = list(self.listbox.curselection())
        if not sel:
            return
        for idx in reversed(sel):
            del self.pdf_files[idx]
        self._refresh_listbox()
        self.status_var.set(f"剩余 {len(self.pdf_files)} 个文件")

    def clear_list(self):
        if self.pdf_files and not messagebox.askyesno("确认", "确定清空文件列表？"):
            return
        self.pdf_files.clear()
        self._refresh_listbox()
        self.status_var.set("列表已清空")

    def move_up(self):
        sel = list(self.listbox.curselection())
        if not sel or sel[0] == 0:
            return
        for idx in sel:
            if idx == 0:
                continue
            self.pdf_files[idx], self.pdf_files[idx - 1] = (
                self.pdf_files[idx - 1],
                self.pdf_files[idx],
            )
        self._refresh_listbox()
        new_sel = [i - 1 if i > 0 else i for i in sel]
        for i in new_sel:
            self.listbox.selection_set(i)

    def move_down(self):
        sel = list(self.listbox.curselection())
        if not sel or sel[-1] == len(self.pdf_files) - 1:
            return
        for idx in reversed(sel):
            if idx == len(self.pdf_files) - 1:
                continue
            self.pdf_files[idx], self.pdf_files[idx + 1] = (
                self.pdf_files[idx + 1],
                self.pdf_files[idx],
            )
        self._refresh_listbox()
        new_sel = [i + 1 if i < len(self.pdf_files) - 1 else i for i in sel]
        for i in new_sel:
            self.listbox.selection_set(i)

    # ---------- 输出 ----------
    def choose_output(self):
        path = filedialog.asksaveasfilename(
            title="保存合并后的 PDF",
            defaultextension=".pdf",
            filetypes=[("PDF 文件", "*.pdf")],
        )
        if path:
            self.out_var.set(path)

    # ---------- 合并 ----------
    def do_merge(self):
        if not self.pypdf_ok:
            messagebox.showerror("错误", "未安装 pypdf，请执行: pip install pypdf")
            return
        if len(self.pdf_files) < 2:
            messagebox.showwarning("提示", "请至少添加两个 PDF 文件。")
            return
        out = self.out_var.get().strip()
        if not out:
            messagebox.showwarning("提示", "请指定输出文件路径。")
            return
        out = os.path.abspath(out)
        if not out.lower().endswith(".pdf"):
            out += ".pdf"
        if os.path.exists(out) and not self.overwrite_var.get():
            if not messagebox.askyesno("文件已存在", f"{out}\n已存在，是否覆盖？"):
                return

        self.status_var.set("正在合并…")
        self.merge_btn.config(state="disabled")
        self.root.update_idletasks()

        writer = None
        try:
            writer = PdfWriter()
            total_pages = 0
            for idx, (_, path) in enumerate(self.pdf_files):
                if not os.path.isfile(path):
                    raise FileNotFoundError(f"文件不存在：\n{path}")
                reader = PdfReader(path)
                for page in reader.pages:
                    writer.add_page(page)
                total_pages += len(reader.pages)
                self.status_var.set(
                    f"正在合并 [{idx + 1}/{len(self.pdf_files)}] {os.path.basename(path)} …"
                )
                self.root.update_idletasks()

            with open(out, "wb") as f:
                writer.write(f)

            self.status_var.set("合并完成")
            messagebox.showinfo(
                "成功",
                f"已生成：\n{out}\n\n共 {len(self.pdf_files)} 个文件，{total_pages} 页",
            )
        except Exception as e:
            self.status_var.set("合并失败")
            messagebox.showerror("合并失败", f"发生错误：\n{e}")
        finally:
            if writer is not None:
                try:
                    writer.close()
                except Exception:
                    pass
            self.merge_btn.config(state="normal")


def main():
    # 如果 tkinterdnd2 可用，则使用其提供的 Tk 类；否则回退到普通 Tk
    if DND_AVAILABLE:
        try:
            root = TkinterDnD.Tk()
        except Exception:
            root = tk.Tk()
    else:
        root = tk.Tk()

    try:
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
    except Exception:
        pass

    PDFMergerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
