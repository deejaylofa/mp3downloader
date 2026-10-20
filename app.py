import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import yt_dlp
import zipfile

def search_youtube(query):
    """Searches YouTube and returns a list of (title, url) tuples."""
    ydl_opts = {
        'format': 'bestaudio/best',
        'default_search': 'ytsearch5',  # Fetch top 5 search results
        'quiet': True,
        'extract_flat': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            if 'entries' in info:
                return [(entry.get('title'), f"https://www.youtube.com/watch?v={entry.get('id')}") for entry in info['entries']]
    except Exception as e:
        print(f"Search error: {e}")
    return []

def run_download_queue(queue_items, output_dir, root, update_status, on_complete):
    try:
        update_status("Creating directories...")
        os.makedirs(output_dir, exist_ok=True)
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'writethumbnail': True,
            'postprocessors': [
                {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'},
                {'key': 'EmbedThumbnail'},
                {'key': 'AddMetadata'},
            ],
            'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
            'ignoreerrors': True,
        }

        total = len(queue_items)
        for index, (title, url) in enumerate(queue_items, 1):
            update_status(f"Downloading ({index}/{total}): {title[:30]}...")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

        update_status("Compressing files into ZIP...")
        zip_filename = os.path.join(output_dir, "youtube_downloads.zip")
        
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root_dir, _, files_list in os.walk(output_dir):
                for file in files_list:
                    if file.endswith('.mp3'):
                        file_path = os.path.join(root_dir, file)
                        zipf.write(file_path, arcname=file)
                        
        root.after(0, lambda: on_complete(True, zip_filename))
    except Exception as e:
        root.after(0, lambda: on_complete(False, str(e)))

class MusicApp:
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube Music Queue & Downloader")
        self.root.geometry("600x560")
        self.root.resizable(False, False)

        # Default output directory is the user's Downloads folder
        self.output_dir = os.path.join(os.path.expanduser("~"), "Downloads")

        # --- Top Section: Input / Search ---
        tk.Label(root, text="Search Song or Paste Playlist URL:", font=("Arial", 11, "bold")).pack(anchor="w", padx=15, pady=(10, 0))
        
        input_frame = tk.Frame(root)
        input_frame.pack(fill="x", padx=15, pady=5)

        self.url_entry = tk.Entry(input_frame, width=45, font=("Arial", 11))
        self.url_entry.pack(side="left", padx=(0, 5), expand=True, fill="x")
        self.url_entry.bind("<Return>", lambda event: self.handle_search())

        search_btn = tk.Button(input_frame, text="Search", bg="#007ACC", fg="white", command=self.handle_search)
        search_btn.pack(side="left")

        # --- Search Results Listbox ---
        tk.Label(root, text="Search Results (Double-click to add to queue):", font=("Arial", 10)).pack(anchor="w", padx=15, pady=(5, 0))
        
        self.results_listbox = tk.Listbox(root, height=5, font=("Arial", 10))
        self.results_listbox.pack(fill="x", padx=15, pady=5)
        self.results_listbox.bind("<Double-Button-1>", lambda event: self.add_selected_to_queue())

        self.search_results_cache = []

        # --- Middle Section: Download Queue ---
        tk.Label(root, text="Download Queue:", font=("Arial", 10, "bold")).pack(anchor="w", padx=15, pady=(10, 0))
        
        queue_frame = tk.Frame(root)
        queue_frame.pack(fill="both", expand=True, padx=15, pady=5)

        self.queue_listbox = tk.Listbox(queue_frame, height=5, font=("Arial", 10), bg="#F4F4F4")
        self.queue_listbox.pack(side="left", fill="both", expand=True)

        queue_scroll = tk.Scrollbar(queue_frame, orient="vertical", command=self.queue_listbox.yview)
        queue_scroll.pack(side="right", fill="y")
        self.queue_listbox.config(yscrollcommand=queue_scroll.set)

        self.download_queue = []  # Stores tuples of (title, url)

        # Queue Management Buttons & Status
        q_btn_frame = tk.Frame(root)
        q_btn_frame.pack(fill="x", padx=15, pady=5)

        tk.Button(q_btn_frame, text="Remove Selected", fg="red", command=self.remove_from_queue).pack(side="left")
        
        self.status_label = tk.Label(q_btn_frame, text="Status: Idle", font=("Arial", 9, "italic"))
        self.status_label.pack(side="right")

        # --- Output Directory Selection Section ---
        out_frame = tk.Frame(root, bd=1, relief="solid", padx=5, pady=5)
        out_frame.pack(fill="x", padx=15, pady=(5, 10))

        tk.Label(out_frame, text="Save Destination:", font=("Arial", 9, "bold")).pack(side="left", padx=(0, 5))
        
        self.path_label = tk.Label(out_frame, text=self.output_dir, font=("Arial", 9), fg="#333333", anchor="w")
        self.path_label.pack(side="left", fill="x", expand=True, padx=(0, 5))

        browse_btn = tk.Button(out_frame, text="Browse...", command=self.browse_output_dir)
        browse_btn.pack(side="right")

        # --- Bottom Section: Process Button ---
        self.process_btn = tk.Button(root, text="Download Queue & Create ZIP", font=("Arial", 11, "bold"), bg="#4CAF50", fg="white", command=self.start_process)
        self.process_btn.pack(fill="x", padx=15, pady=(0, 15))

    def handle_search(self):
        query = self.url_entry.get().strip()
        if not query:
            return
        
        # Check if user pasted a direct link / playlist
        if query.startswith("http://") or query.startswith("https://"):
            self.queue_listbox.insert(tk.END, f"[Direct Link]: {query}")
            self.download_queue.append((query, query))
            self.url_entry.delete(0, tk.END)
            return

        self.status_label.config(text="Status: Searching YouTube...")
        self.root.update()

        results = search_youtube(query)
        self.results_listbox.delete(0, tk.END)
        self.search_results_cache = results

        for title, _ in results:
            self.results_listbox.insert(tk.END, title)

        self.status_label.config(text="Status: Select song to queue")

    def add_selected_to_queue(self):
        selected_idx = self.results_listbox.curselection()
        if not selected_idx:
            return
        
        title, url = self.search_results_cache[selected_idx[0]]
        if (title, url) not in self.download_queue:
            self.download_queue.append((title, url))
            self.queue_listbox.insert(tk.END, title)
            self.status_label.config(text=f"Added: {title[:20]}...")

    def remove_from_queue(self):
        selected_idx = self.queue_listbox.curselection()
        if not selected_idx:
            return
        idx = selected_idx[0]
        self.queue_listbox.delete(idx)
        del self.download_queue[idx]

    def browse_output_dir(self):
        dir_selected = filedialog.askdirectory(initialdir=self.output_dir, title="Select Output Folder")
        if dir_selected:
            self.output_dir = dir_selected
            self.path_label.config(text=self.output_dir)

    def start_process(self):
        if not self.download_queue:
            messagebox.showwarning("Queue Empty", "Please add songs or a playlist link to the queue first.")
            return

        self.process_btn.config(state=tk.DISABLED)

        def update_status(text):
            self.root.after(0, lambda: self.status_label.config(text=text))

        def on_complete(success, result):
            self.process_btn.config(state=tk.NORMAL)
            if success:
                self.status_label.config(text="Status: Complete!")
                messagebox.showinfo("Success", f"All files downloaded and zipped!\nSaved to: {result}")
            else:
                self.status_label.config(text="Status: Error occurred")
                messagebox.showerror("Error", result)

        threading.Thread(
            target=run_download_queue,
            args=(self.download_queue, self.output_dir, self.root, update_status, on_complete),
            daemon=True
        ).start()

def main():
    root = tk.Tk()
    app = MusicApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
