"""PDF report generator using fpdf2."""

import logging
import os
import platform
import shutil
from datetime import datetime

logger = logging.getLogger(__name__)

# Result integer values (matching TestResult enum ordinals)
_RESULT_MAP = {1: "PASSED", 2: "FAILED", 3: "INTERRUPTED", 0: "PENDING"}


def _find_chinese_font() -> str | None:
    """Search for a usable Chinese TTF font across platforms.

    Returns the path to a .ttf file, or None if not found.
    """
    system = platform.system()
    candidates = []

    if system == "Windows":
        font_dir = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
        candidates = [
            os.path.join(font_dir, "msyh.ttf"),      # YaHei (extracted from .ttc)
            os.path.join(font_dir, "msyhbd.ttf"),     # YaHei Bold
            os.path.join(font_dir, "simhei.ttf"),      # SimHei
            os.path.join(font_dir, "simsun.ttc"),      # SimSun (ttc needs extraction)
        ]
    elif system == "Darwin":
        candidates = [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
        ]
    elif system == "Linux":
        candidates = [
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        ]

    for path in candidates:
        if os.path.isfile(path):
            if path.lower().endswith(".ttf"):
                return path
            if path.lower().endswith(".ttc"):
                extracted = _extract_ttc_to_ttf(path)
                if extracted:
                    return extracted

    return None


def _extract_ttc_to_ttf(ttc_path: str) -> str | None:
    """Extract the first font from a .ttc collection to a temp .ttf file.

    Uses fonttools if available, otherwise copies the file as-is
    (fpdf2 may still be able to use it in some cases).
    """
    try:
        from fontTools.ttLib import TTCollection
    except ImportError:
        logger.debug("fonttools not installed, cannot extract .ttc")
        return None

    try:
        ttc = TTCollection(ttc_path)
        if not ttc.fonts:
            return None
        # Extract the first font and save as .ttf
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".ttf", delete=False)
        tmp.close()
        ttc.fonts[0].save(tmp.name)
        return tmp.name
    except Exception as e:
        logger.debug("Failed to extract .ttc %s: %s", ttc_path, e)
        return None


