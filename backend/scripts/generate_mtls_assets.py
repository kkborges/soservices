from pathlib import Path

from app.services.mtls_service import issue_api_server_certificate


def main() -> int:
    ca_path, cert_path, key_path = issue_api_server_certificate()
    print(f"CA={ca_path}")
    print(f"CERT={cert_path}")
    print(f"KEY={key_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
