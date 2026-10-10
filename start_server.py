"""Container startup with hosting-provider PORT support."""
import os
import sys
port = int(os.environ.get("PORT", "8501"))
if not 1 <= port <= 65535:
    raise ValueError("PORT must be between 1 and 65535.")
os.execv(sys.executable, [sys.executable, "-m", "streamlit", "run", "app.py",
                        "--server.address", "0.0.0.0", "--server.port", str(port)])