class PdfReportGenerator:
    """Generate PDF aging test reports for a given test_record_id."""

    def __init__(self):
        self._chinese_font_available = False
        self._font_path: str | None = None

    def _register_font(self, pdf):
        """Try to register a Unicode font for Chinese support.

        Searches common system font paths across Windows/macOS/Linux.
        Falls back to built-in Helvetica if no suitable font is found.
        Returns the font family name to use.
        """
        font_path = _find_chinese_font()
        if font_path and os.path.isfile(font_path):
            try:
                pdf.add_font("chinese", "", font_path, uni=True)
                pdf.add_font("chinese", "B", font_path, uni=True)
                self._chinese_font_available = True
                self._font_path = font_path
                logger.info("Registered Chinese font: %s", font_path)
                return "chinese"
            except Exception as e:
                logger.warning("Failed to register font %s: %s", font_path, e)
        logger.warning("No Chinese font found; PDF will use Helvetica fallback")
        return None

    def _get_db(self):
        from ..storage.database_manager import DatabaseManager
        return DatabaseManager.instance()

    def generate_report(self, test_record_id: int, file_path: str) -> bool:
        """Generate a PDF report for *test_record_id* and save to *file_path*.

        Returns:
            True on success, False on failure.
        """
        from fpdf import FPDF

        try:
            db = self._get_db()
            local = db.local_db

            # --- Load test record ---
            row = local._conn.execute(
                "SELECT record_id, template_id, channel_id, device_sn, device_pn, "
                "start_time, end_time, result, remark FROM test_records WHERE record_id=?",
                (test_record_id,),
            ).fetchone()
            if row is None:
                logger.error("Test record %d not found", test_record_id)
                return False

            record = {
                "record_id": row[0],
                "template_id": row[1],
                "channel_id": row[2],
                "device_sn": row[3],
                "device_pn": row[4],
                "start_time": row[5],
                "end_time": row[6],
                "result": row[7],
                "remark": row[8],
            }

            # Load template name
            template_name = ""
            if record["template_id"] and record["template_id"] > 0:
                tmpl = local.load_template(record["template_id"])
                if tmpl:
                    template_name = tmpl.get("name", "")

            # --- Load alarms for this test period ---
            start_time = record["start_time"]
            end_time = record["end_time"] or datetime.now().isoformat()
            alarms = local._conn.execute(
                "SELECT timestamp, device_name, param_name, current_value, "
                "threshold, is_upper_limit FROM alarms "
                "WHERE timestamp >= ? AND timestamp <= ? ORDER BY timestamp",
                (start_time, end_time),
            ).fetchall()

            # --- Calculate statistics from device data ---
            stats = self._calculate_statistics(local, record, start_time, end_time)

            # --- Build PDF ---
            pdf = FPDF(orientation="P", unit="mm", format="A4")
            pdf.set_auto_page_break(auto=True, margin=20)
            pdf.add_page()

            font_family = self._register_font(pdf)
            title_font = font_family if font_family else "Helvetica"
            body_font = font_family if font_family else "Helvetica"
            title_size = 18 if font_family else 18
            body_size = 11 if font_family else 11

            def use_font(style="", size=body_size):
                if font_family:
                    pdf.set_font(font_family, style, size)
                else:
                    pdf.set_font("Helvetica", style, size)

            # Title
            if self._chinese_font_available:
                use_font("B", title_size)
                pdf.cell(0, 15, "SigenPro \u8001\u5316\u6d4b\u8bd5\u62a5\u544a", ln=True, align="C")
            else:
                use_font("B", title_size)
                pdf.cell(0, 15, "SigenPro Aging Test Report", ln=True, align="C")

            # Date
            use_font("", body_size)
            pdf.cell(0, 8, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ln=True, align="C")
            pdf.ln(5)

            # --- Test info table ---
            use_font("B", 13)
            label = "\u6d4b\u8bd5\u4fe1\u606f" if self._chinese_font_available else "Test Information"
            pdf.cell(0, 10, label, ln=True)

            use_font("", body_size)
            info_data = [
                ("SN", record["device_sn"]),
                ("PN", record["device_pn"]),
                ("Template", template_name),
                ("Start", record["start_time"] or "-"),
                ("End", record["end_time"] or "-"),
                ("Channel", str(record["channel_id"])),
                ("Remark", record["remark"] or "-"),
            ]
            self._draw_table(pdf, info_data, col_widths=[40, 145], header=False, body_font=body_font)
            pdf.ln(5)

            # --- Statistics table ---
            if stats:
                use_font("B", 13)
                label = "\u7edf\u8ba1\u6570\u636e" if self._chinese_font_available else "Statistics"
                pdf.cell(0, 10, label, ln=True)

                use_font("", body_size)
                stat_rows = []
                for param_name, s in stats.items():
                    stat_rows.append((
                        param_name,
                        f"{s['min']:.3f}",
                        f"{s['max']:.3f}",
                        f"{s['avg']:.3f}",
                    ))
                self._draw_table(
                    pdf,
                    stat_rows,
                    col_widths=[50, 45, 45, 45],
                    headers=["Parameter", "Min", "Max", "Avg"]
                        if not self._chinese_font_available
                        else ["\u53c2\u6570", "\u6700\u5c0f", "\u6700\u5927", "\u5e73\u5747"],
                    header=True,
                    body_font=body_font,
                )
                pdf.ln(5)

            # --- Alarm records table ---
            if alarms:
                use_font("B", 13)
                label = "\u62a5\u8b66\u8bb0\u5f55" if self._chinese_font_available else "Alarm Records"
                pdf.cell(0, 10, label, ln=True)

                use_font("", body_size)
                alarm_rows = []
                for a in alarms:
                    direction = ">" if a[5] else "<"
                    alarm_rows.append((
                        a[0],       # timestamp
                        a[1],       # device_name
                        a[2],       # param_name
                        f"{a[3]:.3f}",
                        f"{a[4]:.3f}",
                        direction,
                    ))
                self._draw_table(
                    pdf,
                    alarm_rows,
                    col_widths=[40, 25, 25, 30, 30, 35],
                    headers=["Time", "Device", "Param", "Value", "Threshold", "Dir"]
                        if not self._chinese_font_available
                        else ["\u65f6\u95f4", "\u8bbe\u5907", "\u53c2\u6570", "\u503c", "\u9608\u503c", "\u65b9\u5411"],
                    header=True,
                    body_font=body_font,
                )
                pdf.ln(5)

            # --- Result / Conclusion ---
            result_val = record["result"]
            result_str = _RESULT_MAP.get(result_val, "UNKNOWN")

            if result_val == 1:  # PASSED
                pdf.set_text_color(0, 128, 0)
            elif result_val == 2:  # FAILED
                pdf.set_text_color(200, 0, 0)
            else:
                pdf.set_text_color(128, 128, 128)

            use_font("B", 22)
            result_label = "\u7ed3\u679c" if self._chinese_font_available else "Result"
            pdf.cell(0, 20, f"{result_label}: {result_str}", ln=True, align="C")
            pdf.set_text_color(0, 0, 0)

            # Footer with page number
            pdf.alias_nb_pages()
            pdf.set_y(-15)
            use_font("", 8)
            footer_text = f"Page {pdf.page_no()}/{{nb}}"
            pdf.cell(0, 10, footer_text, align="C")

            # Save
            pdf.output(file_path)
            logger.info("PDF report generated: %s", file_path)
            return True

        except Exception:
            logger.exception("Failed to generate PDF report for record %d", test_record_id)
            return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _calculate_statistics(self, local_db, record: dict,
                              start_time: str, end_time: str) -> dict:
        """Calculate min/max/avg for each parameter from device data.

        Returns dict: param_name -> {"min": float, "max": float, "avg": float}
        """
        device_sn = record.get("device_sn", "")
        if not device_sn:
            return {}

        # Find device_id by looking at the channel
        channel_id = record.get("channel_id", -1)
        if channel_id < 0:
            return {}

        # Query daily tables for device data in the time range
        try:
            start_dt = datetime.fromisoformat(start_time)
        except (ValueError, TypeError):
            start_dt = datetime.now()
        try:
            end_dt = datetime.fromisoformat(end_time) if end_time else datetime.now()
        except (ValueError, TypeError):
            end_dt = datetime.now()

        # We need a device_id; try to find from channels table
        # The actual device_id mapping depends on the test setup.
        # For report purposes, we query all device_data in the time range
        # and aggregate by parameter name.
        data_rows = self._query_all_device_data(local_db, start_dt, end_dt)

        if not data_rows:
            return {}

        # Aggregate per parameter
        param_values: dict[str, list[float]] = {}
        for row in data_rows:
            params = row.get("parameters", {})
            for pname, pval in params.items():
                try:
                    val = float(pval)
                    param_values.setdefault(pname, []).append(val)
                except (ValueError, TypeError):
                    continue

        stats: dict[str, dict] = {}
        for pname, values in param_values.items():
            if values:
                stats[pname] = {
                    "min": min(values),
                    "max": max(values),
                    "avg": sum(values) / len(values),
                }
        return stats

    def _query_all_device_data(self, local_db, start_dt, end_dt) -> list[dict]:
        """Query device data from all relevant daily tables."""
        import json
        from datetime import timedelta

        results = []
        start_iso = start_dt.isoformat()
        end_iso = end_dt.isoformat()
        current = start_dt

        while current <= end_dt:
            date_str = current.strftime("%Y%m%d")
            table_name = f"device_data_{date_str}"

            count = local_db._conn.execute(
                "SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            ).fetchone()[0]

            if count > 0:
                rows = local_db._conn.execute(
                    f"SELECT parameters FROM [{table_name}] "
                    f"WHERE timestamp>=? AND timestamp<=?",
                    (start_iso, end_iso),
                ).fetchall()
                for r in rows:
                    try:
                        params = json.loads(r[0])
                    except (json.JSONDecodeError, TypeError):
                        params = {}
                    results.append({"parameters": params})

            current += timedelta(days=1)

        return results

    def _draw_table(self, pdf, data, col_widths, headers=None,
                    header=False, body_font=11):
        """Draw a simple bordered table.

        Args:
            pdf: FPDF instance.
            data: List of tuples (one per row).
            col_widths: List of column widths in mm.
            headers: Optional list of header strings.
            header: Whether to draw a header row.
            body_font: Font size for body text.
        """
        font_family = pdf.font_family

        if headers and header:
            pdf.set_fill_color(200, 200, 200)
            for i, h in enumerate(headers):
                pdf.cell(col_widths[i], 8, str(h), border=1,
                         fill=True, align="C")
            pdf.ln()

        for row in data:
            for i, cell_val in enumerate(row):
                text = str(cell_val) if cell_val is not None else ""
                # Truncate overly long text
                if len(text) > 40:
                    text = text[:37] + "..."
                pdf.cell(col_widths[i], 7, text, border=1)
            pdf.ln()
