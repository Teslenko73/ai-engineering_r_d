import json
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from pipeline.result_writer import build_record, result_path, save_record


class BatchRunner:
    """Przepuszcza listę dokumentów przez ekstraktor i zapisuje wyniki (jeden JSON na dokument)
    oraz `_run_meta.json` z opisem przebiegu."""

    def __init__(self, extractor, out_dir: Path, meta_base: dict, skip_existing: bool = False):
        self.extractor = extractor
        self.out_dir = Path(out_dir)
        self.meta_base = meta_base  # model, wersja promptu, próbkowanie... (zapisywane przy każdym wyniku)
        self.skip_existing = skip_existing

    def run(self, files: list[Path]) -> dict:
        counts = Counter()
        started = datetime.now()
        t0 = time.perf_counter()
        interrupted = False
        total = len(files)

        try:
            for i, file_path in enumerate(files, start=1):
                prefix = f"[{i}/{total}]"

                if self.skip_existing and result_path(self.out_dir, file_path).exists():
                    print(f"{prefix} ⏭️  {file_path.name} (wynik już istnieje)")
                    counts["skipped"] += 1
                    continue

                print(f"{prefix} 🚀 {file_path.name}", flush=True)
                result = self.extractor.extract_from_file(file_path)
                meta = {**self.meta_base, "timestamp": datetime.now().isoformat(timespec="seconds")}
                record = build_record(file_path, result, meta)
                save_record(record, self.out_dir, file_path)

                counts[result.status] += 1
                cost = f", ${result.cost:.5f}" if result.cost else ""
                icon = "✅" if result.status == "ok" else "❌"
                print(f"           {icon} {result.status} (próby: {result.attempts}, {result.latency_s or 0:.1f}s{cost})")
                if result.status == "failed":
                    print(f"           powód: {(result.error or '')[:200]}")
        except KeyboardInterrupt:
            interrupted = True
            print("\n⛔ Przerwano. Zapisuję to, co jest gotowe (--skip-existing pozwoli wznowić).")
            raise
        finally:
            summary = {
                "ok": counts["ok"], "failed": counts["failed"], "skipped": counts["skipped"],
                "n_files_requested": total, "interrupted": interrupted,
                "wall_time_s": round(time.perf_counter() - t0, 1),
            }
            self._write_run_meta(summary, started)
        return summary

    def _write_run_meta(self, summary: dict, started: datetime) -> None:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        meta = {
            **self.meta_base,
            **summary,
            "started_at": started.isoformat(timespec="seconds"),
            "finished_at": datetime.now().isoformat(timespec="seconds"),
        }
        with open(self.out_dir / "_run_meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2, default=str)

    @staticmethod
    def print_summary(summary: dict) -> None:
        print(f"\nGotowe: poprawne {summary['ok']}, failed {summary['failed']}, pominięte {summary['skipped']} "
              f"(czas: {summary['wall_time_s']} s)")
