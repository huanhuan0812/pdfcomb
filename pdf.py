import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import os
import shutil
from pathlib import Path


class PDFMergerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF 合并工具 (qpdf)")
        self.root.geometry("700x550")
        self.root.minsize(600, 450)

        self.pdf_files = []  # 存储 (显示名, 完整路径)

        self._check_qpdf()
        self._build_ui()

    def _check_qpdf(self):
        """检查系统是否安装了 qpdf"""
        self.qpdf_path = shutil.which("qpdf")
        if not self.qpdf_path:
            # 尝试常见 Windows 安装路径
            possible = [
                r"C:\Program Files\qpdf\bin\qpdf.exe",
                r"C:\Program Files (x86)\qpdf\bin\qpdf.exe",
            ]
            for p in possible:
                if os.path.isfile(p):
                    self.qpdf_path = p
                    break

    def _build_ui(self):
        # ===== 顶部：qpdf 状态 =====
        status_frame = ttk.Frame(self.root, padding=(10, 8))
        status_frame.pack(fill="x")

        if self.qpdf_path:
            ttk.Label(
                status_frame,
                text=f"✔ 已找到 qpdf: {self.qpdf_path}",
                foreground="green",
            ).pack(side="left")
        else:
            ttk.Label(
                status_frame,
                text="✘ 未找到 qpdf，请先安装 qpdf 并加入 PATH",
                foreground="red",
            ).pack(side="left")

        # ===== 中部：文件列表 =====
        list_frame = ttk.LabelFrame(self.root, text="待合并的 PDF 文件（从上到下依次合并）", padding=8)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # 列表框 + 滚动条
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

        # ===== 按钮行（操作列表）=====
        btn_frame = ttk.Frame(self.root, padding=(10, 0))
        btn_frame.pack(fill="x", pady=4)

        ttk.Button(btn_frame, text="添加 PDF 文件…", command=self.add_files).pack(side="left", padx=3)
        ttk.Button(btn_frame, text="添加文件夹…", command=self.add_folder).pack(side="left", padx=3)
        ttk.Separator(btn_frame, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Button(btn_frame, text="上移", command=self.move_up).pack(side="left", padx=3)
        ttk.Button(btn_frame, text="下移", command=self.move_down).pack(side="left", padx=3)
        ttk.Button(btn_frame, text="移除选中", command=self.remove_selected).pack(side="left", padx=3)
        ttk.Button(btn_frame, text="清空", command=self.clear_list).pack(side="left", padx=3)

        # ===== 底部：输出与合并 =====
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

        # 合并按钮
        action_frame = ttk.Frame(self.root, padding=(10, 6))
        action_frame.pack(fill="x")
        self.merge_btn = ttk.Button(action_frame, text="开始合并", command=self.do_merge)
        self.merge_btn.pack(side="right")

        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(action_frame, textvariable=self.status_var).pack(side="left")

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
        if not self.qpdf_path:
            messagebox.showerror("错误", "未找到 qpdf，请安装后重试。")
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

        # 构造 qpdf 命令
        # qpdf --empty --pages file1 file2 ... -- output
        cmd = [self.qpdf_path, "--empty", "--pages"]
        for _, path in self.pdf_files:
            if not os.path.isfile(path):
                messagebox.showerror("错误", f"文件不存在：\n{path}")
                return
            cmd.append(path)
        cmd.append("--")
        cmd.append(out)

        self.status_var.set("正在合并…")
        self.merge_btn.config(state="disabled")
        self.root.update_idletasks()

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode == 0:
                self.status_var.set("合并完成")
                messagebox.showinfo("成功", f"已生成：\n{out}")
            else:
                err = (result.stderr or result.stdout or "").strip()
                self.status_var.set("合并失败")
                messagebox.showerror("qpdf 执行失败", f"返回码：{result.returncode}\n\n{err}")
        except FileNotFoundError:
            messagebox.showerror("错误", "无法执行 qpdf，请确认其路径正确。")
        except Exception as e:
            messagebox.showerror("错误", f"发生异常：\n{e}")
        finally:
            self.merge_btn.config(state="normal")


def main():
    root = tk.Tk()
    try:
        # 让界面跟随系统主题（可选）
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
    except Exception:
        pass
    PDFMergerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()