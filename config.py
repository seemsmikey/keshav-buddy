"""Central configuration for the Keshav Mahavidyalaya RAG helpdesk chatbot."""

import os
import socket
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
KB_DIR = BASE_DIR / "knowledge_base"
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
INDEX_FILE = DATA_DIR / "vector_index.npz"

# Web server binding. 0.0.0.0 exposes the app to the LAN so phones, tablets and
# other computers on the same network can reach it. Override with env vars if needed.
HOST = os.getenv("HELPDESK_HOST", "0.0.0.0")
PORT = int(os.getenv("HELPDESK_PORT", "5000"))

OLLAMA_HOST = "http://localhost:11434"
CHAT_MODEL = "qwen2.5:3b"
EMBED_MODEL = "nomic-embed-text"

CHUNK_SIZE = 700
CHUNK_OVERLAP = 120
TOP_K = 4
MIN_SCORE = 0.25

REQUEST_TIMEOUT = 180

COLLEGE_NAME = "Keshav Mahavidyalaya (University of Delhi)"

SYSTEM_PROMPT = f"""You are "Keshav Buddy", the friendly virtual helpdesk assistant for \
{COLLEGE_NAME}, located in Pitampura, Delhi.

Your job is to help students, parents and applicants with questions about admissions, courses,
fees, placements, facilities, scholarships, contact details and campus life.

Rules you must follow:
1. Answer ONLY using the information in the "Context" section provided below.
2. If the context does not contain the answer, politely say you do not have that information and
   direct the user to the college office at 011-27018805 or admissions@keshav.du.ac.in, or the
   website https://keshav.du.ac.in.
3. Never invent facts, fees, dates, cut-offs or names.
4. Be concise, warm and clear. Use short paragraphs or bullet points when helpful.
5. If fees or dates are mentioned, remind the user to confirm the latest figures on the official
   college website.
"""

SUGGESTED_QUESTIONS = [
    "What courses does Keshav Mahavidyalaya offer?",
    "How do I get admission through CUET and DU CSAS?",
    "What is the fee for B.Com (Hons.)?",
    "What is the fee for B.Sc. (Hons.) Computer Science?",
    "Does the college provide hostel facilities?",
    "What are the placement opportunities?",
    "How can I contact Keshav Mahavidyalaya?",
    "Are there scholarships available for students?",
    "Does the college offer French or German language courses?",
    "Where is the college located and how do I reach it?",
]


def local_ipv4_addresses() -> list[str]:
    """Return LAN IPv4 addresses this machine can be reached on (excludes loopback)."""
    ips: set[str] = set()

    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass

    # The UDP-connect trick asks the OS which interface would reach the internet.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))
            ips.add(probe.getsockname()[0])
    except OSError:
        pass

    return sorted(ip for ip in ips if not ip.startswith("127."))
