from __future__ import annotations

import queue
import threading
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from tkinter import font as tkfont

from src.graph import run_graph
from src.llm.base import BaseLLM
from src.llm.service import create_llm
from src.nodes.output_writer import refresh_json_report, refresh_run_log
from src.nodes.report_qa import answer_report_question
from src.state import AgentState


DEFAULT_COMPETITOR = "Gusto"
DEFAULT_OUTPUT_DIR = "outputs"


@dataclass(frozen=True)
class MarkdownDisplayLine:
    text: str
    tag: str


def markdown_display_lines(markdown: str) -> list[MarkdownDisplayLine]:
    lines: list[MarkdownDisplayLine] = []
    for raw_line in markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        stripped = raw_line.strip()
        if not stripped:
            lines.append(MarkdownDisplayLine("", "body"))
        elif stripped.startswith("# "):
            lines.append(MarkdownDisplayLine(stripped.removeprefix("# ").strip(), "h1"))
        elif stripped.startswith("## "):
            lines.append(MarkdownDisplayLine(stripped.removeprefix("## ").strip(), "h2"))
        elif stripped.startswith("### "):
            lines.append(MarkdownDisplayLine(stripped.removeprefix("### ").strip(), "h3"))
        elif stripped.startswith("#### "):
            lines.append(MarkdownDisplayLine(stripped.removeprefix("#### ").strip(), "h4"))
        elif stripped.startswith("- "):
            lines.append(MarkdownDisplayLine(stripped, "bullet"))
        elif stripped.lower() == "sources" or stripped.lower().endswith(" sources"):
            lines.append(MarkdownDisplayLine(stripped, "sources_heading"))
        elif stripped.startswith("[") and "]" in stripped[:6]:
            lines.append(MarkdownDisplayLine(stripped, "source"))
        else:
            lines.append(MarkdownDisplayLine(raw_line.rstrip(), "body"))
    return lines


