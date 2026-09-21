from .worker import process_one

if __name__ == "__main__":
    ok = process_one()
    print("RINA_WORKER_ONCE", "PROCESSED" if ok else "NO_JOB", flush=True)

