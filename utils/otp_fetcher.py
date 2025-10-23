import os
import re
import sqlite3
from typing import Optional, Tuple

def get_latest_otp_from_hdfcbnk(db_path: Optional[str] = None, max_rows: int = 20) -> Optional[Tuple[str, str]]:
    """
    Looks in the Messages DB for messages from a handle whose id contains 'hdfcbnk'.
    Checks up to `max_rows` recent messages from that sender (by date descending),
    and returns the first one that contains a 6‐digit number (OTP).
    Returns (sender_handle, otp) or None if not found in the first `max_rows`.
    """
    if db_path is None:
        db_path = os.path.expanduser('~/Library/Messages/chat.db')
    if not os.path.isfile(db_path):
        raise FileNotFoundError(f"Database not found at {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    sql = """
    SELECT
      h.id AS sender,
      m.text AS message_text,
      m.date AS msg_date
    FROM
      message m
      JOIN handle h ON m.handle_id = h.ROWID
    WHERE
      lower(h.id) LIKE ?
      AND m.text IS NOT NULL
    ORDER BY
      m.date DESC
    LIMIT ?
    """
    cur.execute(sql, ('%hdfcbk%', max_rows))
    rows = cur.fetchall()
    conn.close()

    for row in rows:
        sender = row['sender']
        text = row['message_text'] or ""        
        # Try to extract any 6-digit number
        m = re.search(r"\b(\d{6})\b", text)
        if m:
            otp = m.group(1)
            return (sender, otp)

    # If we get here no message in the first max_rows had a matching OTP
    return None

if __name__ == "__main__":
    result = get_latest_otp_from_hdfcbnk(max_rows=20)
    if result:
        sender, otp = result
        print(f"Sender: {sender!r}")
        print(f"Extracted OTP: {otp}")
    else:
        print("No OTP found in the latest up to 20 messages from sender containing 'HDFCBN'.")