def format_state_summary(state: AgentState) -> str:
    lines: list[str] = []
    if state.competitor:
        lines.extend(
            [
                "Competitor",
                "----------",
                f"Name: {state.competitor.name}",
                f"Domain: {state.competitor.domain or 'unknown'}",
                f"Confidence: {state.competitor.confidence}",
                "",
            ]
        )

    if state.final_markdown_path or state.final_json_path or state.final_log_path:
        lines.extend(
            [
                "Generated Files",
                "---------------",
                f"Markdown: {state.final_markdown_path or ''}",
                f"JSON: {state.final_json_path or ''}",
                f"Log: {state.final_log_path or ''}",
                "",
            ]
        )

    if state.source_inventory:
        lines.extend(
            [
                "Source Inventory",
                "----------------",
                f"Total sources: {state.source_inventory.total_sources}",
                f"Official sources: {state.source_inventory.official_source_count}",
                f"Third-party sources: {state.source_inventory.third_party_source_count}",
                "",
                "Sources by category:",
            ]
        )
        for category, count in state.source_inventory.category_counts.items():
            lines.append(f"- {category}: {count}")
        lines.append("")

    if state.coverage_summary:
        lines.extend(["Coverage", "--------"])
        for summary in state.coverage_summary.categories:
            lines.append(
                f"- {summary.category}: {summary.status} "
                f"({summary.source_count} sources, {summary.official_count} official, "
                f"{summary.third_party_count} third-party). {summary.notes}"
            )
        lines.append("")

    if state.eval_summary:
        lines.extend(
            [
                "Eval Summary",
                "------------",
                f"Overall quality score: {state.eval_summary.overall_quality_score}",
                f"Claim grounding score: {state.eval_summary.claim_grounding_score}",
                f"Third-party caveat score: {state.eval_summary.third_party_caveat_score}",
                f"Weak sections: {', '.join(state.eval_summary.weak_sections) or 'none'}",
                "",
            ]
        )

    if state.tool_call_logs:
        lines.extend(["Tool Calls", "----------"])
        for log in state.tool_call_logs:
            status = f"{log.sources_returned} sources" if log.success else f"failed: {log.error}"
            lines.append(f"- {log.category} / {log.tool_name}: {status}")
        lines.append("")

    if state.llm_call_logs:
        lines.extend(["LLM Calls", "---------"])
        for log in state.llm_call_logs:
            status = "ok" if log.success else f"failed: {log.error}"
            lines.append(f"- {log.stage} using {log.model}: {status}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def read_report_markdown(state: AgentState) -> str:
    if not state.final_markdown_path:
        return ""
    path = Path(state.final_markdown_path)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


class CompetitiveIntelGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Competitive Intel Agent")
        self.root.geometry("1200x820")
        self.state: AgentState | None = None
        self.llm: BaseLLM | None = None
        self.worker_queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.is_running = False
        self.is_answering = False

        self.competitor_var = tk.StringVar(value=DEFAULT_COMPETITOR)
        self.output_dir_var = tk.StringVar(value=DEFAULT_OUTPUT_DIR)
        self.llm_mode_var = tk.StringVar(value="Auto")
        self.status_var = tk.StringVar(value="Ready")

        self._configure_styles()
        self._build_layout()
        self.root.after(100, self._poll_worker_queue)

    def _configure_styles(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background="#f6f7f9")
        style.configure("TLabel", background="#f6f7f9", foreground="#1d2733")
        style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"))
        style.configure("Muted.TLabel", foreground="#5d6978")
        style.configure("TButton", padding=(10, 6))
        style.configure("Accent.TButton", padding=(12, 7))

    def _build_layout(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)

        top = ttk.Frame(self.root, padding=(16, 14, 16, 8))
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="Competitive Intel Agent", style="Header.TLabel").grid(
            row=0, column=0, columnspan=6, sticky="w"
        )
        ttk.Label(top, text="Target company").grid(row=1, column=0, sticky="w", pady=(12, 0))
        competitor_entry = ttk.Entry(top, textvariable=self.competitor_var)
        competitor_entry.grid(row=1, column=1, sticky="ew", padx=(8, 14), pady=(12, 0))
        competitor_entry.bind("<Return>", lambda _event: self._start_run())

        ttk.Label(top, text="LLM mode").grid(row=1, column=2, sticky="w", pady=(12, 0))
        mode = ttk.Combobox(
            top,
            textvariable=self.llm_mode_var,
            values=["Auto", "Use LLM", "No LLM"],
            width=10,
            state="readonly",
        )
        mode.grid(row=1, column=3, sticky="w", padx=(8, 14), pady=(12, 0))

        self.run_button = ttk.Button(top, text="Run Report", style="Accent.TButton", command=self._start_run)
        self.run_button.grid(row=1, column=4, sticky="e", pady=(12, 0))

        ttk.Label(top, text="Output folder").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(top, textvariable=self.output_dir_var).grid(row=2, column=1, sticky="ew", padx=(8, 14), pady=(8, 0))
        ttk.Button(top, text="Browse", command=self._choose_output_dir).grid(row=2, column=2, sticky="w", pady=(8, 0))
        self.open_markdown_button = ttk.Button(top, text="Open Markdown", command=self._open_markdown, state="disabled")
        self.open_markdown_button.grid(row=2, column=3, sticky="w", padx=(8, 14), pady=(8, 0))
        self.open_folder_button = ttk.Button(top, text="Open Folder", command=self._open_output_folder, state="disabled")
        self.open_folder_button.grid(row=2, column=4, sticky="w", pady=(8, 0))

        status_row = ttk.Frame(self.root, padding=(16, 0, 16, 8))
        status_row.grid(row=1, column=0, sticky="new")
        status_row.columnconfigure(0, weight=1)
        ttk.Label(status_row, textvariable=self.status_var, style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        self.progress = ttk.Progressbar(status_row, mode="indeterminate")
        self.progress.grid(row=0, column=1, sticky="ew", padx=(12, 0))

        main = ttk.Frame(self.root, padding=(16, 28, 16, 16))
        main.grid(row=2, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(0, weight=1)

        self.notebook = ttk.Notebook(main)
        self.notebook.grid(row=0, column=0, sticky="nsew")

        self.report_text = self._text_tab("Report")
        self.qa_text = self._text_tab("Q&A")
        self.details_text = self._text_tab("Run Details")
        self.logs_text = self._text_tab("Pipeline Logs")
        self._configure_report_tags()

        qa_frame = ttk.Frame(main, padding=(0, 10, 0, 0))
        qa_frame.grid(row=1, column=0, sticky="ew")
        qa_frame.columnconfigure(0, weight=1)
        self.question_var = tk.StringVar()
        self.question_entry = ttk.Entry(qa_frame, textvariable=self.question_var, state="disabled")
        self.question_entry.grid(row=0, column=0, sticky="ew")
        self.question_entry.bind("<Return>", lambda _event: self._ask_question())
        self.ask_button = ttk.Button(qa_frame, text="Ask About Report", command=self._ask_question, state="disabled")
        self.ask_button.grid(row=0, column=1, sticky="e", padx=(8, 0))

        self._set_text(
            self.report_text,
            "Enter a target company and run a report. The generated brief will appear here.",
        )

    def _text_tab(self, title: str) -> scrolledtext.ScrolledText:
        frame = ttk.Frame(self.notebook, padding=8)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        text = scrolledtext.ScrolledText(frame, wrap="word", padx=18, pady=16, borderwidth=0)
        text.grid(row=0, column=0, sticky="nsew")
        text.configure(state="disabled", font=("Segoe UI", 10), background="#ffffff", foreground="#1c2530")
        self.notebook.add(frame, text=title)
        return text

    def _configure_report_tags(self) -> None:
        base = tkfont.nametofont("TkDefaultFont")
        h1 = base.copy()
        h1.configure(size=18, weight="bold")
        h2 = base.copy()
        h2.configure(size=14, weight="bold")
        h3 = base.copy()
        h3.configure(size=12, weight="bold")
        h4 = base.copy()
        h4.configure(size=10, weight="bold")
        mono = tkfont.nametofont("TkFixedFont")

        for text in [self.report_text, self.qa_text, self.details_text, self.logs_text]:
            text.tag_configure("h1", font=h1, spacing1=10, spacing3=8, foreground="#111827")
            text.tag_configure("h2", font=h2, spacing1=12, spacing3=6, foreground="#1f3a5f")
            text.tag_configure("h3", font=h3, spacing1=10, spacing3=4, foreground="#22415f")
            text.tag_configure("h4", font=h4, spacing1=8, spacing3=3, foreground="#2d4055")
            text.tag_configure("body", spacing3=4)
            text.tag_configure("bullet", lmargin1=24, lmargin2=42, spacing3=4)
            text.tag_configure("source", font=mono, foreground="#2c5d86", lmargin1=24, lmargin2=42, spacing3=3)
            text.tag_configure("sources_heading", font=h4, spacing1=8, spacing3=4)
            text.tag_configure("question", font=h4, foreground="#143d66", spacing1=8, spacing3=3)
            text.tag_configure("answer", spacing3=5)
            text.tag_configure("error", foreground="#9f1239")

    def _choose_output_dir(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.output_dir_var.get() or ".")
        if selected:
            self.output_dir_var.set(selected)

    def _start_run(self) -> None:
        if self.is_running:
            return
        competitor = self.competitor_var.get().strip()
        if not competitor:
            messagebox.showerror("Missing target company", "Enter a target company or domain.")
            return

        self.is_running = True
        self.state = None
        self.llm = None
        self._set_controls_running(True)
        self.status_var.set(f"Running report for {competitor}...")
        self.progress.start(12)
        self._set_text(self.report_text, "Running report. This can take a few minutes when live tools are enabled.")
        self._set_text(self.details_text, "")
        self._set_text(self.logs_text, "")
        self._set_text(self.qa_text, "Report Q&A will be available after a report is generated with an LLM.")

        use_llm = self._selected_llm_mode()
        output_dir = self.output_dir_var.get().strip() or DEFAULT_OUTPUT_DIR
        thread = threading.Thread(
            target=self._run_report_worker,
            args=(competitor, output_dir, use_llm),
            daemon=True,
        )
        thread.start()

    def _run_report_worker(self, competitor: str, output_dir: str, use_llm: bool | None) -> None:
        try:
            llm = create_llm(use_llm)
            state = run_graph(competitor, output_dir=output_dir, use_llm=use_llm, llm=llm)
            self.worker_queue.put(("run_done", (state, llm)))
        except Exception as exc:
            self.worker_queue.put(("run_error", str(exc)))

    def _selected_llm_mode(self) -> bool | None:
        mode = self.llm_mode_var.get()
        if mode == "Use LLM":
            return True
        if mode == "No LLM":
            return False
        return None

    def _poll_worker_queue(self) -> None:
        try:
            while True:
                kind, payload = self.worker_queue.get_nowait()
                if kind == "run_done":
                    state, llm = payload
                    self._finish_run(state, llm)
                elif kind == "run_error":
                    self._finish_run_error(str(payload))
                elif kind == "qa_done":
                    self._finish_qa(payload)
                elif kind == "qa_error":
                    self._finish_qa_error(str(payload))
        except queue.Empty:
            pass
        self.root.after(100, self._poll_worker_queue)

    def _finish_run(self, state: AgentState, llm: BaseLLM | None) -> None:
        self.is_running = False
        self.state = state
        self.llm = llm if state.real_sources_only else None
        self.progress.stop()
        competitor = state.competitor.name if state.competitor else self.competitor_var.get().strip()
        source_count = state.source_inventory.total_sources if state.source_inventory else len(state.discovered_sources)
        self.status_var.set(f"Generated report for {competitor}. Sources: {source_count}.")
        self._set_controls_running(False)
        self.open_markdown_button.configure(state="normal" if state.final_markdown_path else "disabled")
        self.open_folder_button.configure(state="normal" if state.final_markdown_path else "disabled")
        self._render_report(read_report_markdown(state))
        self._set_text(self.details_text, format_state_summary(state))
        self._set_text(self.logs_text, "\n".join(state.logs) or "No pipeline logs.")
        self._set_text(self.qa_text, "Ask a follow-up question about this report." if self.llm else "Report Q&A requires an LLM-backed run.")
        self._set_qa_enabled(bool(self.llm))

    def _finish_run_error(self, error: str) -> None:
        self.is_running = False
        self.progress.stop()
        self.status_var.set("Report failed.")
        self._set_controls_running(False)
        self._set_qa_enabled(False)
        self._set_text(self.report_text, f"Report failed:\n\n{error}", tag="error")

    def _ask_question(self) -> None:
        if self.is_answering or not self.state or not self.llm:
            return
        question = self.question_var.get().strip()
        if not question:
            return
        self.question_var.set("")
        self.is_answering = True
        self._set_qa_enabled(False)
        self.status_var.set("Answering follow-up question...")
        self._append_qa_question(question)
        thread = threading.Thread(target=self._qa_worker, args=(question,), daemon=True)
        thread.start()

    def _qa_worker(self, question: str) -> None:
        try:
            assert self.state is not None
            assert self.llm is not None
            qa_log = answer_report_question(self.state, question, self.llm)
            refresh_json_report(self.state)
            refresh_run_log(self.state)
            self.worker_queue.put(("qa_done", qa_log.answer))
        except Exception as exc:
            self.worker_queue.put(("qa_error", str(exc)))

    def _finish_qa(self, answer: str) -> None:
        self.is_answering = False
        self.status_var.set("Ready")
        self._append_qa_answer(answer)
        self._set_qa_enabled(bool(self.llm))
        if self.state:
            self._set_text(self.details_text, format_state_summary(self.state))
            self._set_text(self.logs_text, "\n".join(self.state.logs) or "No pipeline logs.")

    def _finish_qa_error(self, error: str) -> None:
        self.is_answering = False
        self.status_var.set("Q&A failed.")
        self._append_qa_answer(f"Q&A failed: {error}", tag="error")
        self._set_qa_enabled(bool(self.llm))

    def _render_report(self, markdown: str) -> None:
        self.report_text.configure(state="normal")
        self.report_text.delete("1.0", "end")
        if not markdown.strip():
            self.report_text.insert("end", "No markdown report was generated.", "body")
        else:
            for line in markdown_display_lines(markdown):
                self.report_text.insert("end", line.text + "\n", line.tag)
        self.report_text.configure(state="disabled")
        self.report_text.see("1.0")

    def _set_text(self, text_widget: scrolledtext.ScrolledText, content: str, tag: str = "body") -> None:
        text_widget.configure(state="normal")
        text_widget.delete("1.0", "end")
        text_widget.insert("end", content, tag)
        text_widget.configure(state="disabled")
        text_widget.see("1.0")

    def _append_qa_question(self, question: str) -> None:
        self.qa_text.configure(state="normal")
        if self.qa_text.get("1.0", "end").strip() in {
            "Ask a follow-up question about this report.",
            "Report Q&A will be available after a report is generated with an LLM.",
        }:
            self.qa_text.delete("1.0", "end")
        self.qa_text.insert("end", f"Question: {question}\n", "question")
        self.qa_text.configure(state="disabled")
        self.qa_text.see("end")

    def _append_qa_answer(self, answer: str, tag: str = "answer") -> None:
        self.qa_text.configure(state="normal")
        self.qa_text.insert("end", "\n", "body")
        for line in markdown_display_lines(answer):
            self.qa_text.insert("end", line.text + "\n", tag if tag == "error" else line.tag)
        self.qa_text.insert("end", "\n", "body")
        self.qa_text.configure(state="disabled")
        self.qa_text.see("end")

    def _set_controls_running(self, running: bool) -> None:
        state = "disabled" if running else "normal"
        self.run_button.configure(state=state)
        if running:
            self.open_markdown_button.configure(state="disabled")
            self.open_folder_button.configure(state="disabled")

    def _set_qa_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled and not self.is_answering else "disabled"
        self.question_entry.configure(state=state)
        self.ask_button.configure(state=state)

    def _open_markdown(self) -> None:
        if not self.state or not self.state.final_markdown_path:
            return
        path = Path(self.state.final_markdown_path)
        if path.exists():
            webbrowser.open(path.resolve().as_uri())

    def _open_output_folder(self) -> None:
        if self.state and self.state.final_markdown_path:
            folder = Path(self.state.final_markdown_path).parent
        else:
            folder = Path(self.output_dir_var.get() or DEFAULT_OUTPUT_DIR)
        if folder.exists():
            webbrowser.open(folder.resolve().as_uri())


def main() -> None:
    root = tk.Tk()
    CompetitiveIntelGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
