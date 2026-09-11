"""Run as a trusted local operator. Never expose this as a public HTTP endpoint."""

import argparse
import os
import time
import jwt
from pathlib import Path
from dotenv import load_dotenv

parser = argparse.ArgumentParser()
parser.add_argument("subject")
args = parser.parse_args()
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
secret = os.environ.get("AUTH_SECRET", "")
if len(secret) < 32:
    raise SystemExit("Set AUTH_SECRET to the same >=32 character secret as the API")
print(
    jwt.encode(
        {
            "sub": args.subject,
            "iss": os.getenv("AUTH_ISSUER", "autoagent"),
            "aud": os.getenv("AUTH_AUDIENCE", "autoagent-api"),
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        },
        secret,
        algorithm="HS256",
    )
)
