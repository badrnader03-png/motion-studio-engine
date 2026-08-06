import runpod


def handler(job: dict) -> dict:
    """Minimal RunPod Serverless test handler."""
    job_input = job.get("input", {})
    return {
        "ok": True,
        "message": "Motion Studio Engine is running",
        "received": job_input,
    }


runpod.serverless.start({"handler": handler})
