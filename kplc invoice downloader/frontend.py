import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
from downloader import InvoiceDownloader

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


class InvoiceApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("KPLC Invoice Downloader")
        self.geometry("600x500")
        self.resizable(True, True)

        self.main_frame = ctk.CTkFrame(self, corner_radius=15)
        self.main_frame.pack(pady=40, padx=40, fill="both", expand=True)

        self.title_label = ctk.CTkLabel(
            self.main_frame,
            text="Download KPLC Invoices",
            font=ctk.CTkFont(size=22, weight="bold")
        )
        self.title_label.pack(pady=20)

        self._add_label("Account Numbers (comma-separated only):")
        self.entry_acc = ctk.CTkEntry(
            self.main_frame,
            width=350,
            height=30,
            placeholder_text="Eg: 1234567890,0987654321"
        )
        self.entry_acc.pack()

        self._add_label("Billing Month (yyyymm):")
        self.entry_month = self._add_entry()
        self.entry_month.configure(placeholder_text="e.g. 202407")

        self._add_label("Select Folder:")
        folder_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        folder_frame.pack(pady=(0, 10))

        self.entry_folder = ctk.CTkEntry(folder_frame, width=290, height=30, placeholder_text="Save to folder")
        self.entry_folder.pack(side="left", padx=(40, 10))

        self.button_folder = ctk.CTkButton(folder_frame, text="Browse", width=90, command=self.choose_folder)
        self.button_folder.pack(side="left")

        self.button_download = ctk.CTkButton(self.main_frame, text="⬇️ Download Invoices", command=self.start_download_thread)
        self.button_download.pack(pady=20)

        self.status = ctk.CTkLabel(self.main_frame, text="", text_color="gray", justify="left")
        self.status.pack(pady=(5, 10))

        self.folder_path = ""

    def _add_label(self, text):
        label = ctk.CTkLabel(self.main_frame, text=text, anchor="w")
        label.pack(pady=(10, 2))

    def _add_entry(self):
        entry = ctk.CTkEntry(self.main_frame, width=350, height=30)
        entry.pack()
        return entry

    def choose_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.folder_path = path
            self.entry_folder.delete(0, "end")
            self.entry_folder.insert(0, path)
            self.status.configure(text="📂 Folder selected", text_color="blue")

    def start_download_thread(self):
        threading.Thread(target=self.download_invoices, daemon=True).start()

    def download_invoices(self):
        raw_accounts = self.entry_acc.get().strip()
        acc_numbers = [acc.strip() for acc in raw_accounts.split(",") if acc.strip()]
        month = self.entry_month.get().strip()
        self.folder_path = self.entry_folder.get().strip()

        if not acc_numbers or not month or not self.folder_path:
            self._show_status("❗ Please fill in all fields", "red", error=True)
            return

        if not month.isdigit() or len(month) != 6:
            self._show_status("❌ Invalid month format. Use yyyymm", "red", error=True)
            return

        self._show_status(" Downloading...", "orange")

        def process_accounts():
            all_results = []

            for acc in acc_numbers:
                try:
                    downloader = InvoiceDownloader(account_number=acc, month=month, save_folder=self.folder_path)
                    downloader.fetch_invoice_ids()
                    results = downloader.download_invoices()
                    all_results.extend(results)
                except Exception as e:
                    all_results.append((f"⚠️ {acc}: {e}", "red"))

            if not any("✅" in msg for msg, _ in all_results):
                all_results.append(("❌ No invoices downloaded.", "red"))
            else:
                all_results.append(("✅ Download successful.", "green"))

            self.show_status_sequence(all_results, 0)

        self.after(1000, lambda: threading.Thread(target=process_accounts, daemon=True).start())

    def show_status_sequence(self, status_list, index):
        if index < len(status_list):
            message, color = status_list[index]
            self._show_status(message, color)
            self.after(2000, lambda: self.show_status_sequence(status_list, index + 1))

    def _show_status(self, message, color, error=False):
        self.status.configure(text=message, text_color=color)
        if error:
            messagebox.showerror("Error", message)


if __name__ == "__main__":
    app = InvoiceApp()
    app.mainloop()
